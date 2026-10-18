# Feature: Advanced Dashboard Widgets

**Goal** — Extend the Dashboards feature with **richer widget types** beyond basic charts: pivot/matrix tables, number/KPI tiles, scatter and tree-map visuals, stacked/grouped multi-series charts, and configurable group-by/pivot dimensions with drill-down. Depends on the base **Dashboards** feature.

**Parity target** — Plane **Business** ("Advanced Dashboard Widgets").

**Background** (grounded) — Base widget model + grid + persistence come from `features/dashboards.md` (`Dashboard`/`DashboardWidget`, `workspace-dashboards.store.ts`, `dashboards/` components). The chart primitives needed already ship in `@plane/propel/charts/`: `bar-chart`, `line-chart`, `area-chart`, `pie-chart`, `radar-chart`, **`scatter-chart`**, **`tree-map`** (`packages/propel/src/charts/*`, per-type subpath imports) plus shared `charts/components/{legend,tick,tooltip}.tsx`. Tables use `@tanstack/react-table` (already a dependency; used in the spreadsheet issue layout `issue-layouts/spreadsheet/`). The analytics data backend `getAdvanceAnalyticsCharts<T>(slug, type, params)` (`apps/web/core/services/analytics.service.ts`) returns generic `{data, schema}` and supports axis selection (see `analytics/select/*` and `customized-insights.tsx` axis selectors) — the seam for pivot dimensions. KPI/stat-tile patterns exist in `analytics/total-insights.tsx` / `insight-card.tsx`. So advanced widgets are **new widget-type renderers + richer config**, not new infrastructure.

**Approach**
- **Backend/models** — Additive only: extend `DashboardWidget.widget_type` allowed values (`pivot`, `kpi`, `scatter`, `tree_map`, `stacked_bar`, …) and enrich the `config` JSON schema (group_by / pivot rows+cols, aggregation, series list, drill-down target). No new tables; a reversible migration only if a widget-type check constraint is added.
- **API** — Reuse dashboard/widget endpoints; extend the widget-data path to accept pivot/group-by params passed through to `getAdvanceAnalyticsCharts` (add `type` variants). Keep `{data, schema}` contract.
- **Frontend** — New renderers under `apps/web/core/components/dashboards/widgets/` — a pivot table (`@tanstack/react-table`, following `issue-layouts/spreadsheet/columns/`), a KPI tile (copy `insight-card.tsx`), and scatter/tree-map/stacked wrappers over `@plane/propel/charts/{scatter-chart,tree-map,bar-chart}`. Extend the widget config modal with a type picker + per-type option panels (pivot dimension pickers, aggregation, series). Extend the widget type in `packages/types/src/` (union of `widget_type`, per-type `config`).

**Feature flag** — `advanced_dashboard_widgets` (F0.1); requires `dashboards` flag ON. Advanced widget types are hidden from the type picker when the flag is off.

**Tasks** (→ child beads) — (1) extend `DashboardWidget` type + config schema (+ migration); (2) widget-data params for pivot/group-by → analytics service; (3) pivot-table renderer (`react-table`); (4) KPI-tile renderer; (5) scatter/tree-map/stacked-chart renderers (propel); (6) config-modal per-type option panels; (7) optional drill-down navigation; (8) tests + docs.

**Acceptance** — API: a widget with `widget_type="pivot"` + group-by config returns a matrix `{data, schema}`; KPI widget returns a single aggregate. UI: add a pivot widget, choose row/column dimensions + aggregation, see a populated matrix; add a KPI tile bound to a metric; scatter and tree-map render from propel; reload persists config; toggling the flag off hides advanced types.

**Risks / upstream-merge impact** — Additive, layered on Dashboards → low merge risk (no core-file edits beyond the shared widget type union). Pivot performance on large datasets — push aggregation server-side via analytics, don't pivot in the browser. Keep `config` JSON versioned/forward-compatible so later widget types don't break stored dashboards.
