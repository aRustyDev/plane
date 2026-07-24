# Feature: Workspace Wiki (+ optional external AFFiNE)

**Goal** — Add **workspace-scoped pages** (a wiki that lives above projects), reusing the existing collaborative page stack. Plus an **optional, clean-room external-doc integration** that maps a Plane wiki node to an AFFiNE document via the page's `external_source`/`external_id` — kept entirely optional behind a flag.

**Parity target** — Plane **Pro** (Workspace Wiki) + Woven (external AFFiNE option).

**Background** (grounded) — The substrate exists. `Page` has a `workspace` FK (no project required) and `is_global` (`apps/api/plane/db/models/page.py` L30, L51). The document-type enum already lists workspace/team: `TWebhookConnectionQueryParams.documentType = "project_page" | "team_page" | "workspace_page"` (`packages/types/src/page/core.ts` L79). External-integration hooks are present: `external_id`, `external_source` on `Page` (L57-58) — the natural AFFiNE attach point. What's missing in CE: (a) `apps/live` only handles `project_page` — `TDocumentTypes = "project_page"` (`apps/live/src/types/index.ts` L26) and `getPageService` (`apps/live/src/services/page/handler.ts`) throws otherwise; `extended.service.ts` is the abstract `PageService` seam ("implementation … in the enterprise repository"). (b) No workspace-scoped page REST — all URLs are `workspaces/<slug>/projects/<project_id>/pages/…` (`apps/api/plane/app/urls/page.py`). (c) No workspace-level page routes/stores in `apps/web`. Wiki empty-state assets already ship (`apps/web/app/assets/empty-state/wiki/`).

**Approach**
- **Backend/API** — New workspace-page viewset + URLs `workspaces/<slug>/pages/…` and `…/pages/{id}/description/` (binary), reusing `PageViewSet` logic scoped to `workspace` with `project` null; access filter `Q(owned_by=user) | Q(access=0)`. No new table (schema exists); additive migration only if an index on `(workspace, parent)` is wanted.
- **apps/live** — Extend `TDocumentTypes` to include `"workspace_page"`; add `WorkspacePageService` (extends `PageService`/`PageCoreService`, `basePath = /api/workspaces/{slug}`); register in `getPageService`. This is exactly the `extended.service.ts` seam.
- **Frontend** — Workspace-pages routes under `app/(all)/[workspaceSlug]/(workspace)/pages/…` (register in `apps/web/app/routes/core.ts`); a `workspacePages` store mirroring `projectPages`; reuse `pages/editor/editor-body.tsx`, passing `documentType: "workspace_page"`.
- **AFFiNE (OPTIONAL, clean-room)** — Store the mapping on `external_source="affine"`, `external_id=<affine doc id>`; add an **external-doc atom-node embed** (mirror work-item-embed) that renders/links the AFFiNE doc via `widgetCallback`; keep it in `TExtensions` disabled/flagged (`packages/editor/src/core/types/extensions.ts`). Optional one-way sync bgtask parallel to `apps/api/plane/db/models/integration/`. No AFFiNE source copied — public API/embed only.

**Feature flag** — `workspace_wiki` (core); `affine_external_docs` (separate, default OFF; also gated via `TExtensions`).

**Tasks** (→ child beads) — (1) workspace-page viewset + URLs + serializer; (2) `apps/live` `WorkspacePageService` + `TDocumentTypes`; (3) frontend routes + `workspacePages` store + nav entry; (4) wiki empty-state wiring; (5) *(optional)* external-doc embed node + AFFiNE adapter/sync + config; (6) tests + docs.

**Acceptance** — API: CRUD at `workspaces/<slug>/pages/…`; binary PATCH round-trips via live server. UI: wiki appears in workspace sidebar, real-time co-editing works (Hocuspocus `workspace_page`), nesting reuses the pages tree. AFFiNE (if enabled): a wiki node with `external_source="affine"` renders the external-doc embed and deep-links; disabling the flag hides the node type with no errors.

**Risks / upstream-merge impact** — `TDocumentTypes`/`getPageService` are `apps/live` core edits (`# woven:`, additive). AFFiNE must stay strictly optional and clean-room (no EE/AFFiNE source). Access/guest rules differ workspace-vs-project — reuse the existing `access` filter, don't invent a parallel one.
