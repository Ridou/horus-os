"""Phase 54 DEPBOT-01 + DEPBOT-02 structural lint for .github/dependabot.yml.

Wave 0 RED-by-design: production assertions fail until Plan 02 creates
.github/dependabot.yml v2 with pip + github-actions ecosystems, four pip
groups (ai-sdks, otel, web-stack, dev-tools), version-updates only, and
NO `applies-to: security-updates` matcher anywhere (DEPBOT-02 hard rule).

Non-vacuity scanners pass NOW via tmp_path fixtures.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPENDABOT_PATH = REPO_ROOT / ".github" / "dependabot.yml"


def _read_dependabot() -> str:
    if not DEPENDABOT_PATH.is_file():
        raise FileNotFoundError(
            f"DEPBOT-01: Plan 02 must create {DEPENDABOT_PATH} (Dependabot v2 config)"
        )
    return DEPENDABOT_PATH.read_text(encoding="utf-8")


def _scan_security_grouping(text: str) -> bool:
    """True if 'applies-to: security-updates' appears anywhere on a non-comment line.

    Comment-only lines are skipped so prose explaining why we forbid this
    matcher does not trigger the scanner.
    """
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        if "applies-to: security-updates" in line:
            return True
    return False


def _scan_groups(text: str, names: list[str]) -> dict[str, bool]:
    """Return {group_name: present} for each name searched as `^\\s+<name>:` (YAML key)."""
    found: dict[str, bool] = {}
    for name in names:
        pattern = re.compile(rf"^\s+{re.escape(name)}:\s*$", re.MULTILINE)
        found[name] = bool(pattern.search(text))
    return found


def test_dependabot_yml_exists() -> None:
    assert DEPENDABOT_PATH.is_file(), f"DEPBOT-01: Plan 02 must create {DEPENDABOT_PATH}"


def test_version_2() -> None:
    text = _read_dependabot()
    assert re.search(r"^version:\s*2\s*$", text, re.MULTILINE), (
        "DEPBOT-01: Dependabot config must declare 'version: 2'"
    )


def test_pip_ecosystem_present() -> None:
    text = _read_dependabot()
    assert "package-ecosystem: pip" in text, (
        "DEPBOT-01: dependabot.yml must declare package-ecosystem: pip"
    )


def test_github_actions_ecosystem_present() -> None:
    text = _read_dependabot()
    assert "package-ecosystem: github-actions" in text, (
        "DEPBOT-01: dependabot.yml must declare package-ecosystem: github-actions "
        "(canonical source of SHA-pin freshness)"
    )


def test_four_pip_groups() -> None:
    text = _read_dependabot()
    found = _scan_groups(text, ["ai-sdks", "otel", "web-stack", "dev-tools"])
    missing = [name for name, present in found.items() if not present]
    assert not missing, f"DEPBOT-01: pip ecosystem must declare 4 groups; missing: {missing}"


def test_each_group_version_updates_only() -> None:
    text = _read_dependabot()
    count = text.count("applies-to: version-updates")
    assert count >= 4, (
        f"DEPBOT-01: every group must declare applies-to: version-updates "
        f"(at least 4 occurrences); got {count}"
    )


def test_no_security_updates_grouping() -> None:
    text = _read_dependabot()
    assert not _scan_security_grouping(text), (
        "DEPBOT-02 hard rule: dependabot.yml MUST NOT contain "
        "'applies-to: security-updates' on any group (security PRs are un-grouped "
        "so CVE PRs never hide inside weekly grouped bumps)"
    )


def test_cooldown_3_days_default() -> None:
    text = _read_dependabot()
    assert "default-days: 3" in text, "DEPBOT-01: cooldown default-days must be 3"


def test_cooldown_14_days_majors() -> None:
    text = _read_dependabot()
    assert "semver-major-days: 14" in text, "DEPBOT-01: cooldown semver-major-days must be 14"


def test_anthropic_in_ai_sdks() -> None:
    text = _read_dependabot()
    assert "anthropic" in text, "DEPBOT-01: ai-sdks group must include anthropic"


def test_google_genai_in_ai_sdks() -> None:
    text = _read_dependabot()
    assert "google-genai" in text, "DEPBOT-01: ai-sdks group must include google-genai"


def test_opentelemetry_in_otel() -> None:
    text = _read_dependabot()
    assert "opentelemetry-*" in text, (
        "DEPBOT-01: otel group must include 'opentelemetry-*' wildcard"
    )


def test_pip_audit_in_dev_tools() -> None:
    text = _read_dependabot()
    assert "pip-audit" in text, "DEPBOT-01: dev-tools group must include pip-audit"


def test_schedule_weekly() -> None:
    text = _read_dependabot()
    assert "interval: weekly" in text, "DEPBOT-01: schedule must include interval: weekly"


# Non-vacuity scanners


def test_scanner_catches_security_grouping(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n    groups:\n"
        "      x:\n        applies-to: security-updates\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert _scan_security_grouping(text), (
        "Non-vacuity: scanner must flag 'applies-to: security-updates'"
    )


def test_scanner_catches_missing_version_2(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text("updates: []\n", encoding="utf-8")
    text = synthetic.read_text(encoding="utf-8")
    assert not re.search(r"^version:\s*2\s*$", text, re.MULTILINE), (
        "Non-vacuity: scanner must flag absence of 'version: 2'"
    )


def test_scanner_catches_single_ecosystem(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert "package-ecosystem: pip" in text
    assert "package-ecosystem: github-actions" not in text, (
        "Non-vacuity: scanner must flag absence of github-actions ecosystem"
    )
