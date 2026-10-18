# Project Templates

**Goal:** Clone a whole project — states, labels, members, settings, enabled features, and its work-item templates — into a brand-new project in one action.

**Parity target:** Plane **Business** — Project Templates.

**Background:** PARTIAL-STUB (UI prop seam only). The project-create flow already threads an unused `templateId?` prop: `apps/web/core/components/project/create-project-modal.tsx:29,78` and `apps/web/core/components/projects/create/root.tsx:33` — but nothing consumes it (no store/service/backend). No `ProjectTemplate` model exists (research/backend-data-model.md §4). **Depends on work-item-page-templates** — it reuses the `Template` app + JSON serialization for the child work-item templates a project template embeds.

**Approach:** Extend the templates app with `template_type = PROJECT` (or a dedicated `ProjectTemplate(BaseModel)`, workspace-scoped). `template_data` snapshots project structure: name/identifier/network, the `DEFAULT_STATES`-style state seed, labels, estimates, `ProjectMember` roster by role, enabled feature flags, `ProjectIssueType` enablement, and references to embedded work-item templates. Soft-delete `deleted_at` + partial unique on `(workspace, name)`. Additive, reversible migration. API: `/workspaces/<slug>/project-templates/` + an **apply** endpoint that, in one DB transaction, creates the `Project`, then seeds `State` rows via `State.save()` (respect the auto `sequence += 15000`), `Label`, `ProjectMember`, `ProjectIssueType`, features — and only then any child work items via `Issue.save()` (never `bulk_create`). Frontend: extend `templateStore` + service; **activate the existing `templateId` prop** so submit in `projects/create/root.tsx` calls apply; add a "Save as template" action on project settings. Settings page under `WORKSPACE_SETTINGS` `FEATURES`; routes in `apps/web/app/routes/core.ts`.

**Feature flag:** `project_templates` (implies `templates`).

**Tasks (→ child beads):** (1) model + migration; (2) capture/snapshot serializer; (3) transactional apply/clone service (states→labels→members→features→WI-templates, ordered); (4) FE store + service; (5) wire `templateId` in create flow + "save as template"; (6) mgmt UI + nav; (7) tests + docs.

**Acceptance:** *API* — snapshot an existing project captures states/labels/members; apply builds a structurally identical project with correct state sequences and no issue-sequence corruption. *UI* — "Create project from template" pre-seeds structure; "save as template" round-trips.

**Risks / upstream-merge impact:** Cloning members must honor RBAC membership + guest rules (**depends on RBAC**); capturing "enabled features" couples to the feature-flag plumbing; clone **ordering** matters (states before issues). Merge impact: additive app + one core edit activating `templateId` in the create flow (mark `# woven:`).
