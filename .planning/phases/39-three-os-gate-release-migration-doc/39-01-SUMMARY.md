---
phase: 39-three-os-gate-release-migration-doc
plan: "01"
subsystem: release
tags: [release, docs, migration, release-gate, pricing-freshness, v0.4, pitfall-5, pitfall-7, pitfall-12, rel-07, rel-08, rel-09, stop-before-tag]

# Dependency graph
requires:
  - phase: "32-01"  # Schema v4 to v5, ObservationBus, SQLitePersister
  - phase: "33-01"  # Runner + SSE-branch capture; Pitfall 1 + 2 v0.3 bug fixes
  - phase: "34-01"  # PricingTable, CostAnnotator, bundled pricing.json, HORUS_OS_PRICING_PATH override
  - phase: "35-01"  # observability/queries.py, /api/observability/* routes, /api/agents extension
  - phase: "36-01"  # /observability dashboard tab with window selector + staleness banner + small-sample guard
  - phase: "37-01"  # horus-os usage CLI subcommand --since --format --by, docs/CLI.md JSON schema
  - phase: "38-01"  # OtelAdapter behind [otel] extra, HORUS_OS_OTEL_CAPTURE_CONTENT opt-in, two-variant install-smoke matrix
provides:
  - "docs/MIGRATION-v0.3-to-v0.4.md: upgrade guide for v0.3 users (schema migration, two v0.3 bugs fixed, new env vars, new CLI surface, new dashboard tab, [otel] extra, pricing override path, upgrade checklist)"
  - "docs/OBSERVABILITY.md: user-facing observability guide (what gets captured per LLM call / tool call / trace, dashboard tour, CLI usage examples, cost math, pricing staleness, privacy note, pre-v0.4 NULL render)"
  - "docs/RELEASE.md: maintainer release procedure (pre-release checklist, release gate explanation with env / flag overrides, pricing.json refresh procedure, full release sequence including tag + GitHub Release, post-release STATE.md update, Pitfall 5 + 12 rationale)"
  - "docs/OTEL.md: Threat model section polished into three subsections (Default mode / Opt-in mode / Trust statement); seven redactor patterns listed verbatim with [REDACTED] outcome; obsolete Phase 39 closing stub removed"
  - "scripts/release_gate.py: pre-tag release-quality gate with four checks (pricing freshness within HORUS_OS_PRICING_MAX_AGE_DAYS default 14, CI two-variant install-smoke presence, wheel pricing.json bundle, pytest pass), --check {pricing,wheel,ci,tests} selection, --skip-build / HORUS_OS_RELEASE_GATE_SKIP_BUILD / HORUS_OS_RELEASE_GATE_SKIP_TESTS overrides, exits 0 on full pass, 1 on any fail with one diagnostic per failing check"
  - "tests/test_release_gate.py: 10 in-process unit tests exercising each check function directly with tmp fixtures; HORUS_OS_PRICING_PATH_OVERRIDE and HORUS_OS_CI_YML_PATH_OVERRIDE env vars keep the main() integration tests hermetic"
  - "pyproject.toml: version bumped 0.3.0 -> 0.4.0"
  - "src/horus_os/__init__.py: __version__ bumped 0.3.0 -> 0.4.0"
  - "CHANGELOG.md: [0.4.0] - 2026-05-26 section synthesized from Phase 32-38 SUMMARYs with Added / Changed / Fixed / Documentation; fresh [Unreleased] stub for the next cycle; [0.3.0], [0.2.0], [0.1.0] sections preserved byte-identical"

requirements-completed:
  - REL-07  # Migration doc + CHANGELOG [0.4.0] + version bump + STOP-BEFORE-TAG protocol for the tag + GitHub Release maintainer steps
  - REL-08  # scripts/release_gate.py enforces pricing freshness AND two-variant install-smoke matrix presence AND wheel pricing.json bundle AND pytest pass
  - REL-09  # docs/OTEL.md Threat model section polished into three subsections covering default vs content-capture modes and operator trust statement

# Tech stack
tech-stack:
  added: []
  patterns:
    - "Release-gate-before-tag pattern: scripts/release_gate.py is the maintainer's last automated step before `git tag -a vN.M.P`. Four checks (pricing freshness, CI two-variant smoke presence, wheel pricing.json bundle, pytest pass) print OK / FAIL / SKIP per check and the runner never short-circuits so the maintainer sees the full picture in one pass."
    - "STOP-BEFORE-TAG protocol: the plan executor prepares everything (docs, gate, version bumps, CHANGELOG) but never runs `git tag` or `gh release create` or pushes tags. Tag creation and GitHub Release publication are user-confirmation gates documented in docs/RELEASE.md `## Release procedure` and reproduced verbatim in the maintainer-only commands block below."
    - "CHANGELOG promotion pattern: [Unreleased] section gets synthesized from per-phase SUMMARYs into a dated [N.M.P] - YYYY-MM-DD block at promotion time, a fresh empty [Unreleased] stub is left above for the next cycle, and prior version sections stay byte-identical."
    - "OTel threat model as three explicit subsections: Default mode (what the collector receives), Opt-in mode (what changes when HORUS_OS_OTEL_CAPTURE_CONTENT=true), Trust statement (operator guidance). The constants-layer absence in _observability/semconv.py is the primary safety guarantee; the seven-pattern redactor allowlist in observability/redact.py is defence-in-depth."
    - "Migration-doc bug-fix disclosure: the `## Bug fixes you inherit for free` section explicitly states pre-v0.4 cost reporting was double-wrong (undercounted tokens AND $0 streaming), with both Pitfall 1 and Pitfall 2 cited by ID. Honesty over false reassurance."

# Key files
key-files:
  created:
    - docs/MIGRATION-v0.3-to-v0.4.md
    - docs/OBSERVABILITY.md
    - docs/RELEASE.md
    - scripts/release_gate.py
    - tests/test_release_gate.py
    - .planning/phases/39-three-os-gate-release-migration-doc/39-01-SUMMARY.md
  modified:
    - pyproject.toml                  # one line: version "0.3.0" -> "0.4.0"
    - src/horus_os/__init__.py        # one line: __version__ "0.3.0" -> "0.4.0"
    - CHANGELOG.md                    # [Unreleased] promoted to [0.4.0] - 2026-05-26; fresh [Unreleased] stub above
    - docs/OTEL.md                    # ## Threat model section polished into three subsections; obsolete Phase 39 stub removed

decisions:
  - name: "STOP-BEFORE-TAG: executor commits version bumps + CHANGELOG + docs + release_gate.py but DOES NOT run `git tag` or `gh release create`"
    rationale: "Tag + GitHub Release are user-confirmation gates per the STOP-BEFORE-TAG protocol in the Phase 39 plan; the maintainer runs them after explicit approval per docs/RELEASE.md `## Release procedure`. The plan's verification gate asserts `git tag -l v0.4.0` returns empty after execution."
  - name: "release_gate.py is a LOCAL gate, not a CI gate"
    rationale: "The maintainer runs it manually before tagging; integrating into CI would require GitHub Actions cron-on-release-tag-creation which is more complex than the 5-second local invocation. The two-variant install-smoke matrix IS already in CI (Phase 38); release_gate.py validates its PRESENCE so the matrix cannot disappear silently between releases."
  - name: "Path-override env vars for tests (HORUS_OS_PRICING_PATH_OVERRIDE, HORUS_OS_CI_YML_PATH_OVERRIDE)"
    rationale: "tests/test_release_gate.py needs to drive main() against tmp fixtures without invoking the real pricing.json or ci.yml. Function arguments to the check functions remain primary; the override env vars exist solely to bridge the main() integration tests. They are NOT documented in docs/RELEASE.md as user-facing because they are test-only seams."
  - name: "Module loaded via importlib.util in tests must be registered in sys.modules"
    rationale: "scripts/release_gate.py uses @dataclass which introspects `sys.modules[cls.__module__]` during decoration. Without registering the loaded module in sys.modules, every dataclass instantiation raised AttributeError. The test helper now stores the module in sys.modules under _release_gate_under_test."

metrics:
  duration_estimate: "~90 minutes"
  completed_date: "2026-05-26"
  total_tests: 718
  new_tests: 10
  commits: 9
  files_created: 6
  files_modified: 4
  anti_scope_touches: 0

---

# Phase 39 Plan 01: Three-OS gate, release, migration doc Summary

Phase 39 ships the v0.4.0 release-quality gate, the three new release-docs (`MIGRATION-v0.3-to-v0.4.md`, `OBSERVABILITY.md`, `RELEASE.md`), the polished `docs/OTEL.md` `## Threat model` section, the version bumps to 0.4.0 in `pyproject.toml` and `src/horus_os/__init__.py`, and the `CHANGELOG.md [0.4.0] - 2026-05-26` section. The plan executor stopped before `git tag -a v0.4.0` and `gh release create` per the STOP-BEFORE-TAG protocol; those commands are reproduced verbatim in the maintainer-only block below.

## Commits

| Order | Commit  | Type     | Summary                                                                                  |
|-------|---------|----------|------------------------------------------------------------------------------------------|
| 1     | 770479c | docs(39) | MIGRATION-v0.3-to-v0.4 guide for the Observability milestone                             |
| 2     | aa07892 | docs(39) | OBSERVABILITY user-facing guide for v0.4                                                 |
| 3     | 3855260 | docs(39) | polish OTEL Threat model to fully satisfy REL-09                                         |
| 4     | 3e73ae4 | test(39) | add failing release_gate unit tests (RED)                                                |
| 5     | 13a562d | feat(39) | release_gate.py with pricing, CI presence, wheel bundle, pytest checks (GREEN)           |
| 6     | 1ceb3a1 | docs(39) | RELEASE manual procedure for v0.x                                                        |
| 7     | 3e8b7c1 | chore(release) | bump version to 0.4.0                                                              |
| 8     | 55a519d | docs(release)  | promote Unreleased to 0.4.0 changelog                                              |
| 9     | (this)  | docs(39) | Phase 39 SUMMARY (release docs, gate, version bump; STOP-BEFORE-TAG)                     |

## Requirements satisfied

- **REL-07** (Migration notes + CHANGELOG + version bump + tag procedure documented): docs/MIGRATION-v0.3-to-v0.4.md ships the upgrade guide; CHANGELOG.md `[0.4.0] - 2026-05-26` is synthesized from Phase 32-38 SUMMARYs; version bumped in pyproject.toml and src/horus_os/__init__.py; the tag + GitHub Release maintainer-only commands are documented in this SUMMARY's STOP-BEFORE-TAG block and in docs/RELEASE.md `## Release procedure`.
- **REL-08** (Release gate enforcing pricing freshness AND two-variant install-smoke matrix): scripts/release_gate.py runs four checks with exit-0-only-on-full-pass semantics. Pricing freshness reads `updated_at` from `src/horus_os/observability/pricing.json` and compares to today's date against `HORUS_OS_PRICING_MAX_AGE_DAYS` (default 14). CI presence greps `.github/workflows/ci.yml` for both `install-smoke-no-otel` and `install-smoke-with-otel` literals. Wheel bundle invokes `python -m build --wheel` and asserts `horus_os/observability/pricing.json` membership via zipfile. Pytest runs `python -m pytest -q` from the repo root.
- **REL-09** (OTel Threat model section covers default vs content-capture modes): docs/OTEL.md `## Threat model` reorganized into `### Default mode: what your collector receives`, `### Opt-in mode: what changes when you set HORUS_OS_OTEL_CAPTURE_CONTENT=true`, `### Trust statement and operator guidance`. Seven redactor patterns listed verbatim with the `[REDACTED]` outcome. The constants-layer absence is named as the primary safety guarantee with the redactor as defence-in-depth. Pitfall 7 cited by ID.

## ROADMAP Success Criteria

- [x] **Docs trio shipped** (`MIGRATION-v0.3-to-v0.4.md`, `OBSERVABILITY.md`, `RELEASE.md`) plus polished `docs/OTEL.md` Threat model section.
- [x] **Release gate enforces pricing freshness within 14 days AND two-variant install-smoke matrix presence in CI**. Live invocation against the tree returns exit 0 with all four checks passing.
- [x] **Version bumped to 0.4.0** in `pyproject.toml` (line 7) AND `src/horus_os/__init__.py` (line 34). Runtime introspection `from horus_os import __version__` returns `0.4.0`.
- [x] **CHANGELOG `[0.4.0] - 2026-05-26` written** with Added / Changed / Fixed / Documentation sections; fresh `[Unreleased]` stub remains above; prior version sections untouched.

The fourth SC ("3-OS CI matrix green") is a maintainer verification step that happens AFTER the executor's commits land on `main` and before tagging. The release_gate's `ci-two-variant-smoke` check asserts the matrix is wired in `.github/workflows/ci.yml`; the actual matrix run is a maintainer responsibility per `docs/RELEASE.md` `## Pre-release checklist` step 1.

## Pitfalls guarded

- **Pitfall 5 (`pricing.json` rots silently between releases)**: closed by the release_gate `pricing-freshness` check with the 14-day default. The threshold is hardcoded as a module constant; raising it via `HORUS_OS_PRICING_MAX_AGE_DAYS` is visible in environment scrutiny. Test `test_pricing_freshness_fails_when_older_than_threshold` pins the failure path. Test `test_pricing_threshold_overridable_via_env` pins the override semantics.
- **Pitfall 7 (PII leaks through OTel span attributes)**: closed by the `docs/OTEL.md` Threat model polish. Three explicit subsections (Default mode / Opt-in mode / Trust statement) document what the collector receives in each mode. The trust statement says "leave default-deny enabled UNLESS you specifically need body content for replay debugging AND your OTel collector plus downstream backends are locked down."
- **Pitfall 12 (`opentelemetry-*` leaks into the no-otel install variant)**: closed by the release_gate `ci-two-variant-smoke` check that asserts both `install-smoke-no-otel` and `install-smoke-with-otel` job literals are present in `.github/workflows/ci.yml`. Test `test_ci_presence_fails_when_no_otel_job_missing` pins one half of the contract, `test_ci_presence_fails_when_with_otel_job_missing` pins the other.

## Anti-scope held

`git diff --stat 41b71d9..HEAD` for the 18 anti-scope paths returns zero lines:

- `src/horus_os/observability/bus.py`
- `src/horus_os/observability/persist.py`
- `src/horus_os/observability/cost.py`
- `src/horus_os/observability/pricing.py`
- `src/horus_os/observability/pricing.json`
- `src/horus_os/observability/queries.py`
- `src/horus_os/observability/redact.py`
- `src/horus_os/_observability/semconv.py`
- `src/horus_os/agent.py`
- `src/horus_os/tools/loop.py`
- `src/horus_os/storage.py`
- `src/horus_os/server/api.py`
- `src/horus_os/adapters/otel_adapter.py`
- `src/horus_os/adapters/discord_adapter.py`
- `src/horus_os/adapters/slack_adapter.py`
- `src/horus_os/adapters/email_adapter.py`
- `src/horus_os/adapters/calendar_adapter.py`
- `src/horus_os/adapters/webhook.py`
- `src/horus_os/_providers/*`
- `src/horus_os/server/static/*`
- `src/horus_os/cli/*`

Phase 39 only touches release-substrate files (docs, scripts, version literals, CHANGELOG). No runtime behavior changed.

## STOP-BEFORE-TAG: maintainer-only commands

The Phase 39 plan executor did NOT run `git tag` or `gh release create`. The commands below are reproduced verbatim from `docs/RELEASE.md` `## Release procedure` so the maintainer runs them AFTER explicit approval to ship v0.4.0.

```bash
# 1. Confirm CI is green on main for the latest commit (the commit
#    that promoted CHANGELOG to [0.4.0]).
gh run list --branch main --limit 1
# Expect: SUCCESS for the full 3-OS x 2-Python matrix including
# install-smoke-no-otel + install-smoke-with-otel.

# 2. Create the annotated tag.
git tag -a v0.4.0 -m "v0.4.0 - Observability milestone

Local-first cost, latency, and tool-reliability instrumentation
against a SQLite source of truth. /observability dashboard tab,
horus-os usage CLI subcommand, opt-in OpenTelemetry exporter
behind a [otel] extra. Two confirmed v0.3 cost-correctness bugs
fixed.

See docs/MIGRATION-v0.3-to-v0.4.md for upgrade notes from v0.3."

# 3. Push the tag.
git push origin v0.4.0

# 4. Publish the GitHub Release. Extract the [0.4.0] CHANGELOG
#    section into a tmp file and hand it to gh release create.
awk '/^## \[0.4.0\]/,/^## \[0.3.0\]/' CHANGELOG.md | sed '$d' > /tmp/release-notes-0.4.0.md
gh release create v0.4.0 \
  --title "v0.4.0 - Observability" \
  --notes-file /tmp/release-notes-0.4.0.md

# 5. Verify visible at:
#    https://github.com/Ridou/horus-os/releases/tag/v0.4.0

# 6. Update .planning/STATE.md:
#    - milestone -> v0.5 (or whatever the next planning step is)
#    - progress.percent and progress.completed_phases reflect the
#      just-shipped milestone.
```

The executor's branch / worktree carries the 9 atomic commits listed in the `## Commits` table. The maintainer reads this SUMMARY, the release gate output below, and the anti-scope confirmation, then runs the STOP-BEFORE-TAG block to actually ship v0.4.0.

## Release gate output

Full real invocation `python scripts/release_gate.py` (no skip flags) against the live tree on 2026-05-26:

```
OK    pricing-freshness: pricing.json is 0 days old (max 14)
OK    ci-two-variant-smoke: install-smoke-no-otel and install-smoke-with-otel present
OK    wheel-pricing-bundle: horus_os-0.4.0-py3-none-any.whl contains pricing.json (1 match)
OK    pytest: 718 passed in 19.67s
```

All four checks pass. The wheel filename `horus_os-0.4.0-py3-none-any.whl` confirms the version bump propagates through the build pipeline.

## Self-Check

- [x] `python scripts/release_gate.py` (no skip flags) exits 0 with all four checks passing on the live tree.
- [x] `grep '^version = "0.4.0"$' pyproject.toml` returns one match.
- [x] `grep '^__version__ = "0.4.0"$' src/horus_os/__init__.py` returns one match.
- [x] `grep '^## \[0.4.0\] - 2026-05-26$' CHANGELOG.md` returns one match.
- [x] `.venv/bin/python -c "from horus_os import __version__; print(__version__)"` prints `0.4.0`.
- [x] `git tag -l v0.4.0` returns EMPTY (STOP-BEFORE-TAG held).
- [x] Full test suite passes: 718 passed (708 baseline + 10 new release_gate tests).
- [x] `ruff check .` returns "All checks passed!".
- [x] `ruff format --check .` returns "144 files already formatted".
- [x] `python scripts/lint_no_wallclock.py` returns `ok (0 violations)`.
- [x] Anti-scope held: zero lines diff against the 18 anti-scope paths.
- [x] Zero em-dashes in any newly created file (`docs/MIGRATION-v0.3-to-v0.4.md`, `docs/OBSERVABILITY.md`, `docs/RELEASE.md`, `scripts/release_gate.py`, `tests/test_release_gate.py`, this SUMMARY).
- [x] STATE.md and ROADMAP.md untouched by the executor (parallel-executor protocol).
