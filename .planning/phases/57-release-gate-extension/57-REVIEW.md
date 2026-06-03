---
phase: 57-release-gate-extension
reviewed: 2026-05-30T11:20:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - scripts/release_gate.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
fix_applied: true
fix_commit: 6fd2266
---

# Phase 57: Code Review Report

**Reviewed:** 2026-05-30T11:20:00Z
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Retroactive standard-depth review of the Phase 57 release-gate extension (5 new check functions + tier filter + dispatch wiring in `scripts/release_gate.py`). The implementation is well-structured: CheckResult dataclass, three-state ok semantics (True/False/None), tier filter via sentinel value, fixture-mode hooks for tests. Coverage of REL-14 + REL-15 is sound and the existing 8 enum values are byte-identical (load-bearing constraint #3 honored).

Two Warning-tier issues surfaced. Both relate to documented-but-unimplemented contracts.

## Warnings

### WR-01: local-pip-audit-clean does not enforce the dated-reason comment contract

**File:** `scripts/release_gate.py:748-805`
**Issue:** The `.github/pip-audit-ignore.txt` header docstring (Phase 53) reads:

> The release-gate `local-pip-audit-clean` check (Phase 57) rejects any entry in this file that lacks a dated reason comment.

The current `check_local_pip_audit_clean` implementation only passes the file as `--ignore-vulns-file` to pip-audit. It does NOT parse the file and reject undocumented entries. Today this is latent (the file is empty at v0.6.0 launch), but the first contributor who adds a CVE without the `# YYYY-MM-DD: <reason>` comment will land an undocumented ignore and the gate will pass.

**Fix:** Add a pre-flight parse step before the subprocess call:
```python
def _validate_pip_audit_ignore_format(ignore_path: Path) -> str | None:
    """Return None on valid file, or an error message on the first violation."""
    if not ignore_path.is_file():
        return None
    lines = ignore_path.read_text(encoding="utf-8").splitlines()
    prev_comment_has_date = False
    DATE_PATTERN = re.compile(r"^\s*#\s*\d{4}-\d{2}-\d{2}:\s+\S")
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            prev_comment_has_date = False
            continue
        if stripped.startswith("#"):
            prev_comment_has_date = bool(DATE_PATTERN.match(line))
            continue
        # Non-comment, non-empty: must be a CVE/GHSA/PYSEC ID with a dated comment above
        if not prev_comment_has_date:
            return f"line {idx}: {stripped!r} is missing the `# YYYY-MM-DD: <reason>` comment above"
        prev_comment_has_date = False
    return None
```
Then in `check_local_pip_audit_clean`:
```python
err = _validate_pip_audit_ignore_format(DEFAULT_PIP_AUDIT_IGNORE_PATH)
if err is not None:
    return CheckResult(
        name="local-pip-audit-clean",
        ok=False,
        diagnostic=f"pip-audit-ignore.txt format violation: {err}",
    )
```
Add a regression test asserting an undated ignore entry FAILS the check.

### WR-02: tier=local + --check local-pip-audit-clean silently produces no result

**File:** `scripts/release_gate.py:1023`
**Issue:** The dispatch reads `if selected in (None, "local-pip-audit-clean") and tier == "release"`. When a user runs `release_gate.py --tier local --check local-pip-audit-clean`, the explicit `--check` request is silently ignored (no result is appended for that check, and the runner reports 0 results for the requested check). The user receives no diagnostic explaining that `local-pip-audit-clean` is not available at tier-local; the script exits 0 (no failures) and the user wrongly believes the check passed.
**Fix:** Add an explicit error when an incompatible combination is requested:
```python
if args.check == "local-pip-audit-clean" and args.tier == "local":
    parser.error(
        "--check local-pip-audit-clean is incompatible with --tier local; "
        "rerun with --tier release"
    )
```
Place after `args = parser.parse_args(argv)` so the error message is visible.

## Info

### IN-01: check_actions_pinned_by_sha only scans .yml extension

**File:** `scripts/release_gate.py:817`
**Issue:** `workflows_dir.glob("*.yml")` will miss any future `.yaml` file. The project uses `.yml` exclusively today (audit.yml, ci.yml, release.yml, zizmor.yml, dependabot.yml), so this is latent.
**Fix:** Glob both extensions:
```python
for workflow in sorted(list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))):
```

### IN-02: docstring claims "EIGHT checks" but the script runs THIRTEEN

**File:** `scripts/release_gate.py:892`
**Issue:** The `main()` docstring still reads `"""Run the eight release-gate checks. Return 0 on full pass, 1 on any fail."""`. Phase 57 extended the script to thirteen checks; the module-level docstring at line 3 was updated but the function-level docstring at line 892 was not.
**Fix:**
```python
def main(argv: list[str] | None = None) -> int:
    """Run the thirteen release-gate checks. Return 0 on full pass, 1 on any fail."""
```

---

_Reviewed: 2026-05-30T11:20:00Z_
_Reviewer: Claude (gsd-code-reviewer, inline-mode)_
_Depth: standard_
