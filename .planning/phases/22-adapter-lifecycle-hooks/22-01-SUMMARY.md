---
phase: 22-adapter-lifecycle-hooks
plan: "01"
subsystem: adapters
tags: [adapter, lifecycle, fastapi, lifespan, status, gate-for-v0.3]

requires:
  - phase: "17-01"
provides:
  - "LifecycleAdapter Protocol with optional async start/stop hooks"
  - "AdapterRegistry tracking per-adapter status, activity, errors"
  - "AdapterContext.registry field with default factory (backwards compatible)"
  - "FastAPI lifespan integration calling start at app boot, stop at shutdown"
  - "GET /api/adapters route returning per-adapter status snapshot"
  - "WebhookAdapter touches the registry on successful requests"

requirements-completed:
  - ART-01  # Adapter Protocol gains optional start(ctx) and stop() hooks; v0.2 adapters work unchanged
  - ART-02  # FastAPI lifespan invokes start on each discovered adapter at startup and stop at shutdown
  - ART-03  # GET /api/adapters returns name, status, last_activity_at, error_count per adapter

duration: ~40m
completed: 2026-05-24
total-tests: 344
delta-tests: +25
v0.3-progress: Phase 22 of 31 complete (gate for Phases 23-26 cleared)
---

# Phase 22 Plan 01 Summary: Adapter lifecycle hooks

## What shipped

The gate for the v0.3 adapter implementations (Discord, Slack, Email,
Calendar). Adapters can now opt into async `start`/`stop` hooks tied
to the FastAPI app lifespan, and their status is queryable via
`GET /api/adapters`.

### New module surface in `horus_os.adapters.base`

| Symbol | Purpose |
|--------|---------|
| `LifecycleAdapter` | Sibling runtime-checkable Protocol with `name`, async `start(context)`, async `stop()`. Existing `Adapter` Protocol is unchanged |
| `AdapterEntry` | Dataclass: `name`, `status`, `last_activity_at`, `error_count`, `error_message` |
| `AdapterRegistry` | Tracks per-app adapter state. `register`, `mark_running`, `mark_stopped`, `mark_error`, `touch`, `get`, `entries` |
| `ADAPTER_STATUS_RUNNING`, `ADAPTER_STATUS_STOPPED`, `ADAPTER_STATUS_ERROR` | String constants for the three status values |

`AdapterContext` gained a `registry: AdapterRegistry` field with a
`field(default_factory=AdapterRegistry)`. Existing direct
constructions like `AdapterContext(config=..., data_dir=...)` keep
working because the field has a default.

All three new public types re-exported from `horus_os.adapters` and
the top-level `horus_os` package, with `__all__` updated.

### FastAPI lifespan integration

`create_app` was restructured so discovery happens before the
`FastAPI(...)` instantiation:

1. `discover_adapters()` walks the entry point group
2. Registry built; one entry per discovered adapter (status `stopped`)
3. AdapterContext constructed carrying config, data_dir, registry
4. Lifespan factory closure captures the adapter list + context
5. `FastAPI(..., lifespan=_lifespan)` built
6. `app.state.adapter_registry = registry`
7. Core routes registered (including `GET /api/adapters`)
8. Adapter `bind` loop: success flips entry to `running`; exception
   flips to `error` with the message captured

The lifespan iterates adapters and calls `start(context)` on any
with a `start` attribute at boot, then iterates in reverse and
calls `stop()` at shutdown. Both phases wrap each call in
try/except and write failures into `mark_error`; siblings always
get their turn, and shutdown never raises.

Runtime dispatch uses `hasattr(adapter, "start")` /
`hasattr(adapter, "stop")` so adapters with only one of the two
hooks still work, per the documented decision in
`22-CONTEXT.md` (section 1).

### GET /api/adapters

```
GET /api/adapters -> {
  "adapters": [
    {
      "name": "webhook",
      "status": "running",
      "last_activity_at": "2026-05-24T...+00:00" | null,
      "error_count": 0,
      "error_message": null
    },
    ...
  ]
}
```

Sorted by name. Empty list when nothing discovered.

### WebhookAdapter activity touch

The reference adapter now calls `context.registry.touch(self.name)`
after a successful request handle. One-line change. This is the
demonstration pattern for the v0.3 adapters and proves the
end-to-end registry path under TestClient.

## Files touched

- `src/horus_os/adapters/base.py`: LifecycleAdapter Protocol,
  AdapterEntry, AdapterRegistry, status constants, AdapterContext
  registry field
- `src/horus_os/adapters/__init__.py`: re-exports of the three new
  public types plus the status constants
- `src/horus_os/__init__.py`: top-level re-exports
- `src/horus_os/adapters/webhook.py`: one-line `registry.touch` call
  after a successful trace record
- `src/horus_os/server/api.py`: discovery moved above FastAPI
  instantiation, lifespan factory, `/api/adapters` route, bind loop
  marks registry status
- `tests/test_adapters_lifecycle.py` (new, 19 tests)
- `tests/test_server_adapters.py` (new, 6 tests)

## Test surface

| File | Tests | Covers |
|------|-------|--------|
| `tests/test_adapters_lifecycle.py` | 19 | AdapterRegistry transitions, register idempotency, mutator no-ops, iso8601 touch, sorted entries; LifecycleAdapter runtime_checkable; AdapterContext default and explicit registry; lifespan dispatch on start, stop, start-raises, stop-raises, hasattr-only paths; WebhookAdapter shows `running` after create_app |
| `tests/test_server_adapters.py` | 6 | `GET /api/adapters` shape (five fields), empty case, sorted by name, real webhook entry as `running`, bind-failure isolation, `last_activity_at` bump after a signed webhook POST |

25 net new tests. Full suite: 344 passed in 2.67s (319 baseline
+ 25 new). All v0.2 adapter, server, and integration tests pass
byte-identical.

## Lint status

`ruff check .` clean. `ruff format --check .` clean. The auto-fix
pass replaced `datetime.now(timezone.utc)` with `datetime.now(UTC)`
(UP017) and sorted imports in the new test files.

## Notable / deferred

- The `Request` import inside `create_app` had to be removed because
  PEP 563 (`from __future__ import annotations`) defers the
  annotation as a string and FastAPI's introspection looks the name
  up in the module globals. The route handler reads `_registry`
  directly from the enclosing closure instead. Cleaner and avoids
  the eager FastAPI import problem
- The lifespan iterates adapters in discovery order on startup and
  in reverse on shutdown. Symmetric with `contextlib.ExitStack`
  semantics; matches operator expectations
- `mark_error` always bumps `error_count` and stores the most recent
  message. Older failures are not preserved; the registry is a
  liveness signal, not an audit log. Phase 27 dashboard view can
  layer a structured log if there is demand
- WebhookAdapter `describe()` was not extended. The describe shape
  is unchanged from v0.2; the status surface now lives at
  `/api/adapters` which is the right place for per-instance state
- `last_activity_at` is only bumped by the adapter itself today.
  Middleware-based auto-touching of every adapter route was
  considered and dropped: adapters know better than middleware
  whether a request was meaningful (signature-valid, agent ran,
  trace recorded). The one-line `context.registry.touch(self.name)`
  is the documented pattern for v0.3 authors
- Phases 23-26 (Discord, Slack, Email, Calendar) can now ship in
  parallel. The Adapter Protocol is the stable contract; the
  registry and lifespan are stable contracts; the status route is
  the stable contract. Future adapters extend none of the above
