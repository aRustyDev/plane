# F0.2 — Permission-layer seam (RBAC + ReBAC ready)

**Goal:** Refactor the `@allow_permission` decorator and DRF permission classes into a
capability-resolving seam that supports custom roles (RBAC) and per-object rules (ReBAC) **without
editing the 38 view files** that enforce access today.

**Parity target:** RBAC / custom roles = **Business** (#1); ReBAC / fine-grained work-item access =
**Enterprise** (#2).

**Background (today).** Roles are a fixed 3-tier integer enum — Admin=20 / Member=15 / Guest=5, **no
Viewer** in CE — duplicated across ≥4 files: `db/models/workspace.py:19`, `db/models/project.py:21,24`,
`app/permissions/base.py:13`, `app/permissions/project.py:13-15`. Two enforcement mechanisms
(`research/auth-permissions.md` §2): **(A)** DRF permission classes in
`apps/api/plane/app/permissions/{base,workspace,project,page}.py` — pure `role__in=[...]` +
`is_active` `.exists()` membership checks, no `has_object_permission` beyond membership; **(B)** the
dominant `@allow_permission([ROLE...], level="PROJECT", creator=False, model=None)` decorator at
`app/permissions/base.py:19` — used by **38 view files** (verified). Its `creator=True, model=Issue`
branch (`base.py:36-38`) is the only per-object escape hatch. Membership lives on `WorkspaceMember`/
`ProjectMember` (`role` + `is_active`); guest queryset scoping is in `app/views/issue/base.py:1039-1050`.

**Approach.** Keep the decorator **signature unchanged** so all 38 call sites are untouched; rewrite
only its body (and the DRF classes' internals) to resolve **capabilities** instead of comparing ints.
*Backend models (additive):* `Role` (workspace-scoped, `is_system` for the 3 built-ins), `Permission`
(capability string, e.g. `issue.delete`), `RolePermission` join — all with soft-delete + partial-unique.
Add a **nullable** `custom_role` FK to `WorkspaceMember`/`ProjectMember`; NULL falls back to the legacy
integer `role`. The seam maps each legacy `ROLE` member a call site passes into a required-capability
set, then checks the member's effective role grants it; built-in roles seed to today's exact behavior
(byte-for-byte backwards-compatible). *ReBAC:* generalize the creator check into a pluggable
`object_grants(user, obj)` resolver consulted when `model`/`creator` is set (per-issue ACL / relation
tuples later), and route guest scoping through a shared `scope_queryset` helper. Role-CRUD API + the
management UI ship as later child features; the seam lands with built-ins only.

**Feature flag.** `WOVEN_FEATURE_RBAC` (custom roles), `WOVEN_FEATURE_REBAC` (object rules). Both OFF →
resolver uses integer roles only = current behavior exactly.

**Tasks.** 1) capability catalog + built-in role→capability map; 2) `Role`/`Permission`/`RolePermission`
models + migration; 3) nullable `custom_role` FK on members; 4) rewrite `allow_permission` body + DRF
class internals to resolve capabilities; 5) `object_grants` / `scope_queryset` hook; 6) parity tests
across the 38 views.

**Acceptance.** *API:* flags OFF → existing permission suite passes unchanged. RBAC ON → a custom role
granting `issue.delete` lets a non-Admin delete; revoking → 403. ReBAC → a per-object grant unlocks one
issue only. *UI:* role editor (later).

**Risks / upstream-merge impact.** Medium. `app/permissions/*` are core files upstream edits — mark
`# woven:` and keep the decorator signature stable so conflicts land inside the seam body, never at the
38 call sites. The role-int duplication means the capability map must track any upstream role change.
