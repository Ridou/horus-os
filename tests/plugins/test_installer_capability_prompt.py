"""INSTALL-05: capability grant prompt + half-grant refusal.

Three branches verified:
  * Refuse (input 'n') → ``PluginInstallError(reason='user_refused_grant')``
    AND no Phase D pip install call AND no plugin_capabilities row inserted.
  * Grant all (input 'y') → PermissionService.grant called for every
    requested capability; one audit row per capability in
    plugin_capability_grants_log.
  * Partial grant ('a' for first cap, 'n' for second → mapped via the
    half-grant detection in prompt_for_grants) →
    ``PluginInstallError(reason='partial_grant_refused')`` AND no
    Phase D AND no grant rows inserted.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from horus_os.plugins import installer
from horus_os.plugins.installer import (
    PluginInstallError,
    install_plugin,
    prompt_for_grants,
)
from horus_os.plugins.spec import CapabilityRequest, PluginSpec
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def _make_spec(*cap_names: str) -> PluginSpec:
    return PluginSpec(
        name="test-plugin",
        version="0.1.0",
        description="",
        author="a",
        license="MIT",
        horus_os_compat=">=0.5,<0.6",
        homepage=None,
        issue_tracker=None,
        tool_entries=(),
        adapter_entries=(),
        capabilities=tuple(CapabilityRequest(name=n) for n in cap_names),
        source="entry_point",
        source_detail="",
        manifest_hash="hash",
    )


def test_prompt_refuse_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _make_spec("filesystem.read", "net.outbound")
    stdin = io.StringIO("n\n")
    stdout = io.StringIO()
    with pytest.raises(PluginInstallError) as excinfo:
        prompt_for_grants(spec, stdin=stdin, stdout=stdout, assume_yes=False)
    assert excinfo.value.phase == "grant"
    assert excinfo.value.reason == "user_refused_grant"


def test_prompt_grant_all_returns_full_set() -> None:
    spec = _make_spec("filesystem.read", "net.outbound")
    stdin = io.StringIO("y\n")
    stdout = io.StringIO()
    granted = prompt_for_grants(spec, stdin=stdin, stdout=stdout, assume_yes=False)
    assert granted == {"filesystem.read", "net.outbound"}


def test_prompt_partial_grant_raises() -> None:
    """User types 'a' to grant only the first capability → partial_grant_refused."""
    spec = _make_spec("filesystem.read", "net.outbound")
    stdin = io.StringIO("a\n")
    stdout = io.StringIO()
    with pytest.raises(PluginInstallError) as excinfo:
        prompt_for_grants(spec, stdin=stdin, stdout=stdout, assume_yes=False)
    assert excinfo.value.reason == "partial_grant_refused"


def test_prompt_assume_yes_skips_input() -> None:
    """assume_yes=True returns full set without consulting stdin."""
    spec = _make_spec("filesystem.read", "net.outbound")
    # Empty stdin — if the prompt tried to read, it'd hit EOF and
    # treat as refuse. assume_yes=True must skip that path.
    stdin = io.StringIO("")
    stdout = io.StringIO()
    granted = prompt_for_grants(spec, stdin=stdin, stdout=stdout, assume_yes=True)
    assert granted == {"filesystem.read", "net.outbound"}


def test_prompt_renders_capability_descriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rendered prompt includes the DESCRIPTIONS text for each capability."""
    spec = _make_spec("filesystem.read", "net.outbound")
    stdin = io.StringIO("y\n")
    stdout = io.StringIO()
    prompt_for_grants(spec, stdin=stdin, stdout=stdout, assume_yes=False)
    output = stdout.getvalue()
    # Each capability's description is mentioned.
    assert "filesystem.read" in output
    assert "Read files from disk paths" in output
    assert "net.outbound" in output
    assert "Open outbound network connections" in output
    # The prompt scheme is present.
    assert "Grant all (y) / per-capability" in output


def _fake_pip_factory(
    wheel_path: Path,
) -> callable[..., subprocess.CompletedProcess[str]]:
    """Build a fake run_pip that copies wheel_path on download and
    pretends ``pip freeze`` shows pydantic 2.7.0 + the new package
    after install.
    """
    state = {"installed": False}

    def fake(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "download":
            for i, a in enumerate(args):
                if a == "--dest" and i + 1 < len(args):
                    dest = Path(args[i + 1])
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copy(wheel_path, dest / wheel_path.name)
                    break
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        if args and args[0] == "freeze":
            if state["installed"]:
                stdout = "pydantic==2.7.0\npackaging==24.0\nhorus-example-clean==0.1.0\n"
            else:
                stdout = "pydantic==2.7.0\npackaging==24.0\n"
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout=stdout, stderr="")
        if args and args[0] == "install":
            state["installed"] = True
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    return fake


def test_refuse_at_prompt_blocks_phase_d(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """End-to-end: refusing at the grant prompt prevents pip install."""
    db = _make_db(tmp_path)
    clean_wheel = installer_fixture_wheels["wheel_clean"]
    captured: list[tuple[str, ...]] = []

    base_fake = _fake_pip_factory(clean_wheel)

    def tracking(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        return base_fake(*args, check=check)

    monkeypatch.setattr(installer, "run_pip", tracking)

    stdin = io.StringIO("n\n")
    stdout = io.StringIO()
    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-clean",
            db=db,
            allow_system_python=True,
            assume_yes=False,
            stdin=stdin,
            stdout=stdout,
        )
    assert excinfo.value.reason == "user_refused_grant"

    # Phase D never ran.
    install_calls = [c for c in captured if c and c[0] == "install"]
    assert install_calls == []

    # No plugin_capabilities rows inserted.
    with db._connect() as conn:
        rows = conn.execute("SELECT * FROM plugin_capabilities").fetchall()
    assert rows == []


def test_grant_all_inserts_audit_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """Granting 'y' inserts one plugin_capabilities row + one audit log row per cap."""
    db = _make_db(tmp_path)
    clean_wheel = installer_fixture_wheels["wheel_clean"]

    monkeypatch.setattr(installer, "run_pip", _fake_pip_factory(clean_wheel))
    # Patch discover_plugins so Phase E sees the plugin "installed".
    from horus_os.plugins.spec import PluginSpec as _Spec

    def fake_discover(*a, **kw):
        spec = _Spec(
            name="horus-example-clean",
            version="0.1.0",
            description="",
            author="a",
            license="Apache-2.0",
            horus_os_compat=">=0.5,<0.6",
            homepage=None,
            issue_tracker=None,
            tool_entries=(),
            adapter_entries=(),
            capabilities=(),
            source="entry_point",
            source_detail="",
            manifest_hash="h",
        )
        return [spec], []

    monkeypatch.setattr(installer, "discover_plugins", fake_discover)

    stdin = io.StringIO("y\n")
    stdout = io.StringIO()
    name = install_plugin(
        "horus-example-clean",
        db=db,
        allow_system_python=True,
        assume_yes=False,
        stdin=stdin,
        stdout=stdout,
    )
    assert name == "horus-example-clean"

    with db._connect() as conn:
        caps = conn.execute(
            "SELECT capability, state FROM plugin_capabilities WHERE plugin_name = ?",
            (name,),
        ).fetchall()
        log = conn.execute(
            "SELECT capability, action, actor FROM plugin_capability_grants_log WHERE plugin_name = ?",
            (name,),
        ).fetchall()
    cap_names = {row["capability"] for row in caps}
    assert cap_names == {
        "filesystem.read",
        "filesystem.write",
        "net.outbound",
        "secrets.read",
    }
    for row in caps:
        assert row["state"] == "granted"
    # One audit row per granted capability, all with actor='cli'.
    log_actions = {(row["capability"], row["action"], row["actor"]) for row in log}
    for cap in cap_names:
        assert (cap, "granted", "cli") in log_actions
