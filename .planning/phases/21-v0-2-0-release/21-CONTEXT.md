# Phase 21 Context: v0.2.0 release

This phase ships v0.2 of horus-os. All ten v0.2 development phases (12-20)
are complete; this is the version bump, CHANGELOG rotation, tag push, and
GitHub Release creation.

## Decisions

- **Tag name:** `v0.2.0` (annotated, pushed to origin)
- **Release date:** 2026-05-23
- **Test baseline at release:** 319 tests, all green
- **CI gate:** all twelve install-smoke matrix jobs (Ubuntu, macOS, Windows
  by Python 3.11, 3.12, with and without optional extras) green on the
  release commit before cutting the GitHub Release

## Version bump locations

Exactly two:

- `pyproject.toml` line with `version = "0.1.0"` becomes `"0.2.0"`
- `src/horus_os/__init__.py` line with `__version__ = "0.1.0"` becomes
  `"0.2.0"`

No other file declares the package version.

## CHANGELOG rotation

The existing `[Unreleased]` section in CHANGELOG.md already enumerates
every v0.2 deliverable (added during Phase 18). The rotation:

1. Rename the existing `## [Unreleased]` heading to
   `## [0.2.0] - 2026-05-23`
2. Insert a fresh empty `## [Unreleased]` placeholder near the top of
   the file, above `[0.1.0]`, with stub `### Added` / `### Changed`
   subsections per Keep a Changelog convention
3. Leave the section bodies exactly as they are. The text is honest as
   written; no aspirational items are added

## GitHub Release body

Derived directly from the CHANGELOG `[0.2.0]` section, quoted faithfully.
Appended at the bottom:

- A pointer to `docs/MIGRATION-v0.1-to-v0.2.md` for upgrade notes
- A pointer to the `examples/` directory for the three runnable scripts

The release is published, not draft, not prerelease.

## Out of scope

- **No PyPI publish.** The roadmap does not require it for v0.2. The
  open release-automation issue (#6 on GitHub) tracks this for future
  work and remains open after this phase
- **No re-tag.** If a fix is needed after the tag exists, it ships as a
  follow-up commit; the tag stays put

## Success criteria (REL-03, REL-04)

1. `v0.2.0` tag exists on origin
2. CHANGELOG.md has a complete `[0.2.0]` section
3. A GitHub Release at the v0.2.0 tag is published, body derived from
   CHANGELOG, links to the migration guide
4. Version bumped to `0.2.0` in `pyproject.toml` and
   `src/horus_os/__init__.py`
