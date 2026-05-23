# Migration from v0.1 to v0.2

## TL;DR

Upgrade by pulling the latest `horus-os` and running any CLI
subcommand once. The SQLite schema migrates automatically and
idempotently from v2 (v0.1) through v3 (`agent_profiles` table) to v4
(`parent_trace_id`, `agent_profile_name` columns on `traces`). v0.1
traces remain readable. The only user-visible behavior change is that
`horus-os run "..."` now streams to stdout by default; pass
`--no-stream` to restore the v0.1 buffered output.

No deprecations land in v0.2. Existing code that imported `run_agent`,
`run_agent_async`, `run_agent_loop`, `Database`, or any built-in tool
factory still works without modification.

## What is new

### Runtime entry points

- `horus_os.run_agent_stream(prompt, *, provider, model, max_tokens, system)`:
  async generator that yields `str` token deltas and any
  `ToolCallEvent` values observed in the response. Purely additive;
  existing `run_agent` / `run_agent_async` / `run_agent_loop` are
  unchanged.
- `horus_os.ToolCallEvent`: a synthetic event type emitted by
  `run_agent_stream` when the model requests a tool. Notification
  only. Tool execution remains the responsibility of
  `run_agent_loop`.
- `horus_os.tools.delegation.IterationBudget`: thread-safe counter
  shared across a delegation tree. Passed by reference into nested
  `run_agent_loop` calls so the iteration cap applies to the whole
  tree rather than to each sub-agent.
- `horus_os.tools.delegation.make_delegate_tool(db, master_registry,
  parent_trace_id, budget, provider)`: factory that returns a
  `delegate_to_agent` `Tool`. Register it on a master registry to let
  a coordinator hand off to named sub-agents.

### Types

- `horus_os.AgentProfile`: dataclass holding `name`, `system_prompt`,
  optional `default_model`, optional `allowed_tools` (None means
  unrestricted), optional `memory_scope`, plus `created_at` and
  `updated_at` set by `Database`.
- `horus_os.Adapter`: `runtime_checkable` Protocol with `name: str`
  and `bind(app, context) -> None`. An optional `describe()` method
  may return a static metadata dict.
- `horus_os.AdapterContext`: frozen dataclass holding the resolved
  `Config` and `data_dir`. Passed to `bind` at app startup.

### Database CRUD

`horus_os.Database` gained:

- `load_profile(name) -> AgentProfile | None`
- `save_profile(profile) -> None` (upsert; preserves `created_at` on
  conflict)
- `list_profiles() -> list[AgentProfile]`
- `delete_profile(name) -> bool`
- `list_child_traces(parent_trace_id) -> list[TraceRecord]`

`record_trace` accepts two new optional keyword arguments:
`parent_trace_id=` and `agent_profile_name=`. Both default to None
for backwards compatibility with single-agent callers.

`TraceRecord` carries two new fields with the same names. v0.1 rows
report null in both.

### CLI surface

- `horus-os agents list`
- `horus-os agents show <name>`
- `horus-os agents create --name N --system-prompt P [--model M] [--allowed-tools "a,b"|all|""] [--memory-scope S]`
- `horus-os agents edit <name> [--system-prompt P] [--model M] [--allowed-tools ...] [--memory-scope S]`
- `horus-os agents delete <name>`
- `horus-os run --agent <name> "<prompt>"`: loads the named profile
  and threads its `system_prompt` and `default_model` through the
  run. User-supplied `--model` wins over the profile default.
- `horus-os run --no-stream "<prompt>"`: opt out of the new streaming
  default. Restores v0.1 buffered output.

Bare `horus-os agents` defaults to `list`.

### Server routes

The FastAPI app (`horus-os serve`) gained:

- `GET /api/agents`: list all profiles plus `last_activity_at`
- `GET /api/agents/{name}`: one profile or 404
- `POST /api/agents`: create, 409 on duplicate, 400 on missing fields
- `PATCH /api/agents/{name}`: update only the supplied fields, 404
  on missing
- `DELETE /api/agents/{name}`: 204 on success, 404 on missing
- `GET /api/traces/{id}/children`: child traces oldest first
- `POST /api/chat/stream`: SSE stream with `type` discriminator
  (`token`, `tool_call`, `done`, `error`) per frame

The dashboard exposes an Agents tab, live token streaming in chat,
and a delegate-tree expander on traces that carry an
`agent_profile_name`.

### Adapter contract

`horus_os.adapters` is a new package. Third-party adapters declare an
entry point in their `pyproject.toml`:

```
[project.entry-points."horus_os.adapters"]
my_adapter = "my_package.adapter:MyAdapter"
```

After `pip install`, `discover_adapters()` finds the adapter and
`create_app` binds it on startup. Per-entry failures are isolated; a
broken adapter cannot break the core dashboard.

The reference `WebhookAdapter` ships in `horus_os.adapters.webhook`.
It mounts `POST /api/adapters/webhook` with HMAC-SHA256 signature
validation keyed by the `HORUS_OS_WEBHOOK_SECRET` environment
variable. It refuses to operate when the secret is unset.

## Schema migration

v0.1 ships SCHEMA_VERSION = 2 (`traces`, `note_writes`). v0.2 lands
SCHEMA_VERSION = 4 in two steps:

1. **v2 to v3.** `CREATE TABLE IF NOT EXISTS agent_profiles (...)` is
   added to the schema script and runs on every `init()` call. The
   bootstrap also inserts a `default` profile (system prompt: "You are
   a helpful assistant.") via `INSERT OR IGNORE`, so the row exists
   exactly once across an unbounded number of `init()` calls.
2. **v3 to v4.** Two `ALTER TABLE traces ADD COLUMN` statements
   (`parent_trace_id TEXT`, `agent_profile_name TEXT`) and a
   `CREATE INDEX IF NOT EXISTS idx_traces_parent_trace_id` run on
   startup. `ALTER TABLE ... ADD COLUMN` is not idempotent in SQLite,
   so each call is wrapped in a `try/except sqlite3.OperationalError`
   block. Re-running the migration is safe; SQLite reports the column
   already exists and the code swallows the error.

The migration is automatic on first startup under v0.2 (any
subcommand that opens the database, including `horus-os run` and
`horus-os serve`, triggers it). It is also idempotent: running it on
a database that is already at v4 is a no-op.

v0.1 trace rows remain fully readable. The new `parent_trace_id` and
`agent_profile_name` columns are null on those rows. The dashboard
treats null-agent traces exactly like v0.1 traces (no expand
affordance) so the v0.1 UI shape is preserved.

## User-visible behavior changes

- `horus-os run "<prompt>"` now writes tokens to stdout as they
  arrive, with a trailing meta line of the form
  `\n\n[{provider}/{model}, {latency_ms}ms, streamed]`. To restore
  the v0.1 single-block output, pass `--no-stream`.
- `ToolCallEvent` values surface mid-stream on stderr as
  `[tool-request] {name}({input})`. They do not pollute stdout.
- The dashboard renders chat replies live as tokens arrive. Existing
  bookmarks to other dashboard tabs continue to work.

No other command, route, or function changes meaning. v0.1 scripts
that drive `run_agent` continue to work unmodified.

## Deprecations

None in v0.2.

## Downgrade

Downgrade is one-way and not supported. A v0.2 database carries
columns that v0.1 does not know about; pointing a v0.1 install at a
v0.2 database would fail on every `SELECT` that names the new
columns. If you need a rollback path, back up the SQLite file before
upgrading:

```
cp ~/.local/share/horus-os/horus.sqlite ~/horus.sqlite.v0.1.bak
# or platform equivalent
```

You can then restore the file alongside a `pip install
horus-os==0.1.0` to return to the v0.1 state.

## Upgrade code samples

### Switching `run_agent` to `run_agent_stream`

v0.1:

```python
from horus_os import run_agent

result = run_agent("Summarize today.", provider="anthropic")
print(result.text)
```

v0.2 (token by token):

```python
import asyncio
from horus_os import ToolCallEvent, run_agent_stream


async def main() -> None:
    async for chunk in run_agent_stream(
        "Summarize today.", provider="anthropic"
    ):
        if isinstance(chunk, ToolCallEvent):
            print(f"[tool] {chunk.name}({chunk.input})")
            continue
        print(chunk, end="", flush=True)
    print()


asyncio.run(main())
```

`run_agent` still works in v0.2 if you want the buffered shape.

### Declaring a custom adapter

Create your package with an adapter class:

```python
# my_package/adapter.py
from typing import Any
from horus_os.adapters import Adapter, AdapterContext


class MyAdapter:
    name = "my_adapter"

    def bind(self, app: Any, context: AdapterContext) -> None:
        @app.get(f"/api/adapters/{self.name}/ping")
        def _ping() -> dict[str, str]:
            return {"adapter": self.name}
```

Declare the entry point in `pyproject.toml`:

```toml
[project.entry-points."horus_os.adapters"]
my_adapter = "my_package.adapter:MyAdapter"
```

Install the package (`pip install -e .` or `pip install my_package`).
The next time `horus-os serve` starts, `discover_adapters()` finds
the entry point and `create_app` calls `MyAdapter().bind(app,
context)`. The route is live at `http://127.0.0.1:8765/api/adapters/my_adapter/ping`.

See `examples/custom_adapter.py` for an inline version that does the
same thing without a separate package install.
