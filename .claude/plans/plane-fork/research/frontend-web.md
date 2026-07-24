# Plane Fork — Frontend Architecture Recon

Scope: `apps/web` (main web app), `apps/admin` (instance-admin), shared packages
(`packages/ui`, `packages/editor`, `packages/types`, `packages/services`, `packages/hooks`,
plus `packages/propel`, `packages/constants`).
Repo root: `/Users/asmith/repos/woven/forks/plane`. Monorepo = pnpm workspaces + Turborepo.
Root version: `1.3.1`. Read-only recon; no code changed.

> IMPORTANT DIVERGENCE FROM UPSTREAM: this fork has migrated the web + admin apps off
> **Next.js** onto **React Router 7 (framework mode, SPA / `ssr:false`)** with Vite.
> Next.js APIs are provided by thin compat shims (`app/compat/next/*`). Any upstream Plane
> doc that says "Next.js app router" is stale here.

---

## 1. Framework & Structure

### Web app (`apps/web`)
- **Router/build:** React Router 7 via `@react-router/dev` + Vite. Scripts: `react-router dev --port 3000`, `react-router build`. Config: `apps/web/react-router.config.ts` (`appDirectory: "app"`, `ssr: false` → static client bundle served by `serve`).
- **Vite:** `apps/web/vite.config.ts` — `reactRouter()` + `vite-tsconfig-paths`; aliases `next/link`, `next/navigation`, `next/script` → `apps/web/app/compat/next/*` (Next.js compat shims, e.g. `usePathname`, `useRouter`). Env: only `VITE_*` vars exposed via `define`.
- **Directory model:**
  - `apps/web/app/` — routing surface. Route groups mirror the old Next app-router layout using parenthesized dirs (`(all)`, `(home)`, `(projects)`, `(settings)`, `(list)`, `(detail)`, `(workspace)`) and bracket params (`[workspaceSlug]`, `[projectId]`, `[issueId]`). Each folder has `layout.tsx` and `page.tsx`. **These files are NOT auto-discovered** — they are explicitly registered (see routing below).
  - `apps/web/core/` — the real application code: `components/`, `hooks/`, `layouts/`, `lib/`, `services/`, `store/`.
  - `apps/web/helpers/`, `apps/web/styles/`, `apps/web/public/`.
- **Path aliases** (`apps/web/tsconfig.json`): `@/*` → `./core/*`, `@/app/*` → `./app/*`, `@/helpers/*`, `@/styles/*`. So `@/components/...`, `@/store/...`, `@/hooks/...` resolve into `core/`.
- **Routing registration (key pattern):**
  - `apps/web/app/routes.ts` — entry: merges `coreRoutes` + `extendedRoutes` via `mergeRoutes`, appends catch-all `*` → `not-found.tsx`.
  - `apps/web/app/routes/core.ts` — the full explicit route tree (uses `route()`, `layout()`, `index()` from `@react-router/dev/routes`). All real routes live here.
  - `apps/web/app/routes/extended.ts` — **empty array in CE** (`extendedRoutes = []`). This is the EE/enterprise extension seam: `mergeRoutes` (`apps/web/app/routes/helper.ts`) deep-merges extended over core by file key, so an EE build injects routes here without touching core.
  - `apps/web/app/routes/redirects/` — legacy URL redirect route modules.
- **Root/entry:** `apps/web/app/root.tsx`, `apps/web/app/entry.client.tsx`, `apps/web/app/layout.tsx`, `apps/web/app/provider.tsx` (AppProvider), `apps/web/app/not-found.tsx`, `apps/web/app/error/{index,dev,prod}.tsx`.
- **Typed routes:** React Router typegen — pages import `Route` from `./+types/<layout|page>` and read typed `params`/`loaderData` (e.g. `Route.ComponentProps`). Run via `react-router typegen && tsc --noEmit` (`check:types`).
- **TypeScript:** strict-ish (`strictNullChecks: true`, `exactOptionalPropertyTypes: false`). Base config `@plane/typescript-config/react-router.json`. Components are `.tsx`, heavy use of `observer()` from `mobx-react`. i18n keys everywhere via `useTranslation()` (`@plane/i18n`).

### Admin app (`apps/admin`) — instance admin
- Same stack (React Router 7 + Vite, `ssr:false`), port 3001. Config `apps/admin/react-router.config.ts`, `apps/admin/vite.config.ts`, same `next/*` compat shims.
- **Routes:** `apps/admin/app/routes.ts` is a **flat manual list** (no core/extended merge). Route groups `(home)` (setup/sign-in) and `(dashboard)` (the admin console).
- **Admin console pages** under `apps/admin/app/(all)/(dashboard)/`: `general`, `workspace` (+ `workspace/create`), `email`, `authentication` (+ `github`/`gitlab`/`google`/`gitea`), `ai`, `image`. Each is a `page.tsx` + a `form.tsx`. Sidebar: `sidebar.tsx`, `sidebar-menu.tsx`, `sidebar-dropdown.tsx`.
- **Admin code lives at app root** (not `core/`): `apps/admin/components/`, `apps/admin/hooks/`, `apps/admin/store/`, `apps/admin/providers/`, `apps/admin/lib/`.
- **Admin store:** `apps/admin/store/root.store.ts` — small MobX `RootStore` with `theme`, `instance`, `user`, `workspace` (has `hydrate()` + `resetOnSignOut()`). This app is only for instance configuration; not where product features go.

---

## 2. State Management & Data Fetching

- **Store library: MobX** (`mobx`, `mobx-react`, `mobx-utils`). `enableStaticRendering(typeof window === "undefined")`. UI components wrapped in `observer()`.
- **Root store:** `apps/web/core/store/root.store.ts` — `class CoreRootStore` (exported also as `RootStore`). Instantiates ~30 domain stores in constructor and passes `this` down (child stores hold a back-ref to root). Has `resetOnSignOut()`. Notable members already present: `workspaceRoot`, `projectRoot`, `memberRoot`, `cycle`, `module`, `projectView`, `globalView`, `issue` (IssueRootStore), `state`, `label`, `dashboard`, `analytics`, `projectPages`, `router`, `commandPalette`, `theme`, `instance`, `user`, `projectInbox`, `projectEstimate`, `multipleSelect`, `workspaceNotification`, `favorite`, `stickyStore`, `editorAssetStore`, `workItemFilters` (from `@plane/shared-state`), `powerK`, `timelineStore`.
- **Store provisioning:** `apps/web/core/lib/store-context.tsx` — module-level singleton `rootStore = new RootStore()`, `StoreContext` (React context), `StoreProvider`. Mounted in `apps/web/app/provider.tsx` (`AppProvider`) which nests: `StoreProvider` → `AppProgressBar` → `TranslationProvider` → `Toast` → `StoreWrapper` → `InstanceWrapper` → `SWRConfig` → children. (`StoreWrapper`/`InstanceWrapper` are lazy `@/lib/wrappers/*`.)
- **Store consumption (hooks):** one hook per store under `apps/web/core/hooks/store/` (e.g. `use-issues.ts`, `use-dashboard.ts`, `use-analytics.ts`, `use-project.ts`, `use-workspace.ts`, `use-member.ts`, `use-kanban-view.ts`, `use-calendar-view.ts`, `use-global-view.ts`, `use-project-view.ts`, `use-work-item-filters/`, `user/` permissions, etc.). These `useContext(StoreContext)` and return the relevant slice.
- **Data fetching = services + SWR:**
  - HTTP layer is `@plane/services` (`packages/services`). Base class `packages/services/src/api.service.ts` — abstract `APIService` wrapping an axios instance (`withCredentials: true`, `baseURL = API_BASE_URL`), exposing `get/post/put/patch/delete`. Every domain service extends it (e.g. `packages/services/src/dashboard/dashboard.service.ts`, `.../issue`, `.../workspace`, `.../project`, `.../cycle`, `.../module`, `.../state`, `.../label`, `.../user`, `.../auth`, `.../ai`, `.../developer`, `.../file`, `.../instance`, `.../intake`). Barrel: `packages/services/src/index.ts`. Also `live.service.ts`, `indexedDB.service.ts`.
  - There is ALSO an app-local service dir `apps/web/core/services/` (30+ dirs) for services not (yet) promoted to the package — check both when locating an API call.
  - **Server-state cache: SWR** (`swr`). Global config `WEB_SWR_CONFIG` from `@plane/constants` applied via `<SWRConfig>` in the provider. Fetch keys centralized in `packages/constants/src/fetch-keys.ts` and `packages/constants/src/swr.ts`. Pattern: components/stores call SWR with a key + a service method; MobX stores hold normalized entity maps and are populated from fetch actions.
- **Forms:** `react-hook-form`. **Tables:** `@tanstack/react-table`. **Charts:** `recharts`. **DnD:** `@atlaskit/pragmatic-drag-and-drop` (+ auto-scroll, hitbox). **Command palette:** `cmdk`. **Dropdown/dialog primitives:** `@headlessui/react` + `@popperjs/core`/`react-popper`.

---

## 3. Settings pages — structure & how to add one

### Registry-driven navigation (the important part)
Settings nav is **data-driven from `@plane/constants`**, not hand-wired per page:
- `packages/constants/src/settings/workspace.ts` — `WORKSPACE_SETTINGS` (record keyed by tab), derived `WORKSPACE_SETTINGS_ACCESS` (href→roles), `GROUPED_WORKSPACE_SETTINGS` (category → items). Categories enum `WORKSPACE_SETTINGS_CATEGORY`: `ADMINISTRATION`, `FEATURES` (**currently empty — natural home for feature-toggle settings**), `DEVELOPER`.
- `packages/constants/src/settings/project.ts` — `PROJECT_SETTINGS`, `PROJECT_SETTINGS_FLAT_MAP`, `GROUPED_PROJECT_SETTINGS`. Categories: `GENERAL`, `FEATURES`, `WORK_STRUCTURE` (states/labels/estimates — **where Work Item Types / custom fields would slot**), `EXECUTION` (automations).
- `packages/constants/src/settings/profile.ts` — profile settings tabs.
- Each item: `{ key, i18n_label, href, access: EUserWorkspaceRoles[]/EUserProjectRoles[], highlight(pathname, baseUrl) }`. Types: `TWorkspaceSettingsItem`/`TWorkspaceSettingsTabs`, `TProjectSettingsItem`/`TProjectSettingsTabs` in `packages/types/src/settings.ts`.

### Layouts, sidebar, helpers
- Settings shell layout: `apps/web/app/(all)/[workspaceSlug]/(settings)/layout.tsx` (sidebar + `<Outlet/>` in a `ContentWrapper`).
- Workspace settings layout (auth-gates via `WORKSPACE_SETTINGS_ACCESS`): `apps/web/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/layout.tsx`.
- Sidebar components: `apps/web/core/components/settings/workspace/sidebar/` (`root.tsx`, `item-categories.tsx`, `header.tsx`, `item-icon.tsx`), `apps/web/core/components/settings/project/sidebar/`, generic `apps/web/core/components/settings/sidebar/item.tsx`.
- Helpers: `apps/web/core/components/settings/helper.ts` — `pathnameToAccessKey`, `getWorkspaceActivePath`, `getProjectActivePath` (build href→label maps from the constants above).
- Shared settings building blocks: `apps/web/core/components/settings/{content-wrapper,heading,page-header,control-item,boxed-control-item,layout}.tsx`; mobile nav `settings/mobile/nav.tsx`.
- Page shell components used inside pages: `SettingsContentWrapper` (`@/components/settings/content-wrapper`), `SettingsHeading` (`@/components/settings/heading`), `PageHead` (`@/components/core/page-title`), `NotAuthorizedView` (`@/components/auth-screens/not-authorized-view`).

### Recipe: add a NEW workspace settings page
1. **Route:** add a `route(...)` inside the `(settings)/settings/(workspace)/layout.tsx` block of `apps/web/app/routes/core.ts`.
2. **Page file:** create `apps/web/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/<name>/page.tsx` (+ optional `header.tsx`). Follow the existing page pattern: `observer()` default export, `SettingsContentWrapper` + `SettingsHeading` + `PageHead`, gate with `useUserPermissions().allowPermissions(...)`. (Model file: `.../settings/(workspace)/exports/page.tsx`.)
3. **Register in nav:** add an entry to `WORKSPACE_SETTINGS` and slot it into a `GROUPED_WORKSPACE_SETTINGS` category in `packages/constants/src/settings/workspace.ts` (access map + sidebar update automatically). Add the i18n label to `@plane/i18n` locale files.
4. **Content component:** build under `apps/web/core/components/settings/workspace/...` (or `apps/web/core/components/workspace/settings/...`, both conventions exist).
5. **Data:** add a service method (`packages/services/src/...` or `apps/web/core/services/...`) + a MobX store (register in `root.store.ts`) or SWR hook as needed.

Project settings adding is analogous under `(settings)/settings/projects/[projectId]/...` + `packages/constants/src/settings/project.ts`.

---

## 4. Adding a new VIEW/route (non-settings)

Same three-step shape as settings minus the constants registry:
1. Register route in `apps/web/app/routes/core.ts` under the right layout group.
2. Create `layout.tsx`/`page.tsx` under the matching `apps/web/app/(all)/[workspaceSlug]/(projects)/...` folder.
3. Build the surface in `apps/web/core/components/...`, wire store hook(s). Add sidebar/nav entry where relevant (`apps/web/core/components/sidebar/`, nav constants in `packages/constants/src/sidebar.ts`).
The EE seam is `apps/web/app/routes/extended.ts` (empty) — routes added there override/extend core via `mergeRoutes` without editing core.

---

## 5. Issue / work-item views (list · kanban · spreadsheet · calendar · gantt)

Layout impls live under `apps/web/core/components/issues/issue-layouts/<layout>/`. Each layout has a "base root" (data wiring) rendering a presentational component.

- **List:** `issue-layouts/list/base-list-root.tsx` (`BaseListRoot`) → `list/default.tsx` (`List`); `list-group.tsx`, `block-root.tsx`, `block.tsx`.
- **Kanban:** `issue-layouts/kanban/base-kanban-root.tsx` (`BaseKanBanRoot`) → `kanban/default.tsx` (`KanBan`) + `kanban/swimlanes.tsx`.
- **Spreadsheet:** `issue-layouts/spreadsheet/base-spreadsheet-root.tsx` → `spreadsheet/spreadsheet-view.tsx`; per-property columns in `spreadsheet/columns/` (registered in `columns/index.ts`). Uses `@tanstack/react-table`.
- **Calendar:** `issue-layouts/calendar/base-calendar-root.tsx` → `calendar/calendar.tsx` (`CalendarChart`).
- **Gantt/timeline:** `issue-layouts/gantt/base-gantt-root.tsx` (`BaseGanttRoot`) renders the generic timeline engine at `apps/web/core/components/gantt-chart/` — entry `gantt-chart/root.tsx` (`GanttChartRoot`) → `gantt-chart/chart/root.tsx`; view math in `gantt-chart/views/{month,quarter,week}-view.ts`.

### Dispatch / switcher
- **Per-scope dispatchers** in `issue-layouts/roots/` — `project-layout-root.tsx`, `cycle-layout-root.tsx`, `module-layout-root.tsx`, `project-view-layout-root.tsx`, `archived-issue-layout-root.tsx`, `all-issue-layout-root.tsx`. Each is a `switch (activeLayout)` over `EIssueLayoutTypes` → that scope's per-layout root.
- **Enum `EIssueLayoutTypes`:** `packages/types/src/issues/issue.ts` (LIST/KANBAN/CALENDAR/GANTT=`gantt_chart`/SPREADSHEET). Same file: `EIssuesStoreType`, `EIssueServiceType`.
- **Layout registry (constants):** `packages/constants/src/issue/layout.ts` — `ISSUE_LAYOUT_MAP`, `ISSUE_LAYOUTS`, `TIssueLayout`.
- **Toolbar picker:** `issue-layouts/filters/header/layout-selection.tsx`; icons `issue-layouts/layout-icon.tsx`.
- **Loading/empty HOC:** `issue-layouts/issue-layout-HOC.tsx` (`IssueLayoutHOC`, per-layout loaders under `core/components/ui/loader/layouts/`).
- `activeLayout` read from `issuesFilter.getIssueFilters(id).displayFilters.layout`.

### Issue store layer (`apps/web/core/store/issue/`)
- **Root:** `store/issue/root.store.ts` (`IssueRootStore`) instantiates every per-scope store + its filter store (project/cycle/module/workspace/profile/archived/project-views/workspace-draft/team/epic) + view-state stores.
- **Abstract bases** (`store/issue/helpers/`): `base-issues.store.ts` (`BaseIssuesStore`, exports `ISSUE_GROUP_BY_KEY`), `issue-filter-helper.store.ts` (`IssueFilterHelperStore`), `base-issues-utils.ts`.
- **Per-scope stores** (each has `issue.store.ts` + `filter.store.ts` + `index.ts`): `project/`, `cycle/`, `module/`, `workspace/`, `profile/`, `archived/`, `project-views/`, `workspace-draft/`.
- **View-state stores:** `issue.store.ts` (shared issue map), `issue_kanban_view.store.ts`, `issue_calendar_view.store.ts`, `issue_gantt_view.store.ts`.
- **Issue detail sub-tree:** `store/issue/issue-details/` (activity/attachment/comment/link/reaction/relation/subscription/sub_issues).
- **Hook access:** `core/hooks/store/use-issues.ts` (`useIssues(storeType)`), `core/hooks/use-issue-layout-store.ts`, `core/hooks/use-issues-actions.tsx`.

### Drag-and-drop (`@atlaskit/pragmatic-drag-and-drop`)
- Shared drop logic: `issue-layouts/utils.tsx` (`handleGroupDragDrop`, `getGroupByColumns`). Hook: `core/hooks/use-group-dragndrop.ts` (`useGroupIssuesDragNDrop`). Adapters in kanban/list/calendar `block.tsx`/`*-group.tsx`. Gantt has its own DnD/resize inside `gantt-chart/`.

### Recipe: ADD A NEW VIEW LAYOUT (registries to touch)
1. Add member to `EIssueLayoutTypes` (`packages/types/src/issues/issue.ts`).
2. Add entry to `ISSUE_LAYOUT_MAP`/`ISSUE_LAYOUTS` (`packages/constants/src/issue/layout.ts`) + i18n keys.
3. Add icon case in `issue-layouts/layout-icon.tsx`.
4. Add loader case in `issue-layouts/issue-layout-HOC.tsx` + loader under `core/components/ui/loader/layouts/`.
5. Create `issue-layouts/<new>/base-<new>-root.tsx` + presentational component + per-scope roots in `issue-layouts/<new>/roots/`.
6. Add a `case` to each scope switcher in `issue-layouts/roots/*-layout-root.tsx`.
7. Register in display-filters config (`ISSUE_DISPLAY_FILTERS_BY_PAGE`, `packages/constants/src/issue/`) so the selector/store accept it; extend filter-helper defaults if it needs group_by/order_by.
8. (If grouped+DnD) reuse `getGroupByColumns`/`useGroupIssuesDragNDrop`; optionally add a view-state store like `issue_<layout>_view.store.ts` and register in `store/issue/root.store.ts`.

---

## 6. UI library (`@plane/ui` / `@plane/propel`) & Editor (`@plane/editor`)

**Styling primitive:** `cn()` at `packages/utils/src/common.ts` = `twMerge(clsx(...))` with an extended tailwind-merge. Tailwind everywhere; shared preset `packages/tailwind-config`. `@plane/propel` adds `class-variance-authority` (cva) for variants. All three UI packages build with `tsdown` and ship Storybook.

### `@plane/ui` (`packages/ui`) — higher-level Plane-styled components
- Single barrel export (`src/index.ts`, `"." → dist`). Depends on `@plane/propel` (composes over it). Key deps: `@headlessui/react`, `react-popper`, `@radix-ui/react-scroll-area`, `@blueprintjs/core`, Atlaskit pragmatic DnD, `lucide-react`, `react-day-picker`, `react-color`.
- Categories (each a `src/` subdir): `button/` (+ `toggle-switch`), `badge/`, `tag/`, `avatar/` (+group), `dropdown/` (typed select) & `dropdowns/` (`custom-menu`, `custom-select`, `custom-search-select`, `combo-box`, `context-menu/`), `modals/` (`modal-core`, `alert-modal`), `popovers/`, `form-fields/` (`input`, `textarea`, `checkbox`, `input-color-picker`, `password/`), `tables/`, `tabs/`, `spinners/` + `loader.tsx`, `tooltip/`, `typography/`, `card/`, `row/`, `header/`, `content-wrapper/`, `collapsible/`, `breadcrumbs/`, `scroll-area.tsx`, `color-picker/`, `progress/`, `sortable/` + `drag-handle`/`drop-indicator`, `auth-form/`, `oauth/`. **No toast here** — toast is in propel.

### `@plane/propel` (`packages/propel`) — low-level primitives (headless-ish)
- Built on `@base-ui-components/react`, `cmdk`, `frimousse`, `framer-motion`, `recharts`, `@tanstack/react-table`, cva. **Per-component subpath exports** (`@plane/propel/button`, `@plane/propel/toast`, `@plane/propel/charts/bar-chart`, …) — no single barrel.
- Primitives: `button/`, `input/`, `switch/`, `combobox/`, `command/` (cmdk), `menu/`, `context-menu/`, `dialog/`, `popover/`, `tooltip/`, `tabs/` + `tab-navigation/`, `table/`, `toast/`, `toolbar/`, `calendar/`, `accordion/`, `collapsible/`, `banner/`, `pill/`, `card/`, `avatar/`, `badge/`, `skeleton/`, `separator/`, `scrollarea/`, `portal/`, `animated-counter/`, `empty-state/`, `emoji-icon-picker/`, `emoji-reaction/`, large `icons/` set.
- **Toast API:** `packages/propel/src/toast/toast.tsx` → `Toast`, `setToast`, `updateToast`, `setPromiseToast`, `TOAST_TYPE`. Consumed via `@plane/propel/toast` (mounted in `app/provider.tsx`).
- **Charts (recharts):** `packages/propel/src/charts/{bar-chart,line-chart,area-chart,pie-chart,radar-chart,scatter-chart,tree-map}/` + shared `charts/components/{legend,tick,tooltip}.tsx`. Per-type subpath imports.

### `@plane/editor` (`packages/editor`) — TipTap v2 / ProseMirror (+ Yjs collab)
- Engine: TipTap v2 on ProseMirror; Yjs + `@hocuspocus/provider` for realtime; `tiptap-markdown`, `lowlight` code blocks, `tippy.js`/`@floating-ui` menus.
- Exports: `"."` → `dist/index.js` (barrel `src/index.ts`), `"./lib"` → server/Yjs helpers (`src/lib.ts`, no React), `"./styles.css"`.
- **Four editor variants** (all `forwardRef`, in `src/core/components/editors/`):
  - `rich-text/editor.tsx` → `RichTextEditorWithRef` (non-collab rich text).
  - `lite-text/editor.tsx` → `LiteTextEditorWithRef` (minimal, e.g. comments).
  - `document/editor.tsx` → `DocumentEditorWithRef` (full page, non-collab).
  - `document/collaborative-editor.tsx` → `CollaborativeDocumentEditorWithRef` (Yjs realtime). Read-only is a prop (`editable`), not a variant.
- **Ref/props API:** `src/core/types/editor.ts` — `EditorRefApi` (imperative: `setEditorValue`, `getDocument`, `getMarkDown`, `getHeadings`, `focus`, `undo/redo`…), `IEditorProps` (`id`, `initialValue`, `editable`, `fileHandler`, `mentionHandler`, `disabledExtensions`, `onChange`…), `TEditorCommands` (all toolbar/slash commands). Config subtypes in `src/core/types/{config,mention,slash-commands-suggestion,collaboration,asset,ai,embed}.ts`.
- **Extensions:** registry `src/core/extensions/extensions.ts` (`CoreEditorExtensions`); name enum `src/core/constants/extension.ts` (`CORE_EXTENSIONS`). Notable dirs under `src/core/extensions/`: `mentions/`, `slash-commands/`, `table/`, `image/` + `custom-image/`, `work-item-embed/` (Plane issue embeds), `callout/`, `emoji/`, `code/`, `custom-link/`, `custom-color.ts`, `text-align.ts`. Menus in `src/core/components/menus/` (`bubble-menu/`, `floating-menu/`, `block-menu.tsx`, `ai-menu.tsx`).
- **Fork-customizable extension seam:** `src/ce/extensions/` (`rich-text-extensions.tsx`, `document-extensions.tsx`, `slash-commands.tsx`) + `src/ce/constants/extensions.ts` (`ADDITIONAL_EXTENSIONS`). `src/ee/` = enterprise override stubs (mostly empty). This is where you register feature-specific editor extensions.
- **Embedding pattern (app side):** app wrappers wire Plane concerns around the package components. Reference: `apps/web/core/components/editor/rich-text/editor.tsx` (wraps `RichTextEditorWithRef`, injects `fileHandler` via `useEditorConfig`, `mentionHandler` via `useEditorMention`/`useMember`, flags via `useEditorFlagging`). Parallel wrappers: `editor/lite-text/editor.tsx`, `editor/document/editor.tsx`, `editor/sticky-editor/editor.tsx`; collaborative page body at `apps/web/core/components/pages/editor/editor-body.tsx`. Import `@plane/editor/styles.css` when embedding.

---

## 7. Dashboards / Analytics / Charts (existing) + where new dashboards slot in

**Verdict:** No generic, user-composable "Dashboards" feature exists today. Present are: (a) a **legacy/deprecated single "home dashboard"** (fixed widget keys, no layouts/grid), (b) a **home-page reorderable widget system** (quick links / recents / stickies — not chart widgets), and (c) a **read-only Analytics section** (2 fixed tabs, recharts charts). A new Dashboards + Advanced Widgets feature is mostly NEW build, reusing `@plane/propel/charts` and the analytics data pipeline.

### (a) Legacy "home dashboard" (deprecated)
- Store `apps/web/core/store/dashboard.store.ts` — single home dashboard per workspace: `homeDashboardId`, `widgetDetails`, `widgetStats`. No multi-dashboard, no layout/grid, no widget create/delete.
- Services: `apps/web/core/services/dashboard.service.ts` (used by store) + near-duplicate `packages/services/src/dashboard/dashboard.service.ts` (`getHomeWidgets`, `getWidgetStats`, `retrieve`, `updateWidget`).
- Types `packages/types/src/dashboard.ts` — `TWidgetKeys` is a **fixed enum**; `TWidget` has no chart type / layout / title; the dashboard type is literally named `TDeprecatedDashboard`.

### (b) Analytics section (read-only)
- Route: `app/(all)/[workspaceSlug]/(projects)/analytics/[tabId]/{page,layout,header}.tsx`. Redirect `analytics → analytics/overview`.
- Tabs (only 2): `core/components/analytics/tabs.tsx` → `overview`, `work-items`; `use-analytics-tabs.tsx`.
- Store `apps/web/core/store/analytics.store.ts` (`BaseAnalyticsStore`) — filter state only (tab, selected projects/duration/cycle/module, peek view). No chart/widget persistence.
- Service `apps/web/core/services/analytics.service.ts` — `getAdvanceAnalytics`, `getAdvanceAnalyticsStats`, `getAdvanceAnalyticsCharts<T>(slug, type, params)` → generic `{data, schema}` chart payloads (reusable widget backend).
- Chart components (recharts via `@plane/propel/charts`): `analytics/work-items/priority-chart.tsx` (BarChart, best copy-from template), `created-vs-resolved.tsx` (AreaChart), `customized-insights.tsx` (axis selectors), `overview/project-insights.tsx` (RadarChart), KPI tiles `total-insights.tsx`/`insight-card.tsx`, axis selectors `analytics/select/*`.
- Data-shaping helpers: `apps/web/core/components/chart/utils.ts` (`parseChartData`, `generateExtendedColors`) — the only file in `components/chart`.

### (c) Home-page reorderable widgets (the live system; NOT charts)
- Store `apps/web/core/store/workspace/home.ts` — `widgetsMap`, `orderedWidgets`, `toggleWidget`, `reorderWidget`, `fetchWidgets`.
- Widgets under `apps/web/core/components/home/widgets/`: `links/` (quick links), `recents/`, `manage/` (reorder modal + pragmatic DnD `widget.helpers.ts`), stickies (`../stickies/widget`), empty-states, loaders. Home shell `home/root.tsx` (`WorkspaceHomeView`), rendered by workspace landing `app/(all)/[workspaceSlug]/(projects)/page.tsx`. `home/home-dashboard-widgets.tsx` maps `HOME_WIDGETS_LIST` (several legacy keys → null).

### Where a NEW "Dashboards" + "Advanced Widgets" feature slots in
- **Route:** new `app/(all)/[workspaceSlug]/(projects)/dashboards/...` mirroring analytics (`[dashboardId]/{layout,header,page}.tsx` + list `page.tsx`). Register in `app/routes/core.ts`.
- **Store:** legacy `dashboard.store.ts` is not extensible → add a **new `workspace-dashboards.store.ts`** (list + per-dashboard widget CRUD/layout), register in `apps/web/core/store/root.store.ts`.
- **Types:** new real widget model (chart type, x/y axis, grid position, title) in `packages/types/src/` — current `TWidget` lacks all of these.
- **Service:** add list/create/delete + widget CRUD/reorder to `packages/services/src/dashboard/dashboard.service.ts` (today only home-fetch + update-existing).
- **Components:** new `apps/web/core/components/dashboards/` (shell + widget grid + config modals). **Reuse** `@plane/propel/charts/*`, `components/chart/utils.ts`, analytics chart components as templates, `getAdvanceAnalyticsCharts` as data backend, and the `home/widgets/manage/widget.helpers.ts` pragmatic-DnD pattern for grid reordering.

---

## 8. Planned-feature scaffolding audit (Work Item Types/custom fields, Templates, Initiatives, Team Spaces, Time Tracking)

This is a CE (community) fork; these five are Plane paid/EE features. All are referenced by marketing/billing/i18n/illustration assets, but real implementation (stores, services, management UI, routes) is absent or reduced to empty extension seams. **All five must be built essentially from scratch.**

### EE / extension seams (cross-cutting)
- Route seam: `apps/web/app/routes/extended.ts` (empty `extendedRoutes: []`, merged in `app/routes.ts`).
- Custom-properties hook seam (empty no-op): `apps/web/core/hooks/use-workspace-issue-properties-extended.tsx`, invoked from `use-workspace-issue-properties.ts`.
- Convention: many `*-extended.ts(x)` files across types/rich-filters/sidebar/admin are EE injection points (CE = empty).
- **No feature-flag enum system.** Feature gating today = marketing strings in `packages/constants/src/subscription.ts` + billing comparison `apps/web/core/components/workspace/billing/comparison/plans.tsx`.

| Feature | Verdict | Strongest evidence (paths) |
|---|---|---|
| 1. Work Item Types / Custom Properties | **PARTIAL-STUB** (data plumbing + empty EE seam; all mgmt UI absent) | `type_id` on issue entity `packages/types/src/issues/issue.ts` (~L65); display/filter mapping `packages/constants/src/issue/common.ts` (`issue_type→type_id`), `filter.ts`; empty seam `apps/web/core/hooks/use-workspace-issue-properties-extended.tsx`. `issues/issue-type-switcher.tsx` only renders the identifier (misnomer). No store/service/mgmt components. |
| 2. Templates (project/work-item/page) | **PARTIAL-STUB** (UI prop seams + no-op handlers + full i18n) | Issue-modal context typedefs/no-ops `issue-modal/context/issue-modal-context.tsx`, `issue-modal/provider.tsx` (`handleTemplateChange: ()=>Promise.resolve()`), consumed in `issue-modal/form.tsx`; unused `templateId` prop `projects/create/root.tsx`, `project/create-project-modal.tsx`; complete strings `packages/i18n/src/locales/en/template.json`. No store/service/routes. |
| 3. Initiatives | **ABSENT** | Only `EFileAssetType.INITIATIVE_DESCRIPTION` (`packages/types/src/enums.ts`); sidebar-collapse UI state in `theme.store.ts` (`initiativesSidebarCollapsed`); reserved slug `packages/constants/src/workspace.ts`; marketing + illustration `packages/propel/src/empty-state/assets/vertical-stack/initiative.tsx`. No store/service/entity/components/routes. |
| 4. Team Spaces / Teamspaces | **PARTIAL-STUB** (enum + routing + store shims aliasing project stores) | Enums `EIssuesStoreType.TEAM`/`TEAM_VIEW`/`TEAM_PROJECT_WORK_ITEMS` (`packages/types/src/issues/issue.ts`); router `teamspaceId` (`store/router.store.ts`); layout mapping `hooks/use-issue-layout-store.ts` + `hooks/store/use-issues.ts`; **`store/issue/root.store.ts` instantiates `teamIssues = new ProjectIssues(...)` etc. (reuses project classes, not dedicated stores)**. No teamspace service/dedicated store/components/routes. |
| 5. Time Tracking / Worklogs | **TYPES-ONLY** | Lone `activity_type: "WORKLOG"` union member `packages/types/src/issues/activity/base.ts`; marketing strings only. No store/service/component/entity/route. (Existing story-point "estimates" — `store/estimates`, `services/estimate.service.ts`, `types/estimate.ts` — is a separate, fully-implemented, unrelated feature.) |

### Bonus: Epics (adjacent to Work Item Types) — PARTIAL-STUB
Analytics-only types `packages/types/src/epics.ts`; service enum `EIssueServiceType.EPICS`; **epic modal is a pure stub** `apps/web/core/components/epic-modal/modal.tsx` (returns empty fragment); root store `epicDetail`/`projectEpics` alias project-issue classes; empty-state assets exist; no epic routes.

### Build-against hooks (for planners)
- **(1) Work Item Types / custom fields:** best hooks — `type_id` already threaded through issue types + the empty `use-workspace-issue-properties-extended` seam; would slot as a project setting under `PROJECT_SETTINGS_CATEGORY.WORK_STRUCTURE` (states/labels/estimates).
- **(4) Teamspaces:** `EIssuesStoreType.TEAM*` enum/routing/store shims exist (currently alias project stores) — the issue-view layer already dispatches teamspace scopes; needs real stores/service/routes/nav.
- **(2) Templates:** UI prop seams + complete i18n present, zero backend/store — needs store + service + management UI; feature-toggle would slot under settings `FEATURES` categories.
- **(3) Initiatives, (5) Time Tracking:** greenfield — only enum/type members + marketing/illustration assets.

---

## Cross-cutting notes for planners
- **Two extension seams exist:** (a) route seam `apps/web/app/routes/extended.ts` (empty in CE, EE injects here); (b) settings registry seams — `WORKSPACE_SETTINGS_CATEGORY.FEATURES` (empty) and `PROJECT_SETTINGS_CATEGORY.WORK_STRUCTURE`/`FEATURES`. New CE features can be added directly to `coreRoutes` + the settings constants.
- **`@plane/types` is the type home** (`packages/types/src/*`) — many feature types may exist there even when UI does not (already present: `dashboard.ts`, `analytics.ts`, `charts/`, `epics.ts`, `home.ts`, `views.ts`, `workspace-views.ts`, `settings.ts`, `estimate.ts`, `rich-filters/`).
- **i18n is mandatory** — every label is a translation key resolved via `useTranslation()` from `@plane/i18n`; new UI must add keys to the locale files.
- **`@plane/shared-state`** hosts cross-cutting stores (e.g. `WorkItemFilterStore`) shared beyond a single app.
