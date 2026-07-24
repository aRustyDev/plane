# F0.3 — Internal event/outbox backbone

**Goal:** A reliable internal event stream (issue/page/member changed) that Audit, Slack, Intake,
external Sync, and Recurring items all consume — reusing the existing outbound webhook pipeline and the
`issue_activity` fan-out rather than inventing plumbing.

**Parity target:** Foundation enabling Audit (Enterprise), Slack (Pro), Intake (Business), External
sync (Pro+Woven), Recurring (Business).

**Background (today).** A real, fork-hardened **outbound webhook** system exists
(`research/integrations-workflow.md` §2): `Webhook`/`WebhookLog`/`ProjectWebhook`
(`apps/api/plane/db/models/webhook.py`; per-event toggles, HMAC-SHA256 signing, an `is_internal` flag,
SSRF-safe `pinned_fetch`). Emission is `apps/api/plane/bgtasks/webhook_task.py`: `model_activity()`
diffs old/new → `webhook_activity()` selects subscribed workspace webhooks → `webhook_send_task()`
(retries, backoff, auto-deactivate). `SERIALIZER_MAPPER`/`MODEL_MAPPER` cover
project/issue/cycle/module/`*_issue`/`issue_comment`/user/`intake_issue`. Trigger sites
(`model_activity.delay(...)`) live in `app/views/{issue,module,cycle,project}/base.py` and
`api/views/*`. The activity+notification pipeline `apps/api/plane/bgtasks/issue_activities_task.py`
(`issue_activity`) logs every field change and is the documented attach point (§4). Broker is RabbitMQ
(`plane-mq`) + Celery. Idempotency hooks: `external_source`/`external_id` on Issue/State/IntakeIssue.
There is **no internal subscriber bus and no inbound receiver**.

**Approach.** Add a thin **outbox** table `EventOutbox(workspace, event_type, entity_type, entity_id,
payload JSON, occurred_at, dispatched_at, external_source/external_id)` with soft-delete +
partial-unique per the gotchas. Emit rows from the **same choke points that already call
`model_activity.delay()`** and from `issue_activity`, via one helper `emit_event(event_type, entity,
payload)` placed beside the existing webhook emission — so no new instrumentation beyond what webhooks
already touch. A Celery dispatcher (`bgtasks/event_dispatch_task.py`) drains the outbox and invokes
**in-process subscribers** registered in the `woven` app (`@subscribe("issue.updated")`): Audit writes
`AuditLog`, Slack/Sync enqueue their own delivery tasks, Recurring reads its schedule. Reuse
`webhook_send_task`'s HMAC + `pinned_fetch` + retry/backoff for any HTTP-outbound subscriber; bridge to
external consumers via internal webhooks (`is_internal=True`). No API/frontend surface of its own —
consumers expose theirs.

**Feature flag.** `WOVEN_FEATURE_EVENT_BUS` (master); per-consumer flags gate individual subscribers.
OFF → outbox not written; webhook behavior unchanged.

**Tasks.** 1) `EventOutbox` model + migration; 2) `emit_event` helper wired at existing
`model_activity`/`issue_activity` sites; 3) subscriber registry + dispatcher task; 4) at-least-once +
idempotent dedupe (delivery id / `external_id`); 5) reuse webhook send/retry for HTTP subscribers;
6) metrics + dead-letter for undispatched rows.

**Acceptance.** *API:* mutating an issue writes exactly one `EventOutbox` row; the dispatcher stamps
`dispatched_at`; a test subscriber receives it exactly once (retry-safe). Webhooks behave identically
when the bus is OFF. Failure path retries then dead-letters without blocking the request.

**Risks / upstream-merge impact.** Low-medium. New table + bgtask + app are additive; the only core
touch is `emit_event(...)` beside existing `model_activity.delay(...)` calls (small, `# woven:`-marked,
same files webhooks already edit). **Bulk ops bypass `Issue.save()`** — sync/import paths must call
`emit_event` explicitly (documented gotcha).
