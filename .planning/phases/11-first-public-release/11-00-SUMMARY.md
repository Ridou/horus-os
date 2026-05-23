---
phase: 11-first-public-release
plan: "00"
subsystem: release
tags: [release, v0.1.0, changelog, tag]

# Dependency graph
requires:
  - phase: "10-00"
provides:
  - "v0.1.0 git tag on origin"
  - "CHANGELOG.md with full v0.1.0 release notes"
  - "Version bumped 0.0.1 -> 0.1.0 across pyproject.toml and __init__.py"
  - "README + PROJECT status reflect alpha release"

requirements-completed:
  - REL-01  # tag v0.1.0 + release notes
  - REL-02  # public GitHub repo with README, LICENSE, CONTRIBUTING (already in place; v0.1.0 confirms readiness)

# Metrics
duration: 18m
completed: 2026-05-23
v0.1-milestone: COMPLETE (11 of 11 phases shipped)
total-tests: 175
total-commits-since-bootstrap: 39
