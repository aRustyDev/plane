# Plane Fork — Auth / AuthZ / Instance Admin Recon

Read-only architecture recon of the Plane fork at `/Users/asmith/repos/woven/forks/plane`.
Scope: Authentication, Authorization/Permissions, Instance Admin (god-mode), Feature gating,
and extension foundations for RBAC / ReBAC / SCIM / Audit / Guests.

Backend: `apps/api` (Django + DRF). Instance-admin UI: `apps/admin` (React Router + MobX).
This is **Plane Community Edition (CE)** — AGPL-3.0. No EE code present.

---

## 1. Authentication

### 1.1 Layout

```
apps/api/plane/authentication/
├── adapter/
│   ├── base.py          # Adapter — shared login/signup pipeline (complete_login_or_signup)
│   ├── credential.py    # CredentialAdapter (email/password, magic code)
│   ├── oauth.py         # OauthAdapter (token exchange + userinfo fetch)
│   ├── error.py         # AUTHENTICATION_ERROR_CODES + AuthenticationException
│   └── exception.py
├── provider/
│   ├── credentials/{email.py, magic_code.py}
│   └── oauth/{google.py, github.py, gitlab.py, gitea.py}
├── views/
│   ├── app/{email,magic,google,github,gitlab,gitea,check,password_management,signout}.py
│   ├── space/{...same set...}   # public "spaces" (published) portal, mirror of app/
│   └── common.py                # CSRFTokenEndpoint etc.
├── session.py           # BaseSessionAuthentication (DRF SessionAuthentication + CSRF)
├── middleware/session.py
├── rate_limit.py
├── urls.py              # all auth routes (mounted under /auth/)
└── utils/{login.py, redirection_path.py, user_auth_workflow.py, workspace_project_join.py, host.py}
```

### 1.2 How login works (the pipeline)

- **Session-based auth**, not JWT. `apps/api/plane/authentication/utils/login.py::user_login()`
  calls Django `login()` and writes a server session cookie. All app APIs authenticate via
  `BaseSessionAuthentication` (`authentication/session.py`), set on `BaseViewSet` /
  `BaseAPIView` (`app/views/base.py:51-55, 149-155`). `permission_classes = [IsAuthenticated]`
  is the default.
- Every provider subclasses `Adapter` (`adapter/base.py:35`). The shared method
  **`Adapter.complete_login_or_signup()`** (`adapter/base.py:309`) is the funnel: sanitizes
  email, finds-or-creates `User`, creates a `Profile`, enforces signup toggle
  (`__check_signup` → `ENABLE_SIGNUP` + `WorkspaceMemberInvite`), rejects deactivated accounts
  (`USER_ACCOUNT_DEACTIVATED`) and bot accounts (`BOT_USER_LOGIN_FORBIDDEN`), optionally
  IDP-syncs profile, then fires the `callback` (`post_user_auth_workflow`) and
  `create_update_account` (persists OAuth tokens to the `Account` model).
- **CredentialAdapter** (`adapter/credential.py`): `authenticate()` → `set_user_data()` →
  `complete_login_or_signup()`.
- **OauthAdapter** (`adapter/oauth.py`): `authenticate()` → `set_token_data()` (POST to
  `token_url`) → `set_user_data()` (GET `userinfo_url`) → `complete_login_or_signup()`.
  `create_update_account()` upserts a `plane.db.models.Account` row (provider,
  provider_account_id, access/refresh tokens, id_token).

### 1.3 The provider adapters

| Provider | File | Kind | Config keys (DB `InstanceConfiguration`) |
|---|---|---|---|
| Email/password | `provider/credentials/email.py` (`EmailProvider`, provider="email") | Credential | `ENABLE_EMAIL_PASSWORD` |
| Magic code | `provider/credentials/magic_code.py` (`MagicCodeProvider`, provider="magic-code") | Credential (Redis 6-digit code, brute-force capped) | `ENABLE_MAGIC_LINK_LOGIN`, `EMAIL_HOST` |
| Google | `provider/oauth/google.py` (`GoogleOAuthProvider`) | OAuth2 | `GOOGLE_CLIENT_ID/SECRET`, `IS_GOOGLE_ENABLED`, `ENABLE_GOOGLE_SYNC` |
| GitHub | `provider/oauth/github.py` | OAuth2 | `GITHUB_CLIENT_ID/SECRET`, `GITHUB_ORGANIZATION_ID`, `IS_GITHUB_ENABLED`, `ENABLE_GITHUB_SYNC` |
| GitLab | `provider/oauth/gitlab.py` (`GitLabOAuthProvider`) | OAuth2, self-hostable via `GITLAB_HOST` | `GITLAB_HOST/CLIENT_ID/SECRET`, `IS_GITLAB_ENABLED`, `ENABLE_GITLAB_SYNC` |
| Gitea | `provider/oauth/gitea.py` (`GiteaOAuthProvider`) | OAuth2/OIDC-ish, self-hosted via `GITEA_HOST`; **scope already `"openid email profile read:user"`** | `GITEA_HOST/CLIENT_ID/SECRET`, `IS_GITEA_ENABLED`, `ENABLE_GITEA_SYNC` |

Each OAuth provider hardcodes `auth_url`/`token_url`/`userinfo_url` (GitLab & Gitea derive them
from a configurable `*_HOST`, so they are the closest existing template for a generic OIDC
issuer). Providers pull secrets at construction via
`plane.license.utils.instance_value.get_configuration_value(...)` (DB config, env fallback) and
raise `*_NOT_CONFIGURED` if missing. Security hardening present: OAuth `state` CSRF check in
views; unverified-email rejection (`OAUTH_PROVIDER_UNVERIFIED_EMAIL`, Google `verified_email`,
GitLab `confirmed_at`); SSRF-safe avatar fetch.

### 1.4 There is NO central provider registry

`authentication/provider/__init__.py`, `.../oauth/__init__.py`, `.../credentials/__init__.py`
are **empty** (license header only). Providers are wired **manually, per provider**, by direct
import in views. Registration is spread across ~6 places.

### 1.5 How to add a new provider (OIDC / SAML / SCIM)

**OIDC (generic issuer)** — fits the existing pattern; ~6 touch-points, mirror `gitea.py`:
1. `provider/oauth/oidc.py` — subclass `OauthAdapter`; derive `auth_url/token_url/userinfo_url`
   from a configurable `OIDC_ISSUER`/discovery doc; map `sub`→`provider_id`, verified email.
2. `views/app/oidc.py` + `views/space/oidc.py` — Initiate + Callback `View`s (copy
   `views/app/google.py`, incl. `state` check + `Instance.is_setup_done` gate).
3. `adapter/error.py` — add `OIDC_NOT_CONFIGURED`, `OIDC_OAUTH_PROVIDER_ERROR` codes;
   extend `OauthAdapter.authentication_error_code()` (`adapter/oauth.py:49`).
4. `authentication/urls.py` — add `oidc/` + `oidc/callback/` (and `spaces/...`).
5. `utils/instance_config_variables/core.py` + `management/commands/configure_instance.py`
   (`IS_OIDC_ENABLED` derivation block) — seed config keys.
6. `license/api/views/instance.py::InstanceEndpoint.get()` — expose `IS_OIDC_ENABLED` in the
   public instance payload; add an `apps/admin` config form (copy `authentication/google/form.tsx`).

**SAML / SCIM** — no equivalent primitives exist. SAML needs a new assertion-consumer flow
(not OAuth code-exchange shaped) — heavier; consider `python3-saml`. SCIM is *provisioning*,
not login — see §5.

---

## 2. Authorization / Permissions

### 2.1 Role model — fixed 3-tier integer enum, workspace + project scoped

Roles are **integers**, defined redundantly in several places (all identical):
- `db/models/workspace.py:19` and `db/models/project.py:21`: `ROLE_CHOICES = ((20,"Admin"),(15,"Member"),(5,"Guest"))`
- `db/models/project.py:24` `class ROLE(Enum): ADMIN=20; MEMBER=15; GUEST=5`
- `app/permissions/base.py:13` duplicate `ROLE` enum; `app/permissions/project.py:13-15`
  `Admin=20/Member=15/Guest=5` constants.

**There is NO "Viewer" role in CE** — only Admin / Member / Guest. (Viewer exists in Plane EE.)

**Membership storage** (join tables, both with `role` + `is_active` + soft-delete):
- `db/models/workspace.py:198 WorkspaceMember` (`role` default 5=Guest, `is_active`).
  Invites: `WorkspaceMemberInvite` (`:234`).
- `db/models/project.py:210 ProjectMember` (`role` default 5, `is_active`). Invites:
  `ProjectMemberInvite` (`:192`).
- Project-level guest visibility flag: `Project.guest_view_all_features` (`project.py:100`).

### 2.2 Enforcement layer — TWO parallel mechanisms

**(A) DRF permission classes** (`apps/api/plane/app/permissions/`), set via
`permission_classes` on the viewset. Resolve workspace via `view.workspace_slug`
(`kwargs["slug"]`) and project via `view.project_id`:
- `workspace.py`: `WorkSpaceBasePermission`, `WorkspaceOwnerPermission` (role==Admin),
  `WorkSpaceAdminPermission` (Admin|Member), `WorkspaceEntityPermission`,
  `WorkspaceViewerPermission`, `WorkspaceUserPermission`, `WorkspaceMemberPermission`.
- `project.py`: `ProjectBasePermission`, `ProjectMemberPermission`, `ProjectEntityPermission`,
  `ProjectAdminPermission`, `ProjectLitePermission`. Note: workspace-Admin who is a project
  member is treated as project-admin (`project.py:42-53`).
- `page.py`: `ProjectPagePermission`.
All are `role__in=[...]` + `is_active=True` DB `.exists()` checks — **no policy engine, no
object-level `has_object_permission`** beyond these membership lookups.

**(B) `@allow_permission` decorator** (`app/permissions/base.py:19`) — the newer, dominant
pattern (**38 view files** use it). Decorates a viewset method:
`@allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT", creator=False, model=None)`.
- `level="WORKSPACE"` → checks `WorkspaceMember`; else `ProjectMember` (+ workspace-admin
  fallback, `base.py:64-78`).
- `creator=True, model=Issue` → per-object escape hatch: the row's `created_by == request.user`
  is allowed regardless of role (`base.py:36-38`). This is the ONLY built-in per-work-item
  access notion today.
- Example: `app/views/issue/base.py` — reads allow GUEST; create/update require MEMBER+;
  delete requires ADMIN or creator. Guest-scoped querysets filter on
  `project__project_projectmember__role` (`issue/base.py:1039-1050`).

Role transitions guarded in `app/views/workspace/member.py` (can't raise above your own role;
demoting to Guest=5 cascades project roles to Guest, `member.py:88-89`).

### 2.3 API-token auth (non-session path)

`app/middleware/api_authentication.py` (`APIKeyAuthentication`) authenticates the external REST
API (`/api/v1/...`) via `X-Api-Key` against `db/models/api.py::APIToken` (per-workspace,
`user_type` Human/Bot). Requests logged to `APIActivityLog` (see §5).

---

## 3. Instance / God-Mode Admin

### 3.1 Backend — `apps/api/plane/license/` app (misnamed; it is instance/config, NOT licensing)

Models (`license/models/instance.py`):
- **`Instance`** (singleton, `Instance.objects.first()`): `instance_id`, `current_version`,
  `edition` (hardcoded default `PLANE_COMMUNITY`), `is_setup_done`, `is_telemetry_enabled`,
  `whitelist_emails`, `domain`. `class InstanceEdition(Enum): PLANE_COMMUNITY` is the ONLY
  edition.
- **`InstanceAdmin`** — the god-mode grant: `(instance, user, role)` unique; `ROLE_CHOICES =
  ((20,"Admin"),)`.
- **`InstanceConfiguration`** — DB-backed key/value config: `key` (unique), `value`,
  `category`, `is_encrypted`. This is where **all auth modes are toggled and stored**.
- `ChangeLog` — release changelog display.

God-mode permission: `license/api/permissions/instance.py::InstanceAdminPermission` —
`InstanceAdmin.objects.filter(role__gte=15, instance=..., user=request.user).exists()`.

Admin auth/session flow (`license/api/views/admin.py`): `InstanceAdminSignUpEndpoint`
(first-boot, one-time — locks the `Instance` row, TOCTOU-hardened, sets `is_setup_done`),
`InstanceAdminSignInEndpoint` (email+password, must be an `InstanceAdmin`),
`InstanceAdminUserSessionEndpoint`, `InstanceAdminEndpoint` (CRUD instance admins),
`InstanceAdminSignOutEndpoint`. Uses the same `user_login()` session mechanism, `is_admin=True`.

Config API (`license/api/views/configuration.py`):
`InstanceConfigurationEndpoint` GET/PATCH (permission `InstanceAdminPermission`) — reads/writes
`InstanceConfiguration`, encrypting `is_encrypted` values (`license/utils/encryption.py`).
`DisableEmailFeatureEndpoint`, `EmailCredentialCheckEndpoint`.
`license/api/views/instance.py::InstanceEndpoint` GET is `AllowAny` and returns the *public*
auth capability flags (`IS_GOOGLE_ENABLED`, `IS_GITHUB_ENABLED`, `IS_GITLAB_ENABLED`,
`IS_GITEA_ENABLED`, `ENABLE_MAGIC_LINK_LOGIN`, `ENABLE_EMAIL_PASSWORD`, `ENABLE_SIGNUP`, …) so
the login screen knows which buttons to show.

Config catalog & seeding:
- `utils/instance_config_variables/core.py` — the master list of config keys + categories
  (`AUTHENTICATION`, `SMTP`, `AI`, `UNSPLASH`, …). `extended.py` is **empty** (`[] `) — the
  EE/extension seam.
- `management/commands/configure_instance.py` — idempotent seeding of `InstanceConfiguration`
  from env; derives `IS_GOOGLE/GITHUB/GITLAB/GITEA_ENABLED` from presence of client id/secret.
- `management/commands/register_instance.py` — creates the `Instance` singleton.

### 3.2 Frontend — `apps/admin`

React Router + MobX SPA served separately (`Dockerfile.admin`, `nginx/`). Talks to backend via
`@plane/services` → `packages/services/src/instance/instance.service.ts`:
`GET/PATCH /api/instances/`, `GET /api/instances/admins/`,
`GET/PATCH /api/instances/configurations/`,
`POST /api/instances/email-credentials-check/`,
`DELETE /api/instances/configurations/disable-email-feature/`.
State: `apps/admin/store/instance.store.ts` (`fetchInstanceConfigurations`,
`updateInstanceConfigurations`, `instanceAdmins`, `formattedConfig`).
Auth toggle UIs: `apps/admin/app/(all)/(dashboard)/authentication/{google,github,gitlab,gitea}/form.tsx`
— each PATCHes the provider's `*_CLIENT_ID/SECRET` + `IS_*_ENABLED` config keys.
Setup wizard: `apps/admin/components/instance/setup-form.tsx`.

---

## 4. Feature Gating — CONFIRMED ABSENT

There is **no license check, no feature flag, no edition gate** in the CE source:
- `edition` is hardcoded to `PLANE_COMMUNITY`; `InstanceEdition` enum has only that one value.
- **`license_key` was explicitly REMOVED** in migration
  `license/migrations/0005_rename_product_instance_edition_and_more.py` (`RemoveField
  license_key`; `product`→`edition`). The current `Instance` model has no license/subscription
  fields.
- Grep for `feature_flag`/`payment`/`subscription`/`is_pro`/`is_enterprise`/`check_license`
  across `apps/api` → no gating logic (only unrelated `subscribe`/issue-subscription hits).
- The `license/` app is a misnomer: it is instance registration + telemetry + DB config, not
  licensing. `bgtasks/telemetry_metrics.py` reports usage only.
- `utils/instance_config_variables/extended.py = []` — a deliberate, empty extension seam.

Nothing needs to be un-gated to build EE-style features here; the fork starts from a clean CE base.

---

## 5. Extension Foundations & Gaps for Planned Features

### RBAC (custom roles) — GAP; needs new model + refactor
- Roles are **hardcoded integers** in ≥4 files (`db/models/{workspace,project}.py`,
  `app/permissions/{base,project}.py`). No `Role`/`Permission` table, no role-permission
  mapping. Custom roles require a new model and threading a role-id through `WorkspaceMember` /
  `ProjectMember` plus rewriting `@allow_permission` + all DRF permission classes to resolve
  capabilities instead of comparing role ints. The single choke-point that helps:
  `@allow_permission` (`app/permissions/base.py`) — 38 files funnel through it, so a
  capability-resolving rewrite there covers most enforcement in one place.

### ReBAC / fine-grained per-work-item access — GAP; thin foundation
- Only existing per-object notion: `@allow_permission(creator=True, model=Issue)` (owner check)
  and guest queryset filtering by `ProjectMember.role`. No relationship/ACL tables, no
  `has_object_permission` graph. `IssueSubscriber`, `IssueAssignee`, `IssueMention` exist as
  relationship rows but are not access-control. A ReBAC layer (e.g. per-issue ACL or a
  relation-tuple store / OpenFGA-style) would be net-new; hook point is again `@allow_permission`
  plus queryset scoping in `app/views/issue/base.py`.

### SCIM (user/group provisioning) — GAP; entirely absent
- No SCIM endpoints/models (`grep scim` → nothing). Provisioning today is invite-based
  (`WorkspaceMemberInvite`/`ProjectMemberInvite`) + JIT signup in
  `Adapter.complete_login_or_signup()`. A SCIM 2.0 service would be a new DRF app mapping
  SCIM Users→`User`+`WorkspaceMember`, Groups→(new) role/team construct; auth via a dedicated
  bearer token (model after `APIToken`). No group primitive exists to map SCIM Groups onto.

### Audit logging — PARTIAL; no general audit log
- **`IssueActivity`** (`db/models/issue.py:415`, table `issue_activities`): per-issue change
  feed (`verb`, `field`, `old_value`, `new_value`, `actor`, `comment`, `epoch`). Rich but
  **issue-scoped only** — populated by `bgtasks/issue_activities_task.py`.
- **`APIActivityLog`** (`db/models/api.py:51`, table `api_activity_logs`): external-API request
  log (token_identifier, path, method, response_code) — populated by `middleware/logger.py`.
- **No workspace/instance-wide audit log** of admin actions, logins, role changes, config
  changes, member add/remove. `InstanceConfiguration` PATCH, `InstanceAdmin` CRUD, and auth
  events are NOT audited. Building Audit Logging (API + UI) = net-new `AuditLog` model +
  emit points (a signal/middleware or explicit calls in the ~38 mutating views) + a read API +
  admin UI. `IssueActivity` is a schema template but not reusable as-is.

### Guests / Guest access — PARTIAL; exists but coarse
- Guest IS a first-class role (value 5) at both workspace and project scope. Enforcement:
  `@allow_permission([...ROLE.GUEST...])` gates which endpoints guests may hit; querysets
  filter guest visibility via `ProjectMember.role` and `Project.guest_view_all_features`
  (`app/views/issue/base.py:1039-1050`, `db/models/project.py:100`). Workspace→Guest demotion
  cascades to project roles (`app/views/workspace/member.py:88-89`).
- Gap vs. a "Guest Access" product feature: no per-entity guest sharing, no external-guest
  identity distinction beyond the role, no guest-scoped audit. Comments have an
  `INTERNAL/EXTERNAL` `access` field (`db/models/issue.py:467`) — a small existing hook for
  external visibility.

---

## Key file index (absolute paths)

- Auth pipeline: `apps/api/plane/authentication/adapter/base.py` (`complete_login_or_signup`),
  `.../adapter/oauth.py`, `.../adapter/credential.py`, `.../adapter/error.py`
- Providers: `apps/api/plane/authentication/provider/oauth/{google,github,gitlab,gitea}.py`,
  `.../provider/credentials/{email,magic_code}.py`
- Auth views/routes: `apps/api/plane/authentication/views/app/*.py`, `.../urls.py`
- Session auth: `apps/api/plane/authentication/session.py`; API-key auth:
  `apps/api/plane/app/middleware/api_authentication.py`
- Permissions: `apps/api/plane/app/permissions/{base,workspace,project,page}.py`
- Base viewsets: `apps/api/plane/app/views/base.py`
- Role/member models: `apps/api/plane/db/models/{workspace,project}.py`
- Instance/god-mode: `apps/api/plane/license/models/instance.py`,
  `.../license/api/views/{admin,instance,configuration}.py`,
  `.../license/api/permissions/instance.py`
- Config catalog/seed: `apps/api/plane/utils/instance_config_variables/{core,extended}.py`,
  `.../license/management/commands/configure_instance.py`
- Audit-ish tables: `apps/api/plane/db/models/issue.py` (`IssueActivity`),
  `apps/api/plane/db/models/api.py` (`APIActivityLog`)
- Admin UI: `apps/admin/store/instance.store.ts`,
  `apps/admin/app/(all)/(dashboard)/authentication/*/form.tsx`,
  `packages/services/src/instance/instance.service.ts`
