# Work Item & Page Templates

**Goal:** Reusable work-item and page templates a user picks to pre-fill a new work item or page (name, priority, state, labels, assignees, type, custom-property values / page body).

**Parity target:** Plane **Pro** — Work Item / Page Templates.

**Background:** PARTIAL-STUB — UI prop seams + no-op handlers + complete i18n, zero backend. The issue modal already carries the seam: `templateId?` in `apps/web/core/components/issues/issue-modal/context/issue-modal-context.tsx:17`, and `handleTemplateChange: () => Promise.resolve()` no-op in `.../issue-modal/provider.tsx:52`, consumed by `.../issue-modal/form.tsx`. Strings are fully translated (`packages/i18n/src/locales/en/template.json`). Backend has **no** `IssueTemplate`/`PageTemplate` model (research/backend-data-model.md §4); closest analog is `DraftIssue` (`apps/api/plane/db/models/draft.py`) — a persisted not-yet-created issue mirroring `Issue` fields incl. `type`, but a draft, not reusable. **Depends on custom-fields (WICF)** to be meaningful: a template must serialize `IssueType` + custom-property values.

**Approach:** New isolated Django app `apps/api/plane/templates/`. `Template(BaseModel)` workspace-scoped with **nullable project** (workspace-global or project-local): `name`, `template_type` enum (`WORK_ITEM|PAGE`), `template_data` `JSONField` (issue: name/priority/state-group/labels/assignees/`type_id`/custom-values; page: `description_json`/title). Follow soft-delete convention — `deleted_at` + `UniqueConstraint(workspace, project, name, condition=Q(deleted_at__isnull=True))`. Additive, reversible migration numbered after `0121`. API: `TemplateViewSet` in `plane/app/views/`, routes `/workspaces/<slug>/templates/` + project-scoped. **Apply = instantiate per item through `Issue.save()`** (advisory lock, `sequence_id`, default state) — never `bulk_create` (research §gotchas). Frontend: new MobX `templateStore` (register in `apps/web/core/store/root.store.ts`), service `packages/services/src/template/`; fill the existing `handleTemplateChange` no-op to populate the form from the store. Management UI as workspace + project settings pages registered in `WORKSPACE_SETTINGS`/`PROJECT_SETTINGS` (`FEATURES`/`WORK_STRUCTURE` category, `packages/constants/src/settings/`); routes in `apps/web/app/routes/core.ts` (CE — no `extended.ts`).

**Feature flag:** `templates` (F0.1 plumbing); hide settings + picker when off.

**Tasks (→ child beads):** (1) app + model + migration; (2) serializer + viewset + URLs; (3) apply/instantiate service honoring `Issue.save()`; (4) FE service + store; (5) wire `handleTemplateChange` + picker; (6) settings mgmt UI + nav registry; (7) page-template variant (creates `Page`+`ProjectPage`); (8) tests + docs.

**Acceptance:** *API* — create template, list scoped, apply→issue with correct `sequence_id`/state/type/custom-values; soft-delete hides. *UI* — save template from issue modal; picking pre-fills new-issue form; page template creates a page.

**Risks / upstream-merge impact:** Without WICF, templates carry only core fields. Merge impact minimal — new app + additive registry entries; the sole core edit fills the pre-existing `handleTemplateChange` seam (mark `# woven:`).
