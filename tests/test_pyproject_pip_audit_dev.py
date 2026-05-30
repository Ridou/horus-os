"""Phase 53 SUPPLY-01 lint for pyproject.toml [project.optional-dependencies] dev.

Wave 0 RED-by-design: production assertions fail until Plan 02 adds
'pip-audit>=2.10,<3' to [project.optional-dependencies].dev. The pin is the
ONE base-dep-extras change in v0.6 (load-bearing constraint #1 from STATE.md).

Non-vacuity parser tests pass NOW via tmp_path fixtures.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

PIP_AUDIT_EXACT_PIN = "pip-audit>=2.10,<3"


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


# Production assertions: RED until Plan 02 adds pip-audit to [dev].


def test_pyproject_exists() -> None:
    assert PYPROJECT_PATH.is_file(), f"{PYPROJECT_PATH} must exist"


def test_dev_extras_includes_pip_audit() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    dev = data["project"]["optional-dependencies"]["dev"]
    assert any(entry.startswith("pip-audit") for entry in dev), (
        f"SUPPLY-01: [project.optional-dependencies].dev must include pip-audit; got {dev}"
    )


def test_dev_extras_pip_audit_version_pinned() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    dev = data["project"]["optional-dependencies"]["dev"]
    pip_audit_entries = [e for e in dev if e.startswith("pip-audit")]
    assert pip_audit_entries, "SUPPLY-01: no pip-audit entry in [dev] (precondition)"
    assert PIP_AUDIT_EXACT_PIN in pip_audit_entries, (
        f"SUPPLY-01: pip-audit pin must be exactly {PIP_AUDIT_EXACT_PIN!r}; got {pip_audit_entries}"
    )


def test_base_deps_unchanged() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    base = data["project"].get("dependencies", [])
    pip_audit_in_base = [e for e in base if e.startswith("pip-audit")]
    assert not pip_audit_in_base, (
        "Load-bearing constraint #1: pyproject [project.dependencies] base must NOT contain "
        "pip-audit (zero base-dep change in v0.6; pip-audit lives in [dev] extras only). "
        f"Offenders: {pip_audit_in_base}"
    )


def test_no_other_optional_extras_have_pip_audit() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    extras = data["project"].get("optional-dependencies", {})
    offenders: dict[str, list[str]] = {}
    for name, entries in extras.items():
        if name == "dev":
            continue
        bad = [e for e in entries if e.startswith("pip-audit")]
        if bad:
            offenders[name] = bad
    assert not offenders, (
        "SUPPLY-01: pip-audit belongs in [dev] ONLY (not [all] meta-extra, not any "
        f"other extras list). Offenders: {offenders}"
    )


# Non-vacuity parser tests: pass NOW.


def test_scanner_catches_missing_pip_audit(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.toml"
    synthetic.write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n\n'
        "[project.optional-dependencies]\n"
        'dev = ["pytest"]\n',
        encoding="utf-8",
    )
    data = _load_pyproject(synthetic)
    dev = data["project"]["optional-dependencies"]["dev"]
    assert not any(e.startswith("pip-audit") for e in dev), (
        "Non-vacuity: scanner must flag a synthetic [dev] list missing pip-audit"
    )


def test_scanner_catches_wrong_pin(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.toml"
    synthetic.write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n\n'
        "[project.optional-dependencies]\n"
        'dev = ["pip-audit"]\n',
        encoding="utf-8",
    )
    data = _load_pyproject(synthetic)
    dev = data["project"]["optional-dependencies"]["dev"]
    pip_audit_entries = [e for e in dev if e.startswith("pip-audit")]
    assert pip_audit_entries
    assert PIP_AUDIT_EXACT_PIN not in pip_audit_entries, (
        "Non-vacuity: scanner must flag an unpinned 'pip-audit' entry as missing the version pin"
    )
