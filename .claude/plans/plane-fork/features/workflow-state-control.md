# Workflow State-Transition Control

**Goal:** Restrict work-item state changes to an explicitly allowed transition graph (per project,
optionally per Work Item Type), replacing today's free-form any→any behavior, enforced on the
`Issue.save()` state-change path.

**Parity target:** Plane Commercial **Business** (Workflows).

**Background** (greenfield enforcement; state schema exists): `State(ProjectBaseModel)`
(`state.py:79`) has only `group` (`StateGroup`: backlog/unstarted/started/completed/cancelled/
triage), `sequence`, `is_triage`, `default` — **no transition table**. `StateViewSet`
(`app/views/state/base.py`) is plain CRUD. Any authorized user can move an issue to **any** project
state; the only server-side rules are `_ensure_default_state()` + `_sync_completed_at()` and the
triage/default manager filtering (`backend-data-model.md §5`). Transition detection already exists:
`Issue` is a `ChangeTrackerMixin` with `TRACKED_FIELDS = ["state_id"]` (`issue.py:105`) and
`_sync_completed_at` already branches on `has_changed("state_id")` (`issue.py:240`) — the exact
hook point for a guard. Depends on **Work Item Types** (optional per-type scoping).

**Approach:**
- *Backend model + migration (additive):* `WorkflowTransition(ProjectBaseModel)` — `from_state`
  FK, `to_state` FK, optional `issue_type` FK, optional allowed-`role` set. Soft-delete +
  `deleted_at` partial-unique on `(project, issue_type, from_state, to_state)` (`§5`). A project
  with **no** transitions defined = unrestricted (backward-compatible default; flag-gated).
- *Enforcement (the heavy path):* add a `_enforce_transition()` check inside `Issue.save()`,
  invoked only when `not self._state.adding and self.has_changed("state_id")` — mirror the
  existing `_sync_completed_at` guard so it runs on the same tracked-field signal. Raise a
  validation error the issue-update view maps to HTTP 400. **Bulk ops bypass `save()`**
  (`§ gotcha 1`) — importer/sync paths must call the same guard explicitly or opt out
  deliberately.
- *API:* `WorkflowTransitionViewSet` under the project scope (admin CRUD); issue-update returns a
  structured "transition not allowed" error listing valid next states.
- *Frontend:* workflow editor under `PROJECT_SETTINGS_CATEGORY.WORK_STRUCTURE`; the state dropdown
  in the issue detail/kanban filters options to allowed `to_state`s (fetch via a store/service).

**Feature flag:** `WORKFLOWS_ENABLED` project/workspace flag (F0.1). Off, or no transitions
defined → any→any (today's behavior) unchanged.

**Tasks (→ child beads):** (1) `WorkflowTransition` model + migration; (2) `_enforce_transition`
hook in `Issue.save()` (guarded, flag-aware) + bulk-path audit; (3) `WorkflowTransitionViewSet` +
structured error; (4) store/service; (5) settings workflow editor + allowed-state dropdown filter.

**Acceptance:** *API* — with transitions defined, a disallowed `state` change 400s with valid
options; an allowed one 200s; flag-off allows anything. *UI* — state dropdown shows only allowed
targets; editor persists the graph.

**Risks / upstream-merge impact:** Touches the hottest write path (`Issue.save()`) — must be a
no-op when flag-off (regression-test create + update + completed_at sync). Any bulk/import writer
silently skips the guard — document and gate. Extended by Multiple Workflows and Approvals; keep
the guard modular.
