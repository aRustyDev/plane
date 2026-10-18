# New-session kickoff — build `plane-07r` (OIDC provider)

> Paste the block below into a fresh Claude Code session opened in
> `/Users/asmith/repos/woven/forks/plane`. It is memory-aware: it primes from beads + the
> committed plan before writing code.

---

You're picking up the **Plane fork "Open-EE"** program in this repo
(`/Users/asmith/repos/woven/forks/plane`). We forked Plane CE to build its paid-tier features
ourselves. **This session: implement bead `plane-07r` — the generic OIDC auth provider** — the
first real code of the program (SSO ships first).

**Prime yourself first:**
1. `bd prime`, then `bd show plane-bbt` and `bd show plane-07r`, then `bd ready`.
2. Read the plan: `.claude/plans/plane-fork/PROGRAM.md` (§2.5 strategy + guardrails) and
   `.claude/plans/plane-fork/features/oidc-saml-sso.md` (**the build-ready slice — authoritative**).
3. Read the grounding: `.claude/plans/plane-fork/research/auth-permissions.md` (there is **no**
   central provider registry; providers are wired at ~6 manual sites).

**Scope of `plane-07r` (this session only — keep the PR tight):**
- Clone `apps/api/plane/authentication/provider/oauth/gitea.py` → `provider/oauth/oidc.py` as
  `OIDCOAuthProvider`: derive authorize/token/userinfo from `OIDC_URL_*` config (or the discovery
  doc), map `sub`→`provider_id`, and **require a verified email** (keep Gitea's verified-only
  guard, GHSA-7j95-vh8g-f365).
- Acceptance: unit-level — token + userinfo parse; an unverified email is rejected.
- Do **not** build the views/urls/config/admin-form yet — those are the next beads
  (`plane-1f2`, `plane-4cr`, `plane-5kc`). This bead is the provider/adapter only.

**Guardrails (non-negotiable):**
- **Clean-room:** design from Plane's public behavior/docs + the Gitea adapter — **never copy
  Plane's closed Commercial/EE code.**
- Branch **`woven/oidc-sso`** off tag **`v1.3.1`** (D-BASE). Additive new files; mark any edit to a
  shared/core file `# woven:`.
- Gate behind the existing `InstanceConfiguration` **`IS_OIDC_ENABLED`** key (no new flag system).
- Track with `bd`: `bd update plane-07r --claim` on start, `bd close` when done; file follow-up
  beads for anything discovered. **Don't commit/push without being asked.**

**Downstream (context only — don't build):** `plane-1f2` → `plane-4cr` → `plane-5kc` → `plane-ub2`
(go-live on `projects.woven`: enter Zitadel client_id `383249177292901445` + endpoints at
`id.auth.woven` into the admin form; secret is out-of-band). The Zitadel app is already applied and
waiting.

Start by priming, then `bd update plane-07r --claim` and implement.
