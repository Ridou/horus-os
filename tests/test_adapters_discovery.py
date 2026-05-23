"""Tests for the adapter Protocol shape and entry-point discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from horus_os.adapters import (
    ADAPTER_ENTRY_POINT_GROUP,
    Adapter,
    AdapterContext,
    discover_adapters,
)
from horus_os.adapters import base as adapters_base
from horus_os.config import Config


class _FakeEntryPoint:
    """Minimal stand-in for importlib.metadata.EntryPoint used in tests."""

    def __init__(self, name: str, target: Any) -> None:
        self.name = name
        self._target = target

    def load(self) -> Any:
        if isinstance(self._target, BaseException):
            raise self._target
        return self._target


class _FakeAdapter:
    name = "fake"

    def __init__(self) -> None:
        self.bound: list[Any] = []

    def bind(self, app: Any, context: AdapterContext) -> None:
        self.bound.append((app, context))


class _OtherAdapter:
    name = "other"

    def bind(self, app: Any, context: AdapterContext) -> None:
        pass


def _stub_entry_points(monkeypatch: pytest.MonkeyPatch, eps: list[_FakeEntryPoint]) -> None:
    def fake(group: str | None = None) -> list[_FakeEntryPoint]:
        if group != ADAPTER_ENTRY_POINT_GROUP:
            return []
        return eps

    monkeypatch.setattr(adapters_base, "entry_points", fake)


def test_entry_point_group_constant() -> None:
    assert ADAPTER_ENTRY_POINT_GROUP == "horus_os.adapters"


def test_adapter_is_runtime_checkable() -> None:
    adapter = _FakeAdapter()
    assert isinstance(adapter, Adapter)


def test_adapter_context_is_frozen(tmp_path: Path) -> None:
    from dataclasses import FrozenInstanceError

    cfg = Config.with_defaults(tmp_path)
    ctx = AdapterContext(config=cfg, data_dir=tmp_path)
    with pytest.raises(FrozenInstanceError):
        ctx.data_dir = tmp_path  # type: ignore[misc]


def test_discover_adapters_returns_empty_list_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_entry_points(monkeypatch, [])
    assert discover_adapters() == []


def test_discover_adapters_instantiates_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("fake", _FakeAdapter)])
    adapters = discover_adapters()
    assert len(adapters) == 1
    assert isinstance(adapters[0], _FakeAdapter)


def test_discover_adapters_accepts_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _FakeAdapter()

    def _factory() -> _FakeAdapter:
        return instance

    _stub_entry_points(monkeypatch, [_FakeEntryPoint("fake", _factory)])
    adapters = discover_adapters()
    assert len(adapters) == 1
    assert adapters[0] is instance


def test_discover_adapters_sorts_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("zebra", _FakeAdapter),
            _FakeEntryPoint("alpha", _OtherAdapter),
            _FakeEntryPoint("mango", _FakeAdapter),
        ],
    )
    adapters = discover_adapters()
    assert [a.name for a in adapters] == ["other", "fake", "fake"]


def test_discover_adapters_skips_failing_load(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("broken", RuntimeError("boom")),
            _FakeEntryPoint("good", _FakeAdapter),
        ],
    )
    adapters = discover_adapters()
    assert len(adapters) == 1
    assert isinstance(adapters[0], _FakeAdapter)


def test_discover_adapters_skips_failing_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Boom:
        def __init__(self) -> None:
            raise ValueError("nope")

    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("broken", _Boom),
            _FakeEntryPoint("good", _FakeAdapter),
        ],
    )
    adapters = discover_adapters()
    assert len(adapters) == 1
    assert isinstance(adapters[0], _FakeAdapter)
