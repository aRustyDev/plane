# SCIM 2.0 Provisioning

**Goal:** Expose a **SCIM 2.0** service so Zitadel (or any IdP) can provision/deprovision Users
and Groups into a Plane workspace automatically, replacing manual invites.

**Parity target:** Plane Commercial **Enterprise** (SCIM provisioning).

**Background** (cite exact files/models): SCIM is **entirely absent** (`grep scim` → nothing;
`research/auth-permissions.md §5`). Provisioning today is invite-based
(`WorkspaceMemberInvite` `db/models/workspace.py:234`, `ProjectMemberInvite`
`db/models/project.py:192`) plus JIT signup in
`Adapter.complete_login_or_signup()` (`authentication/adapter/base.py:309`). The bearer-token
pattern to model auth on is `db/models/api.py::APIToken` + `app/middleware/api_authentication.py`
(`APIKeyAuthentication`, `X-Api-Key`). **No group primitive exists** to map SCIM Groups onto — a
`Group`/`Team` construct must be created (aligns with RBAC roles / Team Spaces).

**Approach:**
- *Backend models + migrations (additive):* new Django app `apps/api/plane/scim/`. Add
  `ScimToken` (per-workspace bearer secret, model after `APIToken`) and a `Group` model (or
  reuse the RBAC `Role`/team construct) with `GroupMember`. Store SCIM `externalId` on `User` /
  `Group` for idempotent mapping (mirror the existing `external_id`/`external_source` pattern).
  Soft-delete conventions per `backend-data-model.md §5`.
- *API (SCIM 2.0):* `/scim/v2/Users` and `/scim/v2/Groups` (GET list w/ filter, GET/POST/PUT/PATCH/DELETE),
  `/scim/v2/ServiceProviderConfig`, `/scim/v2/Schemas`, `/scim/v2/ResourceTypes`. Auth via a
  dedicated `ScimBearerAuthentication`. Map SCIM User → `User` + `WorkspaceMember`; `active=false`
  → deactivate (reuse the deactivated-account path); Group → `Group`+`GroupMember`. Use a SCIM
  library (e.g. `django-scim2`) or hand-roll the serializers.
- *Frontend:* admin/workspace settings page to mint the `ScimToken` and show the SCIM base URL +
  copyable token (one-time reveal).

**Feature flag:** `SCIM_ENABLED` workspace flag (F0.1); endpoints 404 when off.

**Tasks (→ child beads):** (1) `Group`/`GroupMember` model (coordinate with RBAC/Team Spaces);
(2) `ScimToken` + bearer auth; (3) `/scim/v2/Users` CRUD + filter + deactivate; (4)
`/scim/v2/Groups` CRUD + membership; (5) discovery endpoints; (6) settings UI to issue tokens.

**Acceptance:** *API* — IdP creates a user → `WorkspaceMember` appears; PATCH `active:false` →
member deactivated; POST Group with members → `Group` + memberships; RFC-7644 filter
`userName eq "x"` works. *UI* — token issuance + SCIM URL shown; revoke works.

**Risks / upstream-merge impact:** Fully additive new app — low merge risk. Depends on **OIDC**
(identity source) and the **RBAC/group** primitive. SCIM spec conformance is fiddly (list
pagination, PATCH `Operations`); IdP quirks (Zitadel/Okta/Entra) vary. Deprovisioning must reuse
Plane's soft-delete + deactivation, not hard-delete, to preserve `created_by` audit chains.
