# Customers (CRM integration or CRM API)

**Goal:** Model "Customers" as first-class objects that link customer requests/feedback to work
items, so teams can see which accounts want which features. Either sync an external CRM or expose
a Plane CRM-style API — see **D-CRM** below.

**Parity target:** Plane **Business** "Customers" (+ Woven CRM tie-in).

**Background (grounded):** **No customer model exists in CE** — recon confirms all "customer"
grep hits are incidental seed strings (integrations-workflow §1). Reusable spines: public REST
`/api/v1/` with PAT auth (`X-Api-Key`, `api/middleware/api_authentication.py`), the
`external_source`/`external_id` idempotency fields, and outbound webhooks
(`bgtasks/webhook_task.py`). Work item is `Issue` (`db/models/issue.py`, `ProjectBaseModel`).

**Approach:**
- *Models/migrations (new app `plane/customers/`):* `Customer(WorkspaceBaseModel)` → `name`,
  `domain`, `contacts` (JSON), `external_source`/`external_id`, `logo_props`.
  `CustomerRequest(WorkspaceBaseModel)` → `customer` FK, `name`, `description`, `priority`.
  `CustomerRequestIssue` join → request ↔ `Issue` (M2M through, project-scoped issue).
  All with `deleted_at` + partial-unique (data-model §5). Register in `db/models/__init__.py`.
- *API:* CRUD on both `/api/` (UI) and `/api/v1/` (external), registered in
  `api/urls/__init__.py` mirroring the `intake` pattern. `external_source`/`external_id` make
  CRM upserts idempotent. Emit `customer`/`customer_request` webhook events via the fan-out
  (extend `SERIALIZER_MAPPER`/`MODEL_MAPPER`).
- *Frontend:* Customers workspace section — list, detail (linked requests + work items),
  request→work-item linker on the peek view.
- *(Option A) External CRM sync:* a `WorkspaceIntegration` (provider `crm`) + poller/webhook
  receiver mapping CRM accounts/opportunities → `Customer`/`CustomerRequest`, keyed on
  `external_id`.

**D-CRM — recommendation: expose a Plane CRM-style API (Option B), with a thin optional
importer.** Rationale: Woven has no standard CRM to integrate; building sync to a nonexistent
system is speculative. Native objects + `/api/v1/` give immediate value, keep data in Plane's
RBAC/audit boundary, and still let any CRM push via idempotent `external_id` upserts later —
Option A becomes a bolt-on, not a prerequisite.

**Feature flag:** `customers` (Phase-0 F0.1). External-CRM sync gated by the `crm`
`WorkspaceIntegration`.

**Tasks (→ child beads):** 1) Customer/Request/link models + migration. 2) App+v1 CRUD. 3)
Webhook event wiring. 4) Customers UI + request↔issue linker. 5) (opt) CRM importer. 6) Docs +
acceptance tests.

**Acceptance:** *API* — create Customer + Request via `/api/v1/`, link to an Issue; upsert by
`external_id` is idempotent; webhook fires on create/update. *UI* — Customers list + detail show
linked work items; linking from a work item persists.

**Risks / upstream-merge impact:** Low. Fully additive new app; no core edits beyond webhook
mapper extension (`# woven:`). Deferring Option A avoids coupling to an unchosen vendor.
