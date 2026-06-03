"""Phase 54 DEPBOT-03 structural lint for .github/workflows/zizmor.yml.

Wave 0 RED-by-design: production assertions fail until Plan 02 creates
.github/workflows/zizmor.yml as a second layer of workflow-security
enforcement complementing Phase 51 actionlint.

Non-vacuity scanners pass NOW via tmp_path fixtures.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ZIZMOR_PATH = REPO_ROOT / ".github" / "workflows" / "zizmor.yml"

_USES_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)")
_ALLOWED_REF = re.compile(r"^[0-9a-f]{40}$")


def _read_zizmor() -> str:
    if not ZIZMOR_PATH.is_file():
        raise FileNotFoundError(f"DEPBOT-03: Plan 02 must create {ZIZMOR_PATH}")
    return ZIZMOR_PATH.read_text(encoding="utf-8")


def _scan_uses(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        m = _USES_PATTERN.match(line)
        if m is None:
            continue
        pairs.append((m.group(1), m.group(2)))
    return pairs


def _scan_has_pull_request_target(text: str) -> bool:
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        if "pull_request_target" in line:
            return True
    return False


# Production assertions: RED until Plan 02 creates zizmor.yml


def test_zizmor_yml_exists() -> None:
    assert ZIZMOR_PATH.is_file(), f"DEPBOT-03: Plan 02 must create {ZIZMOR_PATH}"


def test_zizmor_on_pull_request() -> None:
    text = _read_zizmor()
    assert re.search(r"on:\s*\n\s*pull_request\s*:", text, re.MULTILINE), (
        "DEPBOT-03: zizmor.yml must trigger on pull_request"
    )


def test_zizmor_paths_filter() -> None:
    text = _read_zizmor()
    assert ".github/workflows/**" in text, (
        "DEPBOT-03: zizmor.yml must filter pull_request paths to .github/workflows/**"
    )


def test_top_level_permissions_read_all() -> None:
    text = _read_zizmor()
    assert re.search(r"^permissions:\s*read-all\s*$", text, re.MULTILINE), (
        "DEPBOT-03 + CIHARD-02: zizmor.yml must declare top-level permissions: read-all"
    )


def test_per_job_security_events_write() -> None:
    text = _read_zizmor()
    assert "security-events: write" in text, (
        "DEPBOT-03: zizmor.yml job must declare security-events: write "
        "(SARIF upload to GitHub code-scanning)"
    )


def test_zizmor_action_present() -> None:
    text = _read_zizmor()
    assert "zizmorcore/zizmor-action" in text, (
        "DEPBOT-03: zizmor.yml must invoke zizmorcore/zizmor-action"
    )


def test_zizmor_action_sha_pinned() -> None:
    text = _read_zizmor()
    pairs = _scan_uses(text)
    refs = [ref for path, ref in pairs if "zizmorcore/zizmor-action" in path]
    assert refs, "DEPBOT-03: no zizmorcore/zizmor-action uses: line found"
    for ref in refs:
        assert _ALLOWED_REF.match(ref), (
            f"CIHARD-04: zizmorcore/zizmor-action must be SHA-pinned to 40-char hex; got {ref!r}"
        )


def test_no_pull_request_target() -> None:
    text = _read_zizmor()
    assert not _scan_has_pull_request_target(text), (
        "CIHARD-01: zizmor.yml MUST NOT use pull_request_target (PITFALL 1 fork-PR leak)"
    )


def test_persist_credentials_false() -> None:
    text = _read_zizmor()
    assert "persist-credentials: false" in text, (
        "CIHARD-03: actions/checkout in zizmor.yml must set persist-credentials: false"
    )


def test_every_uses_sha_pinned() -> None:
    text = _read_zizmor()
    pairs = _scan_uses(text)
    offenders = [
        (path, ref)
        for path, ref in pairs
        if not path.startswith("./") and not _ALLOWED_REF.match(ref)
    ]
    assert not offenders, (
        f"CIHARD-04: every uses: in zizmor.yml must be SHA-pinned; offenders: {offenders}"
    )


# Non-vacuity scanners


def test_scanner_catches_missing_paths_filter(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "name: zizmor\non:\n  pull_request:\njobs:\n  x:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert ".github/workflows/**" not in text, (
        "Non-vacuity: scanner must flag absence of .github/workflows/** path filter"
    )


def test_scanner_catches_mutable_tag(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "jobs:\n  x:\n    steps:\n      - uses: zizmorcore/zizmor-action@v0\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    pairs = _scan_uses(text)
    assert pairs
    assert not _ALLOWED_REF.match(pairs[0][1]), "Non-vacuity: scanner must flag mutable tag v0"


def test_scanner_catches_pull_request_target(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "name: x\non:\n  pull_request_target:\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert _scan_has_pull_request_target(text), (
        "Non-vacuity: scanner must flag pull_request_target trigger"
    )
