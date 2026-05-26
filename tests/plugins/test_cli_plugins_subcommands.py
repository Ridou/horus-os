"""argparse routing for ``horus-os plugins X``.

Each of the nine sub-subparsers is dispatched to ``run_plugins`` with
the right ``plugins_command`` value. Required positional args (name,
capability) and optional flags (--yes, --allow-sdist, etc.) round-trip
through the Namespace. Unknown subcommands exit with code 2 (argparse
default).
"""

from __future__ import annotations

import pytest

from horus_os.__main__ import build_parser
from horus_os.cli.plugins_cmd import run_plugins


def test_install_parses() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "install", "horus-example", "--yes"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "install"
    assert ns.spec == "horus-example"
    assert ns.yes is True
    assert ns.allow_sdist is False
    assert ns.allow_system_python is False


def test_install_accepts_all_flags() -> None:
    p = build_parser()
    ns = p.parse_args(
        [
            "plugins",
            "install",
            "horus-example",
            "--allow-sdist",
            "--allow-system-python",
            "-y",
        ]
    )
    assert ns.allow_sdist is True
    assert ns.allow_system_python is True
    assert ns.yes is True


def test_uninstall_parses() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "uninstall", "horus-example"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "uninstall"
    assert ns.name == "horus-example"


def test_list_parses_with_json_flag() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "list", "--json"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "list"
    assert ns.json is True


def test_list_parses_without_json_flag() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "list"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "list"
    assert ns.json is False


def test_info_parses() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "info", "horus-example"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "info"
    assert ns.name == "horus-example"


def test_enable_parses() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "enable", "horus-example"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "enable"
    assert ns.name == "horus-example"


def test_disable_parses() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "disable", "horus-example"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "disable"
    assert ns.name == "horus-example"


def test_update_parses_with_two_positionals() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "update", "horus-example", "horus-example==0.2"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "update"
    assert ns.name == "horus-example"
    assert ns.spec == "horus-example==0.2"


def test_grant_parses() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "grant", "horus-example", "filesystem.read"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "grant"
    assert ns.name == "horus-example"
    assert ns.capability == "filesystem.read"


def test_revoke_parses() -> None:
    p = build_parser()
    ns = p.parse_args(["plugins", "revoke", "horus-example", "net.outbound"])
    assert ns.func is run_plugins
    assert ns.plugins_command == "revoke"
    assert ns.name == "horus-example"
    assert ns.capability == "net.outbound"


def test_unknown_subcommand_exits_2() -> None:
    p = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        p.parse_args(["plugins", "frobnicate", "foo"])
    assert excinfo.value.code == 2


def test_install_missing_spec_exits_2() -> None:
    """argparse requires the positional spec arg."""
    p = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        p.parse_args(["plugins", "install"])
    assert excinfo.value.code == 2


def test_grant_missing_capability_exits_2() -> None:
    """grant takes TWO positionals; one is not enough."""
    p = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        p.parse_args(["plugins", "grant", "foo"])
    assert excinfo.value.code == 2
