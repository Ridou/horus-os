# Releasing horus-os

This doc captures the manual release procedure the maintainer runs
for every v0.x. Each release follows the same sequence (pricing
refresh, release gate, version bumps, CHANGELOG promotion, tag,
GitHub Release). v0.4 added the `scripts/release_gate.py` step
before the tag; everything else mirrors how v0.1 through v0.3 were
released.

## Pre-release checklist

1. Verify CI is green on `main` for the latest commit:
   `gh run list --branch main --limit 1`.
   Expect SUCCESS for the full 3-OS x 2-Python matrix including
   the `install-smoke-no-otel`, `install-smoke-with-otel`, and
   `install-smoke-plugin` jobs.
2. Confirm no open PRs need merging before the tag.
3. Confirm all phase SUMMARY files for the milestone are committed
   under `.planning/phases/`.
4. Run the release gate locally:
   `python scripts/release_gate.py` (see the release-gate section
   below).

## Release gate

`scripts/release_gate.py` is a local pre-tag quality gate. It runs
eight checks and exits 0 only when all enabled checks pass.

The four v0.4 checks:

- `pricing-freshness`: `src/horus_os/observability/pricing.json`
  `updated_at` is within 14 days of today. The default 14-day
  threshold is the REL-08 contract.
- `ci-two-variant-smoke`: `.github/workflows/ci.yml` contains both
  the `install-smoke-no-otel` and `install-smoke-with-otel` job
  literals. Closes Pitfall 12 by catching install-matrix regression
  before it ships.
- `wheel-pricing-bundle`: `python -m build --wheel` succeeds AND
  the produced wheel contains a `horus_os/observability/pricing.json`
  member. Catches regression in the
  `[tool.setuptools.package-data]` wiring.
- `pytest`: `python -m pytest -q` from the repo root exits 0.

v0.5 extends the gate with four additional checks: `docs-drift`
(between `MANIFEST_V1_SCHEMA` and `docs/manifest-v1.schema.json`),
`plugin-install-smoke-ci` (asserts the `install-smoke-plugin` job is
present in `ci.yml`), `reference-plugin-manifest-valid` (runtime
`validate_manifest()` accepts
`examples/horus-os-example-plugin/horus-plugin.toml` with zero
errors), and `v0-4-fixture-roundtrip`
(`tests/fixtures/v0_4_database.sqlite3` survives the v5 to v6
migration with all three new plugin tables, two new `plugin_name`
columns, and one new index present). Default invocation runs all
EIGHT checks (4 v0.4 + 4 v0.5).

Exit semantics: 0 on full pass; 1 if any check fails. The runner
prints one diagnostic per failing check rather than
short-circuiting, so the maintainer sees everything in one pass.

Environment overrides:

- `HORUS_OS_PRICING_MAX_AGE_DAYS=14` (default 14, the REL-08
  contract). Raise only with a code review trail.
- `HORUS_OS_RELEASE_GATE_SKIP_BUILD=1` skips the wheel build for
  fast local iteration during debugging.
- `HORUS_OS_RELEASE_GATE_SKIP_TESTS=1` skips the pytest invocation
  (useful when running the gate inside a test fixture).

CLI flags:

- `--check pricing|wheel|ci|tests|docs-drift|plugin-install|reference-manifest|fixture-roundtrip`
  runs only the named check.
- `--skip-build` is the alias for `HORUS_OS_RELEASE_GATE_SKIP_BUILD=1`.

If `pricing-freshness` fails, follow the refreshing-pricing
section below before re-running the gate.

## Refreshing pricing.json

The bundled `src/horus_os/observability/pricing.json` carries
LLM rate cards for every model horus-os recognizes. The release
gate blocks any release where `updated_at` is older than 14 days,
so the typical pre-release flow includes a 5-minute refresh.

Source: LiteLLM's `model_prices_and_context_window.json` at
`https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json`.

Procedure:

1. Open the LiteLLM source and the local `pricing.json` side by
   side.
2. For each Anthropic Claude and Google Gemini model in the local
   file, compare the four rates (`input_per_million`,
   `output_per_million`, `cache_write_per_million`,
   `cache_read_per_million`) against the LiteLLM values. Copy any
   updates.
3. Add any newly-supported models the project plans to recognize.
4. Bump the top-level `updated_at` field to today's ISO date
   (`YYYY-MM-DD`).
5. Commit: `chore(release): refresh pricing.json (release N.M.P prep)`.

The 5-minute mechanical task that closes Pitfall 5.

## Refreshing docs/manifest-v1.schema.json

The runtime pydantic schema (`MANIFEST_V1_SCHEMA` in
`src/horus_os/plugins/manifest.py`) and the bundled JSON Schema
(`docs/manifest-v1.schema.json`) must stay byte-identical. The
release gate's `docs-drift` check refuses to tag when they diverge.

Procedure:

1. Run `python scripts/build_manifest_schema.py`. The script is
   idempotent; running it twice in a row produces no diff.
2. If `git diff docs/manifest-v1.schema.json` shows changes, commit
   them with `chore(release): regenerate docs/manifest-v1.schema.json`.

## Release procedure

The full sequence:

1. Refresh `pricing.json` if its `updated_at` is older than 14
   days (per the refreshing-pricing section above).
1b. Regenerate `docs/manifest-v1.schema.json` via
   `python scripts/build_manifest_schema.py` and commit the result
   if there is a diff. The `docs-drift` gate refuses to tag
   otherwise.
2. Run `python scripts/release_gate.py`. Confirm exit 0 and all
   eight checks pass.
3. Bump the version to `N.M.P` in TWO places:
   - `pyproject.toml` line 7: `version = "N.M.P"`.
   - `src/horus_os/__init__.py`: `__version__ = "N.M.P"`.
4. Promote `[Unreleased]` in `CHANGELOG.md` to
   `[N.M.P] - YYYY-MM-DD` (Keep a Changelog 1.1.0 format with
   Added / Changed / Fixed / Deprecated / Removed / Security
   sections as applicable). Leave a fresh empty `[Unreleased]`
   stub at the top for the next cycle.
5. Commit the version bump and CHANGELOG promotion:
   `chore(release): bump to N.M.P`.
6. Push to `main`. Wait for CI green on the full 3-OS x 2-Python
   matrix (`gh run list --branch main --limit 1`).
6.5. Confirm `gitsign` is configured. Run
     `git config --get gitsign.connectorID` and confirm the
     output is non-empty (typically
     `https://github.com/login/oauth`). If empty, follow the
     one-time gitsign setup in `docs/MAINTAINER-RUNBOOK.md`.
     Do not proceed to step 7 until configured.
7. Create the annotated tag:
   `git tag -s vN.M.P -m "vN.M.P - <milestone-name>"`.
   Push: `git push origin vN.M.P`.
8. Publish the GitHub Release. Extract the new CHANGELOG section
   into a tmp file and hand it to `gh release create`:
   ```
   awk '/^## \[N.M.P\]/,/^## \[/{print}' CHANGELOG.md | sed '$d' > /tmp/release-notes.md
   gh release create vN.M.P \
     --title "vN.M.P - <milestone-name>" \
     --notes-file /tmp/release-notes.md
   ```
   If the awk extraction is fragile for this milestone, paste the
   CHANGELOG section manually. Include a link to the migration
   doc (`docs/MIGRATION-vX.Y-to-vN.M.md`) if one exists.
9. Confirm the release is visible at
   `https://github.com/Ridou/horus-os/releases/tag/vN.M.P`.

## Post-release

- Update `.planning/STATE.md`:
  - `milestone` to the next milestone identifier (for example
    `v0.5`).
  - `progress.percent` and `progress.completed_phases` to reflect
    the just-shipped milestone.
- Open a tracking issue or note for the next milestone's planning
  phase.

## One-time repo settings checklist (v0.6 contribution-gate setup)

The v0.6 contribution-gate flip (Phase 59) assumes the following repo settings are enabled. They are one-time toggles; the maintainer runs through this list ONCE at v0.6 setup time and then never again. Each item includes a `gh api` verification command so the state can be re-confirmed if a downstream consumer asks.

### Private vulnerability reporting (GHSA)

Enable via Settings > Code security > Private vulnerability reporting > Enable. Or:

```
gh api -X PATCH /repos/Ridou/horus-os \
  --field security_and_analysis.private_vulnerability_reporting.status=enabled
```

Verify:

```
gh api /repos/Ridou/horus-os --jq '.security_and_analysis.private_vulnerability_reporting.status'
```

Expect `enabled`. This is the substrate the SECURITY.md reporting flow assumes.

### Dependabot alerts

Enable via Settings > Code security > Dependabot alerts > Enable. There is no documented `gh api` toggle for this scope; the UI is the source of truth. Verify by visiting the Security tab > Dependabot alerts; if the link is live (not "enable"), the feature is on.

### Dependabot security updates

Enable via Settings > Code security > Dependabot security updates > Enable. This is what causes Dependabot to auto-open PRs for advisories. Combined with the Phase 54 `.github/dependabot.yml` config (DEPBOT-02 hard rule: no `applies-to: security-updates` grouping), every advisory gets its own PR labelled `security-update`.

### Secret scanning + push protection

Enable via Settings > Code security > Secret scanning > Enable, then Push protection > Enable. Or:

```
gh api -X PATCH /repos/Ridou/horus-os \
  --field security_and_analysis.secret_scanning.status=enabled \
  --field security_and_analysis.secret_scanning_push_protection.status=enabled
```

Verify:

```
gh api /repos/Ridou/horus-os --jq '.security_and_analysis.secret_scanning.status, .security_and_analysis.secret_scanning_push_protection.status'
```

Expect both `enabled`.

### GitHub Discussions

Enable via Settings > General > Features > Discussions > Enable. Or:

```
gh api -X PATCH /repos/Ridou/horus-os --field has_discussions=true
```

Verify:

```
gh api /repos/Ridou/horus-os --jq '.has_discussions'
```

Expect `true`. Then create the four categories via the Discussions Settings UI (no `gh api` mutation path for categories):

- **General**: catch-all conversation.
- **Q&A**: question-with-marked-answer format.
- **Show and Tell**: user-built things on top of horus-os.
- **Ideas**: future-direction proposals (not concrete enough for an issue).

See `docs/MAINTAINER-RUNBOOK.md` Part 4 for the rationale per category.

The pinned "Project Status" Discussion post is created at v0.6.0 ship time as Phase 59 work.

## Why the release gate exists

The two pitfalls the gate closes:

- **Pitfall 5 (`pricing.json` rots silently between releases).**
  LLM rate cards move every few weeks. Without a freshness check,
  a release could ship pricing months out of date and every cost
  number reported by the dashboard or the CLI would silently
  drift. The 14-day threshold matches the typical cadence between
  bundled-pricing refreshes; raising it requires a code change
  visible in review. Source: `PITFALLS.md Pitfall 5`.
- **Pitfall 12 (`opentelemetry-*` leaks into the no-otel install
  variant).** The two-variant install-smoke matrix in CI
  (`install-smoke-no-otel` and `install-smoke-with-otel`) is the
  contract that proves the `[otel]` extra is the only path into
  the OpenTelemetry SDK. If a future maintainer drops one variant
  to "speed up CI," the contract silently breaks. The gate greps
  for both job names in the workflow YAML so the maintainer
  catches the regression locally before tagging. Source:
  `PITFALLS.md Pitfall 12`.

The gate is a LOCAL check the maintainer runs before tagging; it
does not run in CI. The CI matrix runs the install-smoke variants
themselves; the gate's job is to assert their presence so they
cannot disappear silently between releases.
