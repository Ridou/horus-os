---
phase: 10-three-os-install-verification
plan: "00"
subsystem: ci
tags: [ci, three-os, install-smoke, github-actions]

# Dependency graph
requires:
  - phase: "07-01"
  - phase: "08-01"
  - phase: "09-00"
provides:
  - "scripts/install_smoke.py cross-OS smoke driver"
  - "install-smoke job in .github/workflows/ci.yml that runs on (Ubuntu, macOS, Windows) by (3.11, 3.12)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Python smoke driver instead of shell scripts. Cross-OS by construction. subprocess.run with capture_output keeps logs readable on every runner."
    - "install-smoke depends on lint+test via `needs`. A broken syntax error fails on the cheap job first; the matrix only runs once that passes."
    - "Smoke installs from the repo root with `pip install '.[all]'`, no editable, no dev deps. Mirrors what a stranger gets after `pip install horus-os[all]`."

key-files:
  created:
    - "scripts/install_smoke.py, 130 lines, 8 smoke checks"
  modified:
    - ".github/workflows/ci.yml, install-smoke job added"

requirements-completed:
  - TEST-03

known-limitations:
  - "No fresh-VM virtualization. GitHub-hosted runners are shared instances; the smoke confirms the install path works but does not catch issues that only appear on a truly minimal OS image."
  - "No live chat call. The smoke confirms `run` fails cleanly without an API key but does not run the agent against a real provider."

# Metrics
duration: 14m
completed: 2026-05-23
new-ci-jobs: 1 (install-smoke)
