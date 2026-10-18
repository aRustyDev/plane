# F0.1 — Feature-flag + instance/workspace config plumbing

**Goal:** One place to gate every fork feature behind an instance- and workspace-scoped flag, so
features land incrementally and dark-launch OFF.

**Parity target:** Foundation, not a tier. Replaces Plane's closed license/feature-flag gating and
emulates the EE per-workspace feature-toggle surface.

**Background (today).** No feature gating exists (`research/auth-permissions.md` §4): `edition` is
hardcoded `PLANE_COMMUNITY`; `license_key` was removed in
`apps/api/plane/license/migrations/0005_rename_product_instance_edition_and_more.py`; no
`feature_flag`/`is_pro`/`check_license` anywhere. The reusable seam is the DB k/v model
`InstanceConfiguration` (`apps/api/plane/license/models/instance.py`: `key`/`value`/`category`/
`is_encrypted`). The config catalog master list is `apps/api/plane/utils/instance_config_variables/
core.py`; **`extended.py` ships an empty `extended_config_variables = []`** — the sanctioned
extension seam (verified). Keys are seeded idempotently by
`license/management/commands/configure_instance.py` and public capability flags (`IS_GOOGLE_ENABLED`,
…) are surfaced to the login screen via `license/api/views/instance.py::InstanceEndpoint` GET
(`AllowAny`). Frontend has no flag enum (`research/frontend-web.md` §8); gating today is marketing
strings in `packages/constants/src/subscription.ts`, and `WORKSPACE_SETTINGS_CATEGORY.FEATURES` is
empty — the natural home.

**Approach.** Two tiers. (1) **Instance flags:** add `WOVEN_FEATURE_<NAME>` keys to
`extended.py::extended_config_variables` (no core-file edit) + seed them in `configure_instance.py`.
(2) **Workspace flags:** new `WorkspaceFeatureFlag(workspace, key, is_enabled)` model (in the shared
`woven` app) with `deleted_at` + partial-unique constraint per the soft-delete gotcha. A
`feature_flags(workspace, user)` resolver merges instance-default under workspace-override.
*API:* extend the `InstanceEndpoint` public payload with the `IS_*` flags; add
`GET /api/workspaces/{slug}/feature-flags/` (read) + admin PATCH; a DRF helper `@requires_feature("rbac")`
returning 404 when off. *Frontend:* a `useFlag(key)` hook backed by the `instance`/workspace MobX
store reading the public payload; a feature-toggle page under `WORKSPACE_SETTINGS_CATEGORY.FEATURES`;
flag constants in a new `packages/constants` entry (avoid editing `subscription.ts`).

**Feature flag.** This *is* the flag system (always-on). Convention: `WOVEN_FEATURE_<NAME>`, default
**OFF**; instance flag gates availability, workspace flag gates per-tenant enablement.

**Tasks.** 1) enumerate flag keys in `extended.py` + seed; 2) `WorkspaceFeatureFlag` model +
migration; 3) resolver + `@requires_feature`; 4) expose in `InstanceEndpoint` + workspace read/admin
API; 5) frontend `useFlag` hook + FEATURES settings page + constants; 6) docs.

**Acceptance.** *API:* flag OFF → gated endpoint 404; ON at instance **and** workspace → 200; public
instance payload lists `IS_*` flags. *UI:* FEATURES settings toggles a workspace flag and a gated nav
item hides/shows accordingly.

**Risks / upstream-merge impact.** Low. `extended.py` is a zero-drift seam; `WorkspaceFeatureFlag`
is additive. Only core touch is `InstanceEndpoint.get()` payload (small, `# woven:`-marked). If
upstream later ships its own flags, reconcile the key namespace.
