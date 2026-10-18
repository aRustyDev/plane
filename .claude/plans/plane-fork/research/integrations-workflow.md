# Plane Fork — External Integrations, Webhooks, Importers, Workflow/State Recon

Read-only architecture recon. Root: `/Users/asmith/repos/woven/forks/plane`.
Backend is Django + DRF + Celery under `apps/api/plane/`. Monorepo apps: `web` (Next.js),
`admin`, `space` (public deploy boards), `live` (real-time collab), `proxy`, `api`.

Compose services (`docker-compose.yml`): `web, admin, space, api, worker, beat-worker,
migrator, live, plane-db (postgres), plane-redis, plane-mq (rabbitmq broker), plane-minio
(S3), proxy`. **No separate integrations/"silo" microservice is present in this fork.**

---

## 1. Existing integrations (git/Slack/importers)

**Verdict: DB models exist but are VESTIGIAL. There is no live first-party git/Slack/Jira
integration or importer backend in this OSS fork.** In current Plane, real integrations live
in the closed-source "silo" service, which is absent here.

Integration DB models (defined, but NOT wired to any URL/view):
- `apps/api/plane/db/models/integration/base.py` — `Integration`, `WorkspaceIntegration`
  (workspace ↔ provider ↔ bot `APIToken` link, JSON `config`/`metadata`).
- `apps/api/plane/db/models/integration/github.py` — `GithubRepository`,
  `GithubRepositorySync`, `GithubIssueSync`, `GithubCommentSync`.
- `apps/api/plane/db/models/integration/slack.py` — `SlackProjectSync`.
- `apps/api/plane/db/models/importer.py` — `Importer` (service choices: `github`, `jira`;
  status queued/processing/completed/failed; FK to `APIToken`).

Evidence they are dormant:
- Grep of `app/`, `api/`, `space/` shows the ONLY reference to these models is
  `apps/api/plane/app/serializers/importer.py` (`ImporterSerializer`). No views, no URLs.
- Frontend still ships stale integration UI/services that call **non-existent** endpoints:
  - `apps/web/core/components/integration/single-integration-card.tsx`,
    `.../integration/github/select-repository.tsx`, `.../integration/slack/select-channel.tsx`
  - `apps/web/core/services/integrations/integration.service.ts` → calls
    `/api/integrations/`, `/api/workspaces/{slug}/workspace-integrations/`,
    `/api/workspaces/{slug}/importers/`
  - `.../integrations/github.service.ts`, `jira.service.ts` → call
    `/api/workspaces/{slug}/importers/{service}/`, `.../projects/importers/{service}/`,
    `.../workspace-integrations/{slug}/github-repositories`
  None of these backend routes exist in `apps/api/plane/app/urls/`. Dead code.

The only LIVE "external" backend view is **not** git/Slack:
- `apps/api/plane/app/views/external/base.py` — LLM endpoints (`GPTIntegrationEndpoint`,
  `WorkspaceGPTIntegrationEndpoint`; OpenAI/Anthropic/Gemini) + `UnsplashEndpoint`.
  Routed at `apps/api/plane/app/urls/external.py`.

GitHub / GitLab / Gitea / Google appear ONLY as **OAuth login** providers, not issue sync:
- `apps/api/plane/authentication/provider/oauth/{github,gitlab,gitea,google}.py`.

**No GitLab or Gitea issue-integration code, no WakaTime, no AFFiNE, no Beads, no CRM/
Customers model anywhere in the API** (confirmed by grep). "customer" hits are incidental
sample-seed strings.

---

## 2. Webhooks — REAL, working outbound system (fork-hardened)

Outbound only. There is no generic inbound webhook receiver.

- Model: `apps/api/plane/db/models/webhook.py`
  - `Webhook` — workspace-scoped, per-event boolean toggles (`project`, `issue`, `module`,
    `cycle`, `issue_comment`), `secret_key` (`plane_wh_<hex>`), `is_active`, `is_internal`,
    `version` (default `v1`), URL validated against localhost/scheme (SSRF hygiene).
  - `WebhookLog` — request/response audit + `retry_count`.
  - `ProjectWebhook` — project-scoped association.
- Emission pipeline: `apps/api/plane/bgtasks/webhook_task.py`
  - `model_activity(model_name, model_id, requested_data, current_instance, ...)` — diffs
    old vs new, fires `webhook_activity` per changed field (create → single "created" event).
  - `webhook_activity(...)` — selects active workspace webhooks subscribed to the event type,
    fans out to `webhook_send_task`.
  - `webhook_send_task(...)` — POSTs HMAC-SHA256-signed JSON. Headers: `X-Plane-Event`,
    `X-Plane-Signature`, `X-Plane-Delivery`, `User-Agent: Autopilot`. Retries (max 5, backoff),
    auto-deactivates webhook + emails owner after exhaustion.
  - `SERIALIZER_MAPPER` / `MODEL_MAPPER` cover: `project, issue, cycle, module, cycle_issue,
    module_issue, issue_comment, user, intake_issue`.
- **Fork customization — SSRF hardening**: `webhook_send_task` uses `pinned_fetch` (pins the
  connection to a validated IP, no redirects) with `settings.WEBHOOK_ALLOWED_IPS` /
  `WEBHOOK_ALLOWED_HOSTS`. Helpers: `apps/api/plane/utils/url_security.py`,
  `apps/api/plane/utils/ip_address.py`. Tests: `tests/unit/bg_tasks/test_url_security.py`,
  `test_ssrf_advisories.py`.
- Trigger call sites (`model_activity.delay(...)`) — both internal and public API:
  - Internal app: `app/views/issue/base.py`, `app/views/issue/comment.py`,
    `app/views/module/base.py`, `app/views/cycle/base.py`, `app/views/project/base.py`.
  - Public REST v1: `api/views/issue.py` (multiple sites), `api/views/cycle.py`,
    `api/views/module.py`, `api/views/project.py`.
- Management API: `apps/api/plane/app/urls/webhook.py` — CRUD, regenerate secret, logs.
  Serializer `app/serializers/webhook.py`. Views `app/views/webhook/base.py`.
  Frontend: `apps/web/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/webhooks/`.

---

## 3. API surface + external-tool auth (token model)

Root routing — `apps/api/plane/urls.py`:
- `/api/` → `plane.app.urls` — internal app API (session/cookie auth; consumed by web UI).
- `/api/v1/` → `plane.api.urls` — **public REST API** (PAT auth).
- `/api/public/` → `plane.space.urls` — anonymous deploy-board / public intake.
- `/api/instances/` → `plane.license.urls`; `/auth/` → authentication.
- `drf-spectacular` OpenAPI schema available when `ENABLE_DRF_SPECTACULAR` (settings/openapi.py).

Public REST API (`apps/api/plane/api/`, mounted at `/api/v1/`):
- Resources (`api/urls/__init__.py`): `project, work_item` (issue), `cycle, module, state,
  label, member, intake, asset, sticky, user, invite`.
- Base classes: `api/views/base.py` — `BaseAPIView`, `BaseViewSet`. Support `?fields=` /
  `?expand=` selection, cursor pagination (`BasePaginator`), read-replica mixin.
- Rate limiting: `api/rate_limit.py` `ApiKeyRateThrottle` (per-token).

Token / auth model (this is the layer external tools authenticate against):
- Auth: `apps/api/plane/api/middleware/api_authentication.py` — `APIKeyAuthentication`,
  header **`X-Api-Key`**. Validates against `APIToken`, updates `last_used`.
- Model: `apps/api/plane/db/models/api.py`
  - `APIToken` — token string `plane_api_<hex>`, `label`, optional `expired_at`,
    per-token `allowed_rate_limit` (default `60/min`), `user_type` (Human/Bot),
    `is_service`, workspace-scoped (nullable). `APIActivityLog` records each request.
- PAT lifecycle (created via internal app API/UI): `apps/api/plane/app/urls/api.py` →
  `users/api-tokens/` and `users/api-tokens/<uuid:pk>/`.
- **Idempotent external-mapping fields** exist for sync: `external_source` + `external_id`
  on `State`, `IntakeIssue` (and present across many models incl. `Issue`). These are the
  hooks for round-trip sync (Beads / GitHub / GitLab / Gitea / CRM) without duplicate rows.

---

## 4. Workflow / state model + automation (from the automation angle)

State model — `apps/api/plane/db/models/state.py`:
- Free-form `State` rows grouped into FIXED groups (`StateGroup`: backlog, unstarted,
  started, completed, cancelled, triage). Fields: `sequence`, `default`, `color`,
  `external_source`/`external_id`.
- **No transition rules / guards / approvals.** Any state can move to any state; nothing
  constrains transitions. No "multiple workflows" concept. These are EE/Pro (silo) features.
- `"workflow"/"workflows"` in `apps/api/plane/utils/constants.py` are merely **reserved
  slugs**; `settings/openapi.py` mentions are doc prose only. No engine.

Automation that DOES exist (the only one):
- `apps/api/plane/bgtasks/issue_automation_task.py` — Celery-beat
  `archive_and_close_old_issues`:
  - `archive_old_issues()` — archives completed/cancelled issues older than
    `project.archive_in` months.
  - `close_old_issues()` — moves stale backlog/unstarted/started issues older than
    `project.close_in` months into `project.default_state`.
  - Purely project-setting driven; **not** a trigger/condition/action rules engine.
- Activity + notification fan-out: `apps/api/plane/bgtasks/issue_activities_task.py`
  (`issue_activity`) logs every field change and drives notifications + webhooks. **This is
  the natural attach point for any rules/automation/state-transition engine.**

Where new workflow features attach:
- "Workflow State-Transition Control", "Multiple Workflows", "Workflow Approvals" would be
  new models keyed to `State` + `Project` (e.g. allowed-transition matrix, approval gates),
  enforced in the issue **state-change path** — the DRF serializer/view before-save in
  `api/views/issue.py` and `app/views/issue/base.py`, tied into the `issue_activity` pipeline.

---

## 5. Intake / email-to-issue / form intake

- Models: `apps/api/plane/db/models/intake.py` — `Intake`, `IntakeIssue`.
  - `IntakeIssue` fields: `status` (pending/rejected/snoozed/accepted/duplicate),
    `source` (default `IN_APP`), **`source_email`**, `external_source`, `external_id`,
    `extra` (JSON), `duplicate_to`.
  - `SourceType` enum in OSS has **only `IN_APP`** — the email-intake fields are scaffolded
    but there is **no inbound-email ingestion worker** in this fork (`source_email` is only
    read-side in serializers/activity; never populated by an ingestion pipeline). Email
    intake is an EE/silo feature.
- In-app triage view: `apps/api/plane/app/views/intake/base.py` (large; the triage inbox).
- Public REST intake: `api/views/intake.py` + `api/urls/intake.py`; serializer
  `api/serializers/intake.py` (exposes `source`, `external_source`, `external_id`).
- **Anonymous web-form intake** (published boards): `space/views/intake.py`
  (`IntakeIssuePublicViewSet`) + `space/urls/intake.py`:
  `/api/public/anchor/<anchor>/intakes/<intake_id>/intake-issues/` (GET list / POST create,
  AllowAny). This is the closest thing to form-intake scaffolding today.

---

## 6. Insertion points for the planned targets

General pattern: add a new Django app under `apps/api/plane/` (e.g.
`plane/integrations/<provider>/`), compose it into `plane/urls.py` (e.g.
`path("api/integrations/", include(...))`), reuse `WorkspaceIntegration` + `APIToken`
(bot tokens), EMIT via the existing webhook fan-out, and INGEST via new inbound receivers
that feed `issue_activity` / `model_activity`. Use `external_source`/`external_id` for
idempotent mapping. Frontend: revive/extend `apps/web/core/components/integration/*` and
`apps/web/core/services/integrations/*`.

- **Slack (2-way)**: Outbound is already achievable via webhook subscriptions. For true
  2-way, add inbound receiver + slash-command/event endpoints (new app). Dormant
  `SlackProjectSync` / `WorkspaceIntegration` models can be revived. Frontend stub exists
  (`components/integration/slack/select-channel.tsx`).
- **Beads sync**: Cleanest via the public REST API `/api/v1/` + PAT (`X-Api-Key`). Plane→Beads
  direction via a subscribed `Webhook`; Beads→Plane via a poller/worker calling `/api/v1/`.
  Key on `Issue.external_source="beads"` + `external_id`.
- **GitHub / GitLab / Gitea sync**: OAuth login already present (reuse
  `authentication/provider/oauth/*` + `social_connection`). Build sync as a new app; the
  dormant `GithubRepositorySync` / `GithubIssueSync` / `GithubCommentSync` models can be
  revived or generalized across the three forges. Emit via webhooks; ingest via new inbound
  webhook receiver feeding `issue_activity`.
- **WakaTime / WakaAPI (time tracking)**: No time-tracking model exists. Add a new model
  linked to `Issue`/`Project`, an ingestion endpoint/worker (WakaAPI heartbeats), and store
  `external_source`/`external_id`.
- **AFFiNE (wiki)**: Plane has its own `Page` model (`db/models/page.py`) + `apps/live`
  (real-time collab, Hocuspocus/Yjs). AFFiNE integration = a new bridge app syncing `Page`
  ↔ AFFiNE docs; consider the `live` service for real-time.
- **CRM (Customers)**: No customer model in OSS (EE has "Customers"). Add a new app
  `plane/db/models/customer.py` + REST views under `/api/v1/`, linkable to `Issue`/`Project`.

---

## Key file index

| Concern | Path |
|---|---|
| Root URL routing | `apps/api/plane/urls.py` |
| Public REST API (v1) urls | `apps/api/plane/api/urls/` |
| Public REST base views | `apps/api/plane/api/views/base.py` |
| PAT auth middleware | `apps/api/plane/api/middleware/api_authentication.py` |
| APIToken model | `apps/api/plane/db/models/api.py` |
| Webhook model | `apps/api/plane/db/models/webhook.py` |
| Webhook emission/tasks | `apps/api/plane/bgtasks/webhook_task.py` |
| Webhook SSRF guard | `apps/api/plane/utils/url_security.py`, `utils/ip_address.py` |
| Webhook mgmt urls | `apps/api/plane/app/urls/webhook.py` |
| Integration models (dormant) | `apps/api/plane/db/models/integration/{base,github,slack}.py` |
| Importer model (dormant) | `apps/api/plane/db/models/importer.py` |
| LLM/Unsplash "external" views | `apps/api/plane/app/views/external/base.py` |
| OAuth login providers | `apps/api/plane/authentication/provider/oauth/{github,gitlab,gitea,google}.py` |
| State model | `apps/api/plane/db/models/state.py` |
| Automation (archive/close) | `apps/api/plane/bgtasks/issue_automation_task.py` |
| Activity/notification pipeline | `apps/api/plane/bgtasks/issue_activities_task.py` |
| Intake models | `apps/api/plane/db/models/intake.py` |
| In-app intake triage | `apps/api/plane/app/views/intake/base.py` |
| Anonymous form intake | `apps/api/plane/space/views/intake.py`, `space/urls/intake.py` |
| Frontend integration UI (stale) | `apps/web/core/components/integration/`, `apps/web/core/services/integrations/` |
