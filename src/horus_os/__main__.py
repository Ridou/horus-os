"""Console entry point for horus-os."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from horus_os import __version__
from horus_os.cli import (
    run_agents,
    run_doctor,
    run_init,
    run_memory,
    run_plugins,
    run_run,
    run_schedule,
    run_serve,
    run_service,
    run_traces,
    run_usage,
)


def _add_data_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )


def _build_schedule_parser(sub: argparse._SubParsersAction) -> None:
    """Register the `schedule` parent subparser and its six leaves (D-07)."""
    schedule_p = sub.add_parser("schedule", help="Manage recurring agent schedules")
    _add_data_dir(schedule_p)
    schedule_p.set_defaults(func=run_schedule)

    schedule_sub = schedule_p.add_subparsers(dest="schedule_command", metavar="<operation>")

    create_p = schedule_sub.add_parser("create", help="Create a recurring schedule")
    create_p.add_argument("name", help="Schedule name")
    create_p.add_argument(
        "--cron",
        required=True,
        help="Cron expression, an @-alias like @daily, or sugar like 'every 30m'.",
    )
    create_p.add_argument("--profile", required=True, help="Agent profile name to fire")
    create_p.add_argument("--prompt", required=True, help="Prompt sent on each run")
    create_p.add_argument(
        "--catch-up",
        dest="catch_up",
        default="coalesce",
        choices=["coalesce", "skip", "all"],
        help="How to handle runs missed while the process was down (default: coalesce).",
    )
    _add_data_dir(create_p)
    create_p.set_defaults(func=run_schedule, schedule_command="create")

    list_p = schedule_sub.add_parser("list", help="List all schedules")
    _add_data_dir(list_p)
    list_p.set_defaults(func=run_schedule, schedule_command="list")

    edit_p = schedule_sub.add_parser("edit", help="Edit an existing schedule")
    edit_p.add_argument("name", help="Schedule name to edit")
    edit_p.add_argument("--cron", default=None)
    edit_p.add_argument("--profile", default=None)
    edit_p.add_argument("--prompt", default=None)
    edit_p.add_argument(
        "--catch-up",
        dest="catch_up",
        default=None,
        choices=["coalesce", "skip", "all"],
    )
    _add_data_dir(edit_p)
    edit_p.set_defaults(func=run_schedule, schedule_command="edit")

    delete_p = schedule_sub.add_parser("delete", help="Delete a schedule")
    delete_p.add_argument("name", help="Schedule name to delete")
    _add_data_dir(delete_p)
    delete_p.set_defaults(func=run_schedule, schedule_command="delete")

    enable_p = schedule_sub.add_parser("enable", help="Enable a schedule")
    enable_p.add_argument("name", help="Schedule name to enable")
    _add_data_dir(enable_p)
    enable_p.set_defaults(func=run_schedule, schedule_command="enable")

    disable_p = schedule_sub.add_parser("disable", help="Disable a schedule")
    disable_p.add_argument("name", help="Schedule name to disable")
    _add_data_dir(disable_p)
    disable_p.set_defaults(func=run_schedule, schedule_command="disable")


def _build_service_parser(sub: argparse._SubParsersAction) -> None:
    """Register the `service` parent subparser and its five leaves (D-09)."""
    service_p = sub.add_parser("service", help="Install/manage the always-on service")
    _add_data_dir(service_p)
    service_p.set_defaults(func=run_service)

    service_sub = service_p.add_subparsers(dest="service_command", metavar="<operation>")

    install_p = service_sub.add_parser("install", help="Register the platform-native service")
    install_p.add_argument(
        "--print",
        action="store_true",
        help="Print the generated service definition without installing (dry run).",
    )
    _add_data_dir(install_p)
    install_p.set_defaults(func=run_service, service_command="install")

    uninstall_p = service_sub.add_parser("uninstall", help="Remove the registered service")
    _add_data_dir(uninstall_p)
    uninstall_p.set_defaults(func=run_service, service_command="uninstall")

    start_p = service_sub.add_parser("start", help="Start the registered service")
    _add_data_dir(start_p)
    start_p.set_defaults(func=run_service, service_command="start")

    stop_p = service_sub.add_parser("stop", help="Stop the running service")
    _add_data_dir(stop_p)
    stop_p.set_defaults(func=run_service, service_command="stop")

    status_p = service_sub.add_parser("status", help="Report whether the service is running")
    _add_data_dir(status_p)
    status_p.set_defaults(func=run_service, service_command="status")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horus-os",
        description="An open-source, self-hosted autonomous AI command center.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"horus-os {__version__}",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    init_p = sub.add_parser("init", help="Initialize a new horus-os installation")
    init_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    init_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config file if one is present.",
    )
    init_p.add_argument(
        "--interactive",
        action="store_true",
        help="Run the setup wizard with API key onboarding and live validation.",
    )
    init_p.set_defaults(func=run_init)

    traces_p = sub.add_parser("traces", help="List recent agent traces")
    traces_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    traces_p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of traces to display (default 20).",
    )
    traces_p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a table.",
    )
    traces_p.set_defaults(func=run_traces)

    serve_p = sub.add_parser("serve", help="Start the local web dashboard and JSON API")
    serve_p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default 127.0.0.1).",
    )
    serve_p.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Bind port (default 8765).",
    )
    serve_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    serve_p.add_argument(
        "--disable-all-plugins",
        action="store_true",
        dest="disable_all_plugins",
        help=(
            "Skip plugin discovery entirely (ISOLATE-03 escape hatch). Use this when "
            "a misbehaving plugin is preventing the server from booting."
        ),
    )
    serve_p.set_defaults(func=run_serve)

    run_p = sub.add_parser("run", help="Run a single agent prompt with the configured tools")
    run_p.add_argument("prompt", help="The user prompt to send to the agent.")
    run_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    run_p.add_argument(
        "--provider",
        choices=["anthropic", "gemini"],
        default=None,
        help="Override the default LLM provider from config.",
    )
    run_p.add_argument(
        "--model",
        default=None,
        help="Override the default model from config.",
    )
    run_p.add_argument(
        "--max-iterations",
        dest="max_iterations",
        type=int,
        default=10,
        help="Maximum tool-use iterations before forcing the loop to stop (default 10).",
    )
    run_p.add_argument(
        "--no-record",
        dest="no_record",
        action="store_true",
        help="Do not persist a trace row for this run.",
    )
    run_p.add_argument(
        "--agent",
        default=None,
        help="Run against a named agent profile (loaded via `horus-os agents`).",
    )
    run_p.add_argument(
        "--no-stream",
        dest="no_stream",
        action="store_true",
        help="Disable streaming output; buffer the full response before printing.",
    )
    run_p.set_defaults(func=run_run)

    agents_p = sub.add_parser("agents", help="Manage agent profiles")
    agents_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    agents_p.set_defaults(func=run_agents)

    agents_sub = agents_p.add_subparsers(dest="agents_command", metavar="<operation>")

    list_p = agents_sub.add_parser("list", help="List all agent profiles")
    list_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    list_p.set_defaults(func=run_agents, agents_command="list")

    show_p = agents_sub.add_parser("show", help="Show one agent profile in detail")
    show_p.add_argument("name", help="Profile name")
    show_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    show_p.set_defaults(func=run_agents, agents_command="show")

    create_p = agents_sub.add_parser("create", help="Create a new agent profile")
    create_p.add_argument("--name", required=True)
    create_p.add_argument("--system-prompt", dest="system_prompt", required=True)
    create_p.add_argument("--model", default=None)
    create_p.add_argument(
        "--allowed-tools",
        dest="allowed_tools",
        default=None,
        help="Comma-separated tool names, or 'all' for unrestricted (default).",
    )
    create_p.add_argument("--memory-scope", dest="memory_scope", default=None)
    create_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    create_p.set_defaults(func=run_agents, agents_command="create")

    edit_p = agents_sub.add_parser("edit", help="Edit an existing agent profile")
    edit_p.add_argument("name", help="Profile name to edit")
    edit_p.add_argument("--system-prompt", dest="system_prompt", default=None)
    edit_p.add_argument("--model", default=None)
    edit_p.add_argument(
        "--allowed-tools",
        dest="allowed_tools",
        default=None,
        help="Comma-separated tool names, or 'all' to clear restrictions.",
    )
    edit_p.add_argument("--memory-scope", dest="memory_scope", default=None)
    edit_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    edit_p.set_defaults(func=run_agents, agents_command="edit")

    delete_p = agents_sub.add_parser("delete", help="Delete an agent profile")
    delete_p.add_argument("name", help="Profile name to delete")
    delete_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    delete_p.set_defaults(func=run_agents, agents_command="delete")

    _build_schedule_parser(sub)
    _build_service_parser(sub)

    plugins_p = sub.add_parser("plugins", help="Manage installed plugins")
    plugins_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    plugins_p.set_defaults(func=run_plugins)
    plugins_sub = plugins_p.add_subparsers(dest="plugins_command", metavar="<operation>")

    pi_install = plugins_sub.add_parser("install", help="Install a plugin from a pip spec")
    pi_install.add_argument(
        "spec",
        help="A pip-installable spec: PyPI name, ./path, or git+https URL",
    )
    pi_install.add_argument(
        "--allow-sdist",
        action="store_true",
        dest="allow_sdist",
        help=(
            "Permit sdist installs (runs setup.py BEFORE manifest validation; "
            "Pitfall 4 mode 5). Not recommended."
        ),
    )
    pi_install.add_argument(
        "--allow-system-python",
        action="store_true",
        dest="allow_system_python",
        help="Permit install outside a venv (Pitfall 4; not recommended).",
    )
    pi_install.add_argument(
        "--yes",
        "-y",
        action="store_true",
        dest="yes",
        help="Auto-grant every requested capability without prompting.",
    )
    pi_install.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_install.set_defaults(func=run_plugins, plugins_command="install")

    pi_uninstall = plugins_sub.add_parser("uninstall", help="Uninstall an installed plugin")
    pi_uninstall.add_argument("name", help="Plugin name (e.g. 'horus-example-foo')")
    pi_uninstall.add_argument(
        "--yes",
        "-y",
        action="store_true",
        dest="yes",
        help="Skip the confirmation prompt.",
    )
    pi_uninstall.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_uninstall.set_defaults(func=run_plugins, plugins_command="uninstall")

    pi_list = plugins_sub.add_parser("list", help="List installed plugins (table or --json)")
    pi_list.add_argument(
        "--json",
        action="store_true",
        dest="json",
        help="Emit machine-readable JSON instead of a table.",
    )
    pi_list.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_list.set_defaults(func=run_plugins, plugins_command="list")

    pi_info = plugins_sub.add_parser("info", help="Show detailed info for one installed plugin")
    pi_info.add_argument("name", help="Plugin name")
    pi_info.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_info.set_defaults(func=run_plugins, plugins_command="info")

    pi_enable = plugins_sub.add_parser(
        "enable", help="Enable an installed plugin (plugins.enabled = 1)"
    )
    pi_enable.add_argument("name", help="Plugin name")
    pi_enable.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_enable.set_defaults(func=run_plugins, plugins_command="enable")

    pi_disable = plugins_sub.add_parser(
        "disable", help="Disable an installed plugin (plugins.enabled = 0)"
    )
    pi_disable.add_argument("name", help="Plugin name")
    pi_disable.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_disable.set_defaults(func=run_plugins, plugins_command="disable")

    pi_update = plugins_sub.add_parser(
        "update",
        help="Update an installed plugin (runs the upgrade-diff classifier)",
    )
    pi_update.add_argument("name", help="Plugin name")
    pi_update.add_argument(
        "spec",
        help="A pip-installable spec for the new version",
    )
    pi_update.add_argument(
        "--allow-sdist",
        action="store_true",
        dest="allow_sdist",
        help="Permit sdist updates. Not recommended.",
    )
    pi_update.add_argument(
        "--allow-system-python",
        action="store_true",
        dest="allow_system_python",
        help="Permit update outside a venv.",
    )
    pi_update.add_argument(
        "--yes",
        "-y",
        action="store_true",
        dest="yes",
        help="Auto-grant expanded capabilities without prompting.",
    )
    pi_update.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_update.set_defaults(func=run_plugins, plugins_command="update")

    pi_grant = plugins_sub.add_parser("grant", help="Grant a capability to an installed plugin")
    pi_grant.add_argument("name", help="Plugin name")
    # Phase 49 (Task 1): the positional ``capability`` and the new
    # ``--all`` flag are mutually exclusive AND one is required. ``--all``
    # reads the manifest's declared capability set from the plugins table
    # (the user-approved set at install time) and grants every one in a
    # single call - the CI install-smoke-plugin matrix uses it to flip
    # the reference plugin from pending -> loaded without naming each
    # capability. ``nargs='?'`` on the positional lets argparse treat the
    # mutex required=True contract as the authoritative "exactly one"
    # rule rather than the positional's own required-by-position rule.
    grant_target = pi_grant.add_mutually_exclusive_group(required=True)
    grant_target.add_argument(
        "capability",
        nargs="?",
        default=None,
        help="Capability string (e.g. 'filesystem.read')",
    )
    grant_target.add_argument(
        "--all",
        action="store_true",
        dest="grant_all",
        help="Grant every capability declared in the plugin manifest",
    )
    pi_grant.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_grant.set_defaults(func=run_plugins, plugins_command="grant")

    pi_revoke = plugins_sub.add_parser(
        "revoke", help="Revoke a capability from an installed plugin"
    )
    pi_revoke.add_argument("name", help="Plugin name")
    pi_revoke.add_argument("capability", help="Capability string (e.g. 'filesystem.read')")
    pi_revoke.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    pi_revoke.set_defaults(func=run_plugins, plugins_command="revoke")

    usage_p = sub.add_parser("usage", help="Print usage report (cost, latency, tool reliability)")
    usage_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    usage_p.add_argument(
        "--since",
        default="7d",
        help="Window (24h, 7d, 30d, or any Nh/Nd). Default 7d.",
    )
    usage_p.add_argument(
        "--format",
        choices=["json", "csv", "table"],
        default="table",
        help="Output shape. Default table.",
    )
    usage_p.add_argument(
        "--by",
        choices=["agent", "tool", "model"],
        default="agent",
        help="Slice the report. Default agent.",
    )
    usage_p.set_defaults(func=run_usage)

    doctor_p = sub.add_parser("doctor", help="Check integration health and configuration")
    doctor_p.add_argument(
        "--supabase",
        action="store_true",
        help="Report per-table RLS status via Supabase PostgREST RPC.",
    )
    doctor_p.add_argument(
        "--service",
        action="store_true",
        help="Report whether the always-on service is registered and running.",
    )
    doctor_p.add_argument(
        "--local",
        action="store_true",
        help="Probe the configured local LLM endpoint and validate its base URL.",
    )
    doctor_p.add_argument(
        "--memory",
        action="store_true",
        help="Report on-device vector-memory model and index status (no download).",
    )
    doctor_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    doctor_p.set_defaults(func=run_doctor)

    memory_p = sub.add_parser("memory", help="Manage on-device vector memory")
    memory_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    # A bare `horus-os memory` prints the usage block listing the operations.
    memory_p.set_defaults(func=run_memory)
    memory_sub = memory_p.add_subparsers(dest="memory_command", metavar="<operation>")

    mem_download = memory_sub.add_parser(
        "download-model",
        help="Download the on-device embedding model (one-time, the only download trigger).",
    )
    mem_download.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    mem_download.set_defaults(func=run_memory, memory_command="download-model")

    mem_reindex = memory_sub.add_parser(
        "reindex",
        help="Rebuild the vector index from existing notes (reads files only).",
    )
    mem_reindex.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    mem_reindex.set_defaults(func=run_memory, memory_command="reindex")

    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(file=out)
        return 0
    return args.func(args, stdout=out, stderr=err)


if __name__ == "__main__":
    sys.exit(main())
