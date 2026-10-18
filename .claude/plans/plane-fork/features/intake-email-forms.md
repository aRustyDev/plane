# Intake Email / Forms

**Goal:** Complete email-to-issue intake: an inbound-email worker that turns messages into
`IntakeIssue` triage rows (with `source_email` populated), plus hardened public form intake.

**Parity target:** Plane **Business** Intake (email + forms). Public form intake already works;
email is the gap.

**Background (grounded):** Models exist and are mostly wired —
`apps/api/plane/db/models/intake.py`: `Intake(ProjectBaseModel)` and
`IntakeIssue(ProjectBaseModel)` with `status`, `source` (default `IN_APP`), **`source_email`**,
`external_source`/`external_id`, `extra` (JSON), `duplicate_to`. **But `SourceType` enum has
only `IN_APP`** (`intake.py:38`), and `source_email` is read-only — never populated by an
ingestion pipeline (recon §5). In-app triage inbox: `app/views/intake/base.py` (creates with
`source=SourceType.IN_APP`, line 277). Anonymous **form** intake already lives at
`space/views/intake.py` → `/api/public/anchor/<anchor>/intakes/<intake_id>/intake-issues/`
(AllowAny GET/POST). Public REST intake: `api/views/intake.py`, `api/urls/intake.py`. The
activity/notification spine is `bgtasks/issue_activities_task.py`; `intake_issue` is already in
the webhook `SERIALIZER_MAPPER` (`bgtasks/webhook_task.py`).

**Approach:**
- *Models/migrations:* add `EMAIL` (and `FORM`) to `SourceType` (data migration, no schema
  change to existing rows). Optional `IntakeEmailConfig(ProjectBaseModel)` → per-intake inbound
  address/alias + allow-list + spam settings; `deleted_at` + partial-unique.
- *Inbound worker (new):* an ingestion path that accepts mail — either an SES→SNS/S3 webhook
  receiver (Woven runs SES) or an IMAP-poll Celery task. Parse sender/subject/body, resolve the
  target `Intake` by alias, create `Issue` + `IntakeIssue(source="EMAIL", source_email=<from>,
  external_source="email", external_id=<message-id>)`. **Reuse `Issue.save()`** (single-row
  create, not bulk) so `sequence_id`/state/advisory-lock all fire. Feed
  `issue_activity`/`model_activity` so notifications + `intake_issue` webhooks emit.
- *Frontend:* surface `source`/`source_email` in the existing triage inbox; settings to
  configure the inbound alias.

**Feature flag:** `intake_email` (Phase-0 F0.1). Form intake stays always-on.

**Tasks (→ child beads):** 1) Extend `SourceType` + `IntakeEmailConfig` migration. 2) SES/IMAP
inbound receiver. 3) Parse→`Issue`+`IntakeIssue` mapper (idempotent on message-id). 4) Wire
`issue_activity` + webhook emission. 5) Triage-inbox source display + alias settings. 6) Spam/
attachment handling. 7) Acceptance tests.

**Acceptance:** *API* — posting a raw email to the receiver creates exactly one `IntakeIssue`
with `source="EMAIL"`, `source_email` set; replaying the same message-id creates none. *UI* —
email-sourced items appear in triage with sender; accept promotes to a real work item.

**Risks / upstream-merge impact:** Low-moderate. `SourceType` edit is a 1-line core change
(`# woven:`), well isolated. SSRF/abuse surface on the receiver → auth the SES webhook, verify
SNS signatures, allow-list senders. Attachment ingestion reuses `IssueAttachment`/MinIO.
