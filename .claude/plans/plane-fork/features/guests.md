# Guests & Guest Access

**Goal:** Upgrade the coarse Guest role into real **per-entity guest sharing** — invite external
guests to specific projects/work-items/pages with scoped, minimal access, distinct from internal
members.

**Parity target:** Plane Commercial **Pro/Business** (Guest access).

**Background** (cite exact files/models): Guest is already a first-class role (value **5**) at
workspace + project scope (`db/models/workspace.py`, `db/models/project.py`;
`research/auth-permissions.md §2.1/§5`). Enforcement: `@allow_permission([...ROLE.GUEST...])`
gates endpoints; guest visibility is filtered via `ProjectMember.role` +
`Project.guest_view_all_features` (`app/views/issue/base.py:1039-1050`, `db/models/project.py:100`).
Workspace→Guest demotion cascades project roles (`app/views/workspace/member.py:88-89`). **Gaps:**
no per-entity guest sharing, no external-guest identity distinction beyond the role, no
guest-scoped audit. The reusable hook is the comment `access` field with `INTERNAL/EXTERNAL`
values (`db/models/issue.py:467`).

**Approach:**
- *Backend models + migrations (additive):* add an `is_external` / guest-origin marker on the
  guest membership (or a `GuestProfile` extension) to distinguish external guests. Reuse the
  ReBAC `AccessGrant` tuple (see `rebac-fine-grained.md`) as the sharing primitive: a guest gets
  an `AccessGrant(subject=guest, relation=viewer, object=<entity>)` instead of broad project
  membership. Propagate the `INTERNAL/EXTERNAL` `access` pattern (`issue.py:467`) to
  attachments/links surfaced to guests. Soft-delete conventions per `backend-data-model.md §5`.
- *API:* guest-invite endpoint that creates a scoped grant (not full membership); guest
  querysets restricted to granted entities + explicitly-shared items only. *Frontend:* "Share
  with guest" action on project/work-item/page (email + entity + view/comment level); a guest
  landing view that shows only shared entities.

**Feature flag:** `GUEST_ACCESS_ENABLED` (F0.1); off ⇒ current coarse Guest role behavior.

**Tasks (→ child beads):** (1) external-guest marker + guest-origin migration; (2) per-entity
guest grant reusing `AccessGrant`; (3) guest queryset scoping in `issue/base.py` (+ pages,
attachments); (4) guest-invite API; (5) share-with-guest UI + guest landing view; (6) guest
actions surfaced in the audit log (see `audit-logging.md`).

**Acceptance:** *API* — invite an external guest to one work-item → guest reads only that item,
403 on siblings; comment `access=EXTERNAL` visible, `INTERNAL` hidden. *UI* — "Share with guest"
sends invite; guest sees only shared entities.

**Risks / upstream-merge impact:** Depends on **RBAC** and reuses the **ReBAC** grant primitive
(sequence after both). Guest scoping edits concentrate in `issue/base.py` querysets — must not
loosen existing `guest_view_all_features` behavior when the flag is off. Preserve the integer
Guest role for upstream compatibility; mark `# woven:` edits.
