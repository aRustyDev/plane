# Initiatives

**Goal:** A portfolio grouping **above** projects — an Initiative bundles multiple projects (and epics) under one lead/status/date range with rolled-up progress, for cross-project planning.

**Parity target:** Plane **Pro** — Initiatives.

**Background:** ABSENT — greenfield. Only vestigial traces exist: `EFileAssetType.INITIATIVE_DESCRIPTION` (`packages/types/src/enums.ts:72`), a sidebar-collapse UI flag `initiativesSidebarCollapsed` (`apps/web/core/store/theme.store.ts:20,47,183`), reserved slugs `"initiatives"`/`"initiative"` in `RESTRICTED_URLS` (`packages/constants/src/workspace.ts:54-55`), and marketing/illustration assets (`packages/propel/src/empty-state/assets/vertical-stack/initiative.tsx`). No model, store, service, entity, component, or route. **Depends on RBAC** (who manages initiatives).

**Approach:** New isolated app `apps/api/plane/initiatives/`. `Initiative(BaseModel)` workspace-scoped (BaseModel + `workspace` FK): `name`, `description_json/html`, `lead`→User, `status`, `start_date`/`target_date`, `sort_order`, `external_id`/`external_source`. Join `InitiativeProject(BaseModel)` (`initiative`, `project`); optional `InitiativeLabel`, `InitiativeEpic` (link to `Issue` of an epic `IssueType`). Soft-delete `deleted_at` + partial unique on `(workspace, name)` and `(initiative, project)`. Additive, reversible migration after `0121`. API: `plane/app/views/initiative/` → `/workspaces/<slug>/initiatives/` + `/initiatives/<id>/projects/`. Frontend (greenfield): MobX `initiativeStore` + `initiativeDetailStore` registered in `apps/web/core/store/root.store.ts`; service `packages/services/src/initiative/`. Routes: new workspace-level group `apps/web/app/(all)/[workspaceSlug]/(projects)/initiatives/...` (list + `[initiativeId]` detail) registered in `apps/web/app/routes/core.ts`. Sidebar nav entry in `apps/web/core/components/workspace/sidebar/sidebar-menu-items.tsx`; **reuse the existing `initiativesSidebarCollapsed` theme state**. New i18n keys.

**Feature flag:** `initiatives` (F0.1 plumbing).

**Tasks (→ child beads):** (1) models + migration; (2) serializers + viewsets + URLs; (3) FE service + stores; (4) routes + list/detail pages; (5) sidebar nav (reuse collapse state); (6) project-linking UI; (7) rollup progress aggregation; (8) tests + docs.

**Acceptance:** *API* — CRUD initiative, add/remove projects, list scoped to workspace, soft-delete honored. *UI* — Initiatives nav appears, create initiative, link projects, detail shows rolled-up project/issue progress.

**Risks / upstream-merge impact:** Largest greenfield surface of the cluster. Rollup analytics must use the correct managers (`Issue.issue_objects` excludes archived/draft/triage — research §gotcha 2). RBAC: creation/management gated to workspace admins. Merge impact **fully additive** — new app, new `coreRoutes`, new stores; `RESTRICTED_URLS` already reserves the slug, so no route collision.
