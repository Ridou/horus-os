# Examples

Runnable, offline introductions to the v0.2 public API. Every script
executes end to end with no API keys, no network, and no extra
installs. Each one stubs the provider call or the adapter discovery
seam inline; the docstrings document how to swap the stub for a live
call.

Run from the repo root after `pip install '.[dev]'` (or `'.[all]'`).

## `multi_agent.py`

Coordinator-to-sub-agent delegation. Builds a temp SQLite database,
saves a `summarizer` profile alongside the bootstrapped `default`
profile, registers `delegate_to_agent` via `make_delegate_tool`, and
prints the resulting parent/child trace linkage.

```
python examples/multi_agent.py
```

## `streaming.py`

`run_agent_stream` consumption. Stubs the Anthropic streaming helper
so the example paints tokens to stdout offline, then surfaces a
`ToolCallEvent` on stderr after the text stream drains. Mirrors what
the CLI does for `horus-os run` when streaming is on.

```
python examples/streaming.py
```

## `custom_adapter.py`

Implementing the `Adapter` Protocol. Defines a `HelloAdapter` class,
registers it through an inline `entry_points` stub (a real adapter
declares its entry point in `pyproject.toml` instead), and calls
`create_app(data_dir=...)` to mount the route. Prints every
`/api/adapters/...` route the resulting FastAPI app has.

```
python examples/custom_adapter.py
```

## Running against live providers

Each script's docstring describes which stub to remove and which env
var to set for a live run. The shape of the script does not change.
For example, in `streaming.py`, delete the `_stub_anthropic_stream()`
call, set `ANTHROPIC_API_KEY=sk-ant-...`, and rerun.

See `docs/MIGRATION-v0.1-to-v0.2.md` for the broader v0.1 to v0.2
upgrade path, and `ARCHITECTURE.md` for the system shape these
examples touch.
