# Team Spaces

**Goal:** Complete Teamspaces — a real grouping of a subset of projects and members inside a workspace, with a teamspace-scoped work-item view and membership that feeds RBAC.

**Parity target:** Plane **Pro** — Team Spaces.

**Background:** PARTIAL-STUB — enum/routing + store shims aliasing project stores exist; backend and dedicated stores do not. Present: `EIssuesStoreType.TEAM` / `TEAM_VIEW` / `TEAM_PROJECT_WORK_ITEMS` (`packages/types/src/issues/issue.ts:32,36,42`); a computed `teamspaceId` router getter (`apps/web/core/store/router.store.ts:18,83`); issue-view dispatch already handles teamspace scopes (`apps/web/core/hooks/use-issue-layout-store.ts`, `.../hooks/store/use-issues.ts`); and **`apps/web/core/store/issue/root.store.ts:242-243` instantiates `teamIssuesFilter = new ProjectIssuesFilter(this)` / `teamIssues = new ProjectIssues(...)` — reusing project classes, not dedicated stores.** No teamspace model, service, dedicated store, component, or route. This is **stub-completion**, not greenfield. **Depends on RBAC** (membership).

**Approach:** New isolated app `apps/api/plane/teamspace/`. `Teamspace(BaseModel)` workspace-scoped: `name`, `description`, `lead`, `logo_props`, `sort_order`. Joins `TeamspaceProject` (`teamspace`, `project`) and `TeamspaceMember` (`teamspace`, `member`) — the latter feeds RBAC membership. Soft-delete `deleted_at` + partial unique on `(workspace, name)`, `(teamspace, project)`, `(teamspace, member)`. Additive, reversible migration. API: `/workspaces/<slug>/teamspaces/` + `/teamspaces/<id>/projects/` + `/members/`; teamspace work items resolve to the **union of member-project issues** (query filter) so the existing `TEAM_PROJECT_WORK_ITEMS` scope maps to real projects. Frontend: real `teamspaceStore` + `teamspaceDetailStore` (register in `root.store.ts`); **keep the existing `teamIssues`/`teamIssuesFilter` issue-store shims but repoint them** at teamspace-aggregated fetches. Service `packages/services/src/teamspace/`. Routes: `apps/web/app/(all)/[workspaceSlug]/(projects)/teamspaces/[teamspaceId]/...` in `core.ts` (the `teamspaceId` router param already exists). Sidebar nav entry in `apps/web/core/components/workspace/sidebar/sidebar-menu-items.tsx`. New i18n keys.

**Feature flag:** `teamspaces` (F0.1 plumbing).

**Tasks (→ child beads):** (1) models + migration (Teamspace + Project/Member joins); (2) serializers + viewsets + URLs; (3) teamspace-aggregated issue query; (4) FE service + real stores; (5) `teamspaceId` routes + list/detail pages; (6) repoint `teamIssues` shims; (7) RBAC membership integration; (8) nav; (9) tests + docs.

**Acceptance:** *API* — CRUD teamspace, add projects/members, work-items endpoint returns the union of member-project issues; soft-delete honored. *UI* — teamspace nav + detail showing projects and aggregated list/kanban views (already dispatched via `TEAM` enums), member management.

**Risks / upstream-merge impact:** The shim (`teamIssues = new ProjectIssues`) assumes a **single** project scope; aggregating across N projects needs care in `BaseIssuesStore` (grouping, DnD ownership, `sort_order`). RBAC coupling — teamspace membership must reconcile with project membership. Merge impact: additive app + new routes; the store shims already exist upstream so repointing them is a marked (`# woven:`) edit — keep flagged.
