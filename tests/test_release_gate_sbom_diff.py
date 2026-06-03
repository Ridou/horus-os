"""Phase 53 SBOM-03 second-clause regression tests (closed in 57-followup).

Tests for `scripts/release_gate.py::check_sbom_matches_wheel`. The check
diffs a published wheel's actual dependency tree (via `pip install --dry-run
--ignore-installed --report -`) against the CycloneDX 1.6 JSON SBOM. STALE
(in SBOM, not in wheel) and MISSING (in wheel, not in SBOM) divergences
both fail the check.

Test strategy:
- Synthetic wheel fixture (a minimal valid .whl built from a tiny pyproject).
- Synthetic SBOM JSON written to tmp_path with controlled component lists.
- Inject the pip-report payload via the test-only `pip_report_payload`
  kwarg so we never hit the network and never need a working pip resolver
  for the wheel.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "release_gate.py"

_MODULE_NAME = "_release_gate_sbom_diff_under_test"


def _load_release_gate_module():
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(RELEASE_GATE_PATH))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _make_fake_wheel(tmp_path: Path, name: str = "horus_os", version: str = "0.6.0") -> Path:
    """Write a minimal .whl shell to disk; PEP 427 filename is the load-bearing part."""
    wheel_filename = f"{name}-{version}-py3-none-any.whl"
    wheel_path = tmp_path / wheel_filename
    with zipfile.ZipFile(wheel_path, "w") as zf:
        zf.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        )
        zf.writestr(f"{name}-{version}.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    return wheel_path


def _write_sbom(tmp_path: Path, components: list[tuple[str, str]]) -> Path:
    """Write a minimal CycloneDX 1.6 SBOM with the listed (name, version) pairs."""
    payload = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "components": [
            {"type": "library", "name": name, "version": version} for (name, version) in components
        ],
    }
    sbom_path = tmp_path / "horus_os-clean.cdx.json"
    sbom_path.write_text(json.dumps(payload), encoding="utf-8")
    return sbom_path


def _make_pip_report(deps: list[tuple[str, str]]) -> dict:
    """Build a synthetic pip --report payload with the given top-level deps."""
    return {
        "version": "1",
        "install": [{"metadata": {"name": name, "version": version}} for (name, version) in deps],
    }


def test_check_returns_skip_when_wheel_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    result = mod.check_sbom_matches_wheel(
        wheel_path=tmp_path / "missing.whl",
        sbom_path=tmp_path / "missing.cdx.json",
    )
    assert result.ok is None
    assert "SKIPPED" in result.diagnostic


def test_check_returns_skip_when_sbom_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path)
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=tmp_path / "missing.cdx.json",
    )
    assert result.ok is None
    assert "SKIPPED" in result.diagnostic


def test_check_passes_when_sbom_matches_pip_report(tmp_path: Path) -> None:
    """The canonical happy path: SBOM components exactly match pip-report install set."""
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path)
    deps = [("anthropic", "0.40.0"), ("pydantic", "2.7.0"), ("httpx", "0.27.0")]
    sbom = _write_sbom(tmp_path, deps)
    report = _make_pip_report(deps)
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=sbom,
        pip_report_payload=report,
    )
    assert result.ok is True, f"expected clean diff, got: {result.diagnostic}"
    assert "matches the 3 transitive deps" in result.diagnostic


def test_check_fails_when_sbom_stale_missing_component(tmp_path: Path) -> None:
    """A stale SBOM (missing a wheel dep) fails with MISSING diagnostic."""
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path)
    # SBOM lists only 2 of the 3 deps the wheel actually pulls
    sbom = _write_sbom(tmp_path, [("anthropic", "0.40.0"), ("pydantic", "2.7.0")])
    report = _make_pip_report([("anthropic", "0.40.0"), ("pydantic", "2.7.0"), ("httpx", "0.27.0")])
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=sbom,
        pip_report_payload=report,
    )
    assert result.ok is False
    assert "MISSING" in result.diagnostic
    assert "httpx==0.27.0" in result.diagnostic


def test_check_fails_when_sbom_has_extra_component(tmp_path: Path) -> None:
    """An SBOM listing a component pip wouldn't install fails with STALE diagnostic."""
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path)
    # SBOM lists 3 deps but pip would only install 2
    sbom = _write_sbom(
        tmp_path,
        [("anthropic", "0.40.0"), ("pydantic", "2.7.0"), ("requests", "2.32.0")],
    )
    report = _make_pip_report([("anthropic", "0.40.0"), ("pydantic", "2.7.0")])
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=sbom,
        pip_report_payload=report,
    )
    assert result.ok is False
    assert "STALE" in result.diagnostic
    assert "requests==2.32.0" in result.diagnostic


def test_check_fails_on_version_drift(tmp_path: Path) -> None:
    """Same name, different version = both STALE and MISSING (version mismatch)."""
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path)
    sbom = _write_sbom(tmp_path, [("pydantic", "2.7.0")])
    report = _make_pip_report([("pydantic", "2.7.1")])
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=sbom,
        pip_report_payload=report,
    )
    assert result.ok is False
    diag = result.diagnostic
    assert "STALE" in diag and "pydantic==2.7.0" in diag
    assert "MISSING" in diag and "pydantic==2.7.1" in diag


def test_check_canonicalizes_name_variants(tmp_path: Path) -> None:
    """`pydantic_core` (pip) and `pydantic-core` (SBOM) are treated as equal."""
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path)
    sbom = _write_sbom(tmp_path, [("pydantic-core", "2.18.0")])
    report = _make_pip_report([("pydantic_core", "2.18.0")])
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=sbom,
        pip_report_payload=report,
    )
    assert result.ok is True, f"name canonicalization broken: {result.diagnostic}"


def test_check_excludes_wheel_self_from_pip_report(tmp_path: Path) -> None:
    """pip --report includes the wheel itself; SBOM does not. The diff strips it."""
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path, name="horus_os", version="0.6.0")
    # SBOM lists only the deps (cyclonedx-py environment scan never includes self)
    sbom = _write_sbom(tmp_path, [("pydantic", "2.7.0")])
    # pip --report includes the wheel itself as an install entry
    report = _make_pip_report([("horus-os", "0.6.0"), ("pydantic", "2.7.0")])
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=sbom,
        pip_report_payload=report,
    )
    assert result.ok is True, f"wheel self-exclusion broken: {result.diagnostic}"


def test_check_handles_malformed_sbom(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    wheel = _make_fake_wheel(tmp_path)
    bad_sbom = tmp_path / "bad.cdx.json"
    bad_sbom.write_text("{not valid json", encoding="utf-8")
    result = mod.check_sbom_matches_wheel(
        wheel_path=wheel,
        sbom_path=bad_sbom,
        pip_report_payload=_make_pip_report([]),
    )
    assert result.ok is False
    assert "could not read or parse SBOM" in result.diagnostic


# Enum surface area: sbom-matches-wheel appears in --check choices


def test_check_enum_includes_sbom_matches_wheel() -> None:
    """sbom-matches-wheel must remain a member of the --check enum."""
    text = RELEASE_GATE_PATH.read_text(encoding="utf-8")
    assert '"sbom-matches-wheel"' in text, (
        "sbom-matches-wheel missing from --check enum or dispatch"
    )
