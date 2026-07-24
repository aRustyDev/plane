# F0.4 — `woven-ee` isolation convention + core-drift CI

**Goal:** A layout + marking convention that keeps fork features isolated for merge-ability, plus CI
that flags core-file drift against upstream so periodic merges from `makeplane/plane` stay tractable.

**Parity target:** N/A — engineering foundation for clean-room, mergeable development.

**Background (today).** CE has no `ee/` backend app; our features complete absent EE layers clean-room
(PROGRAM.md §2.5). Existing seams the convention builds on: *Backend* —
`apps/api/plane/utils/instance_config_variables/extended.py` (empty list, verified) and the
`apps/live` `extended.service.ts` stub. *Frontend* — the route seam
`apps/web/app/routes/extended.ts` (`extendedRoutes = []`, deep-merged by `mergeRoutes` in
`app/routes.ts`); the editor `packages/editor/src/{ce,ee}/` split (tsconfig aliases
`@/plane-editor → src/ce`; `src/ee` re-exports `ce`); the no-op custom-props hook
`apps/web/core/hooks/use-workspace-issue-properties-extended.tsx`; the `TPageExtended` type
(`packages/types/src/page/extended.ts`); and many `*-extended.ts(x)` injection points.
CI already present in `.github/workflows/`: `copyright-check.yml` runs
`addlicense -check -f COPYRIGHT.txt` over all `.py`/`.ts(x)` (migrations ignored); plus
`build-branch.yml` and lint workflows. Fork base = `makeplane/plane` @ `preview`, pinned to `v1.3.1`.

**Approach.** *Convention (documented in-repo):* net-new backend features go in **new Django apps**
`apps/api/plane/woven_<feature>/` (models/serializers/views/urls/migrations), each composed into
`apps/api/plane/urls.py` via a single `include()`. New frontend surfaces slot into
`app/routes/extended.ts`, the editor `ce/ee` seams, `*-extended` hooks, and new `packages/*`. New
shared config goes in `extended.py`, never `core.py`. Migrations stay additive (new tables/columns,
reversible). *`# woven:` markers:* every unavoidable edit to an upstream-owned file is bracketed with a
`# woven: <reason>` (Python) / `// woven:` (TS) comment so it is greppable and reviewable.
*CI — core-drift guard:* a new `woven-core-drift.yml` that (a) diffs a PR's upstream-owned files
against a pinned upstream base ref, (b) requires each such hunk to carry a `# woven:` marker or an
allowlist entry, (c) fails otherwise — turning silent core edits into an explicit, reviewed decision.
New files get the `COPYRIGHT.txt` header so `copyright-check` stays green.

**Feature flag.** N/A — build-time convention + CI.

**Tasks.** 1) write the convention page (app layout, seams, markers, additive-migration rule);
2) add `woven-core-drift.yml` (pinned upstream ref + marker check); 3) seed an upstream-ownership map
(`.woven/core-files.txt` or CODEOWNERS); 4) marker lint (grep) + copyright header on new files;
5) document the upstream-merge runbook (fetch upstream, rebase, resolve only marked hunks).

**Acceptance.** *CI:* a PR editing a core file without `# woven:` fails `woven-core-drift`; adding the
marker passes; `copyright-check` stays green. A new feature app is importable and `include()`d with
zero core edits. A trial `git merge upstream/preview` surfaces conflicts only inside marked regions.

**Risks / upstream-merge impact.** This *is* the merge-impact control. Risk: over-marking or a stale
ownership map; mitigate by pinning the upstream ref (per D-BASE) and re-reviewing on each upstream bump.
