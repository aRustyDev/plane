# F0.6 — CI/CD & PR Automation + Repo Governance (fork)

**Goal:** Turn the inherited upstream CI into a **fork-owned, tag-driven, signed release pipeline**
with real PR gating, conventional-commit + KeepAChangelog automation, and GitHub-ruleset governance —
and rename the woven integration branch **`master → main`**. Extends **F0.5 / `plane-8xx`**
(`woven-build.yml` image build), which becomes the "container build" stage here.

**Why now:** PRs to `master` (our integration base — see the OIDC PRs #1/#2) get **no CI at all**: the
inherited workflows gate only `preview`, and even those are gated behind `requested_reviewers != null`
with a `CODEOWNERS` pointing at upstream `makeplane` maintainers who aren't fork collaborators. Images
build only on `preview`/`canary` push and push to the **upstream `makeplane` Docker Hub namespace**; there
is no tag/release trigger, no signing/provenance/SBOM, no changelog/SemVer automation, and **zero**
branch protection or rulesets (default branch is `preview`, Actions unrestricted, no SHA pinning).

---

## Current-state baseline (the gaps)

| Area | Today | Gap |
|---|---|---|
| PR linting | `turbo run {check:format,build,check:lint,check:types} --affected` (web) + `ruff` (api) | only on PRs to **`preview`**; gated on `requested_reviewers != null`; nothing runs on `master` |
| Pre-commit | husky `pre-commit → lint-staged` (oxlint/oxfmt) | no `commit-msg`/commitlint; no conventional-commit enforcement; no py `pre-commit` |
| Versioning | root `package.json` `1.3.1`; `check-version.yml` only asserts version ≠ `master`'s | no SemVer format/increment check; **no CHANGELOG**; no automation |
| Container build | 6 Dockerfiles built via `makeplane/actions/build-push` on preview/canary push → **Docker Hub `makeplane/*`** | no `on: push: tags`/`on: release`; not a fork registry; `feature-deployment.yml` refs a missing `./aio/Dockerfile-app` |
| Signing/provenance | none (`grep cosign/sigstore/provenance/slsa` → 0) | no signature, SLSA provenance, or SBOM |
| Governance | rulesets `[]`; `master`/`preview` unprotected; default = **`preview`**; Actions "all", no SHA pinning | no branch/tag/push rules; CI can be edited in a PR |
| Security scanning | default-config CodeQL (python+javascript) only | no Dependabot, dependency-review, image scan (trivy/grype), secret scan (gitleaks), or custom CodeQL |
| Branch model | default `preview`; `master` = our integration base; `master` hardcoded in `check-version.yml`, `codeql.yml`, deploy scripts, docs | rename to `main` + make it default |

---

## Target pipeline

```
PR → smart lint/type/format/build (--affected) + dependency-review + secret scan
   → merge to main
   → [maintainer] Release job: git-cliff bump + CHANGELOG (KeepAChangelog) + annotated tag vX.Y.Z  (App token)
   → on: push tags 'v*': build 6 images → GHCR by DIGEST → cosign keyless sign + SLSA provenance + SBOM
   → GitHub Release (changelog body) + image scan (trivy)
   → infra bumps plane_image_tag (F0.5) → woven-o11y admission verifies cosign identity/issuer
```

---

## Workstreams

### A. Smart linting (GH Actions) + fork-fit PR gating
- Retarget the PR workflows from `preview` → **`main`** (keep a `preview`/`canary` trigger only for the
  deliberate upstream-sync PRs). Drop the `requested_reviewers != null` gate (fork-hostile) — run on all
  non-draft PRs. Replace `/CODEOWNERS` with fork owners (or remove it) so the gate/required-reviews work.
- Keep Turborepo `--affected` smart selection (`TURBO_SCM_BASE/HEAD`) + pnpm/turbo caches; keep `ruff` for
  api and `copyright-check`. Emit **stable, required check names** (these become the ruleset's required checks).

### B. Pre-commit (local)
- Add a husky **`commit-msg`** hook → `@commitlint/cli` + `@commitlint/config-conventional`; keep
  `lint-staged` on `pre-commit`. Optional `cz-git` (`git cz`) prompt. Document the **pnpm-on-PATH** gotcha
  (hooks call `pnpm`; contributors using `npx pnpm` must `corepack enable`) — this bit us when committing.
- Optional `.pre-commit-config.yaml` for `apps/api` (ruff/ruff-format) — the JS husky already covers TS.

### C. SemVer + KeepAChangelog automation — **release-please** (decided)
- **Input gate:** `@commitlint/cli` + `@commitlint/config-conventional` (husky `commit-msg`, §B) — clean
  conventional commits are what release-please consumes.
- **Orchestrator: `googleapis/release-please-action`** (manifest mode, monorepo). Every push to `main` it
  maintains a **release PR** that bumps the version and updates `CHANGELOG.md`; on merge it creates the
  annotated **`vX.Y.Z`** tag + GitHub Release. Configure `changelog-sections` → the **six KeepAChangelog
  sections** (feat→Added, fix→Fixed, perf/refactor/build/deps→Changed, + Deprecated/Removed/Security) so
  headings/`compare` links/`[YANKED]` stay KeepAChangelog-compliant. Seed `.release-please-manifest.json`
  at `1.3.1`; one-time `CHANGELOG.md` backfill.
- **No `workflow_dispatch` release job, no git-cliff** (decided). git-cliff only if we ever need an ad-hoc
  render. Reserve semantic-release solely for any `packages/*` genuinely npm-published.
- **Token:** run release-please with the **release App token** (not `GITHUB_TOKEN`) so the release PR gets
  CI and its commits are API-made → auto-**Verified** (satisfies the signed-commits rule, §G).

### D. Automated container build + release (release-driven, fork registry) — extends `plane-8xx`
- `woven-build.yml` runs **when release-please cuts a release** — either chained in release-please's own
  workflow gated on its `release_created`/`tag_name` outputs, or `on: release: [published]` (sidesteps the
  "tag pushed by a token doesn't fire `on: push: tags`" loop-prevention gotcha). Build the 6 images
  (`admin/web/space/live/api/proxy`) from this fork's Dockerfiles to **GHCR
  `ghcr.io/arustydev/plane-<service>`** (per-service packages), tagged by **digest** + `vX.Y.Z` + `sha`.
  `packages: write` + GHCR OIDC. (F0.5 scopes the registry + infra `plane_image_tag` wiring.)

### E. Attestation & provenance (cosign keyless + SLSA)
- Per image, sign the **digest** (never the tag) keyless via GitHub OIDC: `cosign sign --yes REG/IMG@sha256:…`
  (perms `id-token: write`, `attestations: write`, `packages: write`). Attest **SLSA provenance** and an
  **SBOM**: `cosign attest --type slsaprovenance` + `--type spdxjson`. Add GitHub-native
  `actions/attest-build-provenance` as a companion (`gh attestation verify`).
- **Consumers verify** with mandatory `--certificate-identity-regexp '…/release.yml@refs/tags/v.*'` +
  `--certificate-oidc-issuer https://token.actions.githubusercontent.com`. This is what a **woven-o11y**
  admission policy (Sigstore policy-controller / Kyverno `verifyImages`) enforces before pods run.

### F. Release/tag automation
- The **GitHub Release** published by release-please is the release contract; the build/sign workflow keys
  off release-please's `release_created` output (same workflow) or `on: release: [published]` — **not**
  `on: push: tags` (avoids the `GITHUB_TOKEN`-tag-no-trigger loop gotcha). Protect `v*` with a **tag
  ruleset** (G) so the supply-chain trigger is immutable.

### G. GitHub Rulesets (governance) — **land last**
- **Branch ruleset on `main`:** require PR (+ conversation resolution), **required status checks (strict)**
  = the A check names, **linear history**, block force-push + deletion. **Require signed commits — YES**
  (decided): coherent because release-please commits via the API with the App token (auto-**Verified**) and
  human changes land via **GitHub-UI squash/merge** (GitHub-signed → Verified); local direct pushes to
  `main` are blocked anyway. **Bypass list = the release App** (so it can push the release PR + tag).
- **Tag ruleset `v*`:** restrict creation to maintainers/bot; block update+delete (immutable release tags).
- **Push rulesets (pilot in `Evaluate`):** block edits to `.github/workflows/*` (supply-chain), block
  binary blobs (`*.exe/*.zip/*.db/*.sqlite`), `commit_message_pattern` = Conventional Commits (belt-and-
  suspenders with commitlint). Roll out **Evaluate → Rule Insights → Active**; never all-at-once.

### H. Security scanning
- **Dependabot** (`.github/dependabot.yml`): npm (pnpm), pip (`apps/api`), docker, github-actions.
- **`dependency-review-action`** on PRs; **actions/attest** already in E.
- **SHA-pinned Actions — DEFERRED** (decided): pin all actions to a commit SHA (and optionally enforce via
  ruleset/Actions policy) **once the CI/CD flow is stable**, to avoid churn while iterating on workflows.
- **Image scan** (trivy or grype) in the release workflow (fail on HIGH/CRITICAL, upload SARIF).
- **Secret scan** (gitleaks) on PR + push; enable GitHub secret scanning + push protection (repo setting).
- **CodeQL:** add a `codeql-config.yml` (extend to `actions` language; security-extended queries); retarget
  branches to `main`. Fork-specific `SECURITY.md` contact.

### I. `master → main` rename + default branch
- Rename `master → main` (`gh api -X POST repos/aRustyDev/plane/branches/master/rename -f new_name=main`).
  GitHub **auto-retargets open PRs** (our PR #2) and moves protection/rulesets — low risk mid-review.
- **Make `main` the default branch** (currently `preview`) so PRs/tooling/rulesets default to our line;
  keep `preview`/`canary` as **upstream-sync mirrors** (D-BASE deliberate merges).
- Update hardcoded refs: `check-version.yml` (base + `git fetch/checkout master`, L6/25/29/32/36),
  `codeql.yml` (L6/8), `deployments/{swarm,cli}/community/*.sh`, README/docs blob links, `.claude/skills/*`.
  Local fixups for existing clones: `git branch -m master main && git fetch && git remote set-head origin -a`.

---

## Phased rollout (ordered to respect sequencing risks)

1. **Branch + CI bring-up:** `master→main` + set default; retarget/fix PR workflows to `main`; drop the
   reviewer-gate; fix/remove `CODEOWNERS`. → *PR CI works immediately (fixes the #1/#2 no-CI gap).*
2. **Commit hygiene:** commitlint `commit-msg` hook; `cliff.toml` + one-time `CHANGELOG.md` backfill.
3. **Release automation:** (after the **GitHub App(s) strategy** decision) install the release App; land
   **release-please** (manifest + KeepAChangelog sections) so merges to `main` maintain a release PR → tag
   + Release. Provision **GHCR** + pull creds (ESO, per F0.5).
4. **Release-driven build/sign:** `woven-build.yml` on `release_created`/`release: published` → GHCR by
   digest → cosign keyless sign + SLSA provenance + SBOM + trivy scan.
5. **Cluster enforcement (infra):** woven-o11y admission policy verifies cosign identity/issuer.
6. **Security scanning:** Dependabot, dependency-review, secret scan, CodeQL config.
7. **Rulesets:** branch (incl. **require signed commits**) → tag → push, each **Evaluate → Active**
   (required checks must already exist).
8. **Harden (post-stabilization):** SHA-pin all Actions (+ optional ruleset to enforce).

---

## Decisions (RESOLVED 2026-07-25)

1. **`main` is the default branch** (replaces `preview`); `preview`/`canary` kept as upstream mirrors.
2. **Registry = GHCR** — `ghcr.io/arustydev/plane-<service>` (per-service packages).
3. **Release orchestration = release-please** (manifest mode) from the start — **no `workflow_dispatch`
   release job, no git-cliff**. It owns the version bump, KeepAChangelog `CHANGELOG.md`, release PR,
   `vX.Y.Z` tag, and GitHub Release.
4. **Release identity = 2 personal-account GitHub Apps** (resolved 2026-07-25):
   - **`woven-release`** — release-please / tagging / Releases on the code repo(s): `contents:write`,
     `pull-requests:write`, `issues:write`; on the `main` ruleset **bypass** list.
   - **`woven-deploy`** — the infra image-tag-bump PR: `contents:write` + `pull-requests:write`, installed
     on and scoped to the **infra** repo only.
   Owned by the `aRustyDev` account (not an org) for now; private keys in Actions secrets, tokens minted
   in-workflow via `actions/create-github-app-token`. Transferable to a Woven org later if the repo moves.
5. **Require signed commits on `main` = YES** from the start (coherent with release-please App-API commits
   + GitHub-UI merges — see §G).
6. **SHA-pinned Actions = DEFERRED** until the CI/CD flow is stable (own low-priority task, §H).

---

## Beads (filed under epic `plane-7fn`, feature `F0.6` = `plane-7fn.4`)
1. `master→main` rename + default-branch + ref updates (Phase 1) — `plane-7fn.4.1`
2. Fork-fit PR CI: retarget to `main`, drop reviewer-gate, fix CODEOWNERS (Phase 1) — `plane-7fn.4.2`
3. commitlint `commit-msg` + cz-git (Phase 2) — `plane-7fn.4.3`
4. release-please config (KeepAChangelog sections) + CHANGELOG backfill (Phase 2) — `plane-7fn.4.4`
5. Release App + release-please workflow (release PR → tag + Release) (Phase 3) — `plane-7fn.4.5`
6. Release-driven `woven-build.yml` → GHCR by digest (Phase 4, extends `plane-8xx`) — `plane-7fn.4.6`
7. cosign keyless sign + SLSA provenance + SBOM + trivy (Phase 4) — `plane-7fn.4.7`
8. woven-o11y admission verify (infra) (Phase 5) — `plane-7fn.4.8`
9. Security scanning: Dependabot + dependency-review + secret scan + CodeQL config (Phase 6) — `plane-7fn.4.9`
10. GitHub rulesets: branch (signed commits) + tag + push, Evaluate→Active (Phase 7) — `plane-7fn.4.10`
11. **GitHub Apps: create `woven-release` + `woven-deploy`** (2 personal apps, resolved) — precursor to #5 — `plane-7fn.5`
12. SHA-pin all Actions (DEFERRED, post-stabilization) — `plane-7fn.4.11`
```
