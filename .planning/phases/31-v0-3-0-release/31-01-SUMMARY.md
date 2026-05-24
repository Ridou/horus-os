---
phase: 31-v0-3-0-release
plan: "01"
subsystem: release
tags: [release, v0.3.0, changelog, tag, milestone-complete]

# Dependency graph
requires:
  - phase: "30-01"
provides:
  - "v0.3.0 git tag on origin"
  - "CHANGELOG.md with full v0.3.0 release notes"
  - "Version bumped 0.2.0 -> 0.3.0 across pyproject.toml and src/horus_os/__init__.py"
  - "Public GitHub Release at v0.3.0 with migration guide link"
  - "v0.3 milestone closed in STATE.md and ROADMAP.md"
  - "v0.3 GitHub milestone (#2) closed"

requirements-completed:
  - REL-05  # tag v0.3.0 + release notes + GitHub Release
  - REL-06  # migration guide linked from the release

# Metrics
duration: ~20m
completed: 2026-05-24
v0.3-milestone: COMPLETE (10 of 10 phases shipped, 31 of 31 across all three milestones)
total-tests: 447
release-sha: 2517b59c4158285311f0f881856552ed71444e14
tag-sha: 01a640bca323dd12e9ab3d00aaf6124ef1a777d0
ci-run: https://github.com/Ridou/horus-os/actions/runs/26352766903
release-url: https://github.com/Ridou/horus-os/releases/tag/v0.3.0
---

# Phase 31 Plan 01 Summary: v0.3.0 release

## What shipped

The v0.3.0 release. Eight artifacts crossed the finish line:

1. `pyproject.toml` version `0.2.0` to `0.3.0`
2. `src/horus_os/__init__.py` `__version__` `0.2.0` to `0.3.0`
3. `CHANGELOG.md` rotated: fresh empty `[Unreleased]` at the top,
   the prior Unreleased body now lives under
   `## [0.3.0] - 2026-05-24` with a short release blurb
4. Annotated tag `v0.3.0` pushed to origin
   (`01a640bca323dd12e9ab3d00aaf6124ef1a777d0`, points at release
   commit `2517b59c4158285311f0f881856552ed71444e14`)
5. GitHub Release published at
   https://github.com/Ridou/horus-os/releases/tag/v0.3.0 with the
   CHANGELOG body and links to the migration guide, the
   `docs/adapters/` setup directory, and the `examples/` directory
6. `.planning/STATE.md` flipped to `milestone_complete`, 31 of 31
   phases done, Prior Milestones bullet added for v0.3
7. `.planning/ROADMAP.md` v0.3 milestone bullet checked, every
   Phase 22-31 row checked with completion dates, progress table
   updated
8. CI fully green on the release commit: all six `lint+test` jobs
   plus all six `install-smoke` jobs across (Ubuntu, macOS, Windows)
   x (Python 3.11, 3.12), twelve jobs total

## Process notes

- Test count held at 447 across the release commit. No code-path
  changes; only version strings and Markdown moved.
- `ruff check .` and `ruff format --check .` both clean on the
  release commit (89 files formatted).
- CI run 26352766903 completed in roughly three minutes; all
  twelve matrix jobs green. The Release was cut only after CI was
  confirmed green, never on a red CI.
- No re-tag was needed. The annotated tag was created once and
  pushed once.
- The Release body uses absolute GitHub URLs pinned at `v0.3.0`
  for the migration guide, the `docs/adapters/` directory, and
  the `examples/` directory, so the links survive future doc
  moves.
- v0.3 GitHub milestone (#2) closed after the release was cut.

## Out of scope (deliberate)

- **PyPI publish.** Not in the v0.3 roadmap. GitHub issue #6
  (release automation) remains open for future work, same posture
  as Phase 21.
- **Re-tag.** None required. Future fixes ship as follow-up
  commits past the v0.3.0 tag.

## Success criteria (REL-05, REL-06)

All four roadmap criteria for Phase 31 are met:

1. The `v0.3.0` tag exists on origin
   (`git ls-remote origin refs/tags/v0.3.0` returns the tag SHA)
2. CHANGELOG.md has a complete `[0.3.0] - 2026-05-24` section
   describing the four new adapters (Discord, Slack, Email,
   Calendar), lifecycle hooks (LifecycleAdapter, AdapterRegistry,
   FastAPI lifespan integration, AdapterContext additions), and
   dashboard updates (Adapters tab, toggle routes,
   `supports_toggle`), plus the v0.3 doc and example work from
   Phase 28
3. The GitHub Release at v0.3.0 is published (not draft, not
   prerelease) with the CHANGELOG body and a link to
   `docs/MIGRATION-v0.2-to-v0.3.md`
4. Version bumped to `0.3.0` in `pyproject.toml` and
   `src/horus_os/__init__.py`

## Milestone close-out

v0.3 Adapter Ecosystem is shipped. Phases 22-31 are complete: 10
phases, 10 plans, 22 requirements (ART 3, DISC 3, SLAK 3, MAIL 3,
CAL 2, DASH-3 2, TEST 4, REL 2), 447 tests, three-OS install-smoke
green on Python 3.11 and 3.12, public release with migration
guide and four per-adapter setup guides.

Combined project totals: 31 phases, 34 plans, three shipped
releases (v0.1.0 on 2026-05-23, v0.2.0 on 2026-05-23, v0.3.0 on
2026-05-24). Project is in a clean checkpoint state, ready for
the next round of milestone planning.
