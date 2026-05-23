---
phase: 21-v0-2-0-release
plan: "01"
subsystem: release
tags: [release, v0.2.0, changelog, tag, milestone-complete]

# Dependency graph
requires:
  - phase: "20-01"
provides:
  - "v0.2.0 git tag on origin"
  - "CHANGELOG.md with full v0.2.0 release notes"
  - "Version bumped 0.1.0 -> 0.2.0 across pyproject.toml and src/horus_os/__init__.py"
  - "Public GitHub Release at v0.2.0 with migration guide link"
  - "v0.2 milestone closed in STATE.md and ROADMAP.md"

requirements-completed:
  - REL-03  # tag v0.2.0 + release notes + GitHub Release
  - REL-04  # migration guide linked from the release

# Metrics
duration: ~25m
completed: 2026-05-23
v0.2-milestone: COMPLETE (10 of 10 phases shipped, 21 of 21 across both milestones)
total-tests: 319
release-sha: 1be3ba7f5a50b45fd4dbafe2b3c0a0e783b6da05
tag-sha: 979726f0fe9bbd09c2f1a2f7ef392e475d8c46a8
ci-run: https://github.com/Ridou/horus-os/actions/runs/26333529469
release-url: https://github.com/Ridou/horus-os/releases/tag/v0.2.0
---

# Phase 21 Plan 01 Summary: v0.2.0 release

## What shipped

The v0.2.0 release. Eight artifacts crossed the finish line:

1. `pyproject.toml` version `0.1.0` to `0.2.0`
2. `src/horus_os/__init__.py` `__version__` `0.1.0` to `0.2.0`
3. `CHANGELOG.md` rotated: fresh empty `[Unreleased]` at the top,
   the prior Unreleased body now lives under
   `## [0.2.0] - 2026-05-23`
4. Annotated tag `v0.2.0` pushed to origin
   (`979726f0fe9bbd09c2f1a2f7ef392e475d8c46a8`)
5. GitHub Release published at
   https://github.com/Ridou/horus-os/releases/tag/v0.2.0 with the
   CHANGELOG body and links to the migration guide and the
   `examples/` directory
6. `.planning/STATE.md` flipped to `milestone_complete`, 21 of 21
   phases done
7. `.planning/ROADMAP.md` v0.2 milestone bullet checked, every
   Phase 12-21 row checked, progress table updated
8. CI fully green on the release commit: all six `lint+test` jobs
   plus all six `install-smoke` jobs across (Ubuntu, macOS, Windows)
   x (Python 3.11, 3.12)

## Process notes

- Test count held at 319 across the release commit. No code-path
  changes; only version strings and Markdown moved.
- `ruff check .` and `ruff format --check .` both clean on the
  release commit.
- CI run 26333529469 completed in roughly two minutes; all twelve
  matrix jobs green. The Release was cut only after CI was
  confirmed green, never on a red CI.
- No re-tag was needed. The annotated tag was created once and
  pushed once.
- The Release body uses absolute GitHub URLs pinned at
  `v0.2.0` for both the migration guide and the `examples/`
  directory, so the links survive future doc moves. The migration
  link returned HTTP 200 on verification.

## Out of scope (deliberate)

- **PyPI publish.** Not in the v0.2 roadmap. GitHub issue #6
  (release automation) remains open for future work.
- **Re-tag.** None required. Future fixes ship as follow-up commits
  past the v0.2.0 tag.

## Success criteria (REL-03, REL-04)

All four roadmap criteria for Phase 21 are met:

1. The `v0.2.0` tag exists on origin
   (`git ls-remote origin refs/tags/v0.2.0` returns the tag SHA)
2. CHANGELOG.md has a complete `[0.2.0] - 2026-05-23` section
   describing every multi-agent, streaming, and adapter addition
   from Phases 12-17, plus the v0.2 doc and example work from
   Phase 18
3. The GitHub Release at v0.2.0 is published (not draft, not
   prerelease) with the CHANGELOG body and a link to
   `docs/MIGRATION-v0.1-to-v0.2.md`
4. Version bumped to `0.2.0` in `pyproject.toml` and
   `src/horus_os/__init__.py`

## Milestone close-out

v0.2 Multi-Agent + Streaming is shipped. Phases 12-21 are complete:
10 phases, 11 plans, 18 requirements (MA 4, STREAM 3, ADAPT 3,
MIG 3, TEST 3, REL 2), 319 tests, three-OS install-smoke green on
Python 3.11 and 3.12, public release with migration guide.

Combined project totals: 21 phases, 24 plans, two shipped releases
(v0.1.0 on 2026-05-23 and v0.2.0 on 2026-05-23). Next milestone is
undefined; the project is in a clean checkpoint state, ready for
the next round of planning.
