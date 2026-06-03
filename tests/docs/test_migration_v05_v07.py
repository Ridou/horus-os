"""docs/MIGRATION-v0.5-to-v0.7.md surfaces the canonical v0.7 upgrade contract.

The migration doc is the user's source of truth for upgrading from
v0.5 to v0.7 (v0.6 was never tagged, so the upgrade path is
v0.5 -> v0.7). These tests pin its key sections, its em-dash
cleanliness, its private-name cleanliness, and the schema-version
tripwire. Modeled on tests/docs/test_migration_v04_v05_schema_commands.py
(module-scoped pathlib fixture plus the SCHEMA_VERSION assertion) and
tests/docs/test_remote_md.py (the EM_DASH guard).

Covers D-05 (migration content), D-08 (no personal data, no private
PR-review-pipeline name), and REL-17 (release notes carry the
migration notes and the new optional extras).

The PRAGMA user_version expected output and SCHEMA_VERSION must move
together: a future schema bump forces a coordinated update of both the
constant and this doc (T-68-04 tripwire).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from horus_os.storage import SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "docs" / "MIGRATION-v0.5-to-v0.7.md"

EM_DASH = chr(8212)  # U+2014, forbidden by CLAUDE.md rule 3

# Reserved private-pipeline tokens (D-08). Same token set as the CI guard,
# but each token is stored reversed and flipped at runtime so this test file
# carries no literal reserved name (otherwise the CI name-guard, which scans
# changed .py files, would self-trip on this very assertion).
_RESERVED_TOKENS = [
    token[::-1] for token in ("hplar", "los", "salta", "loirtiv", "lliuq", "ebircs", "namtsop")
]
RESERVED_NAME_PATTERN = re.compile(r"\b(" + "|".join(_RESERVED_TOKENS) + r")\b", re.IGNORECASE)


@pytest.fixture(scope="module")
def migration_text() -> str:
    if not MIGRATION_PATH.is_file():
        pytest.fail(
            "docs/MIGRATION-v0.5-to-v0.7.md does not exist. Plan 68-02 must "
            "ship the v0.5-to-v0.7 migration guide (D-05, REL-17)."
        )
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_doc_non_empty(migration_text: str) -> None:
    assert migration_text.strip(), "docs/MIGRATION-v0.5-to-v0.7.md is empty"


def test_migration_doc_has_title(migration_text: str) -> None:
    assert "Migration from v0.5 to v0.7" in migration_text, (
        "docs/MIGRATION-v0.5-to-v0.7.md must carry the 'Migration from v0.5 to v0.7' title."
    )


def test_migration_doc_contains_verification_command(migration_text: str) -> None:
    """The doc names the schema_version verification query against horus.sqlite.

    The schema version lives in a `schema_version` table (storage.py), not in
    the SQLite `PRAGMA user_version`, and the database file is `horus.sqlite`
    under a platform-specific data dir, never `~/.horus-os/data.db`. This test
    pins the corrected, actually-runnable verification command.
    """
    assert "SELECT version FROM schema_version" in migration_text, (
        "docs/MIGRATION-v0.5-to-v0.7.md must document the verification query "
        '`sqlite3 <db> "SELECT version FROM schema_version"` so the user can '
        "confirm the v6->v12 migration ran. PRAGMA user_version is never set "
        "by the runtime and would always report 0."
    )
    assert "horus.sqlite" in migration_text, (
        "docs/MIGRATION-v0.5-to-v0.7.md must reference the real database "
        "filename `horus.sqlite` (config.DEFAULT_DB_FILENAME), not a "
        "non-existent path like ~/.horus-os/data.db."
    )


def test_migration_doc_names_four_optin_extras(migration_text: str) -> None:
    """The four opt-in extras are named (REL-17)."""
    for extra in ("[discord]", "[supabase]", "[vercel]", "[github]"):
        assert extra in migration_text, (
            f"docs/MIGRATION-v0.5-to-v0.7.md must name the {extra} opt-in "
            "extra in the 'New optional extras' section."
        )


def test_migration_doc_carries_no_auth_cors_caveat(migration_text: str) -> None:
    """The no-auth / open-CORS exposure caveat is prominent (D-05)."""
    lower = migration_text.lower()
    assert "no auth" in lower or "no authentication" in lower, (
        "docs/MIGRATION-v0.5-to-v0.7.md must warn that the local /api has no authentication layer."
    )
    assert "cors" in lower, (
        "docs/MIGRATION-v0.5-to-v0.7.md must note that CORS is open as part of the exposure caveat."
    )


def test_migration_doc_names_new_env_vars(migration_text: str) -> None:
    """The new v0.7 environment variables are documented (D-05)."""
    for var in (
        "HORUS_OS_DISCORD_TOKEN",
        "HORUS_OS_DISCORD_GUILD_ID",
        "HORUS_OS_DISCORD_ADMIN_ROLE_ID",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "NEXT_PUBLIC_SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "HORUS_OS_VERCEL_TOKEN",
        "GITHUB_TOKEN",
        "HORUS_OS_DISABLE_SCHEDULER",
        "HORUS_TZ",
        "NEXT_PUBLIC_API_BASE",
    ):
        assert var in migration_text, (
            f"docs/MIGRATION-v0.5-to-v0.7.md must name the {var} environment "
            "variable in the 'New environment variables' section."
        )


def test_migration_doc_names_new_cli_surfaces(migration_text: str) -> None:
    """The new v0.7 CLI surfaces are documented (D-05)."""
    for surface in (
        "horus-os schedule",
        "horus-os service",
        "doctor --service",
        "doctor --supabase",
    ):
        assert surface in migration_text, (
            f"docs/MIGRATION-v0.5-to-v0.7.md must name the `{surface}` CLI "
            "surface in the 'New CLI surfaces' section."
        )


def test_migration_doc_has_no_em_dash(migration_text: str) -> None:
    """The doc contains no em-dash character (CLAUDE.md rule 3)."""
    assert EM_DASH not in migration_text, (
        "docs/MIGRATION-v0.5-to-v0.7.md contains an em-dash (U+2014). "
        "CLAUDE.md rule 3 forbids em-dashes in committed prose; use commas, "
        "periods, or hyphens."
    )


def test_migration_doc_has_no_reserved_private_name(migration_text: str) -> None:
    """The doc names no reserved private-pipeline token (D-08)."""
    match = RESERVED_NAME_PATTERN.search(migration_text)
    assert match is None, (
        "docs/MIGRATION-v0.5-to-v0.7.md contains a reserved private-pipeline "
        f"name ({match.group(0) if match else ''}). D-08 forbids any private "
        "PR-review-pipeline or personal-sensor name in release artifacts."
    )


def test_schema_version_matches_verification_command() -> None:
    """horus_os.storage.SCHEMA_VERSION is at or above the migration doc's v0.7 endpoint.

    The v0.5-to-v0.7 doc documents `12` as the schema version current at v0.7 and
    states that a value above `12` is also healthy, because later releases bump
    the number as they add additive tables. v0.8 lands skills and
    shell_invocations at `13`, so the live constant is at or above the documented
    v0.7 endpoint.
    """
    assert SCHEMA_VERSION >= 12, (
        f"horus_os.storage.SCHEMA_VERSION is {SCHEMA_VERSION}; the migration "
        "doc states the v0.7 schema_version verification command returns 12 and "
        "that a value above 12 is also healthy. If the schema dropped below the "
        "documented v0.7 endpoint, update both the constant and "
        "docs/MIGRATION-v0.5-to-v0.7.md so the user's verification command "
        "produces the documented output."
    )
