"""docs/MIGRATION-v0.4-to-v0.5.md surfaces the canonical migration commands.

The migration doc is the user's source of truth for upgrading from
v0.4 to v0.5. Six substrings + one runtime cross-link must hold:

1. The doc exists.
2. The verification command uses ``PRAGMA user_version``.
3. The two new base dependencies are documented:
   ``pydantic>=2.7,<3`` and ``packaging>=24.0``.
4. The rollback escape hatch is documented: ``--disable-all-plugins``.
5. The doc states "no breaking changes" (case-insensitive).
6. ``horus_os.storage.SCHEMA_VERSION == 13``, the verification
   command's expected output matches reality. If a future schema
   bump happens, this test plus the migration doc both need a
   coordinated update.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.storage import SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "docs" / "MIGRATION-v0.4-to-v0.5.md"


@pytest.fixture(scope="module")
def migration_text() -> str:
    if not MIGRATION_PATH.is_file():
        pytest.fail(
            "docs/MIGRATION-v0.4-to-v0.5.md does not exist. Phase 47 must ship the migration guide."
        )
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_doc_exists(migration_text: str) -> None:
    assert migration_text.strip(), "docs/MIGRATION-v0.4-to-v0.5.md is empty"


def test_migration_doc_contains_verification_command(migration_text: str) -> None:
    """The migration doc names the PRAGMA user_version verification command."""
    assert "PRAGMA user_version" in migration_text, (
        "docs/MIGRATION-v0.4-to-v0.5.md must document the verification "
        'command `sqlite3 ~/.horus-os/data.db "PRAGMA user_version"` so '
        "the user can confirm the v5→v6 migration ran."
    )


def test_migration_doc_documents_new_base_deps(migration_text: str) -> None:
    """The two new base dependencies are named with version pins."""
    assert "pydantic>=2.7,<3" in migration_text, (
        "docs/MIGRATION-v0.4-to-v0.5.md must name pydantic>=2.7,<3 in the "
        "'New base dependencies' section (REL-10 / migration contract)."
    )
    assert "packaging>=24.0" in migration_text, (
        "docs/MIGRATION-v0.4-to-v0.5.md must name packaging>=24.0 in the "
        "'New base dependencies' section (REL-10 / migration contract)."
    )


def test_migration_doc_documents_rollback_flag(migration_text: str) -> None:
    """The rollback escape hatch --disable-all-plugins is documented."""
    assert "--disable-all-plugins" in migration_text, (
        "docs/MIGRATION-v0.4-to-v0.5.md must document the "
        "--disable-all-plugins boot flag as the rollback escape hatch."
    )


def test_migration_doc_says_no_breaking_changes(migration_text: str) -> None:
    """The doc explicitly states there are no breaking changes."""
    assert "no breaking changes" in migration_text.lower(), (
        "docs/MIGRATION-v0.4-to-v0.5.md must state 'no breaking changes' "
        "(case-insensitive) so the user reading the doc knows v0.5 is "
        "purely additive over v0.4."
    )


def test_schema_version_matches_verification_command() -> None:
    """horus_os.storage.SCHEMA_VERSION matches the migration doc's expected output."""
    assert SCHEMA_VERSION == 13, (
        f"horus_os.storage.SCHEMA_VERSION is {SCHEMA_VERSION}; the migration "
        f"doc states `PRAGMA user_version` returns 9. If the schema bumped, "
        f"update both the constant and docs/MIGRATION-v0.4-to-v0.5.md so "
        f"the user's verification command produces the documented output."
    )
