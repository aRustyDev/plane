# Recurring Work Items

**Goal:** Let users schedule a work item to be created automatically on a recurrence (daily/weekly/
monthly/cron-like), from a saved definition, so routine tasks regenerate without manual effort.

**Parity target:** Plane Commercial **Business** (Recurring Work Items).

**Background** (greenfield — no model, no scheduler task): There is **no** recurrence model and no
recurring-creation task (`backend-data-model.md §4`). Closest analog: **`DraftIssue`**
(`db/models/draft.py`) — a persisted, not-yet-created issue mirroring most `Issue` fields (incl.
`type`) — but it is a **draft, not a template**, so a shape reference only. The scheduling
machinery already exists: Celery Beat in `celery.py` (`app.conf.beat_schedule`), and
`bgtasks/issue_automation_task.py` (`archive_and_close_old_issues` — a daily `crontab(hour=0,
minute=0)` job iterating projects and mutating issues) is the **direct pattern** to copy. Best
built on **Work Item / Page Templates** (recurrence points at a template payload); until templates
land, snapshot a `DraftIssue`-shaped payload.

**Approach:**
- *Backend model + migration (additive):* `RecurringWorkItem(ProjectBaseModel)` — FK → work-item
  template (or an inline JSON payload of issue fields incl. `type`, assignees, labels), recurrence
  rule (`frequency` enum + interval + optional RRULE string), `next_run_at`, `last_run_at`,
  `is_active`, target project/cycle/module. Soft-delete + `deleted_at` partial-unique (`§5`).
- *Scheduler task:* new `bgtasks/recurring_work_item_task.py` modeled on
  `issue_automation_task.py`; register a Beat entry in `celery.py` (e.g. `crontab(minute="*/15")`)
  that selects due `RecurringWorkItem`s and creates issues. **Creation must go through
  `Issue.save()`** (advisory lock, `sequence_id`, `sort_order`, default state, `completed_at`
  sync) — **never `bulk_create`**, which bypasses all of it (`§ gotcha 1`). After creation, roll
  `next_run_at` forward and set `last_run_at` idempotently (guard against double-fire / missed
  ticks).
- *API:* `RecurringWorkItemViewSet` (project-scoped CRUD, pause/resume, "run now").
- *Frontend:* recurrence config in the work-item create modal / a "Recurring" project settings
  page; store/service; register route.

**Feature flag:** `RECURRING_ITEMS_ENABLED` project/workspace flag (F0.1). Off → the Beat task
skips all rows for that scope.

**Tasks (→ child beads):** (1) `RecurringWorkItem` model + migration; (2) `recurring_work_item_task`
+ Beat schedule entry (idempotent, `Issue.save()`-based creation); (3) `RecurringWorkItemViewSet`
(+ pause/resume/run-now); (4) store/service; (5) recurrence UI + route.

**Acceptance:** *API* — define a daily recurrence, advance the clock / run the task, exactly one
issue is created with the template's fields + a valid `sequence_id`; pausing stops creation; no
duplicate on re-tick. *UI* — recurrence editor persists; created items appear in the target
project.

**Risks / upstream-merge impact:** Idempotency is the main hazard — a crashed/re-run tick must not
double-create (advance `next_run_at` inside the creation transaction); decide catch-up vs skip for
missed ticks. Soft dependency on Templates (payload source) — ship inline-payload first if Templates
slips. New table + one Beat entry + one task module; low upstream drift.
