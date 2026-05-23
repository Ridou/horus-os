# Phase 22 Context: Adapter lifecycle hooks

**Date:** 2026-05-24
**Phase:** 22
**Status:** Context captured

## Domain

Phase 22 opens the gate for the four v0.3 adapter implementations
(Discord, Slack, Email, Calendar). v0.2 shipped a bind-only Adapter
Protocol (Phase 17) that is sufficient for short-lived request/response
adapters like the reference webhook receiver. Long-running adapters
need two more affordances: a place to launch background tasks at
startup, and a place to drain them at shutdown. They also need an
introspection surface so the future Phase 27 dashboard view can show
what is running.

Three pieces ship together:

1. Optional `start(context)` and `stop()` lifecycle hooks adapters
   may implement. The v0.2 `WebhookAdapter` does not implement them
   and continues to work byte-identically.
2. FastAPI app lifespan integration. `create_app` returns an app
   whose lifespan context manager calls `start` on each discovered
   adapter at startup and `stop` at shutdown.
3. A `GET /api/adapters` route returning each discovered adapter's
   name, status (running, stopped, error), last_activity_at, error
   count, and last error message.

## Canonical refs

- `.planning/ROADMAP.md` Phase 22 success criteria
- `.planning/REQUIREMENTS.md` ART-01, ART-02, ART-03
- `src/horus_os/adapters/base.py` Protocol to extend
- `src/horus_os/adapters/webhook.py` reference adapter, no lifecycle methods
- `src/horus_os/server/api.py` FastAPI factory, currently does bind-only
- Phase 17 summary for the discovery and bind story this phase extends

## Decisions

### 1. Lifecycle is a sibling Protocol, not new required methods

Python's `runtime_checkable` Protocols cannot encode optional
methods. The clean choice is a sibling Protocol:

```
@runtime_checkable
class LifecycleAdapter(Protocol):
    name: str
    def start(self, context: AdapterContext) -> Awaitable[None]: ...
    def stop(self) -> Awaitable[None]: ...
```

The lifespan code uses `hasattr(adapter, "start")` and
`hasattr(adapter, "stop")` at the call site rather than
`isinstance` on the sibling Protocol. `hasattr` is the most permissive
form, accepts a duck-typed adapter with only one of the two hooks,
and keeps the `Adapter` Protocol unchanged so v0.2 callers remain
byte-identical. The sibling Protocol is still exported for type-hinting
purposes; runtime dispatch is `hasattr`-based.

### 2. Lifecycle methods are async; bind stays sync

`start` and `stop` return awaitables (declared as
`Awaitable[None]` in the docstring; in practice adapters will write
`async def start(self, context)`). Sync bind keeps mounting routes
fast and avoids forcing FastAPI to await before adding routes.

`start` is expected to do its own `asyncio.create_task` for any
background loop. The lifespan handler awaits `start` only long enough
for the adapter to launch its task; it does not block on the task
itself. This is the same pattern Starlette uses internally.

### 3. Status lives in an in-app AdapterRegistry

A new lightweight `AdapterRegistry` class stores per-adapter state:
`name`, `status`, `last_activity_at`, `error_count`, `error_message`.
The registry is attached to `app.state.adapter_registry` so the
`/api/adapters` route can read it, and so adapter code can update
`last_activity_at` via the context (see decision 4).

Why a class and not a dict: the registry exposes named methods
(`mark_running`, `mark_stopped`, `mark_error`, `touch_activity`) that
encapsulate the state transitions and the error-count increment. A
dict is fine but a registry pays for itself the first time a Discord
adapter needs to bump activity from a callback.

### 4. last_activity_at is updated by the adapter

The adapter owns the signal. The registry exposes a
`touch(name)` method, and the `AdapterContext` gains a
`registry: AdapterRegistry` field so adapters can call
`context.registry.touch(self.name)` from their handlers. The webhook
adapter is updated to bump activity at the end of a successful
request; this is a one-line change that also demonstrates the pattern
for the v0.3 adapters.

`AdapterContext` stays a frozen dataclass; the new `registry` field
is a frozen reference to a mutable object, which is the standard
pattern.

### 5. Error isolation: one failing adapter does not break the app

`start` failures: the adapter's registry entry transitions to
`error` with the exception captured. Other adapters continue to
start. `stop` failures: the adapter's registry entry stays at its
current status; the exception is captured into `error_message` but
does not raise out of the lifespan. The app shuts down cleanly even
if every adapter's `stop` raises.

### 6. WebhookAdapter is running but has no lifecycle hooks

The reference adapter does not implement `start` or `stop` because
it has nothing to start (FastAPI handles the HTTP loop). Its
registry entry is created at bind time with status `running`. This
is the explicit ART-01 requirement.

Why `running` and not a separate "bound" status: from an external
operator's perspective, "the route is mounted and ready to receive"
is what running means. Distinguishing "bound but no task" from
"task running" is internal detail. Three statuses keep the API
surface simple.

### 7. FastAPI lifespan integration shape

`create_app` builds the `app` with `lifespan=_make_lifespan(...)`
where the lifespan factory closes over the discovered adapters and
the context. On enter, it iterates adapters and calls `start` on
any that have one, wrapping each in try/except. On exit, it
iterates the same adapters in reverse and calls `stop` on any
that have one, wrapping each in try/except.

The lifespan must be set when the `FastAPI` instance is created,
which means discovery happens before app instantiation. The bind
loop moves to after instantiation, exactly where it is today.

### 8. /api/adapters route shape

```
GET /api/adapters -> {
  "adapters": [
    {
      "name": "webhook",
      "status": "running",
      "last_activity_at": "2026-05-24T12:34:56Z" | null,
      "error_count": 0,
      "error_message": null
    },
    ...
  ]
}
```

Sorted by name for determinism. The route reads
`request.app.state.adapter_registry` and serializes the entries.
Empty list when no adapters are discovered.

### 9. Backwards compatibility

All v0.2 adapter tests pass byte-identical. The Adapter Protocol
itself is unchanged; LifecycleAdapter is additive. The
AdapterContext gains a field, but it is constructed once in
`create_app` and passed to adapters; the dataclass is still frozen.
Direct construction in `test_adapters_webhook.py` passes a registry
explicitly. We add a default `AdapterRegistry()` factory in the
context to keep ad-hoc construction one-liner-friendly: tests that
already write `AdapterContext(config=..., data_dir=...)` continue
to work because `registry` has a default factory.

### 10. Test surface

Two new files:

- `tests/test_adapters_lifecycle.py`: AdapterRegistry transitions,
  start/stop with hasattr dispatch, error isolation, lifespan
  integration via TestClient (TestClient triggers the lifespan).
- `tests/test_server_adapters.py`: the `GET /api/adapters` route
  shape and content, including the webhook adapter's running
  status and the post-request `last_activity_at` update.

The existing `test_adapters_webhook.py` tests must still pass
without modification. The webhook adapter's activity-touch line
is the only behavioral change to the reference adapter.

## Execution split

Single plan: 22-01. The contract extension, registry, lifespan
integration, route, and tests land as a coherent unit; splitting
would create awkward intermediate states.

Atomic commits:

- `docs(22)`: plan + context
- `feat(22)`: LifecycleAdapter Protocol, AdapterRegistry, AdapterContext.registry
- `feat(22)`: FastAPI lifespan + `/api/adapters` route + webhook activity touch
- `test(22)`: lifecycle + adapter status tests
- `docs(22)`: phase summary

The two feat commits may be combined if the diff is small. The
plan + context commit and the summary commit are always separate.

## Deferred / not in scope

- Per-adapter enable/disable from the dashboard. That is Phase 27.
- Health-check ping endpoint per adapter. The status field is enough
  for v0.3 introspection.
- Adapter restart from the API. Operators restart the server.
- Structured logging of lifecycle transitions. The registry captures
  the most recent error; full structured logging is a v0.4 concern.
- The four adapter implementations themselves. Phases 23-26.
