# Plane Fork — Collab / Editor / Pages / Space Recon

Repo root: `/Users/asmith/repos/woven/forks/plane`
Scope: real-time collaboration, the editor, Pages/Wiki, the public/guest Space app, and intake scaffolding.
Read-only architecture recon (CE fork; EE hooks noted where present). All paths absolute.

---

## 1. `apps/live` — Real-time collaboration server

**What it is:** A standalone Node/TypeScript service (`package.json` `name: "live"`, `"type": "module"`) that runs a **Hocuspocus** (Yjs) collaboration server behind an **Express + express-ws** HTTP server. It powers the rich-text/document editor's real-time sync. Dependencies confirm the stack: `@hocuspocus/server`, `@hocuspocus/extension-database`, `@hocuspocus/extension-redis`, `@hocuspocus/extension-logger`, `y-prosemirror`, `y-protocols`, `yjs`, `@tiptap/core`, `@tiptap/html`, `ioredis`, `@react-pdf/renderer` (PDF export). Dockerfiles: `apps/live/Dockerfile.live`, `apps/live/Dockerfile.dev`.

**Process wiring:**
- Entry: `apps/live/src/start.ts` → `apps/live/src/server.ts` (`Server` class). Express app; Helmet + compression + CORS (`CORS_ALLOWED_ORIGINS`); all routes mounted under `env.LIVE_BASE_PATH`.
- `apps/live/src/hocuspocus.ts` — `HocusPocusServerManager` singleton wraps `new Hocuspocus({ onAuthenticate, onStateless, extensions: getExtensions(), debounce: 10000 })`.
- `apps/live/src/controllers/collaboration.controller.ts` — `@Controller("/collaboration")` with a `@WebSocket("/")` handler that hands the socket to `hocusPocusServer.handleConnection(ws, req)`. **This is the WS endpoint the frontends connect to: `<LIVE_BASE_PATH>/collaboration`.**
- Other controllers: `document.controller.ts` (HTML↔binary conversion endpoints), `pdf-export.controller.ts`, `health.controller.ts` (`apps/live/src/controllers/index.ts`).

**Extensions** (`apps/live/src/extensions/index.ts`): `Logger`, `Database`, `Redis`, `TitleSyncExtension`, `ForceCloseHandler`.
- **Redis** (`extensions/redis.ts`, `apps/live/src/redis.ts`) — Hocuspocus Redis extension for **multi-instance fan-out** (this is what makes the server horizontally scalable; force-close broadcasts ride Redis too).
- **Database** (`apps/live/src/extensions/database.ts`) — the persistence bridge. `fetch` loads a page's Yjs binary from the backend; `store` (debounced 10s) writes it back. Uses `@plane/editor` serializers `getAllDocumentFormatsFromDocumentEditorBinaryData` / `getBinaryDataFromDocumentEditorHTMLString` to produce `{ description_binary, description_html, description_json }` (`TDocumentPayload`). On first load, if binary is empty it converts stored `description_html` → binary and back-fills.
- **TitleSync** (`extensions/title-sync.ts`, `extensions/title-update/*`) — extracts the `title` Yjs fragment and PATCHes the page `name` on the backend (debounced).
- **ForceClose** (`extensions/force-close-handler.ts`) — cross-server forced disconnect (e.g. content-too-large 413, page locked/archived), coordinated via Redis.

**How it connects to the backend:** Pure HTTP via axios. `apps/live/src/services/api.service.ts` (`APIService`, base `env.API_BASE_URL`, `withCredentials`). Page services under `apps/live/src/services/page/`:
- `handler.ts` — `getPageService(documentType, context)`; **CE only supports `documentType === "project_page"`** → `ProjectPageService`; anything else throws.
- `project-page.service.ts` — sets `basePath = /api/workspaces/{slug}/projects/{projectId}`, injects the user's `Cookie` header.
- `core.service.ts` (`PageCoreService`) — REST calls: `GET …/pages/{id}/`, `GET/PATCH …/pages/{id}/description/` (binary), `PATCH …/pages/{id}/` (properties/title), `…/pages/{id}/mentions/`, plus asset-URL resolution via 302 following.
- `extended.service.ts` — abstract stub; comment states the real extended impl "is found in the enterprise repository." **This is the seam where EE adds workspace/team page services.**

**How it connects to the frontend / what it syncs:**
- Auth: `apps/live/src/lib/auth.ts` `onAuthenticate` — reads a JSON `token` (`{ id, cookie }` = `TUserDetails`) plus request cookies; validates by calling backend `currentUser(cookie)` (`services/user.service.ts`) and matching `userId`. Context carries `{ documentType, projectId, workspaceSlug, userId, cookie }` (`apps/live/src/types/index.ts`, `HocusPocusServerContext`; `TDocumentTypes = "project_page"` in CE).
- Stateless events: `apps/live/src/lib/stateless.ts` relays `DocumentCollaborativeEvents` (locked/unlocked/archived, etc.) from `@plane/editor/lib` to all clients.
- **Documents synced = Plane Pages** (project pages in CE). Each Yjs doc has two fragments: `default` (body) and `title`. Persisted as `Page.description_binary` in Postgres via the backend.

**Frontend connection point:** `apps/web/core/components/pages/editor/editor-body.tsx` (~L190) builds the WS URL: `LIVE_BASE_URL` (from `@plane/constants`, `LIVE_BASE_PATH`) + `/collaboration`, `ws→wss` by page protocol, and appends `webhookConnectionParams` (`TWebhookConnectionQueryParams` = `{ documentType, projectId, workspaceSlug }`). The editor's `HocuspocusProvider` is created in `packages/editor/src/core/hooks/use-yjs-setup.ts` (`name: docId`, `token`, `url`).

---

## 2. `packages/editor` (`@plane/editor`) — the rich-text editor

**Engine:** **TipTap v2 / ProseMirror**, React node views, Yjs collaboration. Deps include `@tiptap/*`, `@tiptap/starter-kit`, `@tiptap/extension-collaboration`, `y-prosemirror`, `y-protocols`, `y-indexeddb` (offline), `@hocuspocus/provider`, `tiptap-markdown`, `lowlight` (code highlighting), `prosemirror-codemark`.

**Layout / build:** `src/core/` (shared engine), `src/ce/` (community), `src/ee/` (enterprise). `packages/editor/tsconfig.json` aliases **`@/plane-editor/* → ./src/ce/*`** (EE build swaps this to `ee`). `src/ee/extensions/index.ts` currently just re-exports `src/ce/extensions`. Public entry: `src/index.ts`; server helpers: `src/lib.ts` (imported by `apps/live` as `@plane/editor/lib`).

**Editor variants** (`src/core/components/editors/`): `document/` (collaborative page editor), `rich-text/`, `lite-text/`. The collaborative document editor: `document/collaborative-editor.tsx` → `use-collaborative-editor.ts` → `use-editor.ts` + `use-title-editor.ts`. Collaboration is wired with two `Collaboration.configure({ document: provider.document, field: "default" | "title" })` instances (body + title share one Yjs doc). History is disabled in collab mode (Yjs owns undo).

**Document storage / serialization** (`src/core/helpers/yjs-utils.ts`): the canonical format is the **Yjs binary** (`Page.description_binary`, base64). Helpers convert among binary / ProseMirror-JSON / HTML using two schemas built from extension lists:
- `RICH_TEXT_EDITOR_EXTENSIONS = CoreEditorExtensionsWithoutProps`
- `DOCUMENT_EDITOR_EXTENSIONS = Core + DocumentEditorExtensionsWithoutProps` (`src/core/extensions/core-without-props.ts`).
- Key fns: `getBinaryDataFromDocumentEditorHTMLString`, `getAllDocumentFormatsFromDocumentEditorBinaryData` (also extracts `title` fragment), `convertHTMLDocumentToAllFormats`, `applyUpdates`. Yjs fragment names: `"default"` (body) and `"title"`.

**Extension architecture (how to add a new node / embed type):**
- Extension keys enumerated in `src/core/constants/extension.ts` (`CORE_EXTENSIONS` enum; `BLOCK_NODE_TYPES`). Feature-gating type is `TExtensions` (disabled/flagged extensions).
- **Node/embed pattern** — see the existing embed, `src/core/extensions/work-item-embed/`:
  - `extension-config.ts`: `Node.create({ name: CORE_EXTENSIONS.WORK_ITEM_EMBED /* "issue-embed-component" */, group: "block", atom: true, selectable, draggable, addAttributes, parseHTML: [{ tag: "issue-embed-component" }], renderHTML })`.
  - `extension.tsx`: `WorkItemEmbedExtensionConfig.extend({ addNodeView() { return ReactNodeViewRenderer(...) } })` driven by a `widgetCallback` prop (host app supplies the React renderer).
  - Embeds are **atom block nodes** rendered as custom HTML tags so they survive the HTML↔binary round-trip and are detectable server-side.
- **Registration for the collaborative document editor:** `src/ce/extensions/document-extensions.tsx` exposes a `DocumentEditorAdditionalExtensions(props)` **registry** (`extensionRegistry: { isEnabled, getExtension }[]`) — currently only registers `SlashCommands`. `use-collaborative-editor.ts` spreads these in. Additional node registration also flows through `src/ce/extensions/index.ts` (→ `./core`, `./document-extensions`, `./slash-commands`) and `src/ce/extensions/rich-text-extensions.tsx`.
- **Embed config surface (host side):** `src/ce/types/issue-embed.ts` — `TEmbedConfig = { issue?: TIssueEmbedConfig }` with a `widgetCallback`. Today only `issue`. Editor-side embed type union: `TPageEmbedType = "mention" | "issue"` (`packages/types/src/page/core.ts`).
- Slash-command insertion: `src/core/extensions/slash-commands/` + `src/ce/extensions/slash-commands.tsx`. Mentions: `src/core/extensions/mentions/` (users + page mentions). Images/assets: `src/core/extensions/custom-image/`, `image/`.

> **Where a new embed (e.g. an AFFiNE-doc block or a page/sub-page embed) attaches:** add a `Node.create` config + `ReactNodeViewRenderer` under `packages/editor/src/core/extensions/<new>-embed/`, add its key to `CORE_EXTENSIONS`, register it in `src/ce/extensions/document-extensions.tsx` (and a slash command), extend `TEmbedConfig`/`TPageEmbedType`, and — critically — teach the backend `page_transaction` component map (below) about the new custom tag so references are tracked.

---

## 3. Pages — backend model + frontend; nesting, embeds, Wiki, external AFFiNE

### Backend model — `apps/api/plane/db/models/page.py`
- `Page(BaseModel)`: `workspace` FK; `name`; `description_json` / `description_binary` / `description_html` / `description_stripped`; `owned_by`; `access` (0=Public, 1=Private); `is_locked`; `archived_at`; `view_props`, `logo_props`; `is_global` (bool); `labels` M2M (via `PageLabel`); `projects` **M2M via `ProjectPage`**; `sort_order`.
- **NESTED PAGES ALREADY EXIST:** `parent = ForeignKey("self", related_name="child_page", null=True)`. Backend fully supports hierarchy — recursive-CTE archive/unarchive of descendants (`unarchive_archive_page_and_descendants` in `apps/api/plane/app/views/page/base.py` L59-72), reparenting rules on unarchive/delete, and `PageVersion.sub_pages_data` (JSON snapshot of sub-pages).
- **EXTERNAL-INTEGRATION HOOKS ALREADY PRESENT:** `external_id` and `external_source` CharFields on `Page`. **This is the natural attach point for an external-doc (AFFiNE) mapping** — e.g. `external_source="affine"`, `external_id=<affine doc id>`.
- `PageLog` — reference/back-link index: `(page, transaction)` unique; `entity_name`, `entity_type`, `entity_identifier`. Type choices include `issue`, `image`, `page_mention`, `user_mention`, `back_link`, `forward_link`, `cycle`, `module`, `link`, `file`, etc. **This is the embed/mention tracking table.**
- `PageVersion` — version history (binary + html + json + `sub_pages_data`).

### Backend views/serializers/urls
- Views: `apps/api/plane/app/views/page/base.py` (`PageViewSet`, `PageFavoriteViewSet`, `PagesDescriptionViewSet` — the binary `GET/PATCH …/description/` used by `apps/live`; `PageDuplicateEndpoint`), `.../page/version.py`. URLs: `apps/api/plane/app/urls/page.py`.
- List/summary queries filter **`parent__isnull=True`** (only top-level pages returned to the list UI; children fetched per-parent). Access filter `Q(owned_by=user) | Q(access=0)`. Guest handling inline (see §4).
- Serializers: `apps/api/plane/app/serializers/page.py` (`PageSerializer`, `PageDetailSerializer`, `PageBinaryUpdateSerializer`).
- Embed/mention extraction on save: `apps/api/plane/bgtasks/page_transaction_task.py` — `page_transaction` parses `description_html` with BeautifulSoup against a `COMPONENT_MAP` (currently `mention-component`, `image-component`) and diffs old vs new to insert/delete `PageLog` rows. **A new embed tag must be added here to be tracked.** Related bgtasks: `page_version_task.py`, `copy_s3_object.py`.

### Frontend (`apps/web`)
- Routes: `apps/web/app/(all)/[workspaceSlug]/(projects)/projects/(detail)/[projectId]/pages/(list)` and `.../pages/(detail)/[pageId]`; feature toggle at `.../settings/projects/[projectId]/features/pages`.
- Components: `apps/web/core/components/pages/` — `editor/` (incl. `editor-body.tsx` = live/collab wiring, `content-limit-banner.tsx`, `ai/`, `summary/`, `toolbar/`), `list/`, `navigation-pane/` (outline + info tab-panels), `version/`, `modals/`, `dropdowns/`, `header/`.
- Stores (MobX): `apps/web/core/store/pages/` — `base-page.ts`, `extended-base-page.ts`, `project-page.ts`, `project-page.store.ts`, `page-editor-info.ts`. `base-page.ts` exposes `updateAccess`, public/private toggles, submit-state.
- Types: `packages/types/src/page/` — `core.ts` (`TPage`, `TPageVersion`, `TDocumentPayload`, `TPageEmbedType = "mention"|"issue"`, and `TWebhookConnectionQueryParams.documentType = "project_page" | "team_page" | "workspace_page"`). `extended.ts` = `TPageExtended = object` (**CE stub; EE augments `TPage` here** — this is where `parent_id`, `sub_pages_count`, team/workspace fields land in EE). Wiki empty-state assets already shipped: `apps/web/app/assets/empty-state/wiki/`, `.../wiki/navigation-pane/`.

### Gap analysis — "Nested Pages + Embeds", "Workspace Wiki", external AFFiNE
- **Nested pages:** data model + hierarchy ops are done. Gaps are mostly UI/type surface (`TPageExtended` stub, list view only returns top-level, a tree/expand UI in `navigation-pane`) and a page-embed/sub-page node in the editor (mirror `work-item-embed`). A sub-pages API for children under a parent may need surfacing (EE territory).
- **Embeds:** framework exists (atom nodes + `widgetCallback` + `PageLog`/`page_transaction`). Adding a type = editor node + host `widgetCallback` + register in `document-extensions.tsx` + extend `page_transaction` `COMPONENT_MAP`. A **page-embed / mention** of another page and an **external-doc embed** both follow this path.
- **Workspace Wiki:** the substrate exists (`Page.is_global`, `Page.workspace` without a project, `documentType` enum already lists `workspace_page`/`team_page`). Missing in CE: (a) `apps/live` `getPageService` + `TDocumentTypes` only handle `project_page` — needs a `WorkspacePageService` (the `extended.service.ts` stub is the seam); (b) workspace-scoped page REST endpoints (`/api/workspaces/{slug}/pages/…`); (c) frontend workspace-level pages routes/stores; (d) `TPageExtended` fields. Much of this is what EE ("enterprise repository") supplies.
- **External AFFiNE integration — where it attaches:** use `Page.external_source`/`external_id` to map a Plane page/wiki node to an AFFiNE doc. Backend: a new service/adapter (parallel to `apps/api/plane/db/models/integration/` and the intake source pattern) plus optional sync bgtask. Editor: an "external doc" atom-node embed (as in §2) that renders/links the AFFiNE doc via `widgetCallback`. Live server: if AFFiNE round-trips Yjs, an alternate `documentType` + page-service in `apps/live/src/services/page/` (again via the `extended.service.ts` seam). Keep AFFiNE integration **optional** — gate via `TExtensions` disabled/flagged list and a config flag.

---

## 4. `apps/space` — public / guest-facing app; Guest Access

**What it is:** A separate **React Router (framework mode, ex-Remix)** SPA (not Next.js; ships a `next`-compat shim in `apps/space/app/compat/next/`). Deps: `react-router`, `@react-router/serve`, `mobx`, `swr`, `@plane/editor`, `@plane/services`. Served behind its own nginx (`apps/space/nginx/`).

**What it exposes:** **Published boards only, keyed by a `DeployBoard.anchor`** (opaque token). Routes (`apps/space/app/`):
- `app/[workspaceSlug]/[projectId]/page.tsx` — resolves publish settings by project; **only `entity_name === "project"` is handled → redirects to `/issues/{anchor}`; everything else → `/404`.**
- `app/issues/[anchor]/page.tsx` + `layout.tsx` — renders the published **issue board** (`IssuesLayoutsRoot`), peek overview, filters, reactions/votes/comments per publish flags.
- `app/page.tsx`, `app/root.tsx`, `app/not-found.tsx`, `app/error.tsx`.
- **No page/wiki route exists in the Space app today** — only issue boards + intake. Editor usage in space is issue descriptions only (`apps/space/components/editor/rich-text-editor.tsx`, `lite-text-editor.tsx`, `embeds/mentions/`).

**Publish model:** `DeployBoard` (`apps/api/plane/db/models/deploy_board.py`) — `anchor` (unique, default `uuid4().hex`), `entity_name` **TYPE_CHOICES include `project, issue, module, cycle, page, view, intake`** (so `page` publishing is modeled but **not served by the CE Space backend/frontend**), `is_comments_enabled`, `is_reactions_enabled`, `is_votes_enabled`, `is_activity_enabled`, `is_disabled`, optional `intake` FK. Frontend store: `apps/space/store/publish/{publish.store.ts,publish_list.store.ts}` (anchor→`PublishStore`, exposes `canComment/canReact/canVote`); hooks `apps/space/hooks/store/publish/`. Publish settings fetched via `SitesProjectPublishService` (`@plane/services`).

**How anonymous / guest access works:**
- Space backend module: `apps/api/plane/space/` (views/serializers/urls). URL groups (`plane/space/urls/__init__.py`): intake, issue, project, asset.
- **Anonymous read is `AllowAny`**: `plane/space/views/{issue,cycle,module,label,meta,project}.py` set `permission_classes = [AllowAny]` (issue view flips to `IsAuthenticated` only for write actions like comments/reactions — see `issue.py` L222-224). Base viewset default is `IsAuthenticated` (`plane/space/views/base.py` L48) with `BaseSessionAuthentication`; assets use `AllowAny` for GET, `IsAuthenticated` for upload (`asset.py` L30-33). All queries are scoped by `anchor`→`DeployBoard`.
- **"Guest" (in-app role) is distinct from anonymous space visitors.** In the main app, guest = `ROLE.GUEST` / `role=5` on `ProjectMember`, gated by `project.guest_view_all_features`. Enforced in Pages: `apps/api/plane/app/views/page/base.py` `retrieve`/`list`/`summary` restrict guests to their own pages unless `guest_view_all_features` is set. Relevant to any "Guest Access" feature — two separate concepts: (a) anonymous public via published `anchor` (Space app), (b) authenticated Guest role with limited visibility.

---

## 5. Intake (forms / email-to-issue) scaffolding

**Models** — `apps/api/plane/db/models/intake.py`:
- `Intake(ProjectBaseModel)`: per-project intake config (`name`, `description`, `is_default`, `view_props`, `logo_props`).
- `IntakeIssue(ProjectBaseModel)`: links `intake`↔`issue`; `status` (`IntakeIssueStatus`: PENDING/REJECTED/SNOOZED/ACCEPTED/DUPLICATE); `snoozed_till`; `duplicate_to`; **`source`** (default `"IN_APP"`); **`source_email`** (TextField — email-to-issue field is present); `external_source` / `external_id`; `extra` JSON.
- `SourceType(TextChoices)`: **only `IN_APP` in CE** — no `EMAIL`/`FORMS`/`SLACK` enum values shipped. So **email-to-issue is scaffolded at the data layer (`source_email`, `source`, `external_source`) but not implemented in CE** (no email-ingestion pipeline; `EMAIL_*` settings are only outbound SMTP for notifications). Adding email-to-issue = new `SourceType` value + an inbound mail worker that creates `IntakeIssue` with `source="EMAIL"`, `source_email=<from>`.

**Views / endpoints:**
- In-app: `apps/api/plane/app/views/intake/base.py` — creates issues into the triage state and an `IntakeIssue` with `source=SourceType.IN_APP` (L277).
- **Public guest submission (forms-to-issue):** `apps/api/plane/space/views/intake.py` `IntakeIssuePublicViewSet` — `list`/`create` by `anchor`, requires the project's `DeployBoard.intake` to be set; `create` (L108) validates name/priority, sanitizes `description_html` (XSS fix GHSA-hh2r-3hwp-mvq3), creates the Issue in Triage state + `IntakeIssue`. This is the public intake **form** path used by the Space app.
- Also: `apps/api/plane/api/views/intake.py` (external REST API) and serializers under `plane/{app,api,space}/serializers/intake.py`.
- Space frontend: intake submission assets exist (`apps/space/app/assets/instance/intake-sent-*.png`); intake is one of the four Space URL groups.
- DeployBoard supports publishing an `intake` (the `intake` FK) so a project board can expose a public intake form.

---

## Key file index
- Live server: `apps/live/src/{server.ts,hocuspocus.ts,start.ts}`, `apps/live/src/extensions/{index.ts,database.ts,redis.ts,title-sync.ts,force-close-handler.ts}`, `apps/live/src/controllers/collaboration.controller.ts`, `apps/live/src/lib/auth.ts`, `apps/live/src/services/page/{handler.ts,core.service.ts,project-page.service.ts,extended.service.ts}`, `apps/live/src/types/index.ts`.
- Editor: `packages/editor/src/core/helpers/yjs-utils.ts`, `packages/editor/src/core/hooks/{use-collaborative-editor.ts,use-yjs-setup.ts}`, `packages/editor/src/core/components/editors/document/collaborative-editor.tsx`, `packages/editor/src/core/extensions/work-item-embed/{extension-config.ts,extension.tsx}`, `packages/editor/src/core/constants/extension.ts`, `packages/editor/src/ce/extensions/{index.ts,document-extensions.tsx}`, `packages/editor/src/ce/types/issue-embed.ts`, `packages/editor/tsconfig.json` (`@/plane-editor → src/ce`).
- Pages backend: `apps/api/plane/db/models/page.py`, `apps/api/plane/app/views/page/base.py`, `apps/api/plane/app/urls/page.py`, `apps/api/plane/bgtasks/page_transaction_task.py`, `apps/api/plane/app/serializers/page.py`.
- Pages frontend: `apps/web/core/components/pages/editor/editor-body.tsx`, `apps/web/core/store/pages/*`, `packages/types/src/page/{core.ts,extended.ts}`.
- Space: `apps/space/app/{page.tsx,issues/[anchor]/page.tsx,[workspaceSlug]/[projectId]/page.tsx}`, `apps/space/store/publish/*`, `apps/api/plane/db/models/deploy_board.py`, `apps/api/plane/space/views/{base.py,issue.py,intake.py}`.
- Intake: `apps/api/plane/db/models/intake.py`, `apps/api/plane/app/views/intake/base.py`, `apps/api/plane/space/views/intake.py`, `apps/api/plane/api/views/intake.py`.
