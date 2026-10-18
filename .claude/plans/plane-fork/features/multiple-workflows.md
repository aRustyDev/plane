# Multiple Workflows

**Goal:** Support several named workflows per project (and per Work Item Type), each its own set
of allowed transitions, so different types/teams follow different processes. Extends
**Workflow State-Transition Control**.

**Parity target:** Plane Commercial **Enterprise** (Multiple Workflows).

**Background** (extends workflow-state-control): The base feature adds one flat
`WorkflowTransition` graph per project scoped optionally by `issue_type`. There is still no notion
of a *named, selectable* workflow object — states remain project-scoped (`state.py:79`), and the
`Issue.type` FK (`issue.py:164`) is the only per-type discriminator. Multiple Workflows introduces
a first-class `Workflow` entity that a work item resolves to (via its type/project), and the
transition table hangs off it. Depends on **Work Item Types** (default binding = one workflow per
type) and the base transition guard in `Issue.save()` (`issue.py:180`).

**Approach:**
- *Backend models + migrations (additive):* new `Workflow(ProjectBaseModel)` — `name`,
  `is_default`, optional `issue_type` FK; **re-parent** `WorkflowTransition` from project onto a
  `workflow` FK (additive column + data-migration backfilling the base feature's project graph
  into one auto-created default workflow, so upgrades are lossless). Soft-delete + `deleted_at`
  partial-unique on `(project, name)` and on `(workflow, from_state, to_state)` (`§5`).
- *Resolution + enforcement:* extend `_enforce_transition()` (from workflow-state-control) to
  first **resolve the active workflow** for the issue — by `issue.type` binding, else the project
  default — then check that workflow's transitions. Keep the resolver a pure function so
  bulk/import paths can reuse it (`Issue.save()` bulk-bypass gotcha, `§ gotcha 1`).
- *API:* `WorkflowViewSet` (project-scoped CRUD, set default, bind to type); nest transition
  endpoints under a workflow. Serializers validate the bound `issue_type` belongs to the project.
- *Frontend:* extend the settings workflow editor to a list of named workflows with a per-type
  binding selector; the allowed-state dropdown resolves via the issue's active workflow.

**Feature flag:** Same `WORKFLOWS_ENABLED` flag (F0.1); "multiple" is unlocked when >1 workflow
exists. Single-workflow projects behave exactly like workflow-state-control.

**Tasks (→ child beads):** (1) `Workflow` model + `WorkflowTransition.workflow` FK migration +
default-workflow backfill; (2) workflow-resolution function + guard extension; (3) `WorkflowViewSet`
+ type-binding endpoints; (4) store/service updates; (5) named-workflow settings editor + binding UI.

**Acceptance:** *API* — create two workflows, bind each to a different type, verify an issue of
type A is blocked/allowed per workflow A only; base-feature graphs migrate into a default
workflow. *UI* — workflow list + per-type binding persists; dropdown reflects the resolved
workflow.

**Risks / upstream-merge impact:** The re-parent migration must backfill deterministically or
existing transitions orphan. Resolution adds a query on the hot save path — cache per-request /
`select_related`. Prerequisite for **Workflow Approvals**. All new tables + one additive FK; low
upstream drift.
