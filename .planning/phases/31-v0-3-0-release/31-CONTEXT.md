# Phase 31 Context: v0.3.0 release

This phase ships v0.3 of horus-os. All nine v0.3 development phases
(22-30) are complete. This is the version bump, CHANGELOG rotation,
tag push, and GitHub Release creation. Same posture as Phase 21
(v0.2.0 release).

## Decisions

- **Tag name:** `v0.3.0` (annotated, pushed to origin)
- **Release date:** 2026-05-24
- **Test baseline at release:** 447 tests, all green
- **CI gate:** all twelve install-smoke matrix jobs (Ubuntu, macOS,
  Windows by Python 3.11, 3.12) green on the release commit before
  cutting the GitHub Release

## Version bump locations

Exactly two:

- `pyproject.toml` line with `version = "0.2.0"` becomes `"0.3.0"`
- `src/horus_os/__init__.py` line with `__version__ = "0.2.0"` becomes
  `"0.3.0"`

No other file declares the package version.

## CHANGELOG rotation

The existing `[Unreleased]` section in CHANGELOG.md already enumerates
every v0.3 deliverable (added during Phases 22-28). The rotation:

1. Rename the existing `## [Unreleased]` heading to
   `## [0.3.0] - 2026-05-24`
2. Insert a fresh empty `## [Unreleased]` placeholder near the top of
   the file (above the new `[0.3.0]`), with stub `### Added` and
   `### Changed` subsections per Keep a Changelog convention
3. Leave the section bodies exactly as they are. The text is honest
   as written; no aspirational items are added

## GitHub Release body

Derived directly from the CHANGELOG `[0.3.0]` section, quoted
faithfully. Appended at the bottom:

- A pointer to `docs/MIGRATION-v0.2-to-v0.3.md` for upgrade notes
- A pointer to `docs/adapters/` for the four per-adapter setup
  guides (Discord, Slack, Email, Calendar)
- A pointer to the `examples/` directory for the four runnable
  adapter scripts

The release is published, not draft, not prerelease.

## Out of scope

- **No PyPI publish.** Same posture as Phase 21. The open
  release-automation issue (#6 on GitHub) tracks this for future
  work and remains open after this phase
- **No re-tag.** If a fix is needed after the tag exists, it ships
  as a follow-up commit; the tag stays put

## Success criteria (REL-05, REL-06)

1. `v0.3.0` tag exists on origin
2. CHANGELOG.md has a complete `[0.3.0]` section describing the four
   new adapters, lifecycle hooks, and dashboard updates
3. A GitHub Release at the v0.3.0 tag is published with the
   CHANGELOG body and a link to the migration guide
4. Version bumped to `0.3.0` in `pyproject.toml` and
   `src/horus_os/__init__.py`
