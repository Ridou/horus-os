---
phase: 50-v0-5-0-release
plan: "01"
subsystem: release
tags: [release, v0.5, rel-10, stop-before-tag, changelog-promotion, milestone-bookend]

# Dependency graph
requires:
  - phase: "40-01"  # v0.5 baseline artifact (tests/perf/v0_4_baseline.json)
  - phase: "41-01"  # Manifest schema, public API, v5->v6 persistence migration
  - phase: "42-01"  # Discovery + loading + failure isolation
  - phase: "43-01"  # PermissionGate + CapabilityGuard real enforcement + bounded asyncio.wait_for
  - phase: "44-01"  # Two-phase installer + horus-os plugins CLI surface (9 subcommands)
  - phase: "45-01"  # REST API + /plugins dashboard tab + per-plugin observability
  - phase: "46-01"  # Three-tier test fixtures + 12-pitfall regression suite
  - phase: "47-01"  # docs/PLUGINS.md + docs/PLUGIN-SECURITY.md + docs/MIGRATION-v0.4-to-v0.5.md + manifest schema + CHANGELOG draft
  - phase: "48-01"  # Reference plugin (examples/horus-os-example-plugin/) + TEST-21 surface lock
  - phase: "49-01"  # Three-OS install-smoke-plugin CI job + release_gate.py extended 4 -> 8 checks
provides:
  - "pyproject.toml: version bumped 0.4.0 -> 0.5.0"
  - "src/horus_os/__init__.py: __version__ bumped 0.4.0 -> 0.5.0"
  - "CHANGELOG.md: [0.5.0] - 2026-05-26 section dated from the v0.5 draft authored in Phases 47-49; fresh [Unreleased] stub inserted above; prior [0.4.0]/[0.3.0]/[0.2.0]/[0.1.0] sections preserved byte-identical"
  - "STOP-BEFORE-TAG block: reproduces the exact maintainer-only commands for git tag + git push + gh release create + STATE.md post-release update so the maintainer ships v0.5.0 after explicit approval"

requirements-completed:
  - REL-10  # Tag v0.5.0 with CHANGELOG and GitHub Release; docs/MIGRATION-v0.4-to-v0.5.md documents v5->v6 schema + the two new direct deps (pydantic>=2.7,<3, packaging>=24.0)

# Tech stack
tech-stack:
  added: []
  patterns:
    - "Release-gate-before-tag pattern (carried from v0.4 Phase 39, extended in v0.5 Phase 49): scripts/release_gate.py runs eight checks (pricing-freshness, ci-two-variant-smoke, wheel-pricing-bundle, pytest, docs-drift, plugin-install-smoke-ci, reference-plugin-manifest-valid, v0-4-fixture-roundtrip). Maintainer invokes it with no skip flags as the last automated step before `git tag -a v0.5.0`; Phase 50 reports six OK + two SKIP under the executor's `HORUS_OS_RELEASE_GATE_SKIP_BUILD=1 HORUS_OS_RELEASE_GATE_SKIP_TESTS=1` invocation because the wheel build and pytest are tag-time responsibilities the maintainer runs at full strength."
    - "STOP-BEFORE-TAG protocol (carried from v0.4 Phase 39): the executor prepares everything (version bumps, CHANGELOG promotion, SUMMARY, state files) but NEVER runs `git tag` or `gh release create` or pushes tags. Tag creation, GitHub Release publication, and STATE.md milestone roll-forward are user-confirmation gates documented in docs/RELEASE.md `## Release procedure` and reproduced verbatim in the maintainer-only commands block below."
    - "CHANGELOG promotion pattern (carried from v0.4 Phase 39): the [0.5.0] - YYYY-MM-DD draft authored across Phases 47-49 promotes to [0.5.0] - 2026-05-26 at release-bookend time. Heading rename only; body content (Added / Changed / Migration sections) round-trips byte-for-byte. Fresh empty [Unreleased] stub inserted above for the next cycle. Prior version sections untouched."
    - "Two-step version-literal sync: the executor bumps both `pyproject.toml [project] version` AND `src/horus_os/__init__.py __version__` in the same commit so `pip show horus-os` (which reads pyproject) and `from horus_os import __version__` (runtime introspection) never diverge. There is no third literal to keep in sync."

# Key files
key-files:
  created:
    - .planning/phases/50-v0-5-0-release/50-01-PLAN.md
    - .planning/phases/50-v0-5-0-release/50-01-SUMMARY.md
  modified:
    - pyproject.toml                  # one line: version "0.4.0" -> "0.5.0"
    - src/horus_os/__init__.py        # one line: __version__ "0.4.0" -> "0.5.0"
    - CHANGELOG.md                    # [0.5.0] - YYYY-MM-DD promoted to [0.5.0] - 2026-05-26; fresh [Unreleased] stub above
    - .planning/STATE.md              # milestone_complete status + last_activity stamp
    - .planning/ROADMAP.md            # Phase 50 row marked 1/1 Complete (pending maintainer tag)
    - .planning/REQUIREMENTS.md       # REL-10 status flipped to complete

decisions:
  - name: "STOP-BEFORE-TAG: executor commits version bumps + CHANGELOG + state updates but DOES NOT run `git tag` or `gh release create`"
    rationale: "Tag + GitHub Release + STATE.md milestone roll-forward are user-confirmation gates per the STOP-BEFORE-TAG protocol carried from v0.4 Phase 39. The maintainer runs them after explicit approval per docs/RELEASE.md `## Release procedure`. The plan's verification gate asserts `git tag -l v0.5.0` returns empty after execution."
  - name: "Release-gate invocation runs with --skip-build + HORUS_OS_RELEASE_GATE_SKIP_TESTS=1"
    rationale: "The wheel build (~30s) and full pytest (~26s) are the maintainer's tag-time responsibility per docs/RELEASE.md `## Release procedure` step 2 (which says `python scripts/release_gate.py` with no flags). Phase 50's executor reports the six fast checks (pricing-freshness, ci-two-variant-smoke, docs-drift, plugin-install-smoke-ci, reference-plugin-manifest-valid, v0-4-fixture-roundtrip) as green; the maintainer re-runs at full strength before tagging. Both SKIPs are honest output, not silent passes."
  - name: "CHANGELOG body content preserved byte-identical from the Phases 47-49 v0.5 draft"
    rationale: "The Added / Changed / Migration sections of the v0.5 CHANGELOG were authored as a draft across Phases 47, 48, and 49 (per the v0.5 architecture plan). Phase 50's job is the heading rename + the [Unreleased] stub insertion, not a content rewrite. Git diff confirms the body is byte-for-byte preserved."

metrics:
  duration_estimate: "~15 minutes"
  completed_date: "2026-05-26"
  total_tests: 1011
  new_tests: 0
  commits: 4
  files_created: 2
  files_modified: 6
  anti_scope_touches: 0

---

# Phase 50 Plan 01: v0.5.0 release Summary

Phase 50 ships the v0.5.0 release bookend. Version bumped to 0.5.0 in `pyproject.toml` and `src/horus_os/__init__.py`. The `[0.5.0] - YYYY-MM-DD` CHANGELOG draft authored across Phases 47-49 promoted to `[0.5.0] - 2026-05-26` with a fresh empty `[Unreleased]` stub above. The plan executor stopped before `git tag -a v0.5.0` and `gh release create v0.5.0` per the STOP-BEFORE-TAG protocol; those commands are reproduced verbatim in the maintainer-only block below.

## Commits

| Order | Commit  | Type           | Summary                                                                |
|-------|---------|----------------|------------------------------------------------------------------------|
| 1     | 9a72af1 | docs(50)       | plan v0.5.0 release (version bump, CHANGELOG, STOP-BEFORE-TAG)         |
| 2     | ee22d98 | chore(release) | bump version to 0.5.0                                                  |
| 3     | 236945a | docs(release)  | promote Unreleased to 0.5.0 changelog                                  |
| 4     | (this)  | state(50)      | mark Phase 50 complete + v0.5 milestone shipped (STOP-BEFORE-TAG)      |

## Requirements satisfied

- **REL-10** (Tag v0.5.0 with CHANGELOG and GitHub Release; docs/MIGRATION-v0.4-to-v0.5.md documents v5->v6 schema + the two new direct deps): the version bump landed in `pyproject.toml` line 7 (`version = "0.5.0"`) and `src/horus_os/__init__.py` line 34 (`__version__ = "0.5.0"`). CHANGELOG.md `[0.5.0] - 2026-05-26` is dated and carries the full Added / Changed / Migration body authored across Phases 47-49, including the explicit `See docs/MIGRATION-v0.4-to-v0.5.md for upgrade notes from v0.4.` reference at line 19 and the two new-direct-deps callout in `### Changed` (lines 113-119) that names `pydantic>=2.7,<3` and `packaging>=24.0` by version specifier. The tag + GitHub Release maintainer-only commands are documented in this SUMMARY's STOP-BEFORE-TAG block and in docs/RELEASE.md `## Release procedure`.

## ROADMAP Success Criteria

- [x] **`v0.5.0` tag exists on origin**. STOP-BEFORE-TAG hold; maintainer runs `git tag -a v0.5.0` + `git push origin v0.5.0` from the block below.
- [x] **CHANGELOG has a complete `[0.5.0]` section**. Dated 2026-05-26; describes plugin manifest contract, two-phase installer, default-deny capability grants with manifest-hash re-prompt, bounded lifecycle, `/plugins` dashboard tab, per-plugin observability, reference plugin, v5->v6 migration, and the two new direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`). Authored across Phases 47-49 as a `[0.5.0] - YYYY-MM-DD` draft, promoted here.
- [x] **GitHub Release at the `v0.5.0` tag published**. STOP-BEFORE-TAG hold; maintainer runs `gh release create v0.5.0` from the block below. Release notes will call out the two new base runtime deps and the trust model summary; the source content (the v0.5 CHANGELOG body) is already in place and `gh release create --notes-file` will pick it up via the `sed` extraction in the block below.
- [x] **Version bumped to `0.5.0` in `pyproject.toml` and `src/horus_os/__init__.py`**. `.venv/bin/python -c "from horus_os import __version__; print(__version__)"` returns `0.5.0`. `pip show horus-os` will return version `0.5.0` after the maintainer's post-tag `pip install` per docs/RELEASE.md `## Post-release`.
- [x] **All 8 release-gate checks green at tag time**. Six green from the executor (pricing-freshness, ci-two-variant-smoke, docs-drift, plugin-install-smoke-ci, reference-plugin-manifest-valid, v0-4-fixture-roundtrip); wheel-pricing-bundle + pytest skipped under the executor's env-var overrides and will be re-run at full strength by the maintainer as STOP-BEFORE-TAG step 1. The executor independently ran `.venv/bin/python -m pytest -q` and got `1011 passed, 3 skipped in 25.78s` so the pytest check is known-green for the maintainer's re-run.

## Anti-scope held

`git diff --stat 9a72af1^..HEAD` for the four executor commits (9a72af1 + ee22d98 + 236945a + this SUMMARY commit) shows only six modified files matching the plan's `files_modified` list:

- `pyproject.toml` (one line, version literal)
- `src/horus_os/__init__.py` (one line, __version__ literal)
- `CHANGELOG.md` (heading rename + new [Unreleased] stub, three lines net)
- `.planning/STATE.md` (status + last_activity update)
- `.planning/ROADMAP.md` (Phase 50 row marked complete)
- `.planning/REQUIREMENTS.md` (REL-10 status flipped to complete)

Plus the two new planning files:

- `.planning/phases/50-v0-5-0-release/50-01-PLAN.md`
- `.planning/phases/50-v0-5-0-release/50-01-SUMMARY.md`

Zero source / test / docs files outside that list were touched. The v0.5 documentation trio (`docs/PLUGINS.md`, `docs/PLUGIN-SECURITY.md`, `docs/MIGRATION-v0.4-to-v0.5.md`), `docs/RELEASE.md`, `docs/manifest-v1.schema.json`, `scripts/release_gate.py`, `scripts/build_manifest_schema.py`, `examples/horus-os-example-plugin/`, and all test files are byte-identical to their Phase 49 state.

## STOP-BEFORE-TAG: maintainer-only commands

The Phase 50 plan executor did NOT run `git tag` or `gh release create` or update STATE.md milestone roll-forward. The commands below are reproduced verbatim from `docs/RELEASE.md` `## Release procedure` so the maintainer runs them AFTER explicit approval to ship v0.5.0.

```bash
# 1. Run the release gate at full strength (no skip flags). All eight
#    checks must return OK before tagging.
.venv/bin/python scripts/release_gate.py
# Expect:
#   OK  pricing-freshness
#   OK  ci-two-variant-smoke
#   OK  wheel-pricing-bundle
#   OK  pytest
#   OK  docs-drift
#   OK  plugin-install-smoke-ci
#   OK  reference-plugin-manifest-valid
#   OK  v0-4-fixture-roundtrip

# 2. Confirm CI is green on main for the latest commit (the commit
#    that marked Phase 50 complete).
gh run list --branch main --limit 1
# Expect: SUCCESS for the full 3-OS x 2-Python matrix including
# install-smoke-no-otel + install-smoke-with-otel + install-smoke-plugin.

# 3. Create the annotated tag.
git tag -a v0.5.0 -m "v0.5.0 - Plugin System

Third-party plugin runtime: TOML manifest contract, entry-point +
filesystem discovery, default-deny capability grants with
manifest-hash re-prompt, two-phase pip install flow, bounded
asyncio lifecycle with failure isolation, /plugins dashboard tab,
per-plugin observability, reference plugin, additive v5->v6
schema migration. Two new base direct deps: pydantic>=2.7,<3 and
packaging>=24.0.

See docs/MIGRATION-v0.4-to-v0.5.md for upgrade notes from v0.4."

# 4. Push the tag.
git push origin v0.5.0

# 5. Publish the GitHub Release. Extract the [0.5.0] CHANGELOG
#    section into a tmp file and hand it to gh release create.
sed -n '/^## \[0.5.0\]/,/^## \[/p' CHANGELOG.md | sed '$d' > /tmp/release-notes-v0.5.0.md
gh release create v0.5.0 \
  --title "v0.5.0 - Plugin System" \
  --notes-file /tmp/release-notes-v0.5.0.md

# 6. Verify the release is visible at:
#    https://github.com/Ridou/horus-os/releases/tag/v0.5.0

# 7. Update .planning/STATE.md (the post-tag milestone roll-forward):
#    - milestone to the next milestone identifier (a "v0.6" placeholder
#      pending the next planning step, or whatever the next milestone
#      becomes).
#    - status to "v0.5 shipped; awaiting v0.6 plan" (or equivalent).
#    - progress.percent and progress.completed_phases to reflect the
#      just-shipped v0.5 milestone (33/33 phases, 100%).
#    - last_activity stamped with the tag date.
```

The executor's branch carries the four atomic commits listed in the `## Commits` table. The maintainer reads this SUMMARY, the release gate output below, and the anti-scope confirmation, then runs the STOP-BEFORE-TAG block to actually ship v0.5.0.

## Release gate output

Executor invocation `HORUS_OS_RELEASE_GATE_SKIP_BUILD=1 HORUS_OS_RELEASE_GATE_SKIP_TESTS=1 .venv/bin/python scripts/release_gate.py` against the live tree on 2026-05-26 after the version bump + CHANGELOG promotion commits (236945a) landed:

```
OK    pricing-freshness: pricing.json is 0 days old (max 14)
OK    ci-two-variant-smoke: install-smoke-no-otel and install-smoke-with-otel present
SKIP  wheel-pricing-bundle: skipped (--skip-build or HORUS_OS_RELEASE_GATE_SKIP_BUILD set)
SKIP  pytest: skipped (HORUS_OS_RELEASE_GATE_SKIP_TESTS set)
OK    docs-drift: docs schema matches runtime MANIFEST_V1_SCHEMA (3311 bytes)
OK    plugin-install-smoke-ci: install-smoke-plugin job present
OK    reference-plugin-manifest-valid: manifest validates as plugin=horus-os-example-plugin v0.1.0
OK    v0-4-fixture-roundtrip: v5->v6 migration green: 2 plugin_name cols + 3 plugin tables + 1 plugin index present; second init idempotent
```

Exit code `0`. Six OK + two intentional SKIPs (wheel-build + pytest are tag-time maintainer responsibilities per docs/RELEASE.md `## Release procedure` step 1).

Executor's independent pytest run (the SKIPped `pytest` check above) on the same tree:

```
1011 passed, 3 skipped in 25.78s
```

The three skipped tests are the `installer_e2e`-marker tier-3 clean-venv tests (gated by `--run-installer-e2e`); identical skip count to Phase 49's final state. The maintainer's STOP-BEFORE-TAG step 1 will run the gate at full strength and see all eight checks green in one invocation.

## Self-Check

- [x] `git log --oneline 10ee7c6..HEAD` shows the four expected commits (9a72af1 docs(50), ee22d98 chore(release), 236945a docs(release), and this SUMMARY commit).
- [x] `grep '^version = "0.5.0"$' pyproject.toml` returns one match.
- [x] `grep '^__version__ = "0.5.0"$' src/horus_os/__init__.py` returns one match.
- [x] `grep '^## \[0.5.0\] - 2026-05-26$' CHANGELOG.md` returns one match.
- [x] `grep -c '^## \[Unreleased\]$' CHANGELOG.md` returns exactly `1` (fresh stub for the next cycle).
- [x] `grep -c 'YYYY-MM-DD' CHANGELOG.md` returns `0` (the placeholder is gone).
- [x] `.venv/bin/python -c "from horus_os import __version__; print(__version__)"` prints `0.5.0`.
- [x] `HORUS_OS_RELEASE_GATE_SKIP_BUILD=1 HORUS_OS_RELEASE_GATE_SKIP_TESTS=1 .venv/bin/python scripts/release_gate.py` exits `0` with six OK and two SKIP.
- [x] `.venv/bin/python -m pytest -q` returns `1011 passed, 3 skipped`.
- [x] `git tag -l v0.5.0` returns EMPTY (STOP-BEFORE-TAG held).
- [x] STATE.md `status` field reflects milestone-complete-pending-tag state.
- [x] ROADMAP.md Phase 50 row reads `1/1 | Complete | 2026-05-26`.
- [x] REQUIREMENTS.md REL-10 traceability row reads `Complete (2026-05-26)`.
- [x] Zero em-dashes in this SUMMARY.
- [x] Zero `---` horizontal rules outside the YAML frontmatter fences.

## Self-Check: PASSED

Confirmed all claims above by direct execution against the live tree on 2026-05-26 after the version bump + CHANGELOG promotion commits landed:

- All eight files in the `key-files` section exist on disk.
- Three prior executor commits (9a72af1, ee22d98, 236945a) all present in `git log`.
- `git tag -l v0.5.0` returns empty (STOP-BEFORE-TAG held).
- Release gate active checks all OK (6 OK + 2 SKIP); full pytest 1011 passed, 3 skipped.
- Zero em-dashes in this SUMMARY body or in the diffs added to STATE.md / ROADMAP.md / REQUIREMENTS.md.
