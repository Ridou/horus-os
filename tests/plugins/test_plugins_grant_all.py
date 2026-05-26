"""``horus-os plugins grant --all`` flag (Phase 49, Task 1).

The v0.5 ergonomics improvement: instead of requiring the user to type
``horus-os plugins grant <name> <capability>`` once per capability,
``--all`` reads the plugin's manifest capabilities (from the plugins
table at install time, which is the user-approved set) and grants every
one in a single call. The CI ``install-smoke-plugin`` matrix uses this
to flip the reference plugin from ``pending`` to ``loaded`` in one
command.

The flag is mutually exclusive with the positional ``capability`` arg:
either you name ONE capability (v0.4 shape, byte-identical) or you pass
``--all`` (v0.5 shape, NO positional). Passing both is an argparse
error; passing neither is also an argparse error (the mutex group is
``required=True``).

Test shape:

* ``test_grant_all_grants_every_capability`` — seed two pending caps,
  call ``--all``, assert two granted rows + "Granted 2 capabilities"
  in stdout.
* ``test_grant_all_idempotent_on_already_granted`` — run twice in a
  row; second call still says "Granted 2 capabilities" + final row
  count remains 2.
* ``test_grant_positional_byte_identical_to_v0_4`` — single positional
  cap produces the v0.4 message "Granted X to NAME." unchanged.
* ``test_grant_all_with_positional_exits_2`` — argparse mutex error
  (subprocess test for argparse-level rejection).
* ``test_grant_missing_capability_and_all_exits_2`` — neither
  positional nor ``--all`` is the same argparse-level error.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

import pytest

from horus_os.__main__ import build_parser
from horus_os.cli.plugins_cmd import run_plugins
from horus_os.storage import Database

PLUGIN_NAME = "horus-os-example-plugin"
PLUGIN_VERSION = "0.1.0"
PLUGIN_MANIFEST_HASH = "test-hash-49"
CAPS = ("filesystem.read", "secrets.read")


def _seed_plugin_row(db: Database) -> None:
    """Insert the plugins row + plugin_capabilities pending rows.

    Mirrors what ``install_plugin`` does in Phase C without going
    through the wheel-download path. Capabilities are inserted as
    ``state='pending'`` so ``--all`` can flip them to ``granted``.
    """
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES (?, ?, ?, 1, '2026-05-26T00:00:00Z', 'entry_point')
            """,
            (PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_MANIFEST_HASH),
        )
        for cap in CAPS:
            conn.execute(
                """
                INSERT INTO plugin_capabilities
                    (plugin_name, plugin_version, capability, manifest_hash,
                     state, granted_at)
                VALUES (?, ?, ?, ?, 'pending', NULL)
                """,
                (PLUGIN_NAME, PLUGIN_VERSION, cap, PLUGIN_MANIFEST_HASH),
            )


def _make_args(**overrides) -> argparse.Namespace:
    base: dict = {
        "plugins_command": "grant",
        "name": PLUGIN_NAME,
        "capability": None,
        "grant_all": False,
        "data_dir": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _run_grant(
    db: Database,
    monkeypatch: pytest.MonkeyPatch,
    args: argparse.Namespace,
) -> tuple[int, str, str]:
    """Run run_plugins with a synthetic Namespace + Config stub."""
    from horus_os import config as config_mod

    class FakeConfig:
        db_path = db.path

    monkeypatch.setattr(
        config_mod.Config,
        "load",
        staticmethod(lambda data_dir=None: FakeConfig()),
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    rc = run_plugins(args, stdout=stdout, stderr=stderr)
    return rc, stdout.getvalue(), stderr.getvalue()


def _count_granted(db: Database) -> int:
    with db._connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM plugin_capabilities
            WHERE plugin_name = ? AND state = 'granted'
            """,
            (PLUGIN_NAME,),
        ).fetchone()
    return int(row["n"])


def test_grant_all_grants_every_capability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--all`` flips both pending capabilities to granted in one call."""
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    _seed_plugin_row(db)
    # Sanity: pre-grant granted count is zero.
    assert _count_granted(db) == 0

    args = _make_args(grant_all=True)
    rc, out, err = _run_grant(db, monkeypatch, args)

    assert rc == 0, err
    assert "Granted 2 capabilities" in out, out
    # Both caps should appear in the output for human verification.
    assert "filesystem.read" in out
    assert "secrets.read" in out
    assert _count_granted(db) == 2


def test_grant_all_idempotent_on_already_granted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running ``--all`` does not duplicate rows or raise."""
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    _seed_plugin_row(db)

    # First call.
    args = _make_args(grant_all=True)
    rc1, out1, _ = _run_grant(db, monkeypatch, args)
    assert rc1 == 0
    assert "Granted 2 capabilities" in out1

    # Second call — must not raise; row count stays at 2.
    args2 = _make_args(grant_all=True)
    rc2, out2, _ = _run_grant(db, monkeypatch, args2)
    assert rc2 == 0
    assert "Granted 2 capabilities" in out2
    assert _count_granted(db) == 2


def test_grant_positional_byte_identical_to_v0_4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0.4 positional shape preserved: ``grant NAME CAP`` -> "Granted CAP to NAME."."""
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    _seed_plugin_row(db)

    args = _make_args(capability="filesystem.read", grant_all=False)
    rc, out, _ = _run_grant(db, monkeypatch, args)

    assert rc == 0
    # Exact v0.4 message — single capability, byte-identical phrasing.
    assert out == f"Granted filesystem.read to {PLUGIN_NAME}.\n"
    assert _count_granted(db) == 1


def test_grant_argparse_accepts_all_flag() -> None:
    """The argparse layer accepts ``--all`` without a positional capability."""
    p = build_parser()
    ns = p.parse_args(["plugins", "grant", PLUGIN_NAME, "--all"])
    assert ns.plugins_command == "grant"
    assert ns.name == PLUGIN_NAME
    assert ns.grant_all is True
    assert ns.capability is None


def test_grant_argparse_accepts_positional_capability() -> None:
    """The v0.4 shape ``grant NAME CAP`` (no --all) still parses."""
    p = build_parser()
    ns = p.parse_args(["plugins", "grant", PLUGIN_NAME, "filesystem.read"])
    assert ns.plugins_command == "grant"
    assert ns.name == PLUGIN_NAME
    assert ns.capability == "filesystem.read"
    assert ns.grant_all is False


def test_grant_all_with_positional_exits_2() -> None:
    """``grant NAME --all CAP`` rejected: mutex group between --all and CAP.

    Uses subprocess because argparse mutex rejection raises SystemExit
    AFTER writing to stderr, and capturing both via in-process SystemExit
    catching is brittle. Subprocess is the simple path for argparse
    rejection assertions (same shape as the v0.4 release-gate tests).
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "horus_os",
            "plugins",
            "grant",
            PLUGIN_NAME,
            "filesystem.read",
            "--all",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, (
        f"expected argparse mutex error exit code 2; got {proc.returncode}; stderr: {proc.stderr}"
    )
    assert "not allowed" in proc.stderr.lower(), proc.stderr


def test_grant_missing_capability_and_all_exits_2() -> None:
    """Neither positional nor ``--all`` is also a mutex-required error."""
    p = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        p.parse_args(["plugins", "grant", PLUGIN_NAME])
    assert excinfo.value.code == 2
