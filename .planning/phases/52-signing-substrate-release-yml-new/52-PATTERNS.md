# Phase 52: Signing substrate (`release.yml` NEW) - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 10 (5 NEW source + 4 NEW tests + 1 NEW fixture dir + 2 MODIFIED docs/decisions)
**Analogs found:** 10 / 10 (with 1 documented-no-analog: `.planning/decisions/no-pypi-in-v0.6.md` directory is established by this phase; prose shape recommended)

> **Cross-OS reminder.** Every analog excerpt below is from a Python file or YAML/Markdown asset that already runs cleanly on the Ubuntu / macOS / Windows × Python 3.11 / 3.12 CI matrix. Mirror the `pathlib`-only, `subprocess.run([sys.executable, "-m", ...], capture_output=True, text=True, check=False)`, `encoding="utf-8"` discipline visible in every excerpt — that is what keeps Windows green.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| 1. `.github/workflows/release.yml` (NEW) | CI workflow | event-driven (release.published trigger) | `.github/workflows/ci.yml` (post-Phase-51) + `.github/workflows/issue-claim-watcher.yml` | exact (role + structure) |
| 2. `scripts/verify_release.py` (NEW) | Python script (stdlib-only CLI) | request-response (subprocess shell-out) | `scripts/release_gate.py` | exact (role + data flow) |
| 3. `.planning/decisions/no-pypi-in-v0.6.md` (NEW) | decision file (Markdown prose) | n/a | NONE (directory established by this phase) | no analog — see §No Analog Found |
| 4a. `tests/fixtures/sigstore/canonical/README.md` (NEW) | fixture documentation | n/a | `tests/fixtures/installer/__init__.py` + `tests/fixtures/broken_plugins/__init__.py` | role-match (fixture-dir README precedent is __init__.py docstring; recommend Markdown README per CONTEXT.md) |
| 4b. `tests/fixtures/sigstore/canonical/<wheel>.whl` + `<wheel>.whl.sigstore[.json]` (NEW) | fixture (binary artifact) | n/a | `tests/fixtures/v0_4_database.sqlite3` + `tests/fixtures/manifests/manifest_v1_full.toml` | role-match (committed binary/text fixture precedent) |
| 5. `tests/test_release_verification.py` (NEW) | test (unit + integration) | request-response (subprocess + in-process import) | `tests/test_release_gate.py` + `tests/test_lint_no_wallclock.py` | exact (subprocess + importlib.util dual pattern) |
| 6. `tests/test_release_yml_structure.py` (NEW) | test (structural workflow lint) | n/a (file-scan) | `tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py` + `test_pitfall_02_action_sha_pinning.py` | exact (regex over `.github/workflows/*.yml` pattern) |
| 7. `tests/test_release_md_stop_before_tag.py` (NEW) | test (docs prose lint) | n/a (file-scan) | `tests/docs/test_migration_v04_v05_schema_commands.py` + `tests/docs/test_plugin_security_threat_sentence.py` | exact (docs-substring-pin pattern) |
| 8. `tests/test_decision_no_pypi.py` (NEW) | test (decision-file shape + cross-ref) | n/a (file-scan) | `tests/docs/test_plugin_security_threat_sentence.py` (cross-ref pattern; doc + referencing source check) | role-match (no decision-file precedent; mirror the existence + literal-substring + cross-ref shape) |
| 9. `docs/RELEASE.md` (MODIFIED) | docs prose | n/a | existing file lines 142-144 (current step 7 verbatim) | self (in-place edit; byte-identity invariant applies to steps 1-6 and 8-9) |
| 10. `PROJECT.md` (MODIFIED) | docs prose (Markdown table) | n/a | existing file lines 26-34 (architecture-sketch table; same `| col | col | col |` shape) | role-match (table format precedent; key-decisions table is NEW table appended after architecture table) |

---

## Pattern Assignments

### 1. `.github/workflows/release.yml` (CI workflow, event-driven)

**Primary analog:** `.github/workflows/ci.yml` (post-Phase-51)
**Secondary analog:** `.github/workflows/issue-claim-watcher.yml` (per-job permissions opt-in pattern)

**Pattern A — Header + top-level `permissions: read-all` placement** (from `ci.yml:1-11`):
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions: read-all

jobs:
  lint-and-test:
```
**Deviation for `release.yml`:** Trigger block changes to:
```yaml
on:
  release:
    types: [published]
```
The top-level `permissions: read-all` line MUST appear at column 0 before `jobs:` (the regex in `test_ci_hardening_workflow_structure.py:34` matches `^permissions:\s*` at column 0; per-job permissions are intentionally rejected by that test).

**Pattern B — Per-job least-privilege opt-in** (from `issue-claim-watcher.yml:17-22`):
```yaml
permissions: read-all

jobs:
  detect-claim:
    permissions:
      issues: write
    if: >-
      github.event.issue.state == 'open'
```
**Deviation for `release.yml`:** The per-job opt-in block becomes:
```yaml
jobs:
  sign-and-attest:
    permissions:
      id-token: write
      contents: write
      attestations: write
    runs-on: ubuntu-latest
```
**Note:** `ci.yml` does NOT carry a per-job `permissions:` block on `lint-and-test` (it relies on the top-level `read-all`); `issue-claim-watcher.yml` IS the canonical analog for per-job opt-in. `release.yml` needs per-job opt-in (D-02) — copy the `issue-claim-watcher.yml` placement (immediately under the job name, before `runs-on:` / `if:`).

**Pattern C — SHA-pinned `uses:` with trailing `# vN.M.P` comment** (from `ci.yml:22-25, 27-32`):
```yaml
      - name: Check out repository
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml
```
**Apply verbatim to `release.yml`:**
- The two SHAs for `actions/checkout@v4.2.2` and `actions/setup-python@v5.6.0` are byte-identical between `ci.yml` and the new `release.yml` (RESEARCH.md §Standard Stack table cites them as `[VERIFIED: ci.yml line 23/28 post-Phase-51]`).
- `persist-credentials: false` is MANDATORY on every `actions/checkout` step in `release.yml` (enforced by `test_ci_hardening_workflow_structure.py:152-160`).
- The trailing `# vN.M.P` comment after each SHA is the pinact v4.0.0 tag-comment convention (Phase 51 D-03); the structural test does not enforce the comment, but the convention is documented in `51-02-SUMMARY.md`.
- The two NEW SHAs for `sigstore/gh-action-sigstore-python@04cffa1d795717b140764e8b640de88853c92acc` (v3.3.0) and `actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` (v4.1.0) follow the same shape (RESEARCH.md §Standard Stack rows 3-4).

**Pattern D — `python -m pip install` step format** (from `ci.yml:34-37`):
```yaml
      - name: Install package and dev dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .[dev]
```
**Deviation for `release.yml`:** `release.yml` installs `build` not `[dev]`:
```yaml
      - name: Install build
        run: |
          python -m pip install --upgrade pip
          python -m pip install build
```
**Crucial:** `sigstore` is NEVER added to `[project.dependencies]` or `[dev]` (D-03; verify_release.py shells out and prints an install hint). The release-time install of `build` happens here, on the fly, with no `pyproject.toml` change.

**Pattern E — No `${{ github.event.* }}` interpolation inside `run:` shells** (from `test_ci_hardening_workflow_structure.py:51-54, 163-174`):
```python
_EVENT_INTERPOLATION = re.compile(
    r"\$\{\{\s*[^}]*\b(?:github\.event\.[a-zA-Z0-9_.\[\]'\"]+"
    r"|github\.head_ref|github\.base_ref)\b"
)
```
**Apply to `release.yml`:** the release-published trigger exposes `github.event.release.tag_name` and similar; NEVER use these in a `run:` shell line. Pass via `env:` instead. `release.yml`'s tag value is otherwise unused at shell level (the sigstore action consumes OIDC token internally; `attest-build-provenance` reads the subject path from `with:` block, not shell).

**Pattern F — actionlint PR-time gate is inherited** (from `ci.yml:45-48`):
```yaml
      - name: Run actionlint (CIHARD-05)
        uses: raven-actions/actionlint@205b530c5d9fa8f44ae9ed59f341a0db994aa6f8 # v2.1.2
        with:
          version: v1.7.12
```
**No action needed in `release.yml`:** Phase 51's actionlint step in `ci.yml` runs against EVERY `.github/workflows/*.yml`, including the new `release.yml`. The PR that lands Phase 52 will have its `release.yml` linted automatically.

---

### 2. `scripts/verify_release.py` (Python script, request-response)

**Primary analog:** `scripts/release_gate.py`
**Secondary analog:** `scripts/lint_no_wallclock.py` (stdlib-only contract proof)

**Pattern A — Module docstring + stdlib-only invariant declaration** (from `release_gate.py:1-93`):
```python
"""Pre-tag release-quality gate for horus-os (Phase 39 + Phase 49).

Runs EIGHT checks before the maintainer cuts a tag (4 v0.4 + 4 v0.5):

1. pricing-freshness: ...
2. ci-two-variant-smoke: ...
...

Pure stdlib (json, datetime, pathlib, subprocess, sys, os,
argparse, zipfile, tempfile, difflib, shutil, sqlite3, importlib).
The `build` package is invoked via subprocess so this script
imports cleanly without it.
"""
```
**Apply to `verify_release.py`:** Open the docstring with the 5-check enumeration (wheel-signature / sdist-signature / tag-signature / sbom-signature [SKIPPED — Phase 53 flips] / changelog-cross-ref). Close with the stdlib-only declaration verbatim in shape: list every stdlib module used (argparse, dataclasses, os, pathlib, subprocess, sys, re — no third-party). State that `sigstore`, `git`, and `gh` are external CLIs invoked via subprocess.

**Pattern B — `from __future__` + imports + `REPO_ROOT` + module-level constants** (from `release_gate.py:95-135`):
```python
from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PRICING_PATH = REPO_ROOT / "src" / "horus_os" / "observability" / "pricing.json"
DEFAULT_CI_YML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
```
**Apply to `verify_release.py`:** module-level constants follow the same `DEFAULT_<NAME>_PATH = REPO_ROOT / "..."` shape. Add the hardcoded identity constants here:
```python
EXPECTED_IDENTITY_TEMPLATE = (
    "https://github.com/Ridou/horus-os/.github/workflows/release.yml"
    "@refs/tags/{version}"
)
EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"

# Module-import-time invariant per CONTEXT.md §specifics:
assert "refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE, (
    "EXPECTED_IDENTITY_TEMPLATE lost the {version} placeholder; "
    "verify_release.py refuses to run with a broken identity contract."
)
```

**Pattern C — `@dataclass(frozen=True) CheckResult` shape** (from `release_gate.py:137-148`):
```python
@dataclass(frozen=True)
class CheckResult:
    """One check outcome.

    `ok` is True on pass, False on fail, None on skip.
    `diagnostic` is empty on pass, a one-line failure reason on
    fail, or a skip reason on skip.
    """

    name: str
    ok: bool | None
    diagnostic: str
```
**Apply verbatim to `verify_release.py`** (copy this dataclass byte-for-byte; the SBOM check #4 uses `ok=None` for SKIPPED, the same shape).

**Pattern D — Subprocess shell-out with `capture_output=True, check=False`** (from `release_gate.py:307-330`, the canonical pattern):
```python
def check_pytest_pass(repo_root: Path) -> CheckResult:
    """Pass when `python -m pytest -q` from the repo root exits 0."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        last = (proc.stdout.strip().splitlines() or ["(no output)"])[-1]
        return CheckResult(
            name="pytest",
            ok=True,
            diagnostic=last,
        )
    tail_lines = proc.stdout.strip().splitlines()[-20:]
    return CheckResult(
        name="pytest",
        ok=False,
        diagnostic=(
            f"pytest exited {proc.returncode}; last 20 stdout lines: " + " | ".join(tail_lines)
        ),
    )
```
**Apply to `verify_release.py` checks #1, #2, #3, #5:** Use `[sys.executable, "-m", "sigstore", "verify", "identity", "--cert-identity", expected_identity, "--cert-oidc-issuer", EXPECTED_ISSUER, "--bundle", str(bundle_path), str(artifact_path)]` for checks #1 and #2. Use `["git", "verify-tag", f"v{version}"]` for check #3. Use `["gh", "release", "view", f"v{version}", "--json", "body", "--jq", ".body"]` for check #5. ALL use the same `capture_output=True, text=True, check=False` triple. ALL tail to 20 stdout lines on failure (mirrors the diagnostic shape).

**Pattern E — `_print_result` formatter** (from `release_gate.py:634-640`):
```python
def _print_result(result: CheckResult) -> None:
    if result.ok is True:
        print(f"OK    {result.name}: {result.diagnostic}")
    elif result.ok is False:
        print(f"FAIL  {result.name}: {result.diagnostic}")
    else:
        print(f"SKIP  {result.name}: {result.diagnostic}")
```
**Apply verbatim to `verify_release.py`** (copy byte-for-byte; the SBOM check returning `ok=None` will render as `SKIP  sbom-signature: SKIPPED — Phase 53 lands SBOM generation + signing`).

**Pattern F — argparse `--check` enum + main() dispatch** (from `release_gate.py:678-766`):
```python
def main(argv: list[str] | None = None) -> int:
    """Run the eight release-gate checks. Return 0 on full pass, 1 on any fail."""
    parser = argparse.ArgumentParser(
        description="Pre-tag release-quality gate for horus-os.",
    )
    parser.add_argument(
        "--check",
        choices=(
            "pricing",
            "wheel",
            "ci",
            "tests",
            "docs-drift",
            "plugin-install",
            "reference-manifest",
            "fixture-roundtrip",
        ),
        default=None,
        help="Run only the named check.",
    )
    # ...
    args = parser.parse_args(argv)
    # ...
    results: list[CheckResult] = []
    if selected in (None, "pricing"):
        results.append(check_pricing_freshness(pricing_path, max_age_days=max_age))
    if selected in (None, "ci"):
        results.append(check_ci_two_variant_smoke_present(ci_yml_path))
    # ...
    for result in results:
        _print_result(result)
    any_failed = any(r.ok is False for r in results)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
```
**Apply to `verify_release.py`:**
- `choices=("wheel", "sdist", "tag", "sbom", "changelog")` per D-08.
- ADD mandatory `--version` argument (`required=True`, regex-validate against `\d+\.\d+\.\d+(-rc\d+)?`).
- ADD mandatory `--cert-oidc-issuer` argument (`required=True`); compare `args.cert_oidc_issuer == EXPECTED_ISSUER` and call `parser.error(...)` (which exits 2) if mismatched (D-04 hard rule).
- ADD optional `--bundle PATH` and `--artifact PATH` (`type=Path`) for test-mode fixture injection.
- Dispatch list of 5 entries (mirrors release_gate.py:716-759 shape; each entry is `if selected in (None, "<name>"):` followed by `results.append(check_<name>(...))`).
- `any_failed = any(r.ok is False for r in results)` — `ok is None` (SBOM SKIPPED) does NOT count as failure; this is exactly the release_gate.py semantics.

**Pattern G — `HORUS_OS_*_PATH_OVERRIDE` env var for hermetic tests** (from `release_gate.py:643-675`):
```python
def _resolved_pricing_path() -> Path:
    override = os.environ.get("HORUS_OS_PRICING_PATH_OVERRIDE")
    if override:
        return Path(override)
    return DEFAULT_PRICING_PATH


def _resolved_ci_yml_path() -> Path:
    override = os.environ.get("HORUS_OS_CI_YML_PATH_OVERRIDE")
    if override:
        return Path(override)
    return DEFAULT_CI_YML_PATH
```
**Apply to `verify_release.py`:** `HORUS_OS_VERIFY_RELEASE_BUNDLE_OVERRIDE`, `HORUS_OS_VERIFY_RELEASE_ARTIFACT_OVERRIDE`, `HORUS_OS_VERIFY_RELEASE_SIGSTORE_BIN_OVERRIDE` (the last enables tests to inject a mock `sigstore` CLI). Planner finalizes exact env-var names.

**Pattern H — `lint_no_wallclock.py` minimal stdlib-only shape** (from `lint_no_wallclock.py:1-46`):
```python
"""Pitfall 3 (PITFALLS.md): forbid time.time() in observability code paths.

...
Exits 0 with a one-line ok message when no violations are found.
Exits 1 with one offending file:line:text per violation on stderr.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
```
**Use as fallback for `python -m sigstore` install-hint branch:** when `sigstore` CLI is absent, verify_release.py prints `pip install sigstore` to stderr and exits non-zero with a CheckResult diagnostic explaining the install hint — exactly the "fail loudly with one diagnostic" shape lint_no_wallclock.py uses.

---

### 3. `.planning/decisions/no-pypi-in-v0.6.md` (decision file)

**Analog: NONE.** The `.planning/decisions/` directory does not exist yet in the repo (confirmed: `ls .planning/` shows `phases/`, `research/`, `STATE.md`, `PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `README.md`, `config.json` — no `decisions/`). Phase 52 ESTABLISHES this directory with `no-pypi-in-v0.6.md` as its first file (CONTEXT.md §canonical_refs line 169 documents this explicitly).

**Recommended prose shape** (per CONTEXT.md `<code_context>` lines 188-191 and §specifics):

```markdown
# Decision: no PyPI publishing in v0.6

**Status:** OUT for v0.6 (revisited no earlier than v0.7).
**Date:** 2026-MM-DD.
**Owner:** maintainer.

## Context

horus-os v0.6 ships the contribution gate substrate: keyless OIDC artifact
signing (Phase 52), SBOM generation (Phase 53), and a user-facing trust-chain
verifier. The signing substrate makes PyPI Trusted Publishing (PEP 807)
technically feasible, since both rely on the same GitHub Actions OIDC
issuer. The question is whether v0.6 should also wire `pypa/gh-action-pypi-publish`
into `release.yml`.

## Decision criteria

1. horus-os does NOT currently publish to PyPI. There is no `horus-os` (or
   `horus_os`) name reserved on PyPI for this project.
2. There is no `PYPI_API_TOKEN` secret configured on the repo. Trusted
   Publishing removes the need for that token, but reserving the name and
   configuring the project's trusted publisher on PyPI is a separate
   operational step that has not been done.
3. The v0.6 milestone goal is a contribution gate, not a distribution
   channel. Users install via `pip install -e .` from a clone.
4. Adding PEP 807 wiring in v0.6 would introduce a release-time failure
   mode (PyPI Trusted Publishing flow misconfiguration) that is unrelated
   to the contribution gate.

## Decision (final, until revisited)

PyPI Trusted Publishing (PEP 807) is OUT OF SCOPE for v0.6.

v0.7 (or a later milestone) may revisit when (a) the maintainer reserves
the `horus-os` name on PyPI, (b) configures Trusted Publishing on the
PyPI project page, and (c) decides to commit to PyPI as a distribution
channel. At that point, the wiring is a single step in `release.yml` of
the form:

\`\`\`yaml
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@<sha>  # vN.M.P
\`\`\`

with a per-job `id-token: write` permission (already present on the
`sign-and-attest` job per Phase 52 D-02).

## References

- PEP 807: https://peps.python.org/pep-0807/
- `pypa/gh-action-pypi-publish`: https://github.com/pypa/gh-action-pypi-publish
- Phase 52 CONTEXT.md D-09: couples this decision file with PROJECT.md table append.
- Phase 52 RESEARCH.md §Standard Stack: OIDC issuer reused if v0.7 wires PEP 807.
```

**Prose discipline checklist** (from CONTEXT.md `<code_context>`):
- Short: ≤2 pages (≤200 lines of Markdown).
- Terminates with `**Decision (final, until revisited):**` block — this is the load-bearing literal `test_decision_no_pypi.py` greps for.
- Referenced from `PROJECT.md` key-decisions table (see file #10 below).
- No em-dashes (CLAUDE.md HR3).
- No PII / contributor handles other than `Ridou/horus-os` (CLAUDE.md HR1; the `Ridou` in `EXPECTED_IDENTITY_TEMPLATE` is the only allowed handle by design).

---

### 4a. `tests/fixtures/sigstore/canonical/README.md` (fixture documentation)

**Primary analog:** `tests/fixtures/installer/__init__.py:1-16`
**Secondary analog:** `tests/fixtures/broken_plugins/__init__.py:1-17`

The existing precedent uses `__init__.py` docstrings, not standalone `README.md` files. CONTEXT.md D-07 explicitly calls for `README.md` (rehearsal recording procedure documentation), so deviate from the precedent but mirror its CONTENT shape.

**Pattern A — Fixture-dir documentation shape** (from `tests/fixtures/installer/__init__.py:1-16`):
```python
"""Synthetic wheel fixtures for Phase 44 installer tests.

The four template directories under ``tests/fixtures/installer/`` are
turned into real ``.whl`` / ``.tar.gz`` files by
``build_fixture_wheels.build_fixture_wheels(tmp_dir)`` at test-session
start. The synthetic wheels are byte-exact zips of the template
``horus-plugin.toml`` + ``RECORD`` + ``METADATA`` contents, laid out in
the standard ``<dist-info>`` directory layout that
``read_wheel_record`` / ``read_wheel_metadata`` /
``extract_horus_plugin_toml`` parse.

Keeping the templates as plain text files (rather than building a
wheel via ``setuptools`` or ``build``) avoids a real ``pip wheel``
dependency in CI and keeps the per-test wheel construction
deterministic.
"""
```

**Apply to `tests/fixtures/sigstore/canonical/README.md`:** convert from docstring-style to a Markdown README with the same INFORMATIONAL CATEGORIES — what the fixture is, what test consumes it, how it was produced (the rehearsal recording procedure), and why it is committed rather than generated at test time.

Suggested headings (planner finalizes):
- `# Canonical sigstore fixtures for verify_release.py`
- `## Files in this directory` — name + role of each
- `## Recording procedure (v0.6.0-rc1 rehearsal)` — the PITFALL 11 release-rehearsal procedure (cite VALIDATION.md "Manual-Only Verifications" row 1 steps 1-7 verbatim)
- `## Why committed instead of generated` — same rationale as installer/__init__.py (CI hermeticity; live-signing requires `id-token: write` in test runner = forbidden by CIHARD-02)
- `## Observed bundle filename suffix` — sigstore-python's bundle is either `.sigstore` or `.sigstore.json` depending on action version; this README pins which suffix the v0.6.0-rc1 rehearsal produced (RESEARCH.md confidence note flags this as MEDIUM)

### 4b. `tests/fixtures/sigstore/canonical/<wheel>.whl` + `.sigstore[.json]` (binary fixture)

**Primary analog:** `tests/fixtures/v0_4_database.sqlite3` (committed binary fixture)
**Secondary analog:** `tests/fixtures/manifests/manifest_v1_full.toml` (committed text fixture as test-source-of-truth)

**Pattern A — Committed binary fixture precedent** (file `tests/fixtures/v0_4_database.sqlite3`, 110 KB, committed to git): a binary artifact produced once via a build script (`scripts/build_v0_4_fixture.py`) and committed to the repo for hermetic test consumption. The release_gate fixture-roundtrip check (`release_gate.py:619-631`) COPIES it to a tempfile and unlinks in a `finally` block to prevent mutation.

**Apply to sigstore fixtures:** treat the `.whl` and `.sigstore[.json]` files as identical-shape committed binary artifacts. Tests in `tests/test_release_verification.py` MUST NOT mutate them — pass their paths to subprocess as `str(fixture_path)`, never copy-and-modify in place. Sizes should be small (the wheel is from `python -m build` of horus-os itself; expect <1 MB; the bundle is a few KB).

**Pattern B — Test-source-of-truth fixture precedent** (file `tests/fixtures/manifests/manifest_v1_full.toml`, 860 bytes; consumed by `tests/docs/test_plugins_md_anatomy.py:32-33`):
```python
MANIFEST_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "manifests" / "manifest_v1_full.toml"
```
**Apply to sigstore fixtures:** same `REPO_ROOT / "tests" / "fixtures" / "sigstore" / "canonical" / "<filename>"` shape in `tests/test_release_verification.py`.

---

### 5. `tests/test_release_verification.py` (test — unit + integration)

**Primary analog:** `tests/test_release_gate.py` (in-process import of script under test)
**Secondary analog:** `tests/test_lint_no_wallclock.py` (subprocess shell-out to script under test)

**Pattern A — In-process module load without sys.path mutation** (from `test_release_gate.py:31-46`):
```python
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_MODULE_NAME = "_release_gate_under_test"


def _load_release_gate_module():
    """Import scripts/release_gate.py as a module without modifying sys.path.

    The module is registered in `sys.modules` because @dataclass needs to
    introspect the defining module via `sys.modules[cls.__module__]`.
    """
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    script = REPO_ROOT / "scripts" / "release_gate.py"
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module
```
**Apply verbatim** (rename `_release_gate_under_test` to `_verify_release_under_test` and the script path to `scripts/verify_release.py`). This pattern lets tests call `mod.check_wheel_signature(...)` directly without subprocess overhead.

**Pattern B — Per-check unit test shape** (from `test_release_gate.py:84-99`):
```python
def test_pricing_freshness_passes_when_within_threshold(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    _write_pricing_json(pricing, date.today().isoformat())
    result = mod.check_pricing_freshness(pricing_path=pricing, max_age_days=14)
    assert result.ok is True, result.diagnostic


def test_pricing_freshness_fails_when_older_than_threshold(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    stale = (date.today() - timedelta(days=30)).isoformat()
    _write_pricing_json(pricing, stale)
    result = mod.check_pricing_freshness(pricing_path=pricing, max_age_days=14)
    assert result.ok is False
    assert "30" in result.diagnostic
    assert "14" in result.diagnostic
```
**Apply to `test_release_verification.py`:** five tests per VALIDATION.md row 4 (SIGN-04):
1. Canonical-fixture pass — calls `mod.check_wheel_signature(bundle=<fixture path>, artifact=<fixture path>, version="0.6.0-rc1")` and asserts `result.ok is True`.
2. Missing-issuer refuse — calls `mod.main(["--version", "0.6.0-rc1"])` (no `--cert-oidc-issuer`) and asserts `SystemExit` with exit code 2 (argparse `required=True` error).
3. Wrong-issuer refuse — calls `mod.main(["--version", "0.6.0-rc1", "--cert-oidc-issuer", "https://example.com/oauth"])` and asserts non-zero exit + diagnostic mentions the expected issuer.
4. SBOM-stub returns SKIPPED — calls `mod.check_sbom_signature(...)` and asserts `result.ok is None` AND `"SKIPPED" in result.diagnostic` AND `"Phase 53" in result.diagnostic`.
5. Full-run all-checks — calls `mod.main(["--version", "0.6.0-rc1", "--cert-oidc-issuer", EXPECTED_ISSUER, "--bundle", ..., "--artifact", ...])`; asserts exit 0 (or asserts mixed pass/skip exit semantics per release_gate precedent: `ok is None` does not fail).

**Pattern C — Subprocess shell-out integration test** (from `test_lint_no_wallclock.py:20-32`):
```python
def test_no_wallclock_in_observability_paths() -> None:
    script = REPO_ROOT / "scripts" / "lint_no_wallclock.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"lint_no_wallclock found violations:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
```
**Optional for `test_release_verification.py`:** one end-to-end smoke shelling out to `[sys.executable, str(REPO_ROOT / "scripts" / "verify_release.py"), "--version", "0.6.0-rc1", "--cert-oidc-issuer", EXPECTED_ISSUER, "--bundle", ..., "--artifact", ...]`. Cross-OS safe: uses `sys.executable` not bare `python`; `str(path)` everywhere; `capture_output=True, text=True, check=False`.

**Pattern D — Monkeypatch env override** (from `test_release_gate.py:146-159`):
```python
def test_main_exit_zero_when_all_checks_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    _write_pricing_json(pricing, date.today().isoformat())
    ci = tmp_path / "ci.yml"
    _write_ci_yml(ci, has_no_otel=True, has_with_otel=True)
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_TESTS", "1")
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_BUILD", "1")
    monkeypatch.setenv("HORUS_OS_PRICING_PATH_OVERRIDE", str(pricing))
    monkeypatch.setenv("HORUS_OS_CI_YML_PATH_OVERRIDE", str(ci))
    exit_code = mod.main([])
    assert exit_code == 0
```
**Apply to `test_release_verification.py`:** use `monkeypatch.setenv("HORUS_OS_VERIFY_RELEASE_BUNDLE_OVERRIDE", str(canonical_bundle))` (and the artifact equivalent) to inject the canonical fixture path into the script's path-resolution helpers.

---

### 6. `tests/test_release_yml_structure.py` (test — structural workflow lint)

**Primary analog:** `tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py`
**Secondary analog:** `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py`

**Pattern A — Workflow-file regex helpers** (from `test_ci_hardening_workflow_structure.py:24-55`):
```python
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Matches `permissions:` at column 0 (workflow-level, not job-level).
_TOP_LEVEL_PERMISSIONS = re.compile(r"^permissions:\s*", re.MULTILINE)

# Matches a `uses: actions/checkout@...` line.
_CHECKOUT_USES = re.compile(
    r"^(\s*)-?\s*uses:\s*actions/checkout@\S+",
    re.MULTILINE,
)
```
**Note for `test_release_yml_structure.py`:** since this test lives at `tests/` top-level (not nested under `test_contribution_gate_pitfalls/`), `REPO_ROOT = Path(__file__).resolve().parents[1]` (one fewer `.parents` index). Compare:
- `test_release_verification.py` (top-level): `parents[1]`
- `test_ci_hardening_workflow_structure.py` (nested one level): `parents[2]`
The analog uses `parents[2]`; `test_release_yml_structure.py` uses `parents[1]`.

**Pattern B — SHA-pin regex** (from `test_pitfall_02_action_sha_pinning.py:27-31`):
```python
_USES_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)")
_ALLOWED_REF = re.compile(r"^[0-9a-f]{40}$")
```
**Apply directly to `test_release_yml_structure.py`** for the "every `uses:` in release.yml is SHA-pinned" assertion (VALIDATION.md row 1, check #9).

**Pattern C — Test shape: assert-on-violation-list with diagnostic** (from `test_ci_hardening_workflow_structure.py:141-149`):
```python
def test_permissions_read_all_on_every_workflow() -> None:
    """CIHARD-02: every workflow has a top-level `permissions:` key."""
    raw_offenders = _find_workflows_missing_top_level_permissions(WORKFLOWS_DIR)
    offenders = [p.relative_to(REPO_ROOT) for p in raw_offenders]
    assert not offenders, (
        "Workflows without a top-level `permissions:` block (CIHARD-02):\n"
        + "\n".join(f"  {p}" for p in offenders)
        + "\nAdd `permissions: read-all` to the top of every workflow above `jobs:`."
    )
```
**Apply to `test_release_yml_structure.py` (VALIDATION.md row 1 enumerates 9 assertions):**
1. `test_release_yml_exists` — file exists at `.github/workflows/release.yml`.
2. `test_on_release_published_trigger` — text contains `on:\n  release:\n    types: [published]` (allow whitespace flexibility).
3. `test_top_level_permissions_read_all` — text contains `permissions: read-all` at column 0.
4. `test_per_job_id_token_write` — sign-and-attest job has `permissions:\n      id-token: write` within job-block indent.
5. `test_per_artifact_attest` — TWO occurrences of `uses: actions/attest-build-provenance@` in the file (one wheel, one sdist).
6. `test_sigstore_action_literal_present` — text contains literal `sigstore/gh-action-sigstore-python` (Phase 57's release-gate cross-ref depends on this).
7. `test_sigstore_action_sha_pinned` — the sigstore line matches `_USES_PATTERN` AND ref matches `_ALLOWED_REF` (40-char hex).
8. `test_sigstore_step_timeout_minutes_5` — sigstore step block contains `timeout-minutes: 5` (SIGN-01 budget).
9. `test_every_uses_in_release_yml_sha_pinned` — scoped reuse of `_scan_workflow_dir` filtered to release.yml.

---

### 7. `tests/test_release_md_stop_before_tag.py` (test — docs prose lint)

**Primary analog:** `tests/docs/test_migration_v04_v05_schema_commands.py`
**Secondary analog:** `tests/docs/test_plugin_security_threat_sentence.py`

**Pattern A — Module fixture loading doc text** (from `test_migration_v04_v05_schema_commands.py:30-37`):
```python
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "docs" / "MIGRATION-v0.4-to-v0.5.md"


@pytest.fixture(scope="module")
def migration_text() -> str:
    if not MIGRATION_PATH.is_file():
        pytest.fail(
            "docs/MIGRATION-v0.4-to-v0.5.md does not exist — Phase 47 must "
            "ship the migration guide."
        )
    return MIGRATION_PATH.read_text(encoding="utf-8")
```
**Apply to `test_release_md_stop_before_tag.py`:** module-scoped fixture loading `docs/RELEASE.md`. **Path adjustment:** `parents[1]` (top-level test) not `parents[2]` (nested test).

**Pattern B — Substring assertion with helpful diagnostic** (from `test_migration_v04_v05_schema_commands.py:44-50`):
```python
def test_migration_doc_contains_verification_command(migration_text: str) -> None:
    """The migration doc names the PRAGMA user_version verification command."""
    assert "PRAGMA user_version" in migration_text, (
        "docs/MIGRATION-v0.4-to-v0.5.md must document the verification "
        'command `sqlite3 ~/.horus-os/data.db "PRAGMA user_version"` so '
        "the user can confirm the v5→v6 migration ran."
    )
```
**Apply to `test_release_md_stop_before_tag.py`** for the three tests per VALIDATION.md row 3 (SIGN-03):
1. `test_step_6_5_gitsign_inserted` — assert `"git config --get gitsign.connectorID"` literal is in the doc AND appears AFTER current step 6 text AND BEFORE current step 7 text (use string `.find()` index comparison).
2. `test_step_7_uses_tag_dash_s` — assert `"git tag -s vN.M.P"` is present AND `"git tag -a vN.M.P"` is absent (the literal swap).
3. `test_steps_1_through_6_byte_identical` — pin the pre-edit text of steps 1-6 as a literal Python string constant at the top of the test file (extracted from current `docs/RELEASE.md:10-49`); assert it appears verbatim in the post-edit doc. Same for steps 8-9 (current `docs/RELEASE.md:146-157`). This enforces the "insertions allowed, mutations not" discipline (Phase 51 D-06 + ARCHITECTURE.md byte-identity invariant).

**Pattern C — Cross-ref test pattern** (from `test_plugin_security_threat_sentence.py:71-84`):
```python
def test_installer_references_security_doc() -> None:
    """The installer grant prompt references docs/PLUGIN-SECURITY.md."""
    if not INSTALLER_PATH.is_file():
        pytest.fail(
            "src/horus_os/plugins/installer.py not found — cannot verify "
            "installer linkage to the security doc."
        )
    installer_text = INSTALLER_PATH.read_text(encoding="utf-8")
    assert "docs/PLUGIN-SECURITY.md" in installer_text, (
        "The installer grant prompt must reference docs/PLUGIN-SECURITY.md "
        ...
    )
```
**Apply to `test_release_md_stop_before_tag.py` (optional 4th test):** assert that step 6.5 text references `docs/MAINTAINER-RUNBOOK.md` (the Phase 56 forward reference per D-05).

---

### 8. `tests/test_decision_no_pypi.py` (test — decision-file shape + cross-ref)

**Analog:** mirror `tests/docs/test_plugin_security_threat_sentence.py` (existence + literal-substring + cross-ref to referencing source file) — no direct decision-file precedent.

**Pattern A — Three-test structure** (mirrors `test_plugin_security_threat_sentence.py:39-84`):

The three tests per VALIDATION.md row 5 (SIGN-05):

1. `test_decision_file_exists`:
   ```python
   from __future__ import annotations

   from pathlib import Path

   import pytest

   REPO_ROOT = Path(__file__).resolve().parents[1]  # top-level test
   DECISION_PATH = REPO_ROOT / ".planning" / "decisions" / "no-pypi-in-v0.6.md"
   PROJECT_MD_PATH = REPO_ROOT / "PROJECT.md"


   @pytest.fixture(scope="module")
   def decision_text() -> str:
       if not DECISION_PATH.is_file():
           pytest.fail(
               ".planning/decisions/no-pypi-in-v0.6.md does not exist — "
               "Phase 52 SIGN-05 requires this decision file."
           )
       return DECISION_PATH.read_text(encoding="utf-8")


   def test_decision_file_exists(decision_text: str) -> None:
       assert decision_text.strip(), ".planning/decisions/no-pypi-in-v0.6.md is empty"
   ```

2. `test_decision_file_has_terminator`:
   ```python
   def test_decision_file_has_terminator(decision_text: str) -> None:
       """The decision file ends with the canonical decision-block terminator."""
       assert "**Decision (final, until revisited):**" in decision_text, (
           "Decision file must contain the literal '**Decision (final, until revisited):**' "
           "block per CONTEXT.md decision-file shape convention."
       )
   ```

3. `test_project_md_references_decision_file` (mirrors `test_installer_references_security_doc` shape):
   ```python
   def test_project_md_references_decision_file() -> None:
       """PROJECT.md key-decisions table contains a row referencing the decision file."""
       if not PROJECT_MD_PATH.is_file():
           pytest.fail("PROJECT.md not found")
       project_text = PROJECT_MD_PATH.read_text(encoding="utf-8")
       assert ".planning/decisions/no-pypi-in-v0.6.md" in project_text, (
           "PROJECT.md key-decisions table must contain a row referencing "
           ".planning/decisions/no-pypi-in-v0.6.md per SIGN-05 / D-09."
       )
   ```

---

### 9. `docs/RELEASE.md` (MODIFIED — STOP-BEFORE-TAG insertions)

**Analog:** the file itself, current state lines 142-144.

**Existing step 7 verbatim** (`docs/RELEASE.md:142-144` pre-edit):
```markdown
7. Create the annotated tag:
   `git tag -a vN.M.P -m "vN.M.P - <milestone-name>"`.
   Push: `git push origin vN.M.P`.
```

**Existing step 6 verbatim** (`docs/RELEASE.md:140-141` pre-edit):
```markdown
6. Push to `main`. Wait for CI green on the full 3-OS x 2-Python
   matrix (`gh run list --branch main --limit 1`).
```

**Required post-edit shape (D-05):**
```markdown
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
```

**Byte-identity invariant:** steps 1-6 (lines 122-141 in current file) and steps 8-9 (lines 145-157 in current file) MUST remain byte-identical. The Markdown list-numbering across step 6 / step 6.5 / step 7 is the inserted boundary — the test in file #7 pins both halves of the boundary as literal strings.

---

### 10. `PROJECT.md` (MODIFIED — key-decisions table append)

**Analog:** the existing architecture-sketch table at `PROJECT.md:26-34`.

**Existing precedent — Markdown table shape** (`PROJECT.md:26-34`):
```markdown
| Layer | Default choice | Notes |
|-------|----------------|-------|
| Agent runtime | Python + Anthropic SDK + Google Gemini SDK | Synchronous and async paths both supported |
| Persistence | SQLite (WAL mode) | Single file; trivially portable |
| Vector store | Local Chroma or duckdb-vss | Embedding backend pluggable |
| Knowledge base | Local markdown files + indexed search | User edits in any editor |
| Dashboard | Next.js, served locally | Optional; CLI works without it |
| Chat surface | CLI first; web chat next; third-party (Discord, Slack) via opt-in adapters | |
| Process manager | Native OS service file (systemd unit, launchd plist, Windows scheduled task) | One reference recipe per OS |
```

**The key-decisions table does not exist yet in PROJECT.md.** Phase 52 D-09 creates it. CONTEXT.md describes the row shape as `decision | status | reference-file`.

**Recommended addition to `PROJECT.md`** (planner chooses placement — after the "Status" line at the bottom or as a new section before "Out of scope"):

```markdown
## Key decisions (v0.6 contribution gate)

These are the v0.6 milestone's locked architectural decisions. Each
links to a one-page rationale under `.planning/decisions/`.

| Decision | Status | Reference |
|----------|--------|-----------|
| PyPI Trusted Publishing (PEP 807) | OUT for v0.6 | [.planning/decisions/no-pypi-in-v0.6.md](.planning/decisions/no-pypi-in-v0.6.md) |
```

Phase 55/56 will append four more rows (per CONTEXT.md / ROADMAP §55-56: `no-cla.md`, `no-stale-bot.md`, `sigstore-keyless.md`, `sbom-cyclonedx.md`); Phase 52 ships only the `no-pypi-in-v0.6.md` row. The byte-identity invariant for Phase 52: existing rows in the architecture-sketch table (lines 26-34) are NOT reordered or modified.

---

## Shared Patterns

### S-1. Cross-OS subprocess shape

**Source:** `scripts/release_gate.py:307-330`
**Apply to:** `scripts/verify_release.py` (all 5 checks) AND any integration test in `tests/test_release_verification.py` that shells out.

```python
proc = subprocess.run(
    [sys.executable, "-m", "<tool>", ...],
    cwd=str(repo_root),  # always str(), never raw Path on Windows
    capture_output=True,
    text=True,
    check=False,
)
```

**Rules:**
- `sys.executable` not bare `"python"` (CLAUDE.md HR5 + Windows where `python` may resolve to py-launcher).
- `str(path)` everywhere a subprocess arg position expects a string (Windows quirk: some subprocess paths historically rejected `Path` objects).
- `capture_output=True, text=True, check=False` triple — capture both streams, decode as text, NEVER raise on non-zero (the script's caller decides how to handle exit codes).
- For external CLIs (`git`, `gh`, `sigstore` via `python -m sigstore`), the form is `[sys.executable, "-m", "sigstore", ...]` for sigstore (always shell out via `-m`) but `["git", ...]` and `["gh", ...]` for the native binaries (verify_release.py prints install hints if these are absent).

### S-2. `pathlib`-only file access

**Source:** every script and test in this analysis.
**Apply to:** every NEW Python file in Phase 52.

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # for scripts/
# OR
REPO_ROOT = Path(__file__).resolve().parents[1]     # for tests/ top-level
# OR
REPO_ROOT = Path(__file__).resolve().parents[2]     # for tests/<subdir>/

text = path.read_text(encoding="utf-8")
data = path.read_bytes()
```

**Never:** `os.path.join`, string concatenation of paths, missing `encoding="utf-8"` on `read_text`/`write_text` (Windows defaults to cp1252 without it).

### S-3. SHA-pin convention with trailing `# vN.M.P` comment

**Source:** `.github/workflows/ci.yml` (every `uses:` line).
**Apply to:** every `uses:` line in `.github/workflows/release.yml`.

```yaml
uses: <owner>/<repo>@<40-char-hex-sha> # vN.M.P
```

**Enforcement:** `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py:_USES_PATTERN` + `_ALLOWED_REF` regex (already runs against every workflow, automatic coverage for the new `release.yml`).

### S-4. No em-dashes anywhere in committed prose

**Source:** CLAUDE.md HR3.
**Apply to:** release.yml comments, verify_release.py docstrings + diagnostics, no-pypi-in-v0.6.md, PROJECT.md row, RELEASE.md step 6.5 prose, fixture README.

Use commas, periods, or hyphens. The em-dash character (`—`) is forbidden; the en-dash (`–`) is also forbidden by extension of the same rule.

### S-5. No comment-only false positives in regex scanners

**Source:** `scripts/lint_no_wallclock.py:88-91` + `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py:49-52` + `test_ci_hardening_workflow_structure.py:108-110`.
**Apply to:** any workflow-scanning logic in `tests/test_release_yml_structure.py`.

```python
# Skip pure comment lines so workflow documentation comments
# mentioning ${{ github.event.* }} examples are not flagged.
stripped = raw_line.strip()
if stripped.startswith("#"):
    continue
```

---

## No Analog Found

| File | Role | Data Flow | Reason / Recommendation |
|------|------|-----------|-------------------------|
| `.planning/decisions/no-pypi-in-v0.6.md` | decision file | n/a | The `.planning/decisions/` directory does NOT exist in the repo at the time of this mapping. Phase 52 establishes it. Use the prose shape recommended in §Pattern Assignments file #3 (≤200-line Markdown; status / context / decision-criteria / decision-block / references; terminates with the literal `**Decision (final, until revisited):**` block that `test_decision_no_pypi.py` greps for). |
| `tests/fixtures/sigstore/canonical/README.md` (Markdown form) | fixture doc | n/a | The repo precedent for fixture-dir documentation is `__init__.py` docstrings (e.g., `tests/fixtures/installer/__init__.py:1-16`). CONTEXT.md D-07 explicitly requires a Markdown `README.md` (the rehearsal recording procedure is a procedural document, not a Python-package docstring). Mirror the CONTENT structure of `installer/__init__.py` docstring (what / how-built / why-committed) but render as Markdown sections. |
| `PROJECT.md` key-decisions TABLE (the table itself, not the file) | docs prose section | n/a | The `## Key decisions` heading + 3-column table do not exist in PROJECT.md yet. The architecture-sketch table (lines 26-34) is the formatting precedent; Phase 52 ADDS a new sibling table per §Pattern Assignments file #10. |

---

## Metadata

**Analog search scope:**
- `.github/workflows/*.yml` (2 files; both read)
- `scripts/*.py` (12 files listed; 2 read in full: release_gate.py portions + lint_no_wallclock.py)
- `tests/*.py` + `tests/docs/*.py` + `tests/test_contribution_gate_pitfalls/*.py` + `tests/fixtures/**/__init__.py` (analog-bearing files read; 75+ tests scanned for shape)
- `docs/RELEASE.md` (read in full)
- `PROJECT.md` (read in full)
- `.planning/decisions/` (confirmed absent)
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` (grep'd for "key-decisions" precedent)

**Files scanned:** ~25 (analog candidates) + 8 read in full.

**Pattern extraction date:** 2026-05-29.
