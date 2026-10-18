# Feature: Nested Pages + Embeds

**Goal** — Surface Plane's already-built page hierarchy in the UI (a collapsible sub-page tree in the page navigation pane) and add editor **embed node types** — a page/sub-page embed and the tracking plumbing that lets any future embed (issue, external doc) round-trip and be back-linked. Data layer is done; this is a UI + editor-node + type-surface completion.

**Parity target** — Plane **Business** ("Nested Pages + Embeds").

**Background** (grounded) — The data model already supports nesting: `Page.parent = ForeignKey("self", related_name="child_page")` in `apps/api/plane/db/models/page.py` (L40). Recursive hierarchy ops exist — `unarchive_archive_page_and_descendants` and reparent-on-delete rules in `apps/api/plane/app/views/page/base.py` (L59-72), plus `PageVersion.sub_pages_data` snapshots. The list/summary endpoints filter `parent__isnull=True`, so only top-level pages reach the list UI; children must be fetched per-parent. `PageLog` (`(page, transaction)` unique; `entity_type` choices include `page_mention`, `back_link`, `forward_link`) is the back-link index. Embed tracking runs in `apps/api/plane/bgtasks/page_transaction_task.py` — `COMPONENT_MAP` (L21) currently knows only `mention-component`, `image-component`. Editor embed pattern is `packages/editor/src/core/extensions/work-item-embed/` (atom block node + `ReactNodeViewRenderer` + `widgetCallback`). Gaps: `TPageExtended = object` stub (`packages/types/src/page/extended.ts`), no sub-page tree in `apps/web/core/components/pages/navigation-pane/`, no page-embed node, `COMPONENT_MAP` lacks a page tag.

**Approach**
- **Backend/API** — Add a children endpoint `GET …/pages/{id}/sub-pages/` (or `?parent_id=`) returning direct children; expose `parent_id` + `sub_pages_count` in `PageSerializer` (`apps/api/plane/app/serializers/page.py`). No migration — schema exists.
- **Editor** — New `page-embed` atom node under `packages/editor/src/core/extensions/page-embed/` (mirror work-item-embed); add key to `CORE_EXTENSIONS` (`src/core/constants/extension.ts`); register in `src/ce/extensions/document-extensions.tsx` + a slash command; extend `TPageEmbedType` (`packages/types/src/page/core.ts`) and `TEmbedConfig`.
- **page_transaction** — Add `page-embed-component` to `COMPONENT_MAP` so references become `PageLog` `forward_link`/`back_link` rows.
- **Frontend** — Populate `TPageExtended` (`parent_id`, `sub_pages_count`); build an expand/collapse tree in `navigation-pane/`; lazy-load children via the new endpoint; wire create-sub-page in the page store (`apps/web/core/store/pages/`).

**Feature flag** — `nested_pages` (F0.1 registry); editor node gated via `TExtensions` flagged list, off by default until GA.

**Tasks** (→ child beads) — (1) sub-pages API + serializer fields; (2) `TPageExtended` + store child-fetch; (3) navigation-pane tree UI; (4) page-embed editor node + slash command; (5) `COMPONENT_MAP` entry + `PageLog` tags; (6) acceptance tests + docs.

**Acceptance** — API: `GET …/pages/{id}/sub-pages/` returns direct children; creating a page with `parent` then editing a parent that embeds it yields a `PageLog` `forward_link`. UI: expandable sub-page tree renders and lazy-loads; slash-command inserts a page embed that survives reload (HTML↔binary round-trip).

**Risks / upstream-merge impact** — Editor `CORE_EXTENSIONS` and `COMPONENT_MAP` are core-file edits — mark `# woven:` and keep additive. Reparent/soft-delete rules already handle cycles; UI must not offer a page as its own ancestor. Low merge risk: new node dir + additive enum members.
