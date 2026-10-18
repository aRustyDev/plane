# Work Item Custom Properties / Fields

**Goal:** Let workspace admins define custom properties on a Work Item Type (text, number,
select/multi-select, boolean, date, member, URL, relation) and set per-issue values, surfaced in
the work-item modal, detail panel, spreadsheet columns, and filters.

**Parity target:** Plane Commercial **Pro** (Work Item Custom Properties).

**Background** (greenfield — build from scratch): There is **no** custom-field schema — no
property-definition table, no value table, no per-type attribute model (`backend-data-model.md
§4`). **Naming red herring:** the historical `IssueProperty` (mig
`0071_rename_issueproperty_issueuserproperty…`) was **per-user display prefs**, renamed to
`IssueUserProperty`, then **deleted** in mig `0114`. The surviving `*UserProperty`/`*UserProperties`
models are all UI filter/display prefs, **not** custom fields — do not build on them.
`IssueVersion.properties = JSONField(default=dict)` is written as `{}` (`issue.py:771`) — a
reserved, unused hint. Depends on **Work Item Types** (properties key off `IssueType`). Frontend
seam: the empty no-op `core/hooks/use-workspace-issue-properties-extended.tsx` (invoked from
`use-workspace-issue-properties.ts`) is the injection point; spreadsheet columns live in
`issue-layouts/spreadsheet/columns/`.

**Approach:**
- *Backend models + migrations (additive):* `IssuePropertyDefinition` (workspace-scoped
  `BaseModel`, FK → `IssueType`, `name`, `property_type` enum, `settings` JSON for
  options/validation, `is_required`, `sort_order`) + `IssuePropertyValue` (project-scoped
  `ProjectBaseModel`, FK → `Issue` + definition, typed value columns / JSON). Both follow the
  universal **soft-delete + `deleted_at` partial-unique** convention (`§5`) and choose scope
  deliberately (definition = workspace; value = project, matching `Issue`).
- *`Issue.save()` heaviness:* values are separate rows — write them **outside** `Issue.save()`,
  never via `bulk_create` without replicating sequence/lock logic. Emit property-change activity
  through the existing `issue_activities_task` pipeline.
- *API:* `IssuePropertyViewSet` (definitions, admin CRUD) + value read/write on the issue detail
  endpoint; serializers validate against the definition's `property_type`/options.
- *Frontend:* fill the `use-workspace-issue-properties-extended` seam with a real hook + store +
  service; render dynamic fields in `issue-modal/form.tsx`, detail sidebar, and register dynamic
  spreadsheet columns; extend filter config.

**Feature flag:** `CUSTOM_FIELDS_ENABLED` workspace/instance flag (F0.1); gated additionally by
Work Item Types being enabled on the project.

**Tasks (→ child beads):** (1) definition + value models + migrations (soft-delete/partial-unique);
(2) property-type validation + serializers; (3) `IssuePropertyViewSet` + value endpoints +
activity; (4) store/service + `use-workspace-issue-properties-extended` hook; (5) modal + detail +
spreadsheet + filter UI.

**Acceptance:** *API* — define a select property on a type; set/read a value on an issue;
validation rejects out-of-option values; soft-delete preserves history. *UI* — property renders in
modal + detail, shows as a spreadsheet column, filters work.

**Risks / upstream-merge impact:** Entirely new tables (low core-file drift). Value indexing/query
cost on large projects — index `(issue, definition)`. If upstream later ships EE custom fields,
table names may collide — prefix `woven_`-namespaced tables to avoid migration conflicts.
