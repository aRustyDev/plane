# RBAC — Custom Roles

**Goal:** Allow workspace admins to define **custom roles** with granular capabilities, beyond
the fixed 3-tier integer enum (Admin=20 / Member=15 / Guest=5).

**Parity target:** Plane Commercial **Business** (custom roles).

**Background** (cite exact files/models): Roles are **hardcoded integers** in ≥4 places
(`research/auth-permissions.md §2.1`): `db/models/workspace.py:19`, `db/models/project.py:21,24`,
`app/permissions/base.py:13`, `app/permissions/project.py:13-15`. There is **no Viewer role** in
CE. Membership lives on `WorkspaceMember` (`workspace.py:198`) and `ProjectMember`
(`project.py:210`), each with an integer `role` + `is_active`. Enforcement runs through **two**
mechanisms: DRF permission classes (`app/permissions/{workspace,project,page}.py`) and the
dominant **`@allow_permission`** decorator (`app/permissions/base.py:19`, used in **38 view
files**) — all doing `role__in=[...]` `.exists()` checks. This decorator is the single
choke-point that makes custom roles tractable.

**Approach:**
- *Backend models + migrations (additive):* new `Role(BaseModel)` (workspace-scoped, `name`,
  `is_system`) + `RolePermission` mapping to a `Capability` enum (e.g. `issue.create`,
  `member.manage`, `state.edit`). Add nullable `custom_role` FK on `WorkspaceMember` /
  `ProjectMember`; the integer `role` stays as the system-role fallback. Seed system roles
  (Admin/Member/Guest) mapped to today's capability sets. Follow soft-delete + partial-unique
  conventions (`backend-data-model.md §5`).
- *Permission seam (F0.2 dependency):* extend `@allow_permission` to resolve **capabilities**
  from the member's `custom_role` (falling back to the integer role), instead of comparing
  ints. Because 38 files funnel through it, one rewrite covers most enforcement; audit the DRF
  permission classes as a second pass.
- *API:* `RoleViewSet` under `/api/workspaces/<slug>/roles/` (admin-only CRUD); extend member
  endpoints to assign `custom_role`.
- *Frontend:* workspace-settings "Roles" page (capability matrix); role picker in member
  management.

**Feature flag:** `RBAC_ENABLED` workspace/instance flag (F0.1). When off, the integer-role path
is used unchanged.

**Tasks (→ child beads):** (1) F0.2 permission-seam capability resolver; (2) `Role`/`Capability`
models + migration + system-role seed; (3) member `custom_role` wiring + role transition
guards (respect `member.py:88-89` demotion cascade); (4) `RoleViewSet` + API; (5) admin/settings
UI.

**Acceptance:** *API* — create a role granting only `issue.view`; a member with it is 403'd on
create/update but 200 on read; system-role users unaffected. *UI* — capability matrix persists;
member picker shows custom roles.

**Risks / upstream-merge impact:** Rewriting `@allow_permission` touches the hottest auth path —
must be behavior-preserving when the flag is off (regression-test all 38 sites). Depends on the
F0.2 seam; do not fork enforcement logic. Keep integer `role` intact for upstream compatibility.
