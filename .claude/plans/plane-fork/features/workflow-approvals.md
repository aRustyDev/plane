# Workflow Approvals

**Goal:** Gate selected workflow transitions behind an approval: a work item requesting a gated
transition enters a pending state until an authorized approver approves (transition commits) or
rejects (transition blocked). Extends **Multiple Workflows**.

**Parity target:** Plane Commercial **Enterprise** (Workflow Approvals).

**Background** (extends multiple-workflows): Neither approvals nor any pending/gated concept exists
in CE. `WorkflowTransition` (added by workflow-state-control, re-parented onto `Workflow` by
multiple-workflows) is a bare from→to edge; the guard in `Issue.save()` (`issue.py:180`) either
allows or 400s a change — there is no "hold for approval". `IssueActivity` + the
`issue_activities_task` pipeline (`bgtasks/issue_activities_task.py`) already record state changes
and can carry approval events. Depends on **Multiple Workflows** (approval is a property of a
transition edge) and the RBAC capability seam (F0.2, approver authorization).

**Approach:**
- *Backend models + migrations (additive):* add `requires_approval` (bool) + `approver_role` /
  `approver` set to `WorkflowTransition`. New `TransitionApprovalRequest(ProjectBaseModel)` — FK
  → issue, workflow transition, requester, status enum (`pending|approved|rejected`), decided_by,
  decided_at, note. Soft-delete + `deleted_at` partial-unique on `(issue, transition)` where
  pending (`§5`).
- *Enforcement (hot path):* in `_enforce_transition()`, when the resolved edge
  `requires_approval` and no `approved` request exists, **block the `state_id` write** and instead
  create/return a pending `TransitionApprovalRequest` — do not mutate `Issue.state`. On approval,
  a separate action re-invokes `save()` to commit the state change. Emit approval
  request/approve/reject events via `issue_activities_task`. Bulk/import paths bypass `save()` and
  therefore approvals (`§ gotcha 1`) — document.
- *API:* endpoints to request/approve/reject; approver authorization via the RBAC capability
  resolver (F0.2), not hardcoded roles. Notify subscribers via the existing activity/notification
  pipeline.
- *Frontend:* transition editor gains a "requires approval" + approver-role control; issue detail
  shows a pending-approval banner + approve/reject for authorized users; a pending-approvals inbox.

**Feature flag:** `WORKFLOW_APPROVALS_ENABLED` (F0.1), layered on `WORKFLOWS_ENABLED`. Off →
transitions behave as multiple-workflows with no gating.

**Tasks (→ child beads):** (1) transition approval fields + `TransitionApprovalRequest` model +
migration; (2) guard extension that parks the transition + creates the request; (3) request/approve/
reject API + RBAC authorization + activity events; (4) store/service + notifications; (5) approval
UI (editor control, detail banner, inbox).

**Acceptance:** *API* — a gated transition creates a pending request and leaves `state` unchanged;
approve commits the state change; reject blocks it; non-approver is 403'd. *UI* — banner + inbox
reflect pending state; approve/reject updates the item.

**Risks / upstream-merge impact:** Highest-complexity edge on the `Issue.save()` path — the "park,
don't mutate" branch must be airtight against partial state writes (wrap in the existing
`transaction.atomic`). Depends on RBAC + Multiple Workflows. New tables + additive columns;
notifications ride the existing pipeline — low upstream drift.
