# F0.5 — Fork CI + custom image build

**Goal:** CI that builds `plane-*` images from *this fork* and wires them to the infra repo's
`products/plane/kube` deploy, so `projects.woven` runs our images instead of Docker Hub `makeplane/*`.

**Parity target:** N/A — delivery pipeline for the fork.

**Background (today).** The fork inherits upstream CI in `.github/workflows/`: **`build-branch.yml`**
("Branch Build CE") builds six images with buildx on push to `preview`/`canary`, emitting
`dh_img_{web,space,admin,live,backend,proxy,aio}` to Docker Hub `makeplane/*` (verified). Dockerfiles:
`apps/web/Dockerfile.web`, `apps/admin/Dockerfile.admin`, `apps/live/Dockerfile.live`,
`apps/api/Dockerfile.api`, `apps/space/Dockerfile.space`, `apps/proxy/Dockerfile.ce`. Plus
`pull-request-build-lint-{api,web-apps}.yml`, `feature-deployment.yml`, `codeql.yml`,
`copyright-check.yml`. Root version `1.3.1`.
Infra deploy (`products/plane/kube`, infra repo): `helm_release.plane` uses the **upstream chart**
`plane-ce` from `https://helm.plane.so/` (`var.plane_chart_version = 1.6.0`), pins
`planeVersion = var.plane_version` (`v1.3.1`), and adds a local `charts/plane-proxy` (org-CA TLS).
Service images are pulled from Docker Hub `makeplane/plane-*`. PoC proxy/TLS/ESO plumbing is done.

**Approach.** *Build:* add a fork workflow **`woven-build.yml`** (adapted from `build-branch.yml`, not
replacing it) that builds the six images from this fork's Dockerfiles and pushes to a **Woven registry**
(GHCR `ghcr.io/arustydev/plane-*` or ECR), tagged with the git SHA plus a deliberate semver
`v1.3.1-woven.<n>`; `linux/amd64` (arm64 optional). Reuse the existing buildx setup/matrix jobs; keep
`copyright-check` + lint gating PRs. *Wire to deploy:* the `plane-ce` chart supports per-service image
overrides — point each service's image `repository`/`tag` at the Woven registry + fork tag while
keeping `planeVersion` for asset pathing. Preferred (GitOps): parameterize
`products/plane/kube/variables.tf` with `plane_image_registry` + `plane_image_tag` threaded into
`helm_release.plane` values; the fork publishes an immutable tag and infra bumps the pin deliberately
(matches D-BASE "merge upstream deliberately"). Registry pull creds via the existing ESO plumbing.

**Feature flag.** N/A. Rollout is gated by the infra `plane_image_tag` var (pin / rollback).

**Tasks.** 1) `woven-build.yml` — buildx six images → Woven registry, SHA + semver tags; 2) provision
registry + pull creds (ESO); 3) add `plane_image_registry`/`plane_image_tag` vars and thread into
`helm_release.plane` values (infra); 4) confirm the chart's per-service image-override keys; 5)
smoke-deploy to woven-o11y, verify pods pull fork images; 6) document the tag/rollback runbook.

**Acceptance.** *CI:* push to fork `main` builds + pushes six `plane-*` images with matching immutable
tags; PR builds are lint-gated. *Deploy:* bumping `plane_image_tag` + `tofu apply` rolls the cluster to
fork images; `kubectl get pods` shows the Woven registry ref and the app is healthy at `projects.woven`;
rollback = re-pin the previous tag.

**Risks / upstream-merge impact.** Low code-merge impact (CI-only, additive `woven-build.yml`). Risks:
chart image-override key drift across `plane-ce` chart versions; registry cost/auth; keeping
`planeVersion` and the image tag in sync. Keep divergence from upstream `build-branch.yml` minimal —
fork only the registry/env vars.
