# Work Item Types

**Goal:** Complete the dormant `IssueType`/`ProjectIssueType` schema into a working Work Item
Types system — per-workspace types, enabled per project, assignable to work items — with **Epics
as a built-in type** (`is_epic`). Clean-room management layer; the schema is upstream, we add the
missing viewset/URL/creation path.

**Parity target:** Plane Commercial **Pro** (Work Item Types + Epics).

**Background** (stub-completion, NOT greenfield): `IssueType(BaseModel)` already exists
(`db/models/issue_type.py:14`): workspace FK, `name`, `description`, `logo_props`, `is_epic`,
`is_default`, `is_active`, `level`, `external_source/id`. `ProjectIssueType(ProjectBaseModel)`
(`:35`) is the per-project enablement join and already carries the soft-delete partial-unique
constraint. `Issue.type` FK (`issue.py:164`, `SET_NULL`, nullable) and `DraftIssue.type` exist;
`Project.is_issue_type_enabled` boolean exists. Schema landed in mig `0070`. It is wired **only**
into the external REST serializers (`api/serializers/issue.py:66,159`), which fall back to
`IssueType.objects.filter(project_issue_types__project_id=…, is_default=True)`. There is **no
viewset, no URL route, and nothing anywhere creates an IssueType/ProjectIssueType** (`grep
IssueType.objects.create` → none). Frontend already threads `type_id`
(`packages/types/src/issues/issue.ts`); `issues/issue-type-switcher.tsx` renders only the
identifier (a misnomer — no real picker); the epic modal is a pure stub
(`epic-modal/modal.tsx`).

**Approach:**
- *Backend (no new tables):* add `IssueTypeViewSet` + `ProjectIssueTypeViewSet` in new
  `app/views/issue/type.py`; register routes in `app/urls/issue.py`; serializers in
  `app/serializers/`. Provide the creation path: on `is_issue_type_enabled` flip-on, idempotently
  seed one `is_default` type + `ProjectIssueType` (management command / signal — **not**
  `bulk_create`, which bypasses `save()`). `Issue.type` is a plain FK → **no `Issue.save()`
  change**. Respect two-tier managers when querying issues by type.
- *Frontend:* new `issueType` MobX store in `core/store/root.store.ts`; service in
  `packages/services`; project-settings page under `PROJECT_SETTINGS_CATEGORY.WORK_STRUCTURE`;
  real type picker replacing the switcher misnomer; Epic surfaces via `is_epic`; register the
  route in `app/routes/core.ts`.

**Feature flag:** Reuse existing `Project.is_issue_type_enabled` as the per-project gate; register
a workspace/instance default under Phase-0 F0.1 plumbing.

**Tasks (→ child beads):** (1) serializers + `IssueType`/`ProjectIssueType` viewsets + URLs;
(2) enable/seed-default-type path (idempotent, save-respecting); (3) Epic type surfacing;
(4) MobX store + service; (5) project-settings type-management UI + type picker + route.

**Acceptance:** *API* — enable types on a project, create/list types, assign a type to an issue,
disable hides types. *UI* — type-management page persists; work-item picker sets `type`; Epics
appear as a type.

**Risks / upstream-merge impact:** `IssueType` has **no `unique_together`** — duplicate names are
possible; add a name-uniqueness guard. Models are upstream (no schema drift); keep the viewset in
an isolated `# woven:`-marked module so a future upstream EE type API merges cleanly. Foundation
for Custom Fields, Workflows, Recurring items.
