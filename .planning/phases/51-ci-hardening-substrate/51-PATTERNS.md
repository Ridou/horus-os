# Phase 51: CI hardening substrate - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 6 (2 MODIFY workflow YAMLs, 4 NEW Python test files)
**Analogs found:** 6 / 6 (every new/modified file has a direct in-tree precedent)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.github/workflows/ci.yml` (MODIFY) | workflow YAML (CI driver) | event-driven (push/PR) | itself, pre-change (`.github/workflows/ci.yml`) | exact (self-as-analog for step insertion order) |
| `.github/workflows/issue-claim-watcher.yml` (MODIFY) | workflow YAML (event handler) | event-driven (issue_comment) | `.github/workflows/ci.yml` (top-level `permissions:` + SHA-pin shape transplanted here) | role-match (different trigger, same hardening recipe) |
| `tests/test_contribution_gate_pitfalls/__init__.py` (NEW) | test package marker | n/a | `tests/test_plugin_pitfalls/__init__.py` | exact (v0.5 directory marker, two-line comment) |
| `tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py` (NEW) | pytest regression (single-pitfall) | source-tree text scan over `.github/workflows/*.yml` | `tests/test_plugin_pitfalls/test_pitfall_01_default_allow.py` (file shape) + `tests/plugins/test_reference_plugin_public_api_only.py` (regex-over-source-tree mechanism) | role-match (file shape) + exact (scanning mechanism) |
| `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py` (NEW) | pytest regression (single-pitfall) | source-tree regex scan | `tests/plugins/test_reference_plugin_public_api_only.py` (BAD/GOOD regex partition + sorted rglob + offender list) | exact (the closest in-tree precedent for "regex over every line of every file in a dir, collect offenders") |
| `tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py` (NEW) | pytest regression (multi-claim structural) | source-tree text scan, line-level state machine | `scripts/lint_no_wallclock.py` (line-by-line walk with state, anchored substring checks, deterministic file ordering) + `tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py` (multi-`def` structural assertions in one module) | role-match (lint state machine) + exact (multi-`def` test shape) |

## Pattern Assignments

### `.github/workflows/ci.yml` (MODIFY — workflow YAML, event-driven)

**Analog:** itself, pre-change. The planner inserts the new actionlint step into a precise gap and adds three cross-cutting hardening edits in place. Capture the existing step order so insertions land at the right line.

**`lint-and-test` job step ordering pattern** (`.github/workflows/ci.yml` lines 19-55):
```yaml
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml

      - name: Install package and dev dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .[dev]

      - name: Run ruff lint
        run: ruff check .

      - name: Run ruff format check
        run: ruff format --check .

      - name: time.time() lint gate (Pitfall 3)
        run: python scripts/lint_no_wallclock.py
```

Per D-01, the new `Run actionlint (CIHARD-05)` step is inserted **between line 39 (`Run ruff format check`) and line 41 (`time.time() lint gate (Pitfall 3)`)**. The existing step naming uses the literal `(<TAG>)` suffix convention (`(Pitfall 3)`, `(METRIC-05 / TEST-12)` at line 51), so `(CIHARD-05)` matches the in-tree grep convention.

**Step-name-as-grep-target precedent** (`.github/workflows/ci.yml` line 51):
```yaml
      - name: capture-overhead benchmark (METRIC-05 / TEST-12)
        run: pytest tests/perf/test_capture_overhead.py -v
```
This is the established v0.5 convention the planner mirrors with the literal `(CIHARD-05)` substring; the regression test for CIHARD-05 simply greps `ci.yml` for `(CIHARD-05)`.

**Every-job `actions/checkout` site to retrofit** (`.github/workflows/ci.yml` lines 20-21, 68-69, 101-102, 140-141, 180-181):
```yaml
      - name: Check out repository
        uses: actions/checkout@v4
```
Five identical `actions/checkout@v4` invocations across the five jobs (`lint-and-test`, `install-smoke`, `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin`). Each one gets (a) SHA-pin rewrite (CIHARD-04) and (b) `with: persist-credentials: false` block (CIHARD-03).

**Every-job `actions/setup-python` site to retrofit** (`.github/workflows/ci.yml` lines 23-28 and four parallel instances):
```yaml
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml
```
Existing `with:` block stays byte-identical; only the `uses:` line gets the SHA rewrite + trailing `# v5.6.0` tag-comment.

**Top-of-file shape pre-change** (`.github/workflows/ci.yml` lines 1-9):
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
```
Top-level `permissions: read-all` (CIHARD-02) lands as a new block between line 7 (`branches: [main]`) and line 9 (`jobs:`). Triggers are NOT modified (preserves the existing `push`+`pull_request`-only discipline; never `pull_request_target`).

**Byte-identity job-name contract** (`.github/workflows/ci.yml` lines 10, 57, 91, 130, 170):
```yaml
  lint-and-test:
  install-smoke:
  install-smoke-no-otel:
  install-smoke-with-otel:
  install-smoke-plugin:
```
These five job-key lines are byte-identity contracts grep'd by `scripts/release_gate.py`. Phase 51 must not rename, reorder, or delete any. (Inserting a new step inside a job is fine; the job-key line itself is the anchor.)

---

### `.github/workflows/issue-claim-watcher.yml` (MODIFY — workflow YAML, event-driven)

**Analog:** the post-Phase-51 `ci.yml` top-level shape (per D-06: same hardening recipe transplanted; CIHARD-02 + CIHARD-04 only; the file is later deleted in Phase 59).

**Current top-of-file shape pre-change** (`.github/workflows/issue-claim-watcher.yml` lines 1-20):
```yaml
name: Issue claim watcher

# Posts a canned reply when an outside commenter uses
# ... [comment block preserved] ...

on:
  issue_comment:
    types: [created]

permissions:
  issues: write

jobs:
  detect-claim:
```
The existing top-level `permissions: issues: write` (lines 17-18) becomes top-level `permissions: read-all` (CIHARD-02 baseline), and per-job `permissions: issues: write` lands inside `detect-claim:` (line 21). The behavior is unchanged; only the default scope tightens.

**`actions/github-script@v7` sites to retrofit** (`.github/workflows/issue-claim-watcher.yml` lines 44, 64):
```yaml
        uses: actions/github-script@v7
```
Two instances, both get the SHA-pin rewrite + trailing `# v7.1.0` tag-comment (CIHARD-04). The surrounding `with: script: |` block is byte-identical. This file ships ZERO `actions/checkout` steps (the workflow runs purely against the GitHub API), so `persist-credentials: false` is N/A here.

**Trigger shape unchanged** (`.github/workflows/issue-claim-watcher.yml` lines 13-15):
```yaml
on:
  issue_comment:
    types: [created]
```
Phase 51 preserves this byte-identically. CIHARD-01 forbids any drift to `pull_request_target`; the existing `issue_comment` trigger is safe and stays.

---

### `tests/test_contribution_gate_pitfalls/__init__.py` (NEW — test package marker)

**Analog:** `tests/test_plugin_pitfalls/__init__.py` (the v0.5 TEST-17 directory marker).

**Full content pattern** (`tests/test_plugin_pitfalls/__init__.py` lines 1-2):
```python
# Marker file for the Phase 46 pitfall regression suite.
# See .planning/research/PITFALLS.md for the 12 documented pitfalls.
```
Two-line comment, no exports, no imports. New file follows the same shape with phase number 51 and the v0.6 contribution-gate framing (planner picks exact wording; the structural pattern is "two-line comment, nothing else").

---

### `tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py` (NEW — pytest regression)

**Analog (file shape):** `tests/test_plugin_pitfalls/test_pitfall_01_default_allow.py`.
**Analog (scanning mechanism):** `tests/plugins/test_reference_plugin_public_api_only.py`.

**Module-docstring + import-block + structural-assertion pattern** (`tests/test_plugin_pitfalls/test_pitfall_01_default_allow.py` lines 1-40):
```python
"""Pitfall 1: Default-allow capability grants normalize compromise.

See .planning/research/PITFALLS.md §"Pitfall 1" for the documented
threat model: any code path that defaults to "grant" instead of "deny"
...
Three structural assertions:

1. The module constant ``DEFAULT_GRANT_POLICY`` literally equals
   ``"deny"`` — grep target for reviewers.
...
"""

from __future__ import annotations

import pytest

from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.permissions import (
    DEFAULT_GRANT_POLICY,
    ...
)
```
The new file follows this exact opening shape: a module docstring naming the PITFALLS.md entry, an enumerated "N structural assertions" preamble, `from __future__ import annotations`, then imports. Planner adapts the imports to the workflow-scanning surface (`re`, `pathlib.Path`) rather than the runtime-module surface used by v0.5.

**Source-tree-resolution pattern** (`tests/plugins/test_reference_plugin_public_api_only.py` lines 27-30):
```python
REPO_ROOT = Path(__file__).resolve().parents[2]
REF_PLUGIN_SRC = REPO_ROOT / "examples" / "horus-os-example-plugin" / "src"
```
This is the canonical horus-os recipe for "find the repo root from a test file". Per CLAUDE.md workflow expectations (`pathlib`, no string concat). The new file uses `REPO_ROOT / ".github" / "workflows"` instead of the examples path; `parents[2]` is correct because `tests/test_contribution_gate_pitfalls/<file>.py` has the same nesting depth as `tests/plugins/<file>.py`.

**Single-assertion-per-`def` shape** (`tests/test_plugin_pitfalls/test_pitfall_01_default_allow.py` lines 42-45):
```python
def test_default_grant_policy_is_deny() -> None:
    """The module constant must literally be the string ``"deny"``."""
    assert DEFAULT_GRANT_POLICY == "deny"
```
Each test function carries: a focused docstring naming what's pinned, one assertion (with a long-form failure message when the assertion is non-trivial). The new file uses this shape for each `def`: one `def` for "no workflow file contains `pull_request_target`", one for "no workflow that uses `pull_request_target` also checks out PR HEAD" (the second is vacuous in v0.6 but documents the dual-condition shape per CONTEXT.md D-04).

---

### `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py` (NEW — pytest regression)

**Analog:** `tests/plugins/test_reference_plugin_public_api_only.py` (closest in-tree match for "regex partition over every line of every file in a directory, collect offenders, assert empty"; D-04 lets planner choose regex vs YAML parsing, and this analog is the regex precedent).

**BAD/GOOD regex partition pattern** (`tests/plugins/test_reference_plugin_public_api_only.py` lines 33-45):
```python
# Any ``from horus_os...`` or ``import horus_os...`` line is a candidate.
BAD_IMPORT = re.compile(
    r"^\s*(?:"
    r"from\s+horus_os(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\s+import\b"
    r"|"
    r"import\s+horus_os(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\b"
    r")"
)

# The single sanctioned form. A candidate matches GOOD_IMPORT iff it
# starts with ``from horus_os.plugins.api import`` (possibly with
# trailing names/whitespace); everything else under BAD_IMPORT is a
# layer-2 violation.
GOOD_IMPORT = re.compile(r"^\s*from\s+horus_os\.plugins\.api\s+import\s+")
```
The new file mirrors this two-regex partition exactly:
- **BAD analog** = "every line containing `uses:`" (the candidate set: every action invocation, in-tree or third-party);
- **GOOD analog** = "candidate matches `^[^@]+@[0-9a-f]{40}$` OR starts with `./` (local action)" (the sanctioned set: 40-char SHA pins or local refs).
The decision to mirror the BAD/GOOD partition shape (rather than a single allowlist regex) is what handles CONTEXT.md Pitfall 51-C ("TEST-23 false-positive on `./local-action` refs") cleanly.

**Sorted-rglob + offender-list-with-relative-paths pattern** (`tests/plugins/test_reference_plugin_public_api_only.py` lines 48-73):
```python
def _scan_for_bad_imports(root: Path) -> list[str]:
    """Walk ``root/**/*.py`` and return ``file:line:source`` violation strings.
    ...
    """
    offenders: list[str] = []
    if not root.exists():
        return offenders
    for py_path in sorted(root.rglob("*.py")):
        try:
            text = py_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not BAD_IMPORT.match(line):
                continue
            if GOOD_IMPORT.match(line):
                continue
            try:
                rel = py_path.relative_to(REPO_ROOT)
            except ValueError:
                rel = py_path
            offenders.append(f"{rel}:{lineno}:{line.rstrip()}")
    return offenders
```
The new file copies this scanner shape almost verbatim, swapping:
- `root.rglob("*.py")` → `root.glob("*.yml")` (workflows live in a flat directory, not recursive);
- The candidate/sanctioned regex pair (per the BAD/GOOD pattern above).
The `sorted()` wrapper preserves deterministic test output across the 3-OS × 2-Python CI matrix per CLAUDE.md "Cross-OS path handling matters".

**Non-vacuity test pattern** (`tests/plugins/test_reference_plugin_public_api_only.py` lines 103-130):
```python
def test_scanner_catches_synthetic_bad_import(tmp_path: Path) -> None:
    """Layer-2 fires on a known violation — proves the regex is non-vacuous.
    ...
    """
    fake_src = tmp_path / "src" / "fake_plugin"
    fake_src.mkdir(parents=True)
    ...
    bad_file = fake_src / "bad.py"
    bad_file.write_text(
        "from horus_os.adapters import Adapter\n",
        encoding="utf-8",
    )

    offenders = _scan_for_bad_imports(tmp_path / "src")
    assert len(offenders) == 1, ...
    assert "horus_os.adapters" in offenders[0]
```
The new file adopts this **layer-2 non-vacuity discipline**: one `def test_scanner_catches_synthetic_*` that writes a known-bad YAML file into `tmp_path` and asserts the scanner flags it. Without this, the production assertion (`assert offenders == []`) is vacuously true if the regex silently breaks.

---

### `tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py` (NEW — pytest regression, multi-claim structural)

**Analog (state-machine + line-level walk):** `scripts/lint_no_wallclock.py`.
**Analog (multi-`def` structural test file shape):** `tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py`.

**Watched-paths constant pattern** (`scripts/lint_no_wallclock.py` lines 35-42):
```python
REPO_ROOT = Path(__file__).resolve().parents[1]

WATCHED_DIRS: tuple[Path, ...] = (REPO_ROOT / "src" / "horus_os" / "observability",)
WATCHED_FILES: tuple[Path, ...] = (
    REPO_ROOT / "src" / "horus_os" / "agent.py",
    REPO_ROOT / "src" / "horus_os" / "tools" / "loop.py",
    REPO_ROOT / "src" / "horus_os" / "server" / "api.py",
)
```
The new file declares a single `WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"` (no per-file enumeration: every `*.yml` in the dir is in scope). Note that the test file lives one level deeper than `lint_no_wallclock.py` (under `tests/test_contribution_gate_pitfalls/`), so the index is `parents[2]`, not `parents[1]` — the `test_reference_plugin_public_api_only.py` analog already shows this.

**File iteration with sorted determinism pattern** (`scripts/lint_no_wallclock.py` lines 48-54):
```python
def _iter_target_files() -> Iterable[Path]:
    for directory in WATCHED_DIRS:
        if directory.exists():
            yield from sorted(directory.rglob("*.py"))
    for file_path in WATCHED_FILES:
        if file_path.exists():
            yield file_path
```
The `sorted(directory.rglob(...))` shape is the in-tree precedent for cross-OS-stable iteration. New file uses `sorted(WORKFLOWS_DIR.glob("*.yml"))` (flat glob, not rglob).

**Line-by-line state machine with substring needle pattern** (`scripts/lint_no_wallclock.py` lines 57-94):
```python
def _scan_file(file_path: Path) -> list[tuple[Path, int, str]]:
    """Return (path, line_number, line_text) for every violation in file_path.
    ...
    """
    violations: list[tuple[Path, int, str]] = []
    inside_string = False
    text = file_path.read_text(encoding="utf-8")
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line
        # Track triple-quoted string state across lines.
        ...
        # Skip pure comment lines.
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if NEEDLE in line:
            violations.append((file_path, line_number, line.strip()))
    return violations
```
The `enumerate(text.splitlines(), start=1)` + `(path, lineno, text)` tuple + comment-skip discipline is the in-tree precedent for "scan a text file, collect structured offenders". For Phase 51's structural test, the new file applies the same shape with three claim-specific predicates:
- "every workflow file's text contains a top-level `permissions:` line" (CIHARD-02 presence assertion);
- "every `actions/checkout` line is followed by a `with:` block containing `persist-credentials: false`" (CIHARD-03);
- "no `run:` shell line contains `${{ github.event.*` (CIHARD-03 interpolation ban; mirrors the `NEEDLE in line` substring check exactly).

The comment-skip is **especially load-bearing** for the interpolation check: the docstring of a workflow comment could legitimately mention `${{ github.event.* }}` in prose; planner copies the `if stripped.startswith("#"): continue` guard from line 90.

**Multi-`def` structural assertion file shape** (`tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py` lines 44-89):
```python
def test_manifest_v1_schema_emits_object_shape() -> None:
    """``model_json_schema()`` returns an ``object``-typed dict with properties."""
    ...

def test_manifest_v1_schema_serialization_is_byte_stable() -> None:
    """Two calls to model_json_schema() serialize to identical canonical JSON."""
    ...

def test_manifest_v1_schema_includes_canonical_required_fields() -> None:
    """The schema's ``required`` list covers every mandatory v1 field."""
    ...
```
v0.5 precedent for "one test module, three to four independent `def`s each asserting a distinct structural invariant". The new file groups three CIHARD claims (CIHARD-02 permissions, CIHARD-03 persist-credentials, CIHARD-03 interpolation) into three (or more) `def`s in this shape — claims that cluster around workflow structural invariants and would otherwise need their own files. D-04 explicitly chose this cluster grouping.

**Long-form-failure-message convention** (`tests/test_plugin_pitfalls/test_pitfall_08_public_api_leak.py` lines 59-66):
```python
    assert actual == CANONICAL_PUBLIC_API, (
        f"Pitfall 8: horus_os.plugins.api.__all__ drift.\n"
        f"  canonical: {sorted(CANONICAL_PUBLIC_API)}\n"
        f"  actual:    {sorted(actual)}\n"
        f"  missing:   {sorted(CANONICAL_PUBLIC_API - actual)}\n"
        f"  extra:     {sorted(actual - CANONICAL_PUBLIC_API)}\n"
        "Update CANONICAL_PUBLIC_API + docs/PLUGINS.md together."
    )
```
The "name the pitfall + show canonical/actual/diff + tell the maintainer what to do" failure message shape is the v0.5 convention. New file uses the same shape for every CIHARD assertion: `"CIHARD-NN: <claim>. Offenders:\n  <file:line:text>..."`.

---

## Shared Patterns

### Source-tree repo-root resolution
**Source:** `tests/plugins/test_reference_plugin_public_api_only.py` line 29 (`Path(__file__).resolve().parents[2]`) — depth matches the new `tests/test_contribution_gate_pitfalls/<file>.py` files exactly.
**Apply to:** All three new test files.
```python
REPO_ROOT = Path(__file__).resolve().parents[2]
```
This is mandated by CLAUDE.md "pathlib, never raw string concatenation".

### Sorted glob for cross-OS determinism
**Source:** `scripts/lint_no_wallclock.py` line 51 (`sorted(directory.rglob("*.py"))`) and `tests/plugins/test_reference_plugin_public_api_only.py` line 58 (`sorted(py_path.rglob("*.py"))`).
**Apply to:** Every test file that iterates `.github/workflows/*.yml`.
```python
for workflow_path in sorted(WORKFLOWS_DIR.glob("*.yml")):
    ...
```
Mandated by CLAUDE.md "CI exercises 3 OS × 2 Python"; Windows + macOS + Linux must produce identical test ordering.

### Module-docstring naming the pitfall + enumerated assertions preamble
**Source:** `tests/test_plugin_pitfalls/test_pitfall_01_default_allow.py` lines 1-25 (the canonical v0.5 docstring shape).
**Apply to:** All three new test files.
The docstring opens with `"""Pitfall N: <one-line claim>."""`, links to `.planning/research/PITFALLS.md`, then enumerates N structural assertions one paragraph each. v0.5 ships 12 files in this exact shape; v0.6 continues it.

### Conventional `from __future__ import annotations`
**Source:** every file in `tests/test_plugin_pitfalls/` and `tests/plugins/`.
**Apply to:** All three new test files.
Mandated by ruff config + repo-wide convention.

### Step-name-with-tag-suffix grep convention
**Source:** `.github/workflows/ci.yml` line 41 (`time.time() lint gate (Pitfall 3)`) and line 51 (`capture-overhead benchmark (METRIC-05 / TEST-12)`).
**Apply to:** The new `Run actionlint (CIHARD-05)` step in `ci.yml`.
The literal parenthesized tag is what makes the step greppable by future regression tests (TEST-23 specifically asserts the `(CIHARD-05)` substring exists in `ci.yml`).

### SHA-pin trailing-tag-comment convention
**Source:** documented in `.planning/research/PITFALLS.md` Pitfall 2 and reinforced by RESEARCH.md §`Tag-comment convention`. Currently zero in-tree uses (every `uses:` is a tag-only pin pre-Phase-51), so the convention is established by Phase 51 itself.
**Apply to:** Every `uses:` line in both workflows.
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```
`pinact v4.0.0` enforces the trailing comment as a validation error; new files follow this shape from the start.

### Non-vacuity tests in source-tree scanners
**Source:** `tests/plugins/test_reference_plugin_public_api_only.py` lines 103-147 (two `test_scanner_catches_synthetic_*` functions that prove the scanner is not vacuously passing).
**Apply to:** `test_pitfall_02_action_sha_pinning.py` (mandatory) and optionally `test_ci_hardening_workflow_structure.py`.
A scanner that returns `[]` against an empty input file passes the production assertion vacuously; the synthetic-fixture test forces a real-world regression to fail when the regex breaks.

## No Analog Found

None. Every Phase 51 new/modified file maps to a v0.5 in-tree precedent. The closest "no analog" case is the workflow YAML edits themselves — but those use the existing file as its own analog (insertion-point preservation), which is the right framing for a hardening phase that explicitly does not rename or restructure.

## Metadata

**Analog search scope:**
- `.github/workflows/` (full directory; 2 files)
- `tests/test_plugin_pitfalls/` (full directory; 13 files, focus on `__init__.py`, `test_pitfall_01_default_allow.py`, `test_pitfall_08_public_api_leak.py`, `test_pitfall_12_docs_drift.py`)
- `tests/plugins/test_reference_plugin_public_api_only.py` (full file; the closest precedent for regex-over-source-tree-files)
- `scripts/lint_no_wallclock.py` (full file; the closest precedent for a custom Python text-scanning lint with state machine)

**Files scanned:** 6 source files + 2 workflow files = 8 total reads; no re-reads.

**Pattern extraction date:** 2026-05-29
