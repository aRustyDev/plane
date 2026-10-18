# Audit Logging (API + UI)

**Goal:** An instance- and workspace-wide **audit log** capturing logins, role changes, member
add/remove, config/admin changes, and other security-relevant mutations — queryable via API and
visible in admin/workspace settings.

**Parity target:** Plane Commercial **Enterprise** (audit logs).

**Background** (cite exact files/models): Only **two** logs exist today
(`research/auth-permissions.md §5`): `IssueActivity` (`db/models/issue.py:415`, table
`issue_activities`) — rich but **issue-scoped only**, populated by
`bgtasks/issue_activities_task.py`; and `APIActivityLog` (`db/models/api.py:51`) — external-API
request log via `middleware/logger.py`. There is **no workspace/instance-wide audit** of admin
actions, logins, role changes, or config edits: `InstanceConfiguration` PATCH
(`license/api/views/configuration.py`), `InstanceAdmin` CRUD, and the auth events in
`Adapter.complete_login_or_signup()` are **not audited**. `IssueActivity` is a schema template,
not reusable as-is.

**Approach:**
- *Backend models + migrations (additive):* new `AuditLog(BaseModel)` — `actor` (User, SET_NULL),
  `workspace` (nullable → instance-level), `action` (enum: `login`, `member.role_changed`,
  `member.removed`, `config.changed`, `admin.added`, …), `target_type`, `target_id`,
  `metadata` (JSONField: old/new values), `ip`, `user_agent`, `epoch`. Append-only; soft-delete
  columns present for convention but never deleted. Index `(workspace, action, created_at)`.
- *Emit points (F0.3 event backbone):* consume the internal event/outbox stream so emit is
  centralized, not scattered across the ~38 mutating views. Add explicit emits at: auth pipeline
  (`adapter/base.py` login/signup/deactivate), workspace/project member views
  (`app/views/workspace/member.py` role transitions, `member.py:88-89`), and instance config /
  admin views (`license/api/views/{configuration,admin}.py`).
- *API:* read-only `/api/workspaces/<slug>/audit-logs/` (admin-only, filter by action/actor/date)
  + instance-level `/api/instances/audit-logs/`. *Frontend:* workspace-settings + admin "Audit
  log" table (filters, actor, timestamp, diff view).

**Feature flag:** `AUDIT_LOGGING_ENABLED` (F0.1); emits are no-ops when off.

**Tasks (→ child beads):** (1) `AuditLog` model + migration + async writer task (mirror
`issue_activities_task`); (2) F0.3 event consumer + emit points (auth/member/config/admin);
(3) workspace + instance read API; (4) admin/settings UI table + filters.

**Acceptance:** *API* — change a member's role → one `member.role_changed` row with old/new in
`metadata`; PATCH instance config → `config.changed` row; login → `login` row. *UI* — audit table
filters by actor/action/date and renders the diff.

**Risks / upstream-merge impact:** Depends on **F0.3** event backbone (reuse the SSRF-hardened
webhook/`issue_activity` pipeline rather than inventing plumbing). Emit points touch shared
auth/member/config views — keep them one-line calls, `# woven:` marked. High write volume: write
async, never block requests. Do not log secret values (respect `is_encrypted` config keys).
