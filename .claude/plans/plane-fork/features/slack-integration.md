# Slack Integration (2-way)

**Goal:** Two-way Slack: outbound notifications on work-item/comment changes, and inbound
actions (create/update work items, comment) from Slack via a Slack app — slash commands, event
subscriptions, and interactive messages.

**Parity target:** Plane **Pro** Slack integration.

**Background (grounded):** `db/models/integration/slack.py` defines `SlackProjectSync`
(`access_token`, `scopes`, `bot_user_id`, `webhook_url`, `team_id`, FK to `WorkspaceIntegration`)
— a **vestigial stub with no view/URL** (recon §1). `WorkspaceIntegration`/`Integration`
(`integration/base.py`) provide the workspace↔provider↔bot-`APIToken` link and JSON
`config`/`metadata`. Frontend stub exists but calls dead routes:
`apps/web/core/components/integration/slack/select-channel.tsx`,
`apps/web/core/services/integrations/*`. Outbound spine is real: webhooks
(`bgtasks/webhook_task.py`, events incl. `issue`, `issue_comment`) and the `issue_activity`
pipeline. No inbound receiver exists anywhere.

**Approach:**
- *Models/migrations:* revive `SlackProjectSync`; add `SlackUserLink` (Slack user ↔ Plane user
  for authored actions) and store bot creds via `WorkspaceIntegration.config` (secret material
  via ESO, not plaintext). Additive migration, `deleted_at` + partial-unique.
- *Outbound:* an internal `Webhook` (`is_internal=True`) subscribed to `issue`/`issue_comment`,
  delivered to a new formatter that renders Slack Block Kit and POSTs to the channel — riding
  the existing SSRF-hardened `webhook_send_task`.
- *Inbound (new app `plane/integrations/slack/`):* OAuth install (reuse
  `authentication/provider/oauth` HTTP patterns) → persists `WorkspaceIntegration` + bot
  `APIToken`. Endpoints: `/api/integrations/slack/events`, `/commands`, `/interactive`
  (Slack-signature-verified). Handlers create/update `Issue` + `IssueComment` as the linked
  Plane user, going through **`Issue.save()`** (single-row) and feeding
  `issue_activity`/`model_activity`. Compose into `plane/urls.py`.
- *Frontend:* revive `integration/slack/*` against the new routes — install button, channel/
  project mapping.

**Feature flag:** `slack_integration` (Phase-0 F0.1); per-workspace enable via
`WorkspaceIntegration`.

**Tasks (→ child beads):** 1) Revive/extend Slack models + migration. 2) OAuth install flow +
bot token. 3) Signature-verified events/commands/interactive receiver. 4) Inbound→`Issue`/
comment handlers via `issue_activity`. 5) Block Kit outbound formatter on internal webhook. 6)
Revive frontend UI + channel mapping. 7) Acceptance tests.

**Acceptance:** *API* — a state change posts a Block Kit message to the mapped channel; a
`/plane` slash command with a valid signature creates a work item attributed to the linked user;
invalid signature → 401. *UI* — install completes, channel↔project mapping persists, test message
sends.

**Risks / upstream-merge impact:** Moderate. New app + additive models; core untouched except a
webhook formatter hook (`# woven:`). Must verify Slack signing secret + timestamp (replay). Bot
tokens are secrets → ESO. Inbound writes must not bypass `Issue.save()` (no bulk ops).
