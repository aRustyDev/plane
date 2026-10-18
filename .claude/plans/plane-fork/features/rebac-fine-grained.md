# ReBAC — Fine-Grained / Per-Work-Item Access

**Goal:** Relationship-based, **object-level** access control — grant/deny access to individual
work items (and later pages/cycles) independent of project role, beyond today's single
`creator=True` owner escape hatch.

**Parity target:** Plane Commercial **Enterprise** (fine-grained access).

**Background** (cite exact files/models): The only per-object notion today is
`@allow_permission(creator=True, model=Issue)` — the row's `created_by == request.user` bypass
(`app/permissions/base.py:36-38`, `research/auth-permissions.md §2.2/§5`). Guest visibility is
coarse: querysets filter on `ProjectMember.role` + `Project.guest_view_all_features`
(`app/views/issue/base.py:1039-1050`, `db/models/project.py:100`). `IssueSubscriber`,
`IssueAssignee`, `IssueMention` exist as relationship rows but are **not** access control. There
is **no relation-tuple store, no `has_object_permission` graph**. Hook points: `@allow_permission`
(`base.py:19`) + queryset scoping in `app/views/issue/base.py`.

**Approach:**
- *Backend models + migrations (additive):* new `AccessGrant(BaseModel)` relation-tuple table —
  `(subject_type, subject_id, relation, object_type, object_id, effect)` — subject = user /
  role / group; relation = `viewer|editor|owner`; object = issue (extensible to page/cycle).
  Workspace-scoped, soft-delete + partial-unique (`backend-data-model.md §5`). Optionally back
  with an OpenFGA-style engine later; start with an in-DB resolver.
- *Enforcement:* add real `has_object_permission()` to the permission layer and a
  `filter_visible(queryset, user)` helper that unions role-based access with `AccessGrant` rows;
  wire into `app/views/issue/base.py` list/detail/mutate paths and `@allow_permission` (via the
  F0.2 seam). Keep the `creator` bypass as the highest-priority grant.
- *API:* `/api/workspaces/<slug>/projects/<id>/issues/<id>/access/` — list/add/remove grants
  (editor+ only). *Frontend:* a per-work-item "Share / Manage access" panel (reuse the member
  picker); a lock indicator on restricted items.

**Feature flag:** `REBAC_ENABLED` (F0.1); off ⇒ role-only visibility (current behavior).

**Tasks (→ child beads):** (1) `AccessGrant` model + migration + resolver; (2) `has_object_permission`
+ `filter_visible` seam integration; (3) issue-view list/detail/mutate scoping; (4) access API;
(5) share panel UI.

**Acceptance:** *API* — grant user B `viewer` on one issue in a project B can't otherwise see →
B reads that issue only; revoke → 404. *UI* — share panel lists grants; restricted items hidden
from non-grantees.

**Risks / upstream-merge impact:** Depends on **RBAC** (subjects reference roles/groups) and the
F0.2 seam. Object-level filtering is performance-sensitive on large issue lists — index the
tuple table and avoid N+1. Must not weaken existing guest scoping. Enforcement edits concentrate
in `issue/base.py` + the permission seam; mark `# woven:`.
