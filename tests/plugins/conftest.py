"""Shared fixtures for the Phase 42 tests/plugins/test_*.py files.

Four fixtures isolate each test from the host:

* ``fake_plugin_entry_points`` — monkeypatches
  ``horus_os.plugins.discovery.entry_points`` to return a synthetic
  ``EntryPoints``-shaped object, AND monkeypatches
  ``horus_os.plugins.discovery._read_entry_point_manifest_bytes`` to
  resolve a name-keyed manifest bytes lookup. Tests inject the
  entries they want and the helper hands them back. Mirrors the
  ``src/horus_os/adapters/base.py:22`` rebind pattern.
* ``tmp_plugin_dir`` — creates an isolated ``tmp_path/plugins`` and
  points ``HORUS_OS_PLUGIN_DIR`` at it via ``monkeypatch.setenv`` so
  ``discover_plugins()``'s filesystem walk operates against
  ``tmp_path``, never the real ``~/.horus-os/plugins/``.
* ``install_broken_fixture`` — copies one of the
  ``tests/fixtures/broken_plugins/<name>/`` subdirectories into the
  ``tmp_plugin_dir`` so the filesystem walk picks it up.
* ``clean_plugin_registry`` — yields ``(db, registry)`` with the
  Phase 41 schema applied to a tmp_path-scoped SQLite file. The
  registry persists through the schema so tests that round-trip
  status writes against the plugins + plugin_status tables stay
  byte-isolated.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from horus_os.plugins.registry import PluginRegistry
from horus_os.storage import Database

FIXTURES_BROKEN_PLUGINS = Path(__file__).resolve().parents[1] / "fixtures" / "broken_plugins"


@dataclass
class EntryPointLike:
    """Test stand-in for ``importlib.metadata.EntryPoint``.

    Exposes the minimum surface the discovery module reads: ``.name``,
    ``.value``, ``.dist``. ``.load()`` is included for completeness
    even though Phase 42's discovery only reads the manifest bytes
    (loading happens in ``PluginLoader``).
    """

    name: str
    value: str
    dist: Any = None
    _load_target: Any = None

    def load(self) -> Any:
        return self._load_target


@dataclass
class EntryPointsLike:
    """Test stand-in for ``importlib.metadata.EntryPoints``.

    Iterable + ``.select(group=...)`` selectable. The discovery walk
    uses ``entry_points(group=...)`` directly so ``.select`` is the
    only path that fires; the iterable is provided so a test that
    accidentally falls back to iteration still gets the right entries.
    """

    entries: list[EntryPointLike] = field(default_factory=list)

    def __iter__(self) -> Iterator[EntryPointLike]:
        return iter(self.entries)

    def select(self, *, group: str) -> EntryPointsLike:
        return self


class FakeEntryPointsBundle:
    """Composite returned by the ``fake_plugin_entry_points`` fixture.

    ``inject(entries)`` is the only method tests call; each entry is
    a ``(name, value, manifest_bytes)`` tuple OR
    ``(name, value, manifest_bytes, load_target)``. The bundle wires
    both the entry_points walk and the per-entry manifest bytes
    lookup so the test's plugin shows up in
    ``discover_plugins()`` without touching the real importlib.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self._eps: dict[str, EntryPointLike] = {}
        self._manifests: dict[str, bytes] = {}

        # Wire the rebinds. These persist for the duration of the test.
        def _entry_points(*, group: str) -> list[EntryPointLike]:
            return list(self._eps.values())

        def _read_manifest(ep: object) -> bytes:
            ep_name = getattr(ep, "name", None)
            if ep_name in self._manifests:
                return self._manifests[ep_name]
            raise FileNotFoundError(
                f"no manifest bytes wired for entry point {ep_name!r}"
            )

        monkeypatch.setattr(
            "horus_os.plugins.discovery.entry_points", _entry_points
        )
        monkeypatch.setattr(
            "horus_os.plugins.discovery._read_entry_point_manifest_bytes",
            _read_manifest,
        )

    def inject(
        self,
        entries: Iterable[tuple[str, str, bytes] | tuple[str, str, bytes, Any]],
    ) -> None:
        """Register entries for the test.

        Each entry is ``(name, value, manifest_bytes[, load_target])``:
        ``name`` is the entry-point name (the dict key the registry
        uses), ``value`` is the dotted-path the entry_point's ``.value``
        attribute carries, ``manifest_bytes`` is the horus-plugin.toml
        payload, and the optional ``load_target`` is what ``.load()``
        would return on a real entry point (unused by discovery; useful
        for parity tests).
        """
        for entry in entries:
            if len(entry) == 4:
                name, value, manifest_bytes, load_target = entry
            else:
                name, value, manifest_bytes = entry
                load_target = None
            self._eps[name] = EntryPointLike(
                name=name,
                value=value,
                dist=_DistLike(name=name),
                _load_target=load_target,
            )
            self._manifests[name] = manifest_bytes


@dataclass
class _DistLike:
    """Minimal Distribution stand-in carrying just the .name attribute."""

    name: str


@pytest.fixture
def fake_plugin_entry_points(monkeypatch: pytest.MonkeyPatch) -> FakeEntryPointsBundle:
    """Yield a FakeEntryPointsBundle wired into the discovery module."""
    return FakeEntryPointsBundle(monkeypatch)


@pytest.fixture
def tmp_plugin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create tmp_path/plugins, set HORUS_OS_PLUGIN_DIR, return the path."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    monkeypatch.setenv("HORUS_OS_PLUGIN_DIR", str(plugins_dir))
    return plugins_dir


@pytest.fixture
def install_broken_fixture(tmp_plugin_dir: Path) -> Callable[[str], Path]:
    """Return a factory: ``install_broken_fixture("healthy")`` copies the fixture.

    Copies ``tests/fixtures/broken_plugins/<name>/`` to
    ``tmp_plugin_dir/<name>/`` so the filesystem walk picks it up.
    Returns the destination path.
    """
    def _install(name: str) -> Path:
        src = FIXTURES_BROKEN_PLUGINS / name
        if not src.exists():
            raise FileNotFoundError(f"broken-plugin fixture {name!r} not at {src}")
        dst = tmp_plugin_dir / name
        shutil.copytree(src, dst)
        return dst

    return _install


@pytest.fixture
def clean_plugin_registry(tmp_path: Path) -> tuple[Database, PluginRegistry]:
    """Yield (db, registry) with the Phase 41 schema applied to tmp_path/horus.sqlite3."""
    db_path = tmp_path / "horus.sqlite3"
    db = Database(db_path)
    db.init()
    registry = PluginRegistry(db=db)
    return db, registry
