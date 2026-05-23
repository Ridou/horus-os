# Phase 15: CLI Multi-Agent Surface - Research

**Researched:** 2026-05-23
**Domain:** Python argparse CLI extension, async streaming in sync CLI, AgentProfile CRUD surface
**Confidence:** HIGH

## Summary

Phase 15 extends the `horus-os` CLI with two capabilities: an `agents` subcommand for managing named agent profiles stored in SQLite, and a streaming-by-default `run` path that consumes the `run_agent_stream` async generator from Phase 14.

The existing CLI is built on **argparse** with a strict structural pattern: `__main__.py` owns the parser, each subcommand lives in `cli/<name>_cmd.py`, and every subcommand handler has the signature `run_<name>(args, *, stdout, stderr) -> int`. Phase 15 must follow this pattern exactly. No Typer, no Click, no Rich -- the project's explicit `stdout`/`stderr` injection design is what makes CLI logic unit-testable without subprocess overhead.

Streaming to the terminal from an async generator requires wrapping the consumer in `asyncio.run()`. The `--no-stream` fallback continues using the sync `run_agent_loop` path unchanged. Both paths write to the injected `stdout: TextIO` object, so tests use `io.StringIO()` exactly as today.

**Primary recommendation:** Add `cli/agents_cmd.py` (CRUD via nested argparse subparsers), extend `run_cmd.py` with `--agent` and `--no-stream` flags, and register both in `__main__.py`. No new runtime dependencies required.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Agent profile CRUD | Database/Storage (Phase 12 API) | CLI display only | `Database` already owns `list_profiles`, `save_profile`, `load_profile`, `delete_profile` |
| Streaming token display | CLI surface (`run_cmd.py`) | Agent runtime (Phase 14) | CLI layer drives `asyncio.run()` and writes tokens to stdout |
| `--agent <name>` profile load | CLI surface (`run_cmd.py`) | Database/Storage | CLI queries profile, passes `system_prompt` + model down to `run_agent_loop` / `run_agent_stream` |
| Async-to-sync bridge | CLI surface (`run_cmd.py`) | stdlib `asyncio` | `asyncio.run()` is the canonical bridge; no third-party async runner needed |
| Argument parsing | `__main__.py` | per-cmd files | Consistent with all existing subcommands |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| stdlib `argparse` | 3.11+ | Argument parsing | Already used by all existing subcommands - do not switch to Typer or Click |
| stdlib `asyncio` | 3.11+ | Async-to-sync bridge for streaming | `asyncio.run()` is the idiomatic entry point for sync callers; no extra dep |
| stdlib `io` | 3.11+ | StringIO in tests | Already used in all CLI tests |

[VERIFIED: codebase inspection - src/horus_os/__main__.py, src/horus_os/cli/run_cmd.py]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `horus_os.storage.Database` | project | Load/save/list/delete AgentProfile rows | All agents subcommand operations |
| `horus_os.agent.run_agent_loop` | project | Non-streaming run path (--no-stream) | Already used; unchanged |
| `horus_os.agent.run_agent_stream` | project (Phase 14) | Streaming run path | Default path when --no-stream not set; Phase 14 delivers this |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `argparse` + nested subparsers | Typer or Click | Typer/Click are not in `dependencies = []`; switching frameworks mid-project adds friction and breaks the existing test harness that calls `main(argv, stdout=..., stderr=...)` |
| `asyncio.run()` in run_cmd | `anyio.from_thread.run()` | No advantage; anyio not a dependency; `asyncio.run()` is sufficient for a simple streaming consumer |
| Plain `stdout.write(token)` | Rich Live display | Rich is not in `dependencies = []`; stdout injection is the project's testability contract; plain write works with StringIO |

**Installation:** No new packages required. All capabilities come from the Python standard library and existing project code.

## Architecture Patterns

### System Architecture Diagram

```
horus-os agents list
     |
     v
__main__.py build_parser()
     |-- agents subparser --> agents_cmd.py::run_agents(args, stdout, stderr)
            |-- list   --> db.list_profiles() --> _format_profiles_table()
            |-- show   --> db.load_profile(name) --> _format_profile_detail()
            |-- create --> parse flags --> AgentProfile(...) --> db.save_profile()
            |-- edit   --> db.load_profile() --> mutate fields --> db.save_profile()
            `-- delete --> db.delete_profile(name) --> confirm

horus-os run "<prompt>" [--agent <name>] [--no-stream]
     |
     v
__main__.py build_parser()  (new --agent, --no-stream flags on run subparser)
     |
     v
run_cmd.py::run_run(args, stdout, stderr)
     |
     +-- [if --agent <name>]  db.load_profile(name) --> set system_prompt, model
     |
     +-- [--no-stream]  run_agent_loop(...)  -->  _print_result(stdout)
     |
     `-- [default]  asyncio.run(_stream_to_stdout(prompt, system_prompt, ...))
                         |
                         v
               async for token in run_agent_stream(...):
                   stdout.write(token)
                   stdout.flush()
               print footer (provider, model, latency)
```

### Recommended Project Structure

No new top-level modules. Changes are localized to:

```
src/horus_os/
├── __main__.py           # add agents subparser + --agent/--no-stream to run subparser
├── cli/
│   ├── __init__.py       # export run_agents
│   ├── agents_cmd.py     # NEW - CRUD subcommand handler
│   └── run_cmd.py        # add --agent, --no-stream, async streaming path
tests/
├── test_cli_agents.py    # NEW - agents CRUD subcommand tests
└── test_cli_run.py       # add streaming and --agent flag tests
```

### Pattern 1: Nested argparse subparsers for `agents`

**What:** Argparse allows a subparser to contain its own nested subparsers. The `agents` command owns a second level.
**When to use:** Any new subcommand group with its own set of operations.

```python
# Source: Python stdlib argparse docs + existing __main__.py pattern [VERIFIED]
agents_p = sub.add_parser("agents", help="Manage agent profiles")
agents_sub = agents_p.add_subparsers(dest="agents_command", metavar="<operation>")
agents_p.set_defaults(func=run_agents)

list_p = agents_sub.add_parser("list", help="List all agent profiles")
list_p.set_defaults(agents_command="list")

show_p = agents_sub.add_parser("show", help="Show a single agent profile")
show_p.add_argument("name", help="Profile name")

create_p = agents_sub.add_parser("create", help="Create a new agent profile")
create_p.add_argument("--name", required=True)
create_p.add_argument("--system-prompt", dest="system_prompt", required=True)
create_p.add_argument("--model", default=None)

edit_p = agents_sub.add_parser("edit", help="Edit an existing agent profile")
edit_p.add_argument("name", help="Profile name to edit")
edit_p.add_argument("--system-prompt", dest="system_prompt", default=None)
edit_p.add_argument("--model", default=None)

delete_p = agents_sub.add_parser("delete", help="Delete an agent profile")
delete_p.add_argument("name", help="Profile name to delete")
```

### Pattern 2: `agents_cmd.py` subcommand handler

**What:** All agent CRUD ops dispatch through a single `run_agents` function that reads `args.agents_command`.

```python
# Source: codebase pattern from traces_cmd.py adapted for nested subcommands [VERIFIED]
import argparse
from typing import TextIO
from horus_os.config import Config
from horus_os.storage import Database
from horus_os.types import AgentProfile


def run_agents(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    config = Config.load(getattr(args, "data_dir", None))
    if not config.db_path.exists():
        stderr.write(f"No database at {config.db_path}. Run `horus-os init` first.\n")
        return 1
    db = Database(config.db_path)
    op = getattr(args, "agents_command", None)
    if op == "list" or op is None:
        return _cmd_list(db, stdout)
    if op == "show":
        return _cmd_show(db, args.name, stdout, stderr)
    if op == "create":
        return _cmd_create(db, args, stdout, stderr)
    if op == "edit":
        return _cmd_edit(db, args, stdout, stderr)
    if op == "delete":
        return _cmd_delete(db, args.name, stdout, stderr)
    stderr.write(f"Unknown operation: {op!r}\n")
    return 2


def _cmd_list(db: Database, stdout: TextIO) -> int:
    profiles = db.list_profiles()
    if not profiles:
        stdout.write("(no agent profiles yet)\n")
        return 0
    stdout.write(_format_profiles_table(profiles) + "\n")
    return 0


def _format_profiles_table(profiles) -> str:
    header = f"{'name':24}  {'model':30}  system_prompt"
    lines = [header, "-" * 80]
    for p in profiles:
        model = p.default_model or "(default)"
        preview = (p.system_prompt[:40] + "...") if len(p.system_prompt) > 43 else p.system_prompt
        lines.append(f"{p.name:24}  {model:30}  {preview}")
    return "\n".join(lines)
```

### Pattern 3: Streaming run path with `asyncio.run()`

**What:** When `--no-stream` is NOT set, use `asyncio.run()` to drive the async generator from Phase 14.

```python
# Source: codebase pattern from run_cmd.py + Python stdlib asyncio [VERIFIED]
import asyncio
from horus_os.agent import run_agent_stream  # Phase 14 addition


def run_run(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    # ... setup: config, provider, api_key checks, model, db, registry (unchanged) ...
    no_stream: bool = getattr(args, "no_stream", False)
    agent_name: str | None = getattr(args, "agent", None)
    system_prompt: str | None = None

    if agent_name:
        profile = db.load_profile(agent_name)
        if profile is None:
            stderr.write(f"No agent profile named {agent_name!r}.\n")
            return 1
        system_prompt = profile.system_prompt
        model = model or profile.default_model

    if no_stream:
        # existing synchronous path - unchanged
        result = run_agent_loop(prompt, registry=registry, ...)
        _print_result(stdout, result, latency_ms, tool_log)
    else:
        # streaming path
        asyncio.run(
            _stream_run(
                prompt,
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                stdout=stdout,
            )
        )
    return 0


async def _stream_run(
    prompt: str,
    *,
    provider: str,
    model: str,
    system_prompt: str | None,
    stdout: TextIO,
) -> None:
    import time
    start = time.perf_counter()
    async for token in run_agent_stream(
        prompt, provider=provider, model=model, system=system_prompt
    ):
        stdout.write(token)
        stdout.flush()
    latency_ms = int((time.perf_counter() - start) * 1000)
    stdout.write(f"\n\n[{provider}/{model}, {latency_ms}ms, streamed]\n")
```

### Pattern 4: CLI test for streaming (StringIO flush is a no-op)

**What:** `io.StringIO.flush()` is a no-op and does not raise. Tests can use the same StringIO harness as all other CLI tests.

```python
# Source: existing tests/test_cli_run.py pattern [VERIFIED]
import asyncio, io

async def fake_stream(prompt, *, provider, model, system=None):
    for token in ["Hello", ", ", "world"]:
        yield token

def test_run_streams_by_default(tmp_path, monkeypatch):
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setattr("horus_os.cli.run_cmd.run_agent_stream", fake_stream)
    code, out, err = _runcli(["run", "hi", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "Hello, world" in out

def test_run_no_stream_falls_back(tmp_path, monkeypatch):
    # monkeypatch run_agent_loop as before; no streaming should be called
    ...
```

### Anti-Patterns to Avoid

- **Calling `asyncio.get_event_loop().run_until_complete()` instead of `asyncio.run()`:** `asyncio.run()` creates a fresh event loop and is the correct top-level entry point since Python 3.7+. The old `.get_event_loop()` pattern is deprecated and unsafe in nested contexts.
- **Writing a new top-level parser instead of adding subparsers:** The `sub = parser.add_subparsers()` in `__main__.py` already exists. Add the new `agents` subparser to the existing `sub` object.
- **Using `sys.stdout.write()` directly in CLI handler functions:** Always write to the injected `stdout` parameter. Direct `sys.stdout` calls break the test harness.
- **Blocking on `async for` without `asyncio.run()`:** Calling `async for token in run_agent_stream(...)` outside an async context raises `SyntaxError`. The sync CLI must use `asyncio.run()`.
- **Raising instead of returning an int exit code:** Handlers must return int. Exceptions surface as returncode 1 via the outer try/except in `run_run`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Profile persistence | Custom file-based profile store | `Database.save_profile()` / `Database.list_profiles()` | Phase 12 already built and tested the SQLite CRUD layer |
| Async-to-sync bridge | Custom thread executor, queue, or event bridge | `asyncio.run()` | Single call; no extra state; garbage-collects the event loop automatically |
| Token accumulation | Custom buffer object | `io.StringIO()` already collects tokens naturally | Tokens write in order; `getvalue()` returns full text for assertions |
| CLI framework | Typer/Click wrapper layer | argparse with existing `main()` dispatch | Breaking the stdout/stderr injection contract would require rewriting all 15+ existing tests |

**Key insight:** The project's custom stdout/stderr injection is a deliberate testability contract. Any framework that bypasses it (including Typer's `typer.echo`) would require rewriting the entire test suite.

## Common Pitfalls

### Pitfall 1: `asyncio.run()` called from inside an already-running event loop

**What goes wrong:** If any test or caller already has an active event loop (e.g., `pytest-asyncio` with `asyncio_mode = "auto"`), calling `asyncio.run()` inside the CLI handler raises `RuntimeError: This event loop is already running`.

**Why it happens:** `asyncio.run()` creates a NEW event loop and errors if one is running. `pytest-asyncio` in auto mode creates a loop for async tests.

**How to avoid:** The CLI handler tests must be sync functions (not `async def`). Sync tests do not have an active event loop, so `asyncio.run()` inside `run_run` is safe. The fake streaming function is defined as `async def` but the test calling `main(argv, ...)` is a regular `def` - this is the correct pattern matching all existing CLI tests.

**Warning signs:** `RuntimeError: This event loop is already running` in pytest output.

### Pitfall 2: Nested argparse subparser dispatch not reaching the handler

**What goes wrong:** `agents_p.set_defaults(func=run_agents)` is set but `args.agents_command` is not set when the user types `horus-os agents` with no operation. The `run_agents` function receives `agents_command = None`.

**Why it happens:** Argparse does not require a nested subcommand to be specified. Without a default or a guard, `None` slips through.

**How to avoid:** In `run_agents`, treat `agents_command is None` as `"list"` (show help or list is user-friendly). The pattern is: `op = getattr(args, "agents_command", None); if op is None: return _cmd_list(...)`.

### Pitfall 3: Streaming path does not record a trace

**What goes wrong:** The `--no-stream` path records a trace via `db.record_trace(...)`. The streaming path may be written without a trace, creating an inconsistency.

**Why it happens:** The trace-recording call is easy to forget when adding a second code path.

**How to avoid:** The streaming path (`_stream_run`) should also call `db.record_trace(...)` after the stream completes. Phase 13 extends `record_trace` - ensure the streaming path uses the same parameters.

### Pitfall 4: `--agent` flag silently overriding user-supplied `--model`

**What goes wrong:** `--agent foo` loads `foo.default_model`, but the user also passes `--model gpt-4`. The profile's model wins if implemented naively.

**Why it happens:** Simple assignment `model = profile.default_model` overwrites any model the user specified.

**How to avoid:** Explicit precedence: user-supplied `--model` always wins over profile default. Pattern: `model = args.model or profile.default_model or config.model_for(provider)`.

### Pitfall 5: `edit` overwriting fields not provided by the user

**What goes wrong:** `agents edit foo --model claude-3-5-haiku-latest` clears `system_prompt` because the create-new-profile path was reused.

**Why it happens:** Creating a fresh `AgentProfile(name=..., system_prompt=args.system_prompt or "", ...)` blanks unset fields.

**How to avoid:** `edit` must load the existing profile first, then apply only the fields explicitly provided. Pattern: `if args.system_prompt is not None: profile.system_prompt = args.system_prompt`.

## Code Examples

### Verified: `argparse` nested subparser dispatch

```python
# Source: Python 3.11 stdlib docs + codebase __main__.py [VERIFIED]
sub = parser.add_subparsers(dest="command", metavar="<command>")  # already exists
agents_p = sub.add_parser("agents", help="Manage agent profiles")
agents_sub = agents_p.add_subparsers(dest="agents_command", metavar="<operation>")
agents_p.set_defaults(func=run_agents)
```

### Verified: `asyncio.run()` with an async generator consumer

```python
# Source: Python 3.11 stdlib asyncio docs [VERIFIED: asyncio.run is 3.7+]
import asyncio

def run_run(args, *, stdout, stderr):
    # ...
    asyncio.run(_stream_run(prompt, provider=provider, model=model, stdout=stdout))
    return 0

async def _stream_run(prompt, *, provider, model, stdout):
    async for token in run_agent_stream(prompt, provider=provider, model=model):
        stdout.write(token)
        stdout.flush()
```

### Verified: `io.StringIO.flush()` is safe (no-op)

```python
# Source: Python 3.11 io module [VERIFIED - flush() on StringIO is defined as a no-op]
import io
buf = io.StringIO()
buf.write("hello")
buf.flush()   # no-op, no exception
assert buf.getvalue() == "hello"
```

### Verified: AgentProfile CRUD methods available

```python
# Source: src/horus_os/storage.py [VERIFIED: lines 261-310]
# db.list_profiles() -> list[AgentProfile]
# db.load_profile(name: str) -> AgentProfile | None
# db.save_profile(profile: AgentProfile) -> None   # INSERT OR REPLACE semantics
# db.delete_profile(name: str) -> bool
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Blocking full-text wait before output | `async for token in run_agent_stream(...)` | Phase 14 | Incremental output reduces perceived latency |
| Single anonymous agent | Named profiles via `agent_profiles` table | Phase 12 | `--agent <name>` is now possible |

**Deprecated/outdated:**
- `asyncio.get_event_loop().run_until_complete()`: Python 3.10+ deprecates bare `.get_event_loop()` calls outside async context. Use `asyncio.run()`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `run_agent_stream` will accept a `system` parameter matching the `run_agent_loop` pattern | Architecture Patterns, Pattern 3 | Streaming path cannot pass system prompt; Phase 14 must be asked to add this param |
| A2 | Phase 13 adds `system_prompt` to `run_agent_loop`, making `--agent` flag work on non-streaming path | Pattern 3 | Non-streaming `--agent` path cannot inject system prompt; must wait for Phase 13 |
| A3 | ~~`db.save_profile()` uses upsert semantics~~ | Pattern 2 | RESOLVED - see below |

[VERIFIED: src/horus_os/storage.py lines 267-296 - `save_profile` uses `INSERT ... ON CONFLICT(name) DO UPDATE SET`, preserving `created_at` on conflict. Load-then-save for `edit` is correct and safe.]

## Open Questions

1. **Should `agents edit` use upsert or explicit load-then-save?**
   - What we know: `db.save_profile()` semantics - if it is INSERT OR REPLACE, calling it after loading and mutating fields is safe
   - What is unclear: Whether `save_profile` resets `created_at` on each call
   - Recommendation: Load profile, mutate fields, call `save_profile`. Trust the DB method to preserve `created_at` since that column is set at insert time.

2. **Should streaming path record a trace?**
   - What we know: `--no-stream` path records a trace; streaming path must be consistent
   - Recommendation: Yes, record a trace after stream completes. The streaming path knows provider, model, and latency. Text can be accumulated during streaming for trace storage.

3. **`agents edit` - interactive or flag-based?**
   - Recommendation: Flag-based only (e.g., `--system-prompt`, `--model`). Interactive editing is out of scope for Phase 15. Users who need full edits can delete and recreate.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | `asyncio.run()`, async generators | Yes | 3.11/3.12 in CI matrix | -- |
| `horus_os.agent.run_agent_stream` | Streaming path | No - Phase 14 delivers this | -- | `run_agent_loop` (--no-stream path) |
| `horus_os.storage.Database` CRUD | agents subcommand | Yes - Phase 12 ships this | -- | -- |

**Missing dependencies with no fallback:**
- `run_agent_stream` - provided by Phase 14. Phase 15 streaming path has a hard dependency on Phase 14 being complete first. The `--no-stream` path and `agents` subcommand can ship without Phase 14.

**Missing dependencies with fallback:**
- None beyond Phase 14.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio (asyncio_mode = "auto") |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/test_cli_agents.py tests/test_cli_run.py -x -q` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STREAM-02 | `horus-os run` streams tokens by default | unit | `pytest tests/test_cli_run.py -k stream -x` | No - Wave 0 |
| STREAM-02 | `--no-stream` falls back to sync run_agent_loop | unit | `pytest tests/test_cli_run.py -k no_stream -x` | No - Wave 0 |
| STREAM-02 | Streaming path writes incremental tokens to stdout | unit | `pytest tests/test_cli_run.py -k stream -x` | No - Wave 0 |
| (roadmap) | `horus-os agents list` shows profiles table | unit | `pytest tests/test_cli_agents.py -k list -x` | No - Wave 0 |
| (roadmap) | `horus-os agents create` persists a new profile | unit | `pytest tests/test_cli_agents.py -k create -x` | No - Wave 0 |
| (roadmap) | `horus-os agents show <name>` displays profile detail | unit | `pytest tests/test_cli_agents.py -k show -x` | No - Wave 0 |
| (roadmap) | `horus-os agents edit <name>` updates fields without clobbering others | unit | `pytest tests/test_cli_agents.py -k edit -x` | No - Wave 0 |
| (roadmap) | `horus-os agents delete <name>` removes profile | unit | `pytest tests/test_cli_agents.py -k delete -x` | No - Wave 0 |
| (roadmap) | `horus-os run --agent <name>` loads system prompt from profile | unit | `pytest tests/test_cli_run.py -k agent -x` | No - Wave 0 |
| (roadmap) | `--agent <nonexistent>` exits with code 1 and error message | unit | `pytest tests/test_cli_run.py -k agent -x` | No - Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_cli_agents.py tests/test_cli_run.py -x -q`
- **Per wave merge:** `pytest`

### Wave 0 Gaps

- [ ] `tests/test_cli_agents.py` -- covers all 6 agents CRUD operations + error paths
- [ ] `tests/test_cli_run.py` -- extend with streaming, --no-stream, --agent flag tests (file exists, add to it)

## Sources

### Primary (HIGH confidence)

- Codebase inspection: `src/horus_os/__main__.py`, `src/horus_os/cli/run_cmd.py`, `src/horus_os/cli/traces_cmd.py` [VERIFIED: all patterns cited from actual file contents]
- Codebase inspection: `src/horus_os/storage.py` lines 261-310 [VERIFIED: Database CRUD methods confirmed]
- Codebase inspection: `src/horus_os/types.py` lines 82-91 [VERIFIED: AgentProfile fields confirmed]
- Python 3.11 stdlib: `asyncio.run()`, `io.StringIO.flush()` [VERIFIED: stdlib docs]

### Secondary (MEDIUM confidence)

- pyproject.toml `asyncio_mode = "auto"` [VERIFIED: confirmed in pyproject.toml - async test support already present]
- `pyproject.toml` `dependencies = []` [VERIFIED: no required runtime deps; Rich not in scope]

### Tertiary (LOW confidence)

- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - codebase verified, no new dependencies needed
- Architecture: HIGH - follows existing patterns exactly; AsyncIO bridge is stdlib
- Pitfalls: HIGH - pitfalls 1-5 derived from code inspection of actual patterns in use

**Research date:** 2026-05-23
**Valid until:** 2026-08-23 (stable stdlib patterns; valid until Phase 14 API is confirmed)
