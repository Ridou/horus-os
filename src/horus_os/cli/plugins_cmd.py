"""``horus-os plugins`` subcommand dispatcher.

Mirrors the shape of ``agents_cmd.run_agents``: one public
``run_plugins(args, *, stdout, stderr) -> int`` that branches on
``args.plugins_command`` and delegates to the matching ``installer``
verb. Nine subcommands total:

  install   wrap installer.install_plugin
  uninstall wrap installer.uninstall_plugin
  list      tabular or JSON dump of the plugins table
  info      detail view (plugin + capabilities + recent audit)
  enable    flip plugins.enabled = 1 via PluginRegistry
  disable   flip plugins.enabled = 0 via PluginRegistry
  update    wrap installer.update_plugin (upgrade-diff classifier)
  grant     wrap installer.grant_capability
  revoke    wrap installer.revoke_capability

The dispatcher keeps the lifespan-style "open Config + Database;
branch; return int" idiom so a test can build a synthetic Namespace,
pass StringIO buffers as stdout/stderr, and assert on the captured
text without spinning up a subprocess.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TextIO

from horus_os.config import Config
from horus_os.plugins import installer
from horus_os.plugins.installer import PluginInstallError
from horus_os.plugins.registry import PluginRegistry
from horus_os.storage import Database


def run_plugins(
    args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO
) -> int:
    """Dispatch a ``horus-os plugins X`` invocation. Returns CLI exit code."""
    config = Config.load(getattr(args, "data_dir", None))
    if not config.db_path.exists():
        stderr.write(
            f"No database at {config.db_path}. Run `horus-os init` first.\n"
        )
        return 1
    db = Database(config.db_path)
    op = getattr(args, "plugins_command", None)
    if op is None:
        stderr.write(
            "horus-os plugins: provide one of {install, uninstall, list, info, "
            "enable, disable, update, grant, revoke}\n"
        )
        return 2

    handlers = {
        "install": _cmd_install,
        "uninstall": _cmd_uninstall,
        "list": _cmd_list,
        "info": _cmd_info,
        "enable": _cmd_enable,
        "disable": _cmd_disable,
        "update": _cmd_update,
        "grant": _cmd_grant,
        "revoke": _cmd_revoke,
    }
    handler = handlers.get(op)
    if handler is None:
        stderr.write(f"Unknown plugins operation: {op!r}\n")
        return 2
    return handler(db, args, stdout, stderr)


# ----------------------------------------------------------------------
# Per-verb handlers
# ----------------------------------------------------------------------


def _cmd_install(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        name = installer.install_plugin(
            args.spec,
            db=db,
            allow_sdist=getattr(args, "allow_sdist", False),
            allow_system_python=getattr(args, "allow_system_python", False),
            assume_yes=getattr(args, "yes", False),
            stdin=sys.stdin,
            stdout=stdout,
            stderr=stderr,
        )
    except PluginInstallError as exc:
        stderr.write(f"Install failed at phase {exc.phase}: {exc}\n")
        return 1
    stdout.write(
        f"Installed plugin {name}. Restart `horus-os serve` to load it.\n"
    )
    return 0


def _cmd_uninstall(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        installer.uninstall_plugin(args.name, db=db)
    except PluginInstallError as exc:
        stderr.write(f"Uninstall failed: {exc}\n")
        return 1
    stdout.write(f"Uninstalled {args.name}.\n")
    return 0


def _cmd_list(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    rows = _select_plugin_rows(db)
    if getattr(args, "json", False):
        if not rows:
            stdout.write("[]\n")
            return 0
        stdout.write(json.dumps(rows, indent=2) + "\n")
        return 0
    if not rows:
        stdout.write("(no plugins installed)\n")
        return 0
    stdout.write(_format_plugins_table(rows) + "\n")
    return 0


def _cmd_info(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    name = args.name
    with db._connect() as conn:
        plugin_row = conn.execute(
            """
            SELECT p.name, p.version, p.manifest_hash, p.enabled,
                   p.installed_at, p.source, ps.status, ps.error_phase,
                   ps.error_message, ps.last_seen
            FROM plugins p
            LEFT JOIN plugin_status ps ON ps.plugin_name = p.name
            WHERE p.name = ?
            """,
            (name,),
        ).fetchone()
        if plugin_row is None:
            stderr.write(f"No installed plugin named {name!r}.\n")
            return 1
        caps = conn.execute(
            """
            SELECT capability, plugin_version, state, granted_at
            FROM plugin_capabilities
            WHERE plugin_name = ?
            ORDER BY plugin_version DESC, capability ASC
            """,
            (name,),
        ).fetchall()
        log = conn.execute(
            """
            SELECT capability, action, actor, manifest_hash, timestamp
            FROM plugin_capability_grants_log
            WHERE plugin_name = ?
            ORDER BY id DESC
            LIMIT 5
            """,
            (name,),
        ).fetchall()

    stdout.write(f"name:          {plugin_row['name']}\n")
    stdout.write(f"version:       {plugin_row['version']}\n")
    stdout.write(f"manifest_hash: {plugin_row['manifest_hash']}\n")
    stdout.write(f"enabled:       {bool(plugin_row['enabled'])}\n")
    stdout.write(f"status:        {plugin_row['status'] or '(unknown)'}\n")
    stdout.write(f"source:        {plugin_row['source']}\n")
    stdout.write(f"installed_at:  {plugin_row['installed_at']}\n")
    if plugin_row["status"] == "error":
        stdout.write(f"error_phase:   {plugin_row['error_phase']}\n")
        stdout.write(f"error_message: {plugin_row['error_message']}\n")
    stdout.write("\nCapabilities:\n")
    if not caps:
        stdout.write("  (no capability rows)\n")
    for c in caps:
        stdout.write(
            f"  {c['capability']:24}  {c['state']:8}  "
            f"v{c['plugin_version']}  granted_at={c['granted_at'] or '-'}\n"
        )
    stdout.write("\nRecent grants (last 5):\n")
    if not log:
        stdout.write("  (no audit-log entries)\n")
    for entry in log:
        stdout.write(
            f"  {entry['timestamp']}  {entry['action']:18}  "
            f"{entry['capability']:24}  actor={entry['actor']}\n"
        )
    return 0


def _cmd_enable(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    registry = PluginRegistry(db=db)
    if registry.get(args.name) is None:
        # Fall back to a direct row check — the registry restores
        # from disk on init but might miss a freshly-installed
        # plugin in some test paths.
        with db._connect() as conn:
            row = conn.execute(
                "SELECT name FROM plugins WHERE name = ?", (args.name,)
            ).fetchone()
        if row is None:
            stderr.write(f"No installed plugin named {args.name!r}.\n")
            return 1
    registry.enable(args.name)
    stdout.write(f"Enabled {args.name}. Restart to apply.\n")
    return 0


def _cmd_disable(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    registry = PluginRegistry(db=db)
    if registry.get(args.name) is None:
        with db._connect() as conn:
            row = conn.execute(
                "SELECT name FROM plugins WHERE name = ?", (args.name,)
            ).fetchone()
        if row is None:
            stderr.write(f"No installed plugin named {args.name!r}.\n")
            return 1
    registry.disable(args.name)
    stdout.write(f"Disabled {args.name}.\n")
    return 0


def _cmd_update(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        name = installer.update_plugin(
            args.name,
            args.spec,
            db=db,
            allow_sdist=getattr(args, "allow_sdist", False),
            allow_system_python=getattr(args, "allow_system_python", False),
            assume_yes=getattr(args, "yes", False),
            stdin=sys.stdin,
            stdout=stdout,
            stderr=stderr,
        )
    except PluginInstallError as exc:
        stderr.write(f"Update failed at phase {exc.phase}: {exc}\n")
        return 1
    stdout.write(f"Updated plugin {name}.\n")
    return 0


def _cmd_grant(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        installer.grant_capability(args.name, args.capability, db=db)
    except PluginInstallError as exc:
        stderr.write(f"Grant failed: {exc}\n")
        return 1
    stdout.write(f"Granted {args.capability} to {args.name}.\n")
    return 0


def _cmd_revoke(
    db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        installer.revoke_capability(args.name, args.capability, db=db)
    except PluginInstallError as exc:
        stderr.write(f"Revoke failed: {exc}\n")
        return 1
    stdout.write(
        f"Revoked {args.capability} from {args.name}. Plugin will fail "
        f"when it next attempts to use it.\n"
    )
    return 0


# ----------------------------------------------------------------------
# Read helpers (list / info)
# ----------------------------------------------------------------------


def _select_plugin_rows(db: Database) -> list[dict[str, object]]:
    """SELECT every plugin row joined to plugin_status. Stable column order."""
    with db._connect() as conn:
        rows = conn.execute(
            """
            SELECT p.name AS name,
                   p.version AS version,
                   p.manifest_hash AS manifest_hash,
                   p.enabled AS enabled,
                   p.installed_at AS installed_at,
                   p.source AS source,
                   ps.status AS status
            FROM plugins p
            LEFT JOIN plugin_status ps ON ps.plugin_name = p.name
            ORDER BY p.name
            """
        ).fetchall()
    out: list[dict[str, object]] = []
    for r in rows:
        out.append(
            {
                "name": r["name"],
                "version": r["version"],
                "status": r["status"] or "unknown",
                "enabled": bool(r["enabled"]),
                "manifest_hash": r["manifest_hash"],
                "installed_at": r["installed_at"],
                "source": r["source"],
            }
        )
    return out


def _format_plugins_table(rows: list[dict[str, object]]) -> str:
    """Render the plugins list as a fixed-width table."""
    header = f"{'name':28}  {'version':10}  {'status':10}  enabled"
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(
            f"{r['name']!s:28}  {r['version']!s:10}  "
            f"{r['status']!s:10}  {r['enabled']!s}"
        )
    return "\n".join(lines)


__all__ = ["run_plugins"]
