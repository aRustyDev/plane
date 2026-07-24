# External Sync (Beads, GitHub, GitLab, Gitea)

**Goal:** Bi-directional work-item sync with Beads and the three git forges (GitHub, GitLab,
Gitea): Plane changes propagate outward; external changes flow back into Plane — idempotently,
without duplicate rows.

**Parity target:** Plane **Pro** git integrations + Woven-specific Beads sync.

**Background (grounded):** Integrations here are **vestigial** — `GithubRepository`,
`GithubRepositorySync`, `GithubIssueSync`, `GithubCommentSync`
(`db/models/integration/github.py`), `SlackProjectSync`, and `Importer`
(`db/models/importer.py`, services `github`/`jira`) are defined but **have no views/URLs**
(recon §1). GitHub/GitLab/Gitea exist as **OAuth login** providers only
(`authentication/provider/oauth/{github,gitlab,gitea}.py`) — no issue sync. Reusable spines:
outbound webhooks (`bgtasks/webhook_task.py`), `/api/v1/` PAT (`X-Api-Key`), and
`external_source`/`external_id` on `Issue`/`State`/etc. for idempotent mapping.
**Beads** has no code — cleanest via `/api/v1/` + PAT.

**⚠ CRITICAL — replicate `Issue.save()`:** inbound sync must **not** use `bulk_create`/
`bulk_update`. `Issue.save()` (`db/models/issue.py`) takes a per-project `pg_advisory_xact_lock`,
computes `sequence_id`/`sort_order`, strips HTML, assigns default state, and syncs `completed_at`
via `ChangeTrackerMixin` (`TRACKED_FIELDS=["state_id"]`); bulk ops bypass all of it (explicit
`# TODO: Handle identifiers for Bulk Inserts`). Sync writes single-row through `.save()` and feed
`issue_activity`, or a dedicated importer must re-implement sequence/state/lock logic exactly.

**Approach:**
- *Models/migrations (new app `plane/integrations/sync/`):* generalize the dormant
  `*IssueSync`/`*CommentSync` into forge-agnostic `RepoLink`, `IssueSyncMap`(Plane issue ↔
  external repo+number, keyed on `external_source`+`external_id`), `SyncCursor`. Reuse
  `WorkspaceIntegration` + bot `APIToken`. Additive, `deleted_at` + partial-unique.
- *Outbound:* subscribed internal `Webhook` → per-forge adapter (create/update issue+comment via
  forge REST), recording `IssueSyncMap`.
- *Inbound:* per-forge webhook receivers (signature-verified) → upsert `Issue`/`IssueComment` by
  `external_id`, through `Issue.save()` + `issue_activity`. **Beads→Plane**: a poller/worker
  calling `/api/v1/` with a PAT, keyed on `Issue.external_source="beads"`+`external_id`;
  **Plane→Beads** via a subscribed `Webhook`.
- *Frontend:* revive `integration/github/select-repository.tsx`; add repo/project mapping +
  sync-status UI.

**Feature flag:** `external_sync` (Phase-0 F0.1); per-provider via `WorkspaceIntegration`.

**Tasks (→ child beads):** 1) Generalized sync models + migration. 2) OAuth app-token flow per
forge. 3) Outbound adapters on internal webhook. 4) Inbound receivers → `Issue.save()` +
`issue_activity`. 5) Beads poller (`/api/v1/`) both directions. 6) Loop-prevention + mapping UI.
7) Acceptance tests (round-trip idempotency).

**Acceptance:** *API* — create in Plane → appears in forge; edit in forge → reflected in Plane
with no duplicate (`IssueSyncMap` matched); replayed webhook is a no-op; Beads round-trip keyed
on `external_id`. *UI* — repo↔project mapping persists; per-item sync status shows.

**Risks / upstream-merge impact:** High. Largest surface; new app but touches the write path.
Chief risks: **echo loops** (suppress activity originated by the bot user/token), bulk-bypass
correctness, per-forge webhook signatures, secret handling (ESO). Depends on Custom Fields
(WICF) for full field mapping per the PROGRAM dependency graph.
