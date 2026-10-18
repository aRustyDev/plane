# Time Tracking (WakaTime/WakaAPI + Pomodoro)

**Goal:** Give work items first-class worklogs (manual + timer-driven), import coding time
from WakaTime/WakaAPI and attribute it to work items, and ship a Pomodoro timer UI that
persists sessions as worklogs.

**Parity target:** Plane **Pro** "Time Tracking + Worklogs" (advertised at
`apps/web/core/components/workspace/billing/comparison/plans.tsx:183`) + Woven-specific WakaTime pull.

**Background (grounded):** There is **no worklog model** in CE. Worklog exists only as a
frontend type literal — `activity_type: "WORKLOG"` in
`packages/types/src/issues/activity/base.ts:82` — plus an empty-state asset
(`packages/propel/src/empty-state/assets/horizontal-stack/worklog.tsx`). No table, API, or view.
`Issue` is `ProjectBaseModel` (`apps/api/plane/db/models/issue.py`); the activity trail is
`IssueActivity` driven by `bgtasks/issue_activities_task.py`. No WakaTime code anywhere
(confirmed by recon grep). `external_source`/`external_id` idempotency fields exist across models.

**Approach:**
- *Models/migrations (new app `plane/timetracking/`):* `Worklog(ProjectBaseModel)` → `issue` FK,
  `logged_by` FK, `duration` (seconds), `description`, `started_at`, `source`
  (`manual|timer|wakatime`), `external_source`/`external_id`. `PomodoroSession(BaseModel)` →
  user, issue (nullable), `state`, intervals. Additive migration with `deleted_at` +
  partial-unique constraint (per data-model gotcha §5). Register in `db/models/__init__.py`.
- *API:* worklog CRUD on both `/api/` (app, session auth) and `/api/v1/` (PAT, `X-Api-Key`) —
  register in `api/urls/__init__.py` mirroring `intake` pattern. Aggregate endpoint
  (per-issue/per-project/per-user totals).
- *Inbound WakaTime:* Celery task polls WakaAPI (`/users/current/heartbeats`,`/durations`) with
  a per-workspace `WorkspaceIntegration` (provider `wakatime`, token in `config`). Attribute a
  duration to an issue by parsing branch/commit for the work-item identifier
  (`<PROJECT>-<sequence_id>`); write a `Worklog` keyed on `external_id` (heartbeat id) for
  idempotency. Emit `issue_activity` so the WORKLOG activity type finally has a producer.
- *Frontend:* worklog tab on the work-item peek/detail; Pomodoro widget (start/stop → POST
  worklog); workspace settings for the WakaTime token.

**Feature flag:** `time_tracking` (Phase-0 F0.1 flag plumbing); WakaTime pull gated by presence
of the `wakatime` `WorkspaceIntegration`.

**Tasks (→ child beads):** 1) Worklog+Pomodoro models+migration. 2) App/v1 CRUD + aggregates.
3) `issue_activity` WORKLOG emission. 4) WakaAPI poller + attribution + idempotency. 5) Worklog
UI tab. 6) Pomodoro widget. 7) Settings + docs. 8) Acceptance tests.

**Acceptance:** *API* — POST worklog via `/api/v1/` returns 201, appears in aggregate, is
idempotent on `external_id`; WakaTime poll creates ≤1 worklog per heartbeat. *UI* — Pomodoro
run persists a worklog visible on the item; totals render.

**Risks / upstream-merge impact:** Low. New app + additive migration; only core touch is a
`WORKLOG` producer in the activities task (mark `# woven:`). Attribution heuristic (branch→item)
is best-effort — expose manual re-attribution. WakaAPI token is a secret → ESO, never in DB plaintext beyond `config`.
