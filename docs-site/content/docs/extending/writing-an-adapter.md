---
title: "Writing an adapter"
description: "Build a custom inbound channel for horus-os by implementing the Adapter Protocol, registering an entry point, and adding optional lifecycle hooks."
---

## What an adapter is

An adapter is an inbound channel that routes external events into the agent runtime. A chat integration, an HTTP webhook receiver, a poll loop against a mailbox: each is an adapter. The core ships several (Discord, Slack, email, calendar, webhook), and you can add your own without forking horus-os.

The contract lives in `horus_os.adapters`. Discovery is driven by Python entry points, so a third-party adapter is just a pip-installable package that declares one entry. The core never learns about your adapter at build time, and a broken adapter cannot break the dashboard: per-entry load failures are caught and isolated during discovery.

> [!NOTE]
> Adapters mount onto the FastAPI app that powers the dashboard. They require the `dashboard` extra, which is already included in `pip install 'horus-os[all]'`. Run `horus-os serve` to start the app and trigger adapter binding.

If you are writing a Python tool the agent can call (rather than an inbound channel), see [Writing a plugin](/extending/plugins/) instead. An adapter brings events in; a plugin gives the agent new abilities. The two compose: an adapter can also register tools (see [Registering agent tools](#registering-agent-tools-optional) below).

## The Adapter Protocol

The minimum surface is a `runtime_checkable` Protocol with one attribute and one method:

```python
from typing import Any
from horus_os import Adapter, AdapterContext


class HelloAdapter:
    """A minimal adapter that mounts one diagnostic GET route."""

    name = "hello"

    def bind(self, app: Any, context: AdapterContext) -> None:
        @app.get(f"/api/adapters/{self.name}/ping")
        def _ping() -> dict[str, str]:
            return {
                "adapter": self.name,
                "data_dir": str(context.data_dir),
            }
```

Two requirements:

- **`name: str`** is a stable identifier. It is used for diagnostics and, by convention, as the URL prefix for any routes you mount: `/api/adapters/<name>/...`.
- **`bind(self, app, context) -> None`** is called once at app startup. Mount your routes on `app` (a FastAPI instance) and stash whatever you need from `context`.

Because the Protocol is `runtime_checkable`, you can assert your class satisfies it before handing it to the runtime:

```python
assert isinstance(HelloAdapter(), Adapter)
```

There is one optional method on the base Protocol:

- **`describe(self) -> dict`** may return a static metadata dict for diagnostics. Callers probe for it with `hasattr`, so you only add it if you want it. The reference `WebhookAdapter` returns its endpoint, auth scheme, and config env var this way.

## AdapterContext

`bind` (and `start`, if you implement it) receives a frozen `AdapterContext` dataclass. It is the only handle you get into the rest of the system, so read what you need from it:

| Field | Type | What it is |
|-------|------|------------|
| `config` | `Config` | The resolved config. Use `context.config.db_path`, `context.config.default_provider`, model defaults, and so on. |
| `data_dir` | `Path` | The resolved data directory. Read or write your adapter's own state under here. |
| `registry` | `AdapterRegistry` | The live per-app registry. Call `context.registry.touch(self.name)` to record activity. |
| `tool_registry` | `ToolRegistry \| None` | The master tool registry. `None` unless tool registration is wired in. Tool-providing adapters check for `None` before using it. |

The context is frozen, so adapters cannot mutate global state through it. The `registry` and `tool_registry` fields are references to mutable objects; you call methods on them, you do not reassign the fields.

A typical handler reaches the database through the config:

```python
from horus_os.storage import Database

def bind(self, app, context):
    @app.post(f"/api/adapters/{self.name}/event")
    async def _handle():
        db = Database(context.config.db_path)
        # ... run an agent turn, record a trace, etc.
        context.registry.touch(self.name)
        return {"ok": True}
```

## Registering agent tools (optional)

Most adapters only bring events in. An adapter can also go the other way and give the agent new abilities, by registering agent-callable tools onto `context.tool_registry` during `bind`. The shipped Calendar adapter works this way: it registers `list_calendar_events_today` and, when writes are allowed, `create_calendar_event`.

A tool is a `horus_os.types.Tool` dataclass with four fields:

| Field | Type | What it is |
|-------|------|------------|
| `name` | `str` | The tool name the model uses to call it. Keep it unique across the registry. |
| `description` | `str` | A short, model-facing description of what the tool does. |
| `parameters` | `dict` | A JSON Schema object describing the inputs the model must produce. |
| `handler` | `Callable \| None` | The Python callable invoked with the model's input as keyword arguments. |

Register tools in `bind`, after you guard for a missing `tool_registry`:

```python
from horus_os.types import Tool


class WeatherAdapter:
    name = "weather"

    def bind(self, app, context):
        # tool_registry is None unless the runtime wired one in.
        # Surface a clear error instead of raising; the rest of the
        # app keeps running.
        if context.tool_registry is None:
            context.registry.mark_error(
                self.name,
                "AdapterContext.tool_registry is None; this adapter needs "
                "a ToolRegistry on the context to register its tools",
            )
            return

        def _get_forecast(city: str) -> dict:
            # ... call your service, return a JSON-serializable result
            return {"city": city, "summary": "clear"}

        context.tool_registry.register(
            Tool(
                name="get_forecast",
                description="Return today's forecast for a city.",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
                handler=_get_forecast,
            ),
            replace=True,
        )
        context.registry.mark_running(self.name)
```

`ToolRegistry.register` raises `ValueError` on a duplicate name unless you pass `replace=True`. When the model selects your tool, the runtime calls `handler(**tool_input)` with the model-supplied arguments, so the handler's keyword parameters must match the names in your `parameters` schema.

`create_app` constructs one `ToolRegistry`, threads it through every adapter's `AdapterContext`, and also exposes it as `app.state.tool_registry`. Because the field is optional and defaults to `None`, always check for `None` first: an adapter constructed with a bare `AdapterContext` (for example in a test) will not have one.

> [!TIP]
> See `examples/calendar_adapter.py` for a full, offline run: it builds an `AdapterContext` carrying a real `ToolRegistry`, calls `bind`, lists the registered tools, and invokes `list_calendar_events_today` the way the agent runtime would.

## Lifecycle hooks (optional)

If your adapter needs a long-running task (a gateway socket, a poll loop, a scheduled tick), implement the sibling `LifecycleAdapter` Protocol alongside the base one. Both hooks are async:

```python
from collections.abc import Awaitable
from typing import Any
from horus_os import AdapterContext


class MyAdapter:
    name = "my_adapter"

    def bind(self, app: Any, context: AdapterContext) -> None:
        ...

    async def start(self, context: AdapterContext) -> None:
        """Launch any background tasks the adapter needs."""
        ...

    async def stop(self) -> None:
        """Drain background tasks. Must complete promptly."""
        ...
```

How the FastAPI lifespan drives these hooks:

- At **startup**, the lifespan calls `await adapter.start(context)` on every discovered adapter that exposes a `start` coroutine. `start` receives the same `AdapterContext` passed to `bind`.
- At **shutdown**, the lifespan walks adapters in reverse order and awaits `stop()` on each one.
- Exceptions raised by either hook are caught, logged into the registry via `mark_error`, and do not propagate. One broken adapter cannot block startup or shutdown of the others.

Dispatch uses `hasattr`, not `isinstance`, so an adapter that implements only `start` (or only `stop`) still works. Adapters that implement both `start` and `stop` report `supports_toggle: true` on `GET /api/adapters` and can be enabled or disabled at runtime through the dashboard's Adapters tab.

> [!TIP]
> Lazily import any heavy or optional SDK inside `start` or `bind`, never at module top level. That way your adapter module imports cleanly even when its optional dependency is not installed, and you can record a clear "X is not installed" error in the registry instead of crashing discovery. The shipped Discord, Slack, and calendar adapters all do this.

## The AdapterRegistry

`AdapterRegistry` tracks per-adapter status for the life of the app. It is attached to `app.state.adapter_registry`, and each discovered adapter gets one `AdapterEntry` row:

| Field | Meaning |
|-------|---------|
| `name` | The adapter's `name`. |
| `status` | One of `running`, `stopped`, `error`. New entries default to `stopped`. |
| `last_activity_at` | UTC iso8601 string, updated via `touch`. `None` until first activity. |
| `error_count` | Increments on every `mark_error` call. |
| `error_message` | The most recent error, formatted as `type(exc).__name__: str(exc)`. |

You mutate your own row through narrow methods on the registry and read it back with `get(name)` or `entries()`:

```python
context.registry.mark_running(self.name)   # flip status to running
context.registry.mark_stopped(self.name)   # flip status to stopped
context.registry.mark_error(self.name, "TOKEN is not set")  # status -> error
context.registry.touch(self.name)          # bump last_activity_at
```

Mutator methods are no-ops for unknown names, so a caller bug cannot raise out of a lifespan handler. Use `mark_error` to surface a misconfiguration (a missing secret, an absent SDK) rather than raising: the adapter stays offline, the error shows on `GET /api/adapters`, and the rest of the app keeps running.

The constants `ADAPTER_STATUS_RUNNING`, `ADAPTER_STATUS_STOPPED`, and `ADAPTER_STATUS_ERROR` are exported from `horus_os.adapters` if you prefer them over string literals.

## Registering for discovery

horus-os finds adapters by walking the `horus_os.adapters` entry-point group. To register yours, declare an entry in your package's `pyproject.toml`:

```toml
[project.entry-points."horus_os.adapters"]
my_adapter = "my_package.adapter:MyAdapter"
```

The group name is also available as the constant `ADAPTER_ENTRY_POINT_GROUP`. After `pip install` (or `pip install -e .` during development), `discover_adapters()` picks up your adapter the next time `create_app` runs. Entries are sorted by name for deterministic ordering.

The entry-point target can be any of three things; discovery handles each:

- a **class**, which is instantiated with no arguments,
- a **factory** (a function or lambda) that returns an adapter instance, or
- an **already-constructed instance**, used as-is.

Discovery distinguishes a factory from an instance by checking for the Protocol's required `bind` attribute, which functions do not have.

## Configuration

Adapters read non-secret defaults from `context.config` and secrets from environment variables. Never read a token or signing secret from the config file or a committed file. The convention used by the core adapters is an env var prefixed `HORUS_OS_`, for example `HORUS_OS_WEBHOOK_SECRET` for the reference webhook adapter and `HORUS_OS_DISCORD_TOKEN` for Discord.

Guard your adapter on its required secret and surface a clear error instead of crashing:

```python
import os

SECRET_ENV = "HORUS_OS_MY_ADAPTER_TOKEN"

async def start(self, context):
    token = os.environ.get(SECRET_ENV) or ""
    if not token:
        context.registry.mark_error(self.name, f"{SECRET_ENV} is not set")
        return
    context.registry.mark_running(self.name)
    # ... open your connection
```

> [!WARNING]
> Environment variables are read by the process that started `horus-os serve`. If you export a variable in your shell after launching the server, the running process does not inherit it. Set the variable first, then start (or restart) the server.

## A minimal end-to-end example

The repository ships `examples/custom_adapter.py`, a runnable script that defines a `HelloAdapter`, registers it for discovery without a `pip install` (by stubbing the entry-point source inline), and calls `create_app(data_dir=...)` to mount its route alongside the core routes. Run it from the repo root:

```bash
python examples/custom_adapter.py
```

The script mirrors what `horus-os init` does before serving: it writes a config and initializes the SQLite database so `create_app` finds them, then prints every `/api/adapters/...` route the resulting app mounted. The same shape, with a real `pyproject.toml` entry point instead of the inline stub, is all a published adapter package needs.

For full lifecycle and registry behavior, read `examples/discord_adapter.py`. It injects a fake `discord` module, calls `start` so the gateway client is wired and the `on_message` coroutine is captured, dispatches a fabricated message, and prints the channel reply plus the resulting `AdapterRegistry` entry status. It runs offline with no token, no SDK install, and no network. The other `examples/*_adapter.py` scripts (Slack, email, calendar) follow the same offline pattern.

## Checklist

Before you publish an adapter, confirm:

- The class has a stable `name` and a `bind(self, app, context)` method.
- Heavy or optional SDKs are imported lazily inside `bind` or `start`, not at module top level.
- A missing secret or missing dependency calls `context.registry.mark_error(...)` and returns, rather than raising.
- Long-running work lives in `start`/`stop`, and `stop` completes promptly.
- Activity is recorded with `context.registry.touch(self.name)`.
- The entry point is declared under `[project.entry-points."horus_os.adapters"]` in `pyproject.toml`.

## See also

- [Writing a plugin](/extending/plugins/) for giving the agent new callable tools
- [Plugin security](/extending/plugin-security/) for the trust model around third-party code
- [Integrations overview](/integrations/overview/) for the adapters that ship with horus-os
- [Architecture](/concepts/architecture/) for how adapters fit into the runtime
