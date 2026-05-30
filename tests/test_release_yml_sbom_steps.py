"""Phase 53 SBOM-01 + SBOM-02 structural lint for .github/workflows/release.yml additions.

Wave 0 RED-by-design: production assertions fail until Plan 02 extends release.yml
with two SBOM-generation steps + two attest-sbom invocations + sigstore inputs
glob extension. Non-vacuity scanners pass NOW via tmp_path synthetic fixtures.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_YML_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"

_USES_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)")
_ALLOWED_REF = re.compile(r"^[0-9a-f]{40}$")


def _read_release_yml() -> str:
    if not RELEASE_YML_PATH.is_file():
        raise FileNotFoundError(
            f"{RELEASE_YML_PATH} not found (Phase 52 should have created it; sanity check failed)"
        )
    return RELEASE_YML_PATH.read_text(encoding="utf-8")


def _scan_uses_lines(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        match = _USES_PATTERN.match(line)
        if match is None:
            continue
        pairs.append((match.group(1), match.group(2)))
    return pairs


def _has_fresh_venv_sbom(text: str) -> tuple[bool, bool]:
    """Return (has_clean_venv, has_extras_venv) booleans."""
    return ("python -m venv .venv-sbom-clean" in text, "python -m venv .venv-sbom-extras" in text)


def _count_attest_sbom(text: str) -> int:
    """Count occurrences of `uses: actions/attest-sbom@`."""
    return len(re.findall(r"uses:\s*actions/attest-sbom@", text))


def _sigstore_inputs_line(text: str) -> str | None:
    """Find the sigstore step's inputs: line value (or None)."""
    match = re.search(r"^\s*inputs:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


# Production assertions: RED until Plan 02 extends release.yml.


def test_release_yml_exists() -> None:
    assert RELEASE_YML_PATH.is_file(), (
        f"{RELEASE_YML_PATH} not found (Phase 52 should have created it)"
    )


def test_fresh_venv_sbom_generation() -> None:
    text = _read_release_yml()
    has_clean, has_extras = _has_fresh_venv_sbom(text)
    assert has_clean, (
        "SBOM-01 FRESH-venv rule: release.yml must contain "
        "'python -m venv .venv-sbom-clean' (NOT pip freeze of the dev venv)"
    )
    assert has_extras, (
        "SBOM-01 + SBOM-02 FRESH-venv: release.yml must also contain "
        "'python -m venv .venv-sbom-extras' for the [dev,otel] variant"
    )


def test_cyclonedx_environment_called() -> None:
    text = _read_release_yml()
    assert "cyclonedx-py environment" in text, (
        "SBOM-01: release.yml must invoke 'cyclonedx-py environment' (NOT pip freeze)"
    )


def test_schema_version_1_6_locked() -> None:
    text = _read_release_yml()
    assert "--schema-version 1.6" in text, (
        "SBOM-01: CycloneDX schema version MUST be locked to 1.6 (--schema-version 1.6)"
    )


def test_output_format_json() -> None:
    text = _read_release_yml()
    assert "--output-format JSON" in text, (
        "SBOM-01: cyclonedx-py environment must specify --output-format JSON"
    )


def test_two_sbom_variants() -> None:
    text = _read_release_yml()
    assert "horus_os-clean.cdx.json" in text, (
        "SBOM-02: release.yml must produce dist/horus_os-clean.cdx.json (clean install SBOM)"
    )
    assert "horus_os-dev-otel.cdx.json" in text, (
        "SBOM-02: release.yml must produce dist/horus_os-dev-otel.cdx.json ([dev,otel] SBOM)"
    )


def test_cyclonedx_bom_version_pinned() -> None:
    text = _read_release_yml()
    assert "'cyclonedx-bom>=7.3,<8'" in text, (
        "SBOM-01: cyclonedx-bom version range must be pinned to '>=7.3,<8' "
        "(single-quoted to lock the range in the run: line)"
    )


def test_sigstore_inputs_include_cdx_json() -> None:
    text = _read_release_yml()
    # Look for any inputs: line containing all three globs
    has_cdx_input = bool(
        re.search(
            r"inputs:[^\n]*\./dist/\*\.whl[^\n]*\./dist/\*\.tar\.gz[^\n]*\./dist/\*\.cdx\.json",
            text,
        )
    )
    assert has_cdx_input, (
        "SBOM-01 + Phase 52 D-10: sigstore step inputs: line must include "
        "./dist/*.cdx.json (smallest possible Phase 53 diff to the Phase 52 glob)"
    )


def test_two_attest_sbom_invocations() -> None:
    text = _read_release_yml()
    count = _count_attest_sbom(text)
    assert count == 2, (
        f"SBOM-03: release.yml must contain EXACTLY TWO 'uses: actions/attest-sbom@' "
        f"invocations (one for clean SBOM, one for dev-otel SBOM); got {count}"
    )


def test_attest_sbom_sha_pinned() -> None:
    text = _read_release_yml()
    pairs = _scan_uses_lines(text)
    attest_refs = [ref for path, ref in pairs if "actions/attest-sbom" in path]
    assert attest_refs, "SBOM-03: no actions/attest-sbom uses: line found"
    for ref in attest_refs:
        assert _ALLOWED_REF.match(ref), (
            f"CIHARD-04: actions/attest-sbom must be SHA-pinned (40-char hex); got {ref!r}"
        )


def test_attest_sbom_sbom_path_paired() -> None:
    text = _read_release_yml()
    assert "sbom-path: 'dist/horus_os-clean.cdx.json'" in text, (
        "SBOM-03: attest-sbom for clean variant must reference dist/horus_os-clean.cdx.json"
    )
    assert "sbom-path: 'dist/horus_os-dev-otel.cdx.json'" in text, (
        "SBOM-03: attest-sbom for dev-otel variant must reference dist/horus_os-dev-otel.cdx.json"
    )


def test_pip_install_wheel_for_extras() -> None:
    text = _read_release_yml()
    assert "dist/*.whl[dev,otel]" in text, (
        "SBOM-02: extras SBOM venv must install the wheel with [dev,otel] extras"
    )


# Non-vacuity scanner tests: pass NOW.


def test_scanner_catches_pip_freeze_substitution(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "jobs:\n  x:\n    steps:\n      - name: SBOM\n        run: pip freeze > sbom.txt\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert "cyclonedx-py environment" not in text, (
        "Non-vacuity: scanner must flag absence of cyclonedx-py environment (pip freeze used)"
    )
    has_clean, _ = _has_fresh_venv_sbom(text)
    assert not has_clean, "Non-vacuity: scanner must flag absence of .venv-sbom-clean creation"


def test_scanner_catches_single_attest_sbom(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "jobs:\n  x:\n    steps:\n"
        "      - uses: actions/attest-sbom@aaaa1111bbbb2222cccc3333dddd4444eeee5555\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert _count_attest_sbom(text) == 1, (
        "Non-vacuity: scanner must count exactly 1 attest-sbom occurrence in single-invocation fixture"
    )


def test_scanner_catches_unpinned_schema_version(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "jobs:\n  x:\n    steps:\n"
        "      - run: cyclonedx-py environment .venv-sbom/bin/python --output-format JSON\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert "--schema-version 1.6" not in text, (
        "Non-vacuity: scanner must flag absence of --schema-version 1.6"
    )
