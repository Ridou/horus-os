---
phase: 52-signing-substrate-release-yml-new
reviewed: 2026-05-29T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - .github/workflows/release.yml
  - scripts/verify_release.py
  - tests/test_release_verification.py
  - tests/test_release_yml_structure.py
  - tests/test_release_md_stop_before_tag.py
  - tests/test_decision_no_pypi.py
  - docs/RELEASE.md
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 52: Code Review Report

**Reviewed:** 2026-05-29
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 52 lands the keyless signing substrate (SIGN-01 + SIGN-02 in `release.yml`,
SIGN-04 in `verify_release.py`, SIGN-03 in `docs/RELEASE.md`, SIGN-05 in the
decision file and test scaffolding) at high overall quality. The workflow file
is SHA-pinned on every `uses:` line per CIHARD-04, observes the top-level
`permissions: read-all` + per-job opt-in pattern, includes
`persist-credentials: false` on checkout, has `timeout-minutes: 5` on the
sigstore step, splits attest-build-provenance into two per-artifact
invocations, and contains no event-context interpolation. The verifier is
stdlib-only, uses `sys.executable` for all subprocess invocations, never sets
`shell=True`, validates `--cert-oidc-issuer` against a hardcoded constant,
hardcodes `EXPECTED_IDENTITY_TEMPLATE` with the load-bearing
`refs/tags/{version}` substring, and defends that constant at module-import
time. Tests use `encoding="utf-8"` on every `read_text()`, `sys.executable` on
every subprocess invocation, `pathlib.Path(__file__).resolve().parents[1]` for
the repo root, and ship non-vacuity synthetic fixtures for every absence-of-
pattern assertion. No em-dashes, no PII, no hardcoded secrets, no
`pull_request_target`, no `eval`/`shell=True`/`==`-on-strings hazards.

That said, there is ONE blocker that breaks the entire verification chain plus
several warnings around test reliability and error-message clarity that should
be cleaned up before v0.6.0 ships.

## Critical Issues

### BL-01: `EXPECTED_IDENTITY_TEMPLATE` substitution drops the `v` prefix; every sigstore verify will FAIL

**File:** `scripts/verify_release.py:54-56, 66, 160, 230, 299`
**Issue:**

The verifier substitutes the bare CLI `--version` value (e.g. `0.6.0`) into
the `{version}` placeholder of `EXPECTED_IDENTITY_TEMPLATE`, producing a
`--cert-identity` URL with the suffix `refs/tags/0.6.0`. The actual git tag,
however, is `vN.M.P` (with a `v` prefix) per the project's tagging convention
(`docs/RELEASE.md` step 7: `git tag -s vN.M.P -m "vN.M.P - <milestone-name>"`)
and every existing tag in the repo confirms this (`v0.1.0`, `v0.2.0`,
`v0.3.0`, `v0.4.0`, `v0.5.0`). When the release workflow fires on
`release: published`, GitHub's OIDC token embeds the actual git ref
`refs/tags/v0.6.0`, sigstore-python records that ref into the Rekor entry,
and `sigstore verify identity --cert-identity .../refs/tags/0.6.0` (missing
the `v`) will mismatch and exit non-zero. Every wheel-signature and
sdist-signature check fails.

Evidence the script treats `--version` as un-prefixed and prepends the `v`
itself for the git tag path:

```python
# verify_release.py:66
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-rc\d+)?$")  # rejects 'v' prefix

# verify_release.py:230, 299
tag = f"v{version}"  # script knows to prepend 'v' for the git tag

# verify_release.py:160 - BUT NOT for the identity:
expected_identity = EXPECTED_IDENTITY_TEMPLATE.format(version=version)
# -> ".../refs/tags/0.6.0" instead of ".../refs/tags/v0.6.0"
```

This is not caught by any test today because
`test_canonical_fixture_passes_wheel_check` and
`test_full_run_all_checks_with_canonical_fixture` both skip when the
canonical binary fixture is absent (current Wave 0 state). The bug will only
surface at the v0.6.0-rc1 rehearsal recording when the maintainer runs the
verifier against the real signed artifact and gets an identity mismatch.

This is the load-bearing PITFALL 3 mitigation the phase set out to land,
and it is broken by an off-by-one substring.

**Fix:**

Apply the `v` prefix at substitution time so the identity URL matches the
actual git ref present in the Rekor entry. Two options; either works:

Option A (minimal change, format-site fix):

```python
# verify_release.py:160
-    expected_identity = EXPECTED_IDENTITY_TEMPLATE.format(version=version)
+    expected_identity = EXPECTED_IDENTITY_TEMPLATE.format(version=f"v{version}")
```

Option B (constant carries the `v`, more legible):

```python
# verify_release.py:54-56
 EXPECTED_IDENTITY_TEMPLATE = (
-    "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"
+    "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/v{version}"
 )
```

Either fix MUST also update the module-import-time invariant:

```python
# verify_release.py:61-63
-assert "refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE, (
-    "EXPECTED_IDENTITY_TEMPLATE corrupted: must contain 'refs/tags/{version}'"
+assert "refs/tags/v{version}" in EXPECTED_IDENTITY_TEMPLATE, (
+    "EXPECTED_IDENTITY_TEMPLATE corrupted: must contain 'refs/tags/v{version}'"
 )
```

(Option B requires the invariant change; Option A does not but the assertion
no longer asserts the post-substitution shape.) Mirror the same fix into
`tests/test_release_verification.py:69-71` and the
`test_expected_identity_template_invariant_is_documented` substring
(`tests/test_release_verification.py:256`) so the test scaffolding stays in
lockstep with the production constant.

Add a regression unit test that does NOT require fixture binaries:

```python
def test_expected_identity_includes_v_prefix() -> None:
    """BL-01 regression: the formatted identity URL must contain refs/tags/v<version>."""
    mod = _load_verify_release_module()
    formatted = mod.EXPECTED_IDENTITY_TEMPLATE.format(version="v0.6.0-rc1")
    assert "refs/tags/v0.6.0-rc1" in formatted, formatted
```

## Warnings

### WR-01: `test_full_run_all_checks_with_canonical_fixture` will FAIL once fixtures land, even on a clean rehearsal

**File:** `tests/test_release_verification.py:209-233`
**Issue:**

The test skips today (canonical fixtures absent) but the assertion is
`exit_code == 0`. When the v0.6.0-rc1 rehearsal records the fixture and
unblocks the skip, `main(["--version", "0.6.0-rc1", "--cert-oidc-issuer", ...,
"--bundle", ..., "--artifact", ...])` runs ALL FIVE checks, including:

- `check_tag_signature("0.6.0-rc1")` -> shells out `git verify-tag v0.6.0-rc1`
  in the developer's working tree. That tag will not exist on the developer
  machine running the test (it is only pushed at real-release time), so the
  check returns `ok=False` with `git verify-tag exited 128` or similar.
- `check_changelog_cross_ref("0.6.0-rc1")` -> shells out
  `gh release view v0.6.0-rc1`. That release does not exist either; returns
  `ok=False`.

The result is `exit_code == 1`, which violates the test's assertion. The
test silently breaks the moment the skip clears.

**Fix:**

Pass `--check wheel` (or `--check sdist`) so the full-run smoke is scoped to
the actually-fixture-verifiable subset, or call `main` once per
non-fixture-dependent check explicitly:

```python
exit_code = mod.main(
    [
        "--version", "0.6.0-rc1",
        "--cert-oidc-issuer", EXPECTED_ISSUER,
        "--bundle", str(bundle),
        "--artifact", str(wheel),
        "--check", "wheel",
    ]
)
```

Alternatively, document the test as requiring the tag + GH release to exist
and gate it behind an opt-in env var (e.g. `HORUS_OS_VERIFY_RELEASE_END_TO_END=1`)
that only the rehearsal harness sets.

### WR-02: `_VERSION_PATTERN` rejects valid PEP 440 release identifiers used elsewhere in the repo

**File:** `scripts/verify_release.py:66, 401-404`
**Issue:**

The regex `^\d+\.\d+\.\d+(-rc\d+)?$` accepts only `X.Y.Z` and `X.Y.Z-rcN`.
PEP 440 (and Python packaging conventions used by other parts of this repo,
e.g. `pyproject.toml`) also allow `X.Y.Z.devN`, `X.Y.Z.postN`, `X.Y.ZaN`,
`X.Y.ZbN`, `X.Y.ZrcN` (no hyphen), and post-release identifiers. If a future
release ships as `0.6.0rc1` (no hyphen) or `0.6.1.post1`, the verifier will
refuse to run with `argparse.error` and the maintainer will see a confusing
shape-error instead of a substantive verification failure.

This is not strictly a bug today (the procedure pins the
`X.Y.Z`/`X.Y.Z-rcN` shape), but it is a fragile coupling between the regex
and the conventions used in `pyproject.toml` / `__init__.py`.

**Fix:**

Either widen the regex to cover the PEP 440 release-segment shapes the
project actually uses, or extract the shape into a module-level docstring
constant referenced from both the regex and the `--version` help text so a
future maintainer cannot drift one without the other. Minimum widening:

```python
_VERSION_PATTERN = re.compile(
    r"^\d+\.\d+\.\d+(?:[-.]?(?:a|b|rc|alpha|beta|dev|post)\d+)?$"
)
```

### WR-03: `_resolved_bundle_path` / `_resolved_artifact_path` accept empty-string env vars and silently use them

**File:** `scripts/verify_release.py:128-141`
**Issue:**

`os.environ.get("HORUS_OS_VERIFY_RELEASE_BUNDLE_OVERRIDE")` returns an empty
string when the env var is set to `""` (e.g. `HORUS_OS_VERIFY_RELEASE_BUNDLE_OVERRIDE= python ...`).
The current `if override:` check correctly treats `""` as falsy, but a value
like `" "` (single space) bypasses the guard and is then wrapped in `Path(" ")`,
which silently constructs a path of `' '` and is later passed verbatim to the
sigstore subprocess. The resulting `--bundle " "` will fail with a confusing
FileNotFoundError from sigstore rather than a clear "override env var is
malformed" message.

**Fix:**

Strip and re-check:

```python
def _resolved_bundle_path(cli_arg: Path | None) -> Path | None:
    override = os.environ.get("HORUS_OS_VERIFY_RELEASE_BUNDLE_OVERRIDE", "").strip()
    if override:
        return Path(override)
    return cli_arg
```

Apply symmetrically to `_resolved_artifact_path`.

### WR-04: `_extract_changelog_section` regex is anchored to `## [` only, but Keep a Changelog 1.1.0 sections may use `## [N.M.P] - YYYY-MM-DD` AND occasionally `## [Unreleased]` directly above the target section

**File:** `scripts/verify_release.py:285-294`
**Issue:**

The pattern `^## \[{version}\][^\n]*\n(.*?)(?=^## \[|\Z)` uses the lookahead
`(?=^## \[|\Z)` which terminates the capture at the NEXT `## [` heading or
end-of-file. This is correct in steady-state, but two corner cases bite:

1. If `[Unreleased]` is moved BELOW the released section (unconventional but
   possible during a hotfix), the lookahead terminates at the literal `## [`
   so the body of `[N.M.P]` is correctly bounded. OK.
2. If the CHANGELOG has nested headings (e.g. `### [Sub-release]`) the
   pattern is anchored to exactly TWO `#` so this is fine.
3. If the CHANGELOG section's body itself contains a `## [...]` literal
   inside a fenced code block (procedurally possible: a release note that
   says "we renamed `## [Old]` to `## [New]`"), the lookahead splits the
   capture mid-section. The `check_changelog_cross_ref` then compares only
   the head of the section against the release body and reports a spurious
   mismatch.

This is a low-probability bug but high-impact when it fires (false negative
verification).

**Fix:**

Either skip fenced code blocks during extraction, or normalize the
comparison to extract the relevant section from BOTH the CHANGELOG and the
release body and compare them after the same extraction, which makes the
asymmetry irrelevant. Minimum acknowledgment: add a docstring note that
fenced `## [...]` literals inside the section body will cause a false
negative and the operator should manually verify in that case.

## Info

### IN-01: `del version  # unused until Phase 53 flips the stub` is the wrong idiom for an intentionally-ignored stub parameter

**File:** `scripts/verify_release.py:272`
**Issue:**

`del version` actively deletes the local binding, which signals "this was a
mistake, clean it up." A clearer signal for "this stub will use the
parameter when Phase 53 flips it" is the underscore-prefix convention or a
no-op comment. The current form makes a reader assume the parameter is dead
code and may invite a future cleanup PR that removes the parameter entirely,
breaking the call-site contract.

**Fix:**

Either rename to `_version` and drop the `del`, or replace `del version`
with a comment:

```python
def check_sbom_signature(version: str) -> CheckResult:
    """STUB per D-08: Phase 53 lands SBOM generation + signing."""
    # Parameter is currently unused; Phase 53 binds it to the SBOM artifact path.
    _ = version
    return CheckResult(...)
```

### IN-02: `_print_result` writes to stdout for FAIL too; would benefit from stderr routing

**File:** `scripts/verify_release.py:83-89`
**Issue:**

All three branches (`OK`, `FAIL`, `SKIP`) write to stdout. A downstream
consumer that captures stdout for parsing (`gh` workflow, scripted CI gate)
cannot distinguish failure diagnostics from pass output without re-parsing
the prefix. Routing `FAIL` lines to stderr matches the convention the
existing `main()` already uses at line 410 (which DOES write to stderr for
the issuer-mismatch case).

**Fix:**

```python
def _print_result(result: CheckResult) -> None:
    if result.ok is True:
        print(f"OK    {result.name}: {result.diagnostic}")
    elif result.ok is False:
        print(f"FAIL  {result.name}: {result.diagnostic}", file=sys.stderr)
    else:
        print(f"SKIP  {result.name}: {result.diagnostic}")
```

### IN-03: `test_release_yml_structure.py` synthetic-fixture tests do not assert the GOOD-PATH (positive) case

**File:** `tests/test_release_yml_structure.py:333-409`
**Issue:**

The three synthetic-fixture non-vacuity tests (`test_scanner_catches_synthetic_*`)
correctly prove the scanner flags violations. They do NOT prove the scanner
PASSES a known-clean fixture, which is the symmetric guard that catches
"scanner became permanently green and now never flags anything" regressions.

The Phase 51 Plan 01 precedent the docstring cites includes both
absence-of-violation and presence-of-pass synthetic tests; only the former
half is present here.

**Fix:**

Add three sibling tests that write a known-clean synthetic `release.yml` to
`tmp_path` and assert `result["missing_permissions"] is False`,
`result["sha_violations"] == []`, `result["attest_count"] == 2`. Low-cost,
high-value (prevents a future scanner regression where someone breaks the
regex and the production assertion stops catching real violations).

---

_Reviewed: 2026-05-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
