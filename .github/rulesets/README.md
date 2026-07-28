<!-- woven: plane-7fn.4.10 -->
# Repository rulesets (governance-as-code)

These JSON files are the source-of-truth definitions for the repo's GitHub **rulesets**. GitHub has
no native "apply rulesets from the repo" sync, so they are applied via the REST API and kept here
for review + reproducibility. Edit the JSON, then re-apply with the commands below.

## Live rulesets

| File | Target | Enforcement | Rules |
|------|--------|-------------|-------|
| `main-branch.json` | `refs/heads/main` | **active** | require PR (0 approvals, conversation resolution, squash-only), required status checks (`check:lint`, `check:types`, `check:format`, `Build packages`, `Copy Right Check`), require signed commits, linear history, block force-push, block deletion |
| `release-tags.json` | `refs/tags/v*` | **active** | block deletion, block non-fast-forward (released tags are immutable) |

**No bypass actors.** release-please operates entirely through pull requests merged via GitHub's
web-flow squash (which is signed → Verified) and by *creating* new `v*` tags (allowed — only
delete/update are blocked), so nothing needs to bypass these rules. If a ruleset ever blocks
legitimate work, a repo admin can edit/disable it in **Settings → Rules**.

## Apply / update

```bash
# Create (first time):
gh api -X POST repos/aRustyDev/plane/rulesets --input .github/rulesets/main-branch.json
gh api -X POST repos/aRustyDev/plane/rulesets --input .github/rulesets/release-tags.json

# Update an existing ruleset (find <id> via the list below):
gh api repos/aRustyDev/plane/rulesets --jq '.[] | "\(.id)\t\(.name)"'
gh api -X PUT repos/aRustyDev/plane/rulesets/<id> --input .github/rulesets/main-branch.json
```

## Required status checks — why this exact set

Only checks that run on **every** PR and are reliably green are required, because a required check
that doesn't report (or is red) blocks the merge:

- Included: `check:lint`, `check:types`, `check:format`, `Build packages`, `Copy Right Check`.
- **Excluded (for now):** `dependency-review` (currently failing — see follow-up), `CodeQL` /
  `Analyze (*)` (often reports `neutral`), the API build (path-filtered to `apps/api/**`, so it
  doesn't run on every PR), and third-party `Socket Security` checks. Expand once they're stable.

These required checks are also the gate that makes **Dependabot auto-merge** safe
(`.github/workflows/dependabot-auto-merge.yml`): patch & minor bumps merge only after they pass.

## Deferred

- **Push rulesets** (protect `.github/workflows`, block binary blobs, commit-message pattern):
  the metadata rules (`commit_message_pattern`, `file_path_restriction`, …) are **Enterprise/org-only**
  and are rejected on this user-owned repo. Commit-message conformance is already enforced by the
  commitlint `commit-msg` hook + PR title convention, so this is low loss. Revisit if the repo moves
  under an organization.
- **Release App on the bypass list + `v*` creation restriction:** not required with the current
  rule set (see above); add if direct-to-main automation is ever introduced.
