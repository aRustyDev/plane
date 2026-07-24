# OIDC / SAML SSO

**Goal:** Ship a generic **OIDC** auth provider (and, in a second stage, **SAML**) so
`projects.woven` logs in via Zitadel. The Zitadel OIDC app is already applied and dormant:
authorize/token/userinfo at `id.auth.woven`, redirect
`https://projects.woven/auth/oidc/callback/`. This is the FIRST deliverable of the program and
is near-standalone (no dependency on the F0 permission seam).

**Parity target:** Plane Commercial (Enterprise) SSO — generic OIDC + SAML.

**Background** (cite exact files): There is **no central provider registry** — providers are
wired manually at ~6 sites (`research/auth-permissions.md §1.4–1.5`). The closest existing
template is the self-hosted **Gitea** adapter
`apps/api/plane/authentication/provider/oauth/gitea.py` (`GiteaOAuthProvider`, already
scoped `openid email profile read:user`, derives URLs from a configurable `GITEA_HOST`). It
subclasses `OauthAdapter` (`authentication/adapter/oauth.py`: `authenticate()` →
`set_token_data()` → `set_user_data()` → `complete_login_or_signup()`). Views mirror
`authentication/views/app/google.py` (state-CSRF check + `Instance.is_setup_done` gate).

**Approach — provider wiring (clone Gitea, 6 sites):**
1. `provider/oauth/oidc.py` — `OIDCOAuthProvider`; derive `auth_url/token_url/userinfo_url`
   from `OIDC_URL_*` config (or a discovery doc); map `sub`→`provider_id`, require verified
   email (reuse Gitea's verified-only guard, GHSA-7j95-vh8g-f365).
2. `views/app/oidc.py` + `views/space/oidc.py` — Initiate + Callback `View`s (copy `google.py`);
   export from `views/__init__.py`.
3. `adapter/error.py` — add `OIDC_NOT_CONFIGURED`, `OIDC_OAUTH_PROVIDER_ERROR`; extend
   `OauthAdapter.authentication_error_code()` (`oauth.py:49-59`, `else` branch today).
4. `authentication/urls.py` — add `oidc/`, `oidc/callback/` + `spaces/...` (mirror lines 79-91).
5. `utils/instance_config_variables/core.py` — add `oidc_config_variables` (`OIDC_CLIENT_ID`,
   `OIDC_CLIENT_SECRET` encrypted, `OIDC_URL_*`); `configure_instance.py` — derive
   `IS_OIDC_ENABLED` (mirror the `IS_GITEA_ENABLED` block, lines 122-144).
6. `license/api/views/instance.py::InstanceEndpoint.get()` — expose `is_oidc_enabled` (mirror
   lines 93-135); add admin form `apps/admin/.../authentication/oidc/form.tsx` (copy
   `google/form.tsx`).

**SAML (stage 2):** net-new **assertion-consumer** flow (not OAuth-code shaped) via
`python3-saml` — SP metadata endpoint + ACS POST view calling `complete_login_or_signup()`.
Separate config category + admin form. Do NOT block OIDC on it.

**Feature flag:** `IS_OIDC_ENABLED` / `IS_SAML_ENABLED` `InstanceConfiguration` keys (existing
DB-config mechanism); login screen reads the public `InstanceEndpoint` payload.

**Tasks (→ child beads):** (1) OIDC provider + adapter; (2) app+space views + urls + error
codes; (3) config seeding + `InstanceEndpoint` flag; (4) admin `oidc/form.tsx`; (5) wire
Zitadel end-to-end on `projects.woven`; (6) SAML ACS flow (separate bead, deferred).

**Acceptance:** *API* — `GET /auth/oidc/` 302s to Zitadel authorize; callback creates
`User`+`Account(provider="oidc")` and a session; verified-email guard rejects unverified.
*UI* — "Continue with SSO" button shows when `is_oidc_enabled`; admin form toggles it.

**Risks / upstream-merge impact:** All work is **additive new files** except small edits to
4 shared files (`oauth.py`, `error.py`, `urls.py`, `instance.py`) — mark each `# woven:`.
Upstream may later add its own OIDC; namespace ours to avoid collision. SAML dependency
(`python3-saml`/`xmlsec`) adds native build deps to the image.
