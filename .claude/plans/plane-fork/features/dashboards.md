# Feature: Dashboards

**Goal** — A **user-composable, multi-dashboard** feature: users create named dashboards, add chart widgets (bar/line/area/pie/radar), arrange them on a grid, and persist the layout. Reuse `@plane/propel/charts` and the existing analytics data pipeline as the widget backend.

**Parity target** — Plane **Pro** (Dashboards).

**Background** (grounded, from `research/frontend-web.md` §7) — No generic dashboards feature exists today. Present are only: (a) a **deprecated single "home dashboard"** — `apps/web/core/store/dashboard.store.ts` (one `homeDashboardId`, fixed `widgetDetails`; the type is literally `TDeprecatedDashboard` in `packages/types/src/dashboard.ts` with a fixed `TWidgetKeys` enum, no chart type / layout / title); (b) a home-page reorderable-widget system (quick links/recents/stickies — not charts) in `apps/web/core/store/workspace/home.ts`; (c) a **read-only Analytics** section (`app/(all)/[workspaceSlug]/(projects)/analytics/[tabId]/`, 2 fixed tabs). The reusable spine: `apps/web/core/services/analytics.service.ts` `getAdvanceAnalyticsCharts<T>(slug, type, params)` returns generic `{data, schema}` payloads; recharts widgets in `core/components/analytics/work-items/*` (e.g. `priority-chart.tsx` = best copy-from); data-shaping in `core/components/chart/utils.ts` (`parseChartData`, `generateExtendedColors`); DnD reorder pattern in `home/widgets/manage/widget.helpers.ts` (`@atlaskit/pragmatic-drag-and-drop`). So this is mostly **greenfield build on existing pieces**.

**Approach**
- **Backend/models + migrations** — New Django app `apps/api/plane/dashboard/` (isolation per PROGRAM §2.3). Tables: `Dashboard` (workspace FK, name, `owned_by`, `access`, `layout_config` JSON) and `DashboardWidget` (dashboard FK, `widget_type`, `chart_type`, `config` JSON = x/y axis + filters, `grid_position` {x,y,w,h}). All additive; `deleted_at` + partial unique constraint per PROGRAM gotcha.
- **API** — Dashboard CRUD `workspaces/<slug>/dashboards/…`; widget CRUD + bulk `PATCH …/dashboards/{id}/widgets/` for layout persistence. Widget *data* served by reusing `getAdvanceAnalyticsCharts`.
- **Frontend** — New route tree `app/(all)/[workspaceSlug]/(projects)/dashboards/[dashboardId]/{layout,header,page}.tsx` + list `page.tsx` (register in `apps/web/app/routes/core.ts`); new `workspace-dashboards.store.ts` (list + per-dashboard widget CRUD/layout) registered in `root.store.ts` (do **not** extend the deprecated store); service methods in `packages/services/src/dashboard/dashboard.service.ts`; new real widget type in `packages/types/src/` (chart type, axes, `grid_position`, title). Components `apps/web/core/components/dashboards/` (shell + grid + config modal), reusing `@plane/propel/charts/*` and analytics chart components as templates; grid reordering via `pragmatic-drag-and-drop`.

**Feature flag** — `dashboards` (F0.1 registry); nav entry + route gated by flag.

**Tasks** (→ child beads) — (1) `dashboard` Django app: models + migrations; (2) dashboard/widget viewsets + URLs; (3) types + service methods; (4) `workspace-dashboards.store.ts` + root-store wiring; (5) routes + list/detail pages; (6) widget grid + chart render (reuse propel + analytics); (7) config modal (chart type + axis picker); (8) tests + docs.

**Acceptance** — API: create dashboard → add widget → reorder → reload persists `grid_position`; widget data endpoint returns `{data, schema}`. UI: create a dashboard, add a bar-chart widget bound to a metric, drag to reposition, reload preserves layout; empty state renders.

**Risks / upstream-merge impact** — Fully additive (new app, new routes, new store) → low merge conflict. Do not touch `dashboard.store.ts`/`TDeprecatedDashboard` (leave for upstream). Widget data reuses analytics filters — keep permission scoping identical to Analytics. Grid perf with many widgets: lazy-render off-screen charts.
