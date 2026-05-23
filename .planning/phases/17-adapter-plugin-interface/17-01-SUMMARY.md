# Phase 17 Plan 01 Summary

**Status:** Shipped
**Commit:** feat(17): adapter contract, entry-point discovery, FastAPI wiring
**Date:** 2026-05-23

## What shipped

The adapter plugin contract and the discovery pipeline that makes
third-party packages first-class citizens in horus-os. ADAPT-01 and
ADAPT-03 (contract definition, third-party registration without
forking) are both satisfied. The reference adapter (Plan 02) is a
consumer of this surface; nothing in Plan 01 ties it to any
particular adapter implementation.

### New module: `horus_os.adapters`

| Symbol | Purpose |
|--------|---------|
| `Adapter` | Runtime-checkable Protocol with `name: str` and `bind(app, context) -> None`. Optional `describe()` method documented in the docstring |
| `AdapterContext` | Frozen dataclass carrying the resolved `Config` and `data_dir: Path` |
| `discover_adapters()` | Walks `entry_points(group="horus_os.adapters")`, sorts by name, instantiates each (class, factory callable, or already-built instance), returns the list. Per-entry failures are isolated |
| `ADAPTER_ENTRY_POINT_GROUP` | The literal `"horus_os.adapters"` exported for downstream pyproject snippets |

The module-level `entry_points` binding inside `adapters/base.py` is
the test seam: `monkeypatch.setattr(adapters_base, "entry_points",
fake)` replaces it without touching the importlib internals.

### FastAPI wiring

`create_app(data_dir)` ends with:

1. `discover_adapters()` once
2. Resolves the `data_dir` consistently with the `_config()` closure
3. Builds an `AdapterContext` per app instance
4. Calls `bind(app, context)` on each discovered adapter
5. Catches and skips bind failures so a broken adapter cannot brick
   the core dashboard

### Top-level re-exports

`from horus_os import Adapter, AdapterContext, discover_adapters`
works. The three names are sorted into the existing `__all__`.

### Test surface

| File | Tests | Covers |
|------|-------|--------|
| `tests/test_adapters_discovery.py` | 9 | Protocol shape, frozen context, factory vs class instantiation, deterministic name ordering, load and factory failure isolation |
| `tests/test_adapters_integration.py` | 4 | Empty entry-point list keeps core routes alive, stubbed third-party adapter mounts a route via `create_app`, sibling bind failure does not affect well-behaved adapters, context `data_dir` matches the call argument |

13 net new tests. Full suite: 288 passed in 1.97s.

## Files touched

- `src/horus_os/adapters/__init__.py` (new): re-exports the contract
  symbols
- `src/horus_os/adapters/base.py` (new): Adapter, AdapterContext,
  discover_adapters, ADAPTER_ENTRY_POINT_GROUP
- `src/horus_os/server/api.py`: imports `AdapterContext` and
  `discover_adapters`; binds discovered adapters before
  `return app`
- `src/horus_os/__init__.py`: top-level re-exports
- `tests/test_adapters_discovery.py` (new): 9 cases
- `tests/test_adapters_integration.py` (new): 4 cases

## Lint status

`ruff check .` clean. `ruff format --check .` clean (one auto-format
pass on the three modified files).

## Notable / deferred

- `discover_adapters` distinguishes a factory callable from an
  already-constructed instance by checking `hasattr(target, "bind")`.
  A function (no `bind` attribute) is called; an instance (has
  `bind`) is used as-is. This handles the three common patterns
  (class, lambda factory, pre-built singleton) without configuration
- A failed adapter `bind()` is silently caught. A future revision
  could route the failure to a structured warning log; for v0.2 the
  hard requirement is "do not break the core app" and silence is
  the simplest mitigation
- Adapter ordering is sorted by entry-point name for determinism.
  Two adapters declaring the same route would conflict in FastAPI's
  registration; this is detectable at startup and surfaces as a
  clear error to the operator
- The Protocol is `runtime_checkable` so `isinstance(adapter, Adapter)`
  works. The downside is that the Protocol only checks attribute
  presence, not call signatures. This matches Python's Protocol
  defaults and is good enough for the discovery path
- No diagnostics surface yet (no `/api/adapters` GET route). If
  there is demand we can expose discovered adapter metadata under a
  future inspection route; for v0.2 the dashboard does not need it
