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

Phase 46 additions:

* ``make_synthetic_plugin(name, capabilities, raise_in=None)`` — tier-1
  helper returning a ``(PluginSpec, types.SimpleNamespace)`` tuple for
  tests that exercise post-validation runtime objects without going
  through ``validate_manifest``. The ``raise_in`` kwarg attaches a
  side-channel attribute the loader (or a synthetic adapter) can read
  to inject a per-phase exception.
* ``make_fake_entry_point(spec, module_obj)`` — tier-2 helper returning
  the ``(name, value, manifest_bytes)`` tuple shape
  ``FakeEntryPointsBundle.inject`` expects, so a test can wire a
  synthetic plugin into the discovery walk with one line.
"""

from __future__ import annotations

import shutil
import types
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from horus_os.plugins.manifest import compute_manifest_hash
from horus_os.plugins.registry import PluginRegistry
from horus_os.plugins.spec import CapabilityRequest, PluginSpec
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


@pytest.fixture(scope="session")
def installer_fixture_wheels(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build the four synthetic installer fixture archives once per session.

    Returns a dict keyed by template directory name
    (``wheel_clean``, ``wheel_with_pth``, ``wheel_downgrades_pydantic``,
    ``sdist_only``) → ``Path`` to the built artifact. Wheel templates
    produce ``.whl`` files; the sdist template produces ``.tar.gz``.

    Built lazily on first request so test sessions that do not exercise
    the installer pay zero cost.
    """
    from tests.fixtures.installer.build_fixture_wheels import build_fixture_wheels

    dest_dir = tmp_path_factory.mktemp("installer_wheels")
    return build_fixture_wheels(dest_dir)


@pytest.fixture
def installed_db(tmp_path: Path) -> Database:
    """Return a fresh Database with the v6 schema applied (no plugins yet)."""
    db_path = tmp_path / "horus.sqlite3"
    db = Database(db_path)
    db.init()
    return db


# --- Phase 46 tier-1 / tier-2 helpers --------------------------------------


def make_synthetic_plugin(
    name: str = "foo",
    capabilities: Iterable[str] = ("filesystem.read",),
    *,
    version: str = "1.0.0",
    raise_in: str | None = None,
) -> tuple[PluginSpec, types.SimpleNamespace]:
    """Return a ``(PluginSpec, ModuleNamespace)`` tuple for tier-1 tests.

    ``capabilities`` is an iterable of capability NAME strings (the
    catalog values such as ``"filesystem.read"``). The returned
    ``PluginSpec`` carries them as a tuple of ``CapabilityRequest``
    instances (matching the runtime shape that ``validate_manifest``
    produces).

    ``raise_in`` is a side-channel string (``"start"``, ``"stop"``,
    ``"load"``) attached as ``_raise_in`` on the returned namespace;
    tests that wire a synthetic adapter can inspect it to decide
    whether to raise from the named lifecycle phase.

    ``manifest_hash`` is computed via the production
    ``compute_manifest_hash`` so two synthetic specs with the same
    capability SET produce the same hash — capability-order-independent
    and duplicate-tolerant (matches Phase 41 manifest_hash semantics).
    """
    caps_tuple = tuple(
        CapabilityRequest(name=cap_name, reason="") for cap_name in capabilities
    )
    manifest_hash = compute_manifest_hash([c.name for c in caps_tuple])
    spec = PluginSpec(
        name=name,
        version=version,
        description=f"synthetic plugin {name!r} for tier-1 tests",
        author="horus-os test suite",
        license="Apache-2.0",
        horus_os_compat=">=0.5,<0.6",
        homepage=None,
        issue_tracker=None,
        tool_entries=(),
        adapter_entries=(),
        capabilities=caps_tuple,
        source="synthetic",
        source_detail="tests/plugins/conftest.py:make_synthetic_plugin",
        manifest_hash=manifest_hash,
    )
    module_obj = types.SimpleNamespace(
        _plugin_name=name,
        _plugin_version=version,
        _raise_in=raise_in,
    )
    return spec, module_obj


def make_fake_entry_point(
    spec: PluginSpec,
    module_obj: types.SimpleNamespace,
    *,
    entry_point_value: str | None = None,
) -> tuple[str, str, bytes]:
    """Return a ``(name, value, manifest_bytes)`` tuple for tier-2 injection.

    Produces the shape ``FakeEntryPointsBundle.inject`` expects so a
    test can write::

        bundle.inject([make_fake_entry_point(spec, mod)])

    ``manifest_bytes`` is a minimal v1 ``horus-plugin.toml`` payload
    that round-trips through ``validate_manifest`` and yields a spec
    with the same ``spec.name``, ``spec.version``, and ``capabilities``
    set as the input ``spec``. Other fields use neutral defaults.

    ``entry_point_value`` defaults to a synthetic dotted-path keyed off
    the spec name; tests rarely consume it directly because
    ``FakeEntryPointsBundle`` returns the manifest bytes the loader
    reads, not the entry-point target.
    """
    if entry_point_value is None:
        entry_point_value = f"horus_os_test.{spec.name}:plugin"
    caps_lines = "\n".join(
        f'  "{c.name}",' for c in spec.capabilities
    )
    if caps_lines:
        caps_block = f"capabilities = [\n{caps_lines}\n]\n"
    else:
        caps_block = "capabilities = []\n"
    manifest_text = (
        f"manifest_version = 1\n"
        f'name = "{spec.name}"\n'
        f'version = "{spec.version}"\n'
        f'description = "synthetic plugin for tier-2 tests"\n'
        f'author = "horus-os test suite"\n'
        f'license = "Apache-2.0"\n'
        f'horus_os_compat = ">=0.5,<0.6"\n'
        f"{caps_block}"
    )
    # The module_obj is intentionally unused in the manifest bytes — it
    # rides along as the entry point's load_target only if the caller
    # passes a 4-tuple to FakeEntryPointsBundle.inject. Discovery does
    # not load it, but tier-2 tests that mock the loader can attach it.
    _ = module_obj
    return spec.name, entry_point_value, manifest_text.encode("utf-8")
