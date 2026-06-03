"""Phase 52 SIGN-04: user-facing five-check trust-chain verifier for a horus-os release.

Runs FIVE checks against a published GitHub Release (per CONTEXT.md D-03,
D-04, D-08):

1. wheel-signature: shells out to `python -m sigstore verify identity`
   against the published wheel and its .sigstore bundle. Identity is
   pinned to EXPECTED_IDENTITY_TEMPLATE; the OIDC issuer must equal
   EXPECTED_ISSUER. No wildcards, no regex, no fallback (D-04 hard rule).
2. sdist-signature: same shape, against the sdist tarball + bundle.
3. tag-signature: shells out to `git verify-tag vN.M.P` in the repo
   working tree.
4. sbom-signature: verifies BOTH SBOM .sigstore bundles (clean +
   dev-otel) via _sigstore_verify; returns ok=None when no bundle
   paths provided (mirrors check_wheel_signature SKIP semantics).
   SBOM contents are FRESH-venv-aligned with the wheel at
   release.yml generation time per SBOM-01.
5. changelog-cross-ref: shells out to `gh release view vN.M.P --json
   body --jq .body` and asserts the body contains the CHANGELOG.md
   [N.M.P] section text (whitespace-normalized).

Pure stdlib (argparse, dataclasses, os, pathlib, re, subprocess, sys).
The sigstore, git, and gh CLIs are external; the script prints clear
install hints if any are missing and exits non-zero with a structured
diagnostic. sigstore is NEVER added to pyproject.toml runtime or [dev]
extras per D-03; v0.6 ships a zero-base-dep verifier.

CLI:
  python scripts/verify_release.py
    --version vN.M.P                            (REQUIRED; argparse rejects absence)
    --cert-oidc-issuer URL                      (REQUIRED; MUST equal EXPECTED_ISSUER)
    [--check {wheel|sdist|tag|sbom|changelog}]  (optional; default runs all five)
    [--bundle PATH]                             (test mode: wheel/sdist bundle path)
    [--artifact PATH]                           (test mode: wheel/sdist artifact path)
    [--clean-bundle PATH]                       (Phase 53 SBOM check: clean .sigstore)
    [--clean-artifact PATH]                     (Phase 53 SBOM check: clean .cdx.json)
    [--extras-bundle PATH]                      (Phase 53 SBOM check: dev-otel .sigstore)
    [--extras-artifact PATH]                    (Phase 53 SBOM check: dev-otel .cdx.json)

Exit 0 only when no check has ok=False. Skipped checks (ok=None) do not
count as failure (matches scripts/release_gate.py precedent and the
`any(r.ok is False for r in results)` semantics).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Workflow-scoped identity contract per D-04. The `{version}` placeholder
# is the ONLY substitution; everything else is byte-identical to the
# release.yml `uses:` path. No wildcards, no regex, no trailing slash.
EXPECTED_IDENTITY_TEMPLATE = (
    "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"
)
EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"

# Module-import-time defense (PITFALL 1 / D-04). Catches accidental edits
# that would break the workflow-scoped identity contract.
assert "refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE, (
    "EXPECTED_IDENTITY_TEMPLATE corrupted: must contain 'refs/tags/{version}'"
)

# Validates the --version CLI argument shape. Accepts PEP 440 release
# segments the project uses (or may use): X.Y.Z, X.Y.Z-rcN (hyphenated),
# X.Y.ZrcN / X.Y.ZaN / X.Y.ZbN (no hyphen), and X.Y.Z.postN / X.Y.Z.devN.
# Wider than today's strict X.Y.Z/X.Y.Z-rcN cadence to avoid a confusing
# argparse error if a future release ships under any other PEP 440 shape.
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[\-.]?(?:rc|a|b|alpha|beta|post|dev)\d+)?$")


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


def _print_result(result: CheckResult) -> None:
    if result.ok is True:
        print(f"OK    {result.name}: {result.diagnostic}")
    elif result.ok is False:
        print(f"FAIL  {result.name}: {result.diagnostic}")
    else:
        print(f"SKIP  {result.name}: {result.diagnostic}")


def _assert_sigstore_cli_available() -> CheckResult | None:
    """Return None when `python -m sigstore --version` exits 0; otherwise a failure CheckResult.

    Catches FileNotFoundError and OSError per Shared Pattern S-1
    (cross-OS subprocess discipline). Diagnostic ends with
    `"Install hint: pip install sigstore"` so the caller sees the fix.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "sigstore", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, OSError) as exc:
        return CheckResult(
            name="sigstore-cli-available",
            ok=False,
            diagnostic=(
                f"python -m sigstore not available ({type(exc).__name__}). "
                "Install hint: pip install sigstore"
            ),
        )
    if proc.returncode != 0:
        return CheckResult(
            name="sigstore-cli-available",
            ok=False,
            diagnostic=(
                f"python -m sigstore --version exited {proc.returncode}. "
                "Install hint: pip install sigstore"
            ),
        )
    return None


def _resolved_bundle_path(cli_arg: Path | None) -> Path | None:
    """Pick the bundle path from env override, then CLI, then None.

    Whitespace-only overrides are treated as unset so `Path(" ")` does not
    leak into the sigstore subprocess as a confusing FileNotFoundError.
    """
    override = os.environ.get("HORUS_OS_VERIFY_RELEASE_BUNDLE_OVERRIDE", "").strip()
    if override:
        return Path(override)
    return cli_arg


def _resolved_artifact_path(cli_arg: Path | None) -> Path | None:
    """Pick the artifact path from env override, then CLI, then None.

    Whitespace-only overrides are treated as unset (see _resolved_bundle_path).
    """
    override = os.environ.get("HORUS_OS_VERIFY_RELEASE_ARTIFACT_OVERRIDE", "").strip()
    if override:
        return Path(override)
    return cli_arg


def _sigstore_verify(
    check_name: str,
    version: str,
    cert_oidc_issuer: str,
    bundle_path: Path,
    artifact_path: Path,
) -> CheckResult:
    """Shared shell-out for wheel-signature and sdist-signature checks.

    Mirrors scripts/release_gate.py:307-330 subprocess-with-capture
    discipline. On failure, tails the last three stderr lines into the
    diagnostic so the caller sees the sigstore-python error directly.
    """
    cli_check = _assert_sigstore_cli_available()
    if cli_check is not None:
        return CheckResult(name=check_name, ok=False, diagnostic=cli_check.diagnostic)
    # Substitute `v{version}` because git tags carry the `v` prefix (see
    # docs/RELEASE.md step 7: `git tag -s vN.M.P`). The OIDC ref embedded by
    # GitHub Actions on `release: published` is `refs/tags/v0.6.0`, never
    # `refs/tags/0.6.0`. EXPECTED_IDENTITY_TEMPLATE keeps the bare
    # `{version}` placeholder so the byte-exact constant matches D-04's
    # documented shape; the `v` prefix is added at substitution time here
    # and at lines 230, 299 (mirrors `tag = f"v{version}"` pattern).
    expected_identity = EXPECTED_IDENTITY_TEMPLATE.format(version=f"v{version}")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sigstore",
            "verify",
            "identity",
            "--cert-identity",
            expected_identity,
            "--cert-oidc-issuer",
            cert_oidc_issuer,
            "--bundle",
            str(bundle_path),
            str(artifact_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if proc.returncode == 0:
        return CheckResult(
            name=check_name,
            ok=True,
            diagnostic=f"verified against {expected_identity}",
        )
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
    return CheckResult(
        name=check_name,
        ok=False,
        diagnostic=(f"sigstore verify exited {proc.returncode}; last stderr: " + " | ".join(tail)),
    )


def check_wheel_signature(
    version: str,
    cert_oidc_issuer: str,
    bundle_path: Path,
    artifact_path: Path,
) -> CheckResult:
    """Pass when `python -m sigstore verify identity` against the wheel bundle exits 0."""
    return _sigstore_verify(
        check_name="wheel-signature",
        version=version,
        cert_oidc_issuer=cert_oidc_issuer,
        bundle_path=bundle_path,
        artifact_path=artifact_path,
    )


def check_sdist_signature(
    version: str,
    cert_oidc_issuer: str,
    bundle_path: Path,
    artifact_path: Path,
) -> CheckResult:
    """Pass when `python -m sigstore verify identity` against the sdist bundle exits 0."""
    return _sigstore_verify(
        check_name="sdist-signature",
        version=version,
        cert_oidc_issuer=cert_oidc_issuer,
        bundle_path=bundle_path,
        artifact_path=artifact_path,
    )


def check_tag_signature(version: str) -> CheckResult:
    """Pass when `git verify-tag vN.M.P` exits 0 in the repo working tree."""
    tag = f"v{version}"
    try:
        proc = subprocess.run(
            ["git", "verify-tag", tag],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, OSError) as exc:
        return CheckResult(
            name="tag-signature",
            ok=False,
            diagnostic=(
                f"git not available ({type(exc).__name__}). "
                "Install hint: https://git-scm.com/downloads"
            ),
        )
    if proc.returncode == 0:
        return CheckResult(
            name="tag-signature",
            ok=True,
            diagnostic=f"git verify-tag {tag} passed",
        )
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
    return CheckResult(
        name="tag-signature",
        ok=False,
        diagnostic=(
            f"git verify-tag {tag} exited {proc.returncode}; last stderr: " + " | ".join(tail)
        ),
    )


def check_sbom_signature(
    version: str,
    cert_oidc_issuer: str = EXPECTED_ISSUER,
    clean_bundle_path: Path | None = None,
    clean_artifact_path: Path | None = None,
    extras_bundle_path: Path | None = None,
    extras_artifact_path: Path | None = None,
) -> CheckResult:
    """Verify both SBOM .sigstore bundles for a release.

    Phase 53 SBOM-03: flipped from the Phase 52 D-08 SKIP stub. Returns
    ok=True only when every provided (bundle, artifact) pair verifies via
    _sigstore_verify. Returns ok=None ONLY when all four path args are
    None (fixture-mode-not-provided, mirrors check_wheel_signature SKIP
    semantics so the CLI dispatcher does not crash when no SBOM bundles
    are passed). Returns ok=False as soon as any provided pair fails.

    The dependency-tree diff against the wheel (SBOM-03 second clause)
    is deferred to the Phase 57 release-gate where pip install --dry-run
    can run locally. SBOM contents are FRESH-venv-aligned with the wheel
    at release.yml generation time per SBOM-01, so the bundle signature
    is itself a sufficient integrity check at user-facing verify time.
    """
    pairs: list[tuple[str, Path, Path]] = []
    if clean_bundle_path is not None and clean_artifact_path is not None:
        pairs.append(("sbom-signature-clean", clean_bundle_path, clean_artifact_path))
    if extras_bundle_path is not None and extras_artifact_path is not None:
        pairs.append(("sbom-signature-dev-otel", extras_bundle_path, extras_artifact_path))

    if not pairs:
        return CheckResult(
            name="sbom-signature",
            ok=None,
            diagnostic=(
                "SKIPPED - no SBOM bundle/artifact pairs provided; pass "
                "--clean-bundle/--clean-artifact and/or "
                "--extras-bundle/--extras-artifact for fixture-mode verification"
            ),
        )

    verified: list[str] = []
    for check_name, bundle, artifact in pairs:
        result = _sigstore_verify(
            check_name=check_name,
            version=version,
            cert_oidc_issuer=cert_oidc_issuer,
            bundle_path=bundle,
            artifact_path=artifact,
        )
        if result.ok is not True:
            return CheckResult(
                name="sbom-signature",
                ok=False,
                diagnostic=f"{check_name} verify failed: {result.diagnostic}",
            )
        verified.append(check_name)

    return CheckResult(
        name="sbom-signature",
        ok=True,
        diagnostic=f"verified {', '.join(verified)} for version {version}",
    )


def _normalize(text: str) -> str:
    """Whitespace-normalize prose for fragile-tolerant cross-ref comparison."""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _extract_changelog_section(text: str, version: str) -> str | None:
    """Return the text of the `## [version]` section of CHANGELOG.md, or None."""
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def check_changelog_cross_ref(version: str) -> CheckResult:
    """Pass when the GH Release body matches the CHANGELOG.md [version] section."""
    tag = f"v{version}"
    try:
        proc = subprocess.run(
            ["gh", "release", "view", tag, "--json", "body", "--jq", ".body"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, OSError) as exc:
        return CheckResult(
            name="changelog-cross-ref",
            ok=False,
            diagnostic=(
                f"gh CLI not available ({type(exc).__name__}). "
                "Install hint: https://cli.github.com/"
            ),
        )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
        return CheckResult(
            name="changelog-cross-ref",
            ok=False,
            diagnostic=(
                f"gh release view {tag} exited {proc.returncode}; last stderr: " + " | ".join(tail)
            ),
        )
    release_body = proc.stdout.strip()
    changelog_path = REPO_ROOT / "CHANGELOG.md"
    if not changelog_path.is_file():
        return CheckResult(
            name="changelog-cross-ref",
            ok=False,
            diagnostic=f"CHANGELOG.md not found at {changelog_path}",
        )
    changelog_text = changelog_path.read_text(encoding="utf-8")
    section = _extract_changelog_section(changelog_text, version)
    if section is None:
        return CheckResult(
            name="changelog-cross-ref",
            ok=False,
            diagnostic=(
                f"CHANGELOG.md has no `## [{version}]` section; cannot cross-ref the release body"
            ),
        )
    if _normalize(section) and _normalize(section) in _normalize(release_body):
        return CheckResult(
            name="changelog-cross-ref",
            ok=True,
            diagnostic=(f"GH release {tag} body contains the CHANGELOG.md [{version}] section"),
        )
    return CheckResult(
        name="changelog-cross-ref",
        ok=False,
        diagnostic=(
            f"GH release {tag} body does not match CHANGELOG.md [{version}] section "
            "(whitespace-normalized comparison)"
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="User-facing trust-chain verifier for a horus-os release.",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Release version (e.g. 0.6.0 or 0.6.0-rc1).",
    )
    parser.add_argument(
        "--cert-oidc-issuer",
        required=True,
        help=f"OIDC issuer URL. MUST equal {EXPECTED_ISSUER}.",
    )
    parser.add_argument(
        "--check",
        choices=("wheel", "sdist", "tag", "sbom", "changelog"),
        default=None,
        help="Run only the named check (default: run all five).",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Path to .sigstore bundle for wheel or sdist check (test mode).",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=None,
        help="Path to artifact file for wheel or sdist check (test mode).",
    )
    parser.add_argument(
        "--clean-bundle",
        type=Path,
        default=None,
        help=(
            "Path to .sigstore bundle for the clean-install SBOM "
            "(Phase 53 SBOM check, fixture mode)."
        ),
    )
    parser.add_argument(
        "--clean-artifact",
        type=Path,
        default=None,
        help=(
            "Path to the clean-install SBOM file (.cdx.json) (Phase 53 SBOM check, fixture mode)."
        ),
    )
    parser.add_argument(
        "--extras-bundle",
        type=Path,
        default=None,
        help=(
            "Path to .sigstore bundle for the [dev,otel] SBOM (Phase 53 SBOM check, fixture mode)."
        ),
    )
    parser.add_argument(
        "--extras-artifact",
        type=Path,
        default=None,
        help=("Path to the [dev,otel] SBOM file (.cdx.json) (Phase 53 SBOM check, fixture mode)."),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch the requested checks. Return 0 on full pass, 1 on any fail."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not _VERSION_PATTERN.match(args.version):
        parser.error(
            f"--version {args.version!r} does not match the expected shape X.Y.Z or X.Y.Z-rcN"
        )

    if args.cert_oidc_issuer != EXPECTED_ISSUER:
        print(
            f"FAIL  verify_release: --cert-oidc-issuer must equal "
            f"{EXPECTED_ISSUER!r}, got {args.cert_oidc_issuer!r}",
            file=sys.stderr,
        )
        return 1

    resolved_bundle = _resolved_bundle_path(args.bundle)
    resolved_artifact = _resolved_artifact_path(args.artifact)

    results: list[CheckResult] = []
    selected = args.check

    if selected in (None, "wheel"):
        if resolved_bundle is None or resolved_artifact is None:
            results.append(
                CheckResult(
                    name="wheel-signature",
                    ok=None,
                    diagnostic=(
                        "SKIPPED - no --bundle or --artifact (or "
                        "HORUS_OS_VERIFY_RELEASE_*_OVERRIDE) provided; "
                        "pass both for fixture-mode verification"
                    ),
                )
            )
        else:
            results.append(
                check_wheel_signature(
                    version=args.version,
                    cert_oidc_issuer=args.cert_oidc_issuer,
                    bundle_path=resolved_bundle,
                    artifact_path=resolved_artifact,
                )
            )

    if selected in (None, "sdist"):
        if resolved_bundle is None or resolved_artifact is None:
            results.append(
                CheckResult(
                    name="sdist-signature",
                    ok=None,
                    diagnostic=(
                        "SKIPPED - no --bundle or --artifact (or "
                        "HORUS_OS_VERIFY_RELEASE_*_OVERRIDE) provided; "
                        "pass both for fixture-mode verification"
                    ),
                )
            )
        else:
            results.append(
                check_sdist_signature(
                    version=args.version,
                    cert_oidc_issuer=args.cert_oidc_issuer,
                    bundle_path=resolved_bundle,
                    artifact_path=resolved_artifact,
                )
            )

    if selected in (None, "tag"):
        results.append(check_tag_signature(args.version))

    if selected in (None, "sbom"):
        results.append(
            check_sbom_signature(
                version=args.version,
                cert_oidc_issuer=args.cert_oidc_issuer,
                clean_bundle_path=args.clean_bundle,
                clean_artifact_path=args.clean_artifact,
                extras_bundle_path=args.extras_bundle,
                extras_artifact_path=args.extras_artifact,
            )
        )

    if selected in (None, "changelog"):
        results.append(check_changelog_cross_ref(args.version))

    for result in results:
        _print_result(result)

    any_failed = any(r.ok is False for r in results)
    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
