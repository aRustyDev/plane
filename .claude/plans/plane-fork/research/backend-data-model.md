# Plane Fork — Backend Data Model & Schema Recon

Read-only architecture recon of the Django/Python backend under `apps/api`. This is the
**Community Edition (CE)** codebase — there is **no `ee/`/enterprise backend app** (only
`packages/editor/src/ee` on the frontend). Several "Pro/EE" features exist as *schema stubs*
with no management API in this fork.

All model files referenced live in:
`/Users/asmith/repos/woven/forks/plane/apps/api/plane/db/models/`

---

## 1. Core models & relationships

| Model | File | Base class | Scope | Key relationships |
|-------|------|-----------|-------|-------------------|
| `Workspace` | `workspace.py` | `BaseModel` | tenant root | `owner` → User; `slug` unique |
| `Project` | `project.py` | `BaseModel` | workspace | `workspace` FK; `default_state`, `estimate`, `default_assignee`, `project_lead` |
| `Issue` (the work item) | `issue.py` | `ChangeTrackerMixin` + `ProjectBaseModel` | project | `state`, `type`(IssueType), `parent`(self), `estimate_point`; M2M `assignees`, `labels` |
| `Cycle` | `cycle.py` | `ProjectBaseModel` | project | issues via `CycleIssue` (through) |
| `Module` | `module.py` | `ProjectBaseModel` | project | issues via `ModuleIssue`; members via `ModuleMember`; `status` enum |
| `Page` | `page.py` | `BaseModel` | workspace | `workspace` FK; M2M `projects` via `ProjectPage`; `is_global`; labels via `PageLabel` |
| `State` | `state.py` | `ProjectBaseModel` | project | `group` = `StateGroup` enum |
| `Label` | `label.py` | `WorkspaceBaseModel` | workspace *or* project | `parent`(self); project **nullable** |
| `IssueType` | `issue_type.py` | `BaseModel` | workspace | + `ProjectIssueType` join; `is_epic`, `is_default` |

### Base-class hierarchy (`db/models/base.py`, `db/mixins.py`)

```
AuditModel = TimeAuditModel(created_at, updated_at)
           + UserAuditModel(created_by, updated_by)   # SET_NULL FKs to User
           + SoftDeleteModel(deleted_at)              # objects / all_objects managers
BaseModel(AuditModel)            -> UUID pk (uuid4), auto-sets created_by/updated_by via crum
ProjectBaseModel(BaseModel)      -> project FK (NOT NULL) + workspace FK; workspace auto = project.workspace
WorkspaceBaseModel(BaseModel)    -> workspace FK + project FK (NULLABLE)
```

**Scoping gotcha:** work items, states, cycles, modules are **project-scoped**
(`ProjectBaseModel`). Labels, Pages, IssueTypes are **workspace-scoped** (`WorkspaceBaseModel`
with nullable project, or plain `BaseModel` + workspace FK). Any new custom-property model must
deliberately choose the right base.

Model registry / exports: `apps/api/plane/db/models/__init__.py`.

---

## 2. The Issue (work item) in detail — `issue.py:104` (`class Issue`)

**Direct fields:** `name` (CharField 255), `description_json/html/stripped/binary`,
`priority` (choices urgent/high/medium/low/none), `point` (0–12), `start_date`, `target_date`,
`sequence_id` (per-project running int), `sort_order` (float), `completed_at`, `archived_at`,
`is_draft`, `external_source`/`external_id` (import provenance).

**FKs:** `parent` (self, sub-issues), `state` → `db.State` (CASCADE, nullable),
`estimate_point` → `db.EstimatePoint` (SET_NULL), `type` → `db.IssueType` (SET_NULL, nullable),
plus `project` + `workspace` (inherited).

**M2M (through models):** `assignees` via `IssueAssignee`, `labels` via `IssueLabel`.
Cycle/Module membership is *not* on Issue — it lives in `CycleIssue` / `ModuleIssue`.

**Satellite models in `issue.py`:** `IssueBlocker`, `IssueRelation` (typed:
duplicate/relates_to/blocked_by/start_before/finish_before/implemented_by, with bidirectional
reverse mapping), `IssueMention`, `IssueLink`, `IssueAttachment`, `IssueActivity` (audit trail:
verb/field/old_value/new_value), `IssueComment`, `IssueSequence`, `IssueSubscriber`,
`IssueReaction`, `CommentReaction`, `IssueVote`, `IssueVersion`, `IssueDescriptionVersion`.

### How state/status works
- No standalone "status" field. Status = the `state` FK, whose `group` is a `StateGroup`
  (`backlog|unstarted|started|completed|cancelled|triage`).
- `Issue.save()` calls `_ensure_default_state()` (picks project default/non-triage state when
  none set) and `_sync_completed_at()` (sets/clears `completed_at` when the state's group is
  `completed`). Change detection uses `ChangeTrackerMixin` with `TRACKED_FIELDS = ["state_id"]`.
- `IssueManager` (`Issue.issue_objects`) **excludes** triage, archived, archived-project, and
  draft issues. The plain `Issue.objects` manager returns everything.

### Extensibility of Issue
- **Adding scalar/FK fields:** straightforward Django migration.
- **Arbitrary custom properties:** *not modeled.* `Issue` has no generic JSON bag beyond
  `description_json`. `IssueVersion.properties = JSONField(default=dict)` exists but is written
  as `{}` (see `IssueVersion.log_issue_version`, `issue.py:771`) — reserved/unused, a hint of
  where EE custom properties would serialize.
- Work-item typing is via the `type` FK (see §4).

---

## 3. Migration strategy

- **Locations:** `apps/api/plane/db/migrations/` (main `db` app, `0001_initial` →
  `0121_alter_estimate_type`, **122 files**) and `apps/api/plane/license/migrations/`
  (separate `license` app).
- **Naming:** standard Django auto-generated (`makemigrations`) names, e.g.
  `0116_workspacemember_explored_features_and_more.py`, interspersed with hand-named data
  migrations, e.g. `0107_migrate_filters_to_rich_filters.py`,
  `0074_deploy_board_and_project_issues.py`. Data migrations use `RunPython`.
- **Generated via** `python manage.py makemigrations` — no custom migration framework.
- `IssueType`/`ProjectIssueType` schema was introduced in **`0070_...`**.
- **Convention to preserve:** soft-delete partial unique constraints (see §5) are declared in
  every migration alongside `unique_together`. New tables must add both.

---

## 4. Extension points for planned features

### Work Item Types — **partial schema stub, EE-gated, no CE management API**
- `IssueType(BaseModel)` (`issue_type.py:14`): `workspace` FK, `name`, `description`,
  `logo_props`, `is_epic` (bool — Epics are just an IssueType), `is_default`, `is_active`,
  `level` (float). `ProjectIssueType(ProjectBaseModel)` (`issue_type.py:35`) is the
  per-project enablement join with its own `level`/`is_default`.
- `Issue.type` and `DraftIssue.type` FKs exist. `Project.is_issue_type_enabled` boolean flag.
- Wired **only** into the external REST serializers (`plane/api/serializers/issue.py:66,159`)
  which fall back to `IssueType.objects.filter(project_issue_types__project_id=..., is_default=True)`.
- **No `IssueType` viewset, no URL route, and NO code anywhere creates an IssueType or
  ProjectIssueType** (`grep IssueType.objects.create` → none). So in CE it is a dormant stub:
  reading works, nothing populates it. Full type management is an absent EE layer.

### Work Item Custom Properties/Fields — **absent, no scaffolding**
- No `IssueProperty`(custom-field-def), no `PropertyValue`, no per-type attribute tables.
- **Naming red herring:** the historical `IssueProperty` model (migration
  `0071_rename_issueproperty_issueuserproperty_and_more.py`) was **per-user display
  preferences**, renamed to `IssueUserProperty`, and later **deleted** in
  `0114_projectuserproperty_delete_issueuserproperty_and_more.py`. Today the only "property"
  models (`ProjectUserProperty`, `CycleUserProperties`, `ModuleUserProperties`,
  `WorkspaceUserProperties`) are all **UI filter/display prefs**, not custom fields.
- Implementers would build this from scratch (likely `IssuePropertyDefinition` keyed to
  `IssueType` + `IssuePropertyValue` keyed to `Issue`), plus serializers/views/migrations.

### Workflow / State-Transition control — **absent, transitions are free-form**
- No allowed-transition table, no guard logic. `StateViewSet`
  (`plane/app/views/state/base.py`) is plain CRUD; issue update accepts any `state` in the
  project. The only server-side "rules" are: `completed_at` auto-sync on `completed` group,
  default-state assignment, and triage exclusion in the default manager.
- A workflow feature would need a new `WorkflowTransition`(from_state, to_state, roles…) model
  and enforcement hooked into `Issue.save()`/the issue update view.

### Recurring Work Items — **absent** (no model, no scheduler task).

### Templates (work-item / project / page) — **absent as first-class models.**
- Closest analog: `DraftIssue` + `DraftIssueAssignee/Label/Module/Cycle` (`draft.py`) — a
  persisted, not-yet-created issue (mirrors most `Issue` fields incl. `type`). It is a *draft*,
  not a reusable template. No `ProjectTemplate`/`PageTemplate`/`IssueTemplate` exist.

---

## 5. State/workflow model today

- `State(ProjectBaseModel)` (`state.py:79`): `name`, `color`, `slug`, `sequence` (float,
  auto-incremented by +15000 on create), `group` (`StateGroup`), `is_triage`, `default`.
- `StateGroup` enum + `DEFAULT_STATES` seed list (`state.py:14`, `:24`): Backlog, Todo,
  In Progress, Done, Cancelled, Triage.
- Managers: `State.objects` (excludes triage), `all_state_objects` (everything),
  `triage_objects` (triage only). Mirrors the Issue manager split.
- **Transition enforcement = none.** Any authorized user can move an issue to any project
  state. "Workflow" today is purely the group taxonomy + `completed_at` bookkeeping + the
  default/triage filtering. There is no transition graph to migrate/extend — it must be added.

---

## Top gotchas for implementers

1. **`Issue.save()` is heavy and bypassed by bulk ops.** It takes a per-project
   `pg_advisory_xact_lock`, computes `sequence_id` and `sort_order`, strips HTML, assigns a
   default state, and syncs `completed_at` via `ChangeTrackerMixin` (`TRACKED_FIELDS =
   ["state_id"]`). `bulk_create`/`bulk_update` skip all of this (there's an explicit
   `# TODO: Handle identifiers for Bulk Inserts`). New change-driven side effects must be added
   to `TRACKED_FIELDS`, and any importer/bulk path must replicate sequence/state logic.

2. **Two-tier default managers silently hide rows.** `Issue.issue_objects` (and `State.objects`)
   exclude triage/archived/draft; `Issue.objects` / `State.all_state_objects` return all. Using
   the wrong manager is an easy correctness bug in new queries and analytics.

3. **Soft-delete + partial-unique everywhere.** Every model uses `deleted_at` soft deletion
   (`SoftDeleteModel`, `objects` vs `all_objects`), with `unique_together` including
   `deleted_at` **and** a matching `UniqueConstraint(..., condition=Q(deleted_at__isnull=True))`.
   Deletes cascade asynchronously via `soft_delete_related_objects.delay(...)`. New tables
   (e.g., custom-field defs/values) must follow this exact pattern or they break uniqueness and
   soft-delete semantics. Also mind scope: pick `ProjectBaseModel` vs `WorkspaceBaseModel`
   deliberately (work items are project-scoped; types/labels/pages are workspace-scoped).
