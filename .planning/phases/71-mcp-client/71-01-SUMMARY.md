---
phase: 71-mcp-client
plan: "01"
subsystem: mcp_client
tags: [mcp, tools, namespacing, trust-gate, sanitization, subprocess, lifecycle-adapter, pitfall-mc1, pitfall-mc2, pitfall-mc3, pitfall-mc4, v0.8]
dependency_graph:
  requires: [ToolRegistry, Tool, LifecycleAdapter, mcp_extra]
  provides: [MCPServerConfig, MCPClient, MCPRegistry, sanitize_tool_description, register_namespaced, CollisionError]
  affects:
    - pyproject.toml
    - src/horus_os/mcp_client/
    - src/horus_os/tools/registry.py
tech_stack:
  added: ["mcp>=1.27 (official Anthropic MCP SDK, MIT, opt-in [mcp] extra)"]
  patterns: [lazy-sdk-import-clean-runtimeerror, dedicated-thread-event-loop, run-coroutine-threadsafe-bridge, explicit-finally-teardown, opt-in-trust-gate, namespaced-collision-refusal, untrusted-description-sanitization]
key_files:
  created:
    - src/horus_os/mcp_client/__init__.py
    - src/horus_os/mcp_client/config.py
    - src/horus_os/mcp_client/sanitize.py
    - src/horus_os/mcp_client/client.py
    - src/horus_os/mcp_client/registry.py
    - tests/mcp/__init__.py
    - tests/mcp/conftest.py
    - tests/mcp/test_mcp_config.py
    - tests/mcp/test_mcp_namespacing.py
    - tests/mcp/test_mcp_sanitize.py
    - tests/mcp/test_mcp_trust_gate.py
  modified:
    - pyproject.toml
    - src/horus_os/tools/registry.py
decisions:
  - "MC-4 final-name collision rule: register_namespaced raises CollisionError when tool.name (the final, normally mcp-prefixed name) equals a reserved builtin. The mcp: prefix is the disambiguator, so mcp:fs:read_file registers cleanly next to builtin read_file; an unprefixed builtin name passed through is refused. This matches the two PINNED namespacing tests (test_discovered_tool_gets_mcp_prefix succeeds, test_collision_with_builtin_raises_collision_error refuses the unprefixed form)."
  - "MC-3 teardown via a thin _ProcessHandle abstraction (terminate/wait/kill/is_running) so the unit test injects a fake recording the call sequence; the real stdio path captures the SDK's spawned anyio process by briefly wrapping mcp.client.stdio._create_platform_compatible_process during connect, giving stop() an explicit teardown path independent of the SDK lifespan (SDK issue 1027 Windows zombie bug)."
  - "Each MCPClient runs its SDK session on a dedicated worker thread with its own asyncio event loop; call_tool_sync bridges the synchronous ToolRegistry.invoke handler onto that loop via run_coroutine_threadsafe, avoiding any deadlock with the FastAPI lifespan loop or an execute_tool_uses worker thread."
  - "streamable-http uses the SDK's streamablehttp_client and destructures the yielded streams[0]/streams[1] defensively (the SDK yields a 3-tuple read/write/get_session_id in 1.27.2; a future 2-tuple still works)."
  - "MCPRegistry mirrors DiscordAdapter resilience: a per-server CollisionError or connect failure is recorded against that server and re-exposed via errors() (never swallowed) and the offending client is torn back down, so other servers still register."
metrics:
  completed_date: "2026-06-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 11
  files_modified: 2
---

# Phase 71 Plan 01: MCP client core (config, sanitize, client, registry) Summary

A new opt-in `src/horus_os/mcp_client/` package that connects to explicitly
allowlisted MCP servers over stdio / SSE / streamable-HTTP, discovers their
tools, sanitizes each description, and registers each discovered tool into
the shared `ToolRegistry` under a `mcp:{server}:{tool}` namespace. Delivers
the four security-critical behaviors as testable units: the opt-in trust
gate (MCP-03 BLOCKING), namespacing with collision refusal (MCP-02 / MC-4),
description sanitization against tool poisoning (MC-2), and explicit cross-OS
subprocess teardown (MCP-04 / MC-3). Lifespan wiring, agent/CLI surfaces,
doctor status, docs/MCP.md, and the full cross-OS integration suite land in
71-02.

## Tasks Completed

| Task | Name | Key Files |
|------|------|-----------|
| 1 | [mcp] extra, namespacing + CollisionError in ToolRegistry, description sanitizer | pyproject.toml, src/horus_os/tools/registry.py, src/horus_os/mcp_client/sanitize.py |
| 2 | MCPServerConfig loader (opt-in trust gate) + MCPClient with cross-OS teardown | src/horus_os/mcp_client/config.py, src/horus_os/mcp_client/client.py |
| 3 | MCPRegistry (LifecycleAdapter) wiring config to sanitized namespaced tools | src/horus_os/mcp_client/registry.py, src/horus_os/mcp_client/__init__.py |

## What Was Built

### pyproject.toml
- New optional extra `mcp = ["mcp>=1.27"]`; `"mcp>=1.27"` appended to the `all` superset. NOT in base `[project.dependencies]` and NOT in `[dev]` (opt-in only).

### src/horus_os/tools/registry.py
- New module-level `CollisionError(Exception)`.
- New `ToolRegistry.register_namespaced(tool, builtin_names)` that raises `CollisionError` (and registers nothing) when `tool.name` equals a reserved builtin, otherwise registers via the same duplicate-safe map as `register`. Module docstring notes this is the MCP path and the error must surface (MC-4). `register` left byte-identical.

### src/horus_os/mcp_client/sanitize.py
- `MCP_DESCRIPTION_MAX_CHARS = 1024` and `sanitize_tool_description(text)`: returns "" for None / non-str; strips Unicode tag chars U+E0000-U+E007F; drops Cf/Cc format/control chars except newline/tab/CR/space; length-caps with a `...` truncation marker inside the cap; never raises (MC-2).

### src/horus_os/mcp_client/config.py
- Frozen `MCPServerConfig` (name, transport, command, args, env, url), `SUPPORTED_TRANSPORTS = ("stdio", "sse", "streamable-http")`, `MCPServerConfig.load(path)` returning `[]` on absent / empty / malformed file (MCP-03 trust gate) and skipping unsupported-transport entries, plus `default_mcp_config_path(data_dir)`.

### src/horus_os/mcp_client/client.py
- `MCP_TERMINATE_TIMEOUT_S = 5.0`, `MCP_EXTRA_HINT`, `DiscoveredTool`, `_ProcessHandle`, and `MCPClient`. Lazy-imports `mcp` inside `start()` (clean `RuntimeError(MCP_EXTRA_HINT)` on missing extra). Session runs on a dedicated worker thread/loop. `call_tool`/`call_tool_sync` flatten TextContent to a string. `stop()` performs explicit `terminate()` -> bounded `wait()` -> `kill()` in a `finally` block, idempotent, race-safe.

### src/horus_os/mcp_client/registry.py
- `MCPRegistry` LifecycleAdapter (`name="mcp"`, async `start`/`stop`). Empty config registers nothing (MCP-03 fast path). Per server: connect (off the event loop via `asyncio.to_thread`), sanitize each description, build a `mcp:{server}:{tool}` Tool whose handler bridges to `client.call_tool_sync`, register via `register_namespaced`. CollisionError / failure recorded per server and re-exposed via `errors()`. `stop()` tears down clients in reverse.

### src/horus_os/mcp_client/__init__.py
- Re-exports MCPServerConfig, default_mcp_config_path, MCPClient, MCP_EXTRA_HINT, MCPRegistry, sanitize_tool_description, MCP_DESCRIPTION_MAX_CHARS.

### tests/mcp/ (new suite, 24 tests)
- `conftest.py`: `FakeProcess` (records terminate/wait/kill), `FakeMCPClient`, `make_factory` (all in-process, no network/subprocess/model download).
- `test_mcp_sanitize.py`: tag-char strip, zero-width/format control strip, length cap + marker, malformed input never raises.
- `test_mcp_namespacing.py`: prefix applied without touching builtin, collision refusal (final-name rule), unprefixed-builtin refusal, handler-calls-session bridge, description sanitized at registration.
- `test_mcp_config.py`: two-server parse, unsupported-transport skip, missing-name skip, malformed-TOML empty, default path.
- `test_mcp_trust_gate.py`: absent/empty config empty, empty-config registers zero tools, terminate/wait/kill sequence + idempotency + skip-kill-on-exit + race-swallow, collision surfaces via errors() without shadowing, stop tears down all clients.

## Verification Results

- `pytest tests/mcp/ -q` -- 24 passed.
- `pytest tests/mcp/test_mcp_sanitize.py tests/mcp/test_mcp_namespacing.py::test_collision_with_builtin_raises_collision_error tests/mcp/test_mcp_namespacing.py::test_discovered_tool_gets_mcp_prefix -q` (Task 1 gate) -- pass.
- `pytest tests/mcp/test_mcp_config.py tests/mcp/test_mcp_trust_gate.py::test_absent_config_file_yields_empty_server_list tests/mcp/test_mcp_trust_gate.py::test_stop_terminates_and_waits -q` (Task 2 gate) -- pass.
- `ruff check` and `ruff format --check` on src/horus_os/mcp_client, src/horus_os/tools/registry.py, tests/mcp -- all clean.
- Module import without the mcp SDK on the path -- succeeds; `MCPClient.start()` raises a clean `RuntimeError("MCP client requires 'pip install horus-os[mcp]'")`, never a bare `ModuleNotFoundError`.
- pyproject: base deps and [dev] have no mcp; [mcp] extra and all include `mcp>=1.27`.
- Broad suite (excluding the four pre-existing test_adapters_otel* files) -- 1467 passed, 10 skipped; only the two documented pre-existing release_gate failures remain (test_main_exit_zero_when_all_checks_pass, test_pricing_threshold_overridable_via_env; pip-audit 2.10 flag rename, Phase 76). Confirmed pre-existing by stashing this plan's changes.
- No U+2014 em-dash in any added line.

## Deviations from Plan

### Notes

- MC-4 collision semantics resolved to the FINAL-name rule (the prefixed name vs a reserved builtin), which is what the two PINNED namespacing tests require: `mcp:fs:read_file` registers cleanly while an unprefixed `read_file` is refused. The MCPRegistry "collision surfaces" test exercises the surfacing path by pre-registering a builtin occupying the exact namespaced slot the MCP tool would produce, so `start()` records the CollisionError in `errors()` without overwriting the existing entry.
- The package directory is named `mcp_client/` (per this plan's `files_modified`), not `mcp/` as the older ARCHITECTURE.md sketch suggested, to avoid a name clash with the third-party `mcp` SDK on the import path.
- `MCPClient.start()`/`stop()`/`call_tool_sync` are synchronous and drive a private worker-thread event loop; `MCPRegistry` invokes them via `asyncio.to_thread` so the FastAPI lifespan loop stays responsive. This is the deadlock-free bridge the plan called for ("run the call on a dedicated client loop").

## Known Stubs / Deferred to 71-02

- FastAPI lifespan wiring of `MCPRegistry`, agent/CLI surfaces, `horus-os doctor` MCP status, `docs/MCP.md` (with threat model), and the real cross-OS stdio no-zombie teardown integration test all land in plan 71-02. This plan delivers only the unit slice of TEST-34.

## Threat Flags

- T-71-01 (EoP via tool registration): mitigated -- register_namespaced refuses builtin-name collisions; CollisionError surfaces.
- T-71-02 (trust gate spoofing/tampering): mitigated -- load() returns [] for absent/empty config; empty config registers zero tools; no network probe for unlisted servers.
- T-71-03 (prompt injection via descriptions): mitigated -- sanitize_tool_description strips tag chars + Cf/Cc and length-caps before any description reaches the model; never raises.
- T-71-04 (subprocess resource leak): mitigated (unit) -- stop() drives terminate/wait/kill in a finally block, idempotent, race-safe; cross-OS no-zombie proof deferred to 71-02.
- T-71-05 (info disclosure via result flattening): accept -- unchanged baseline; MCP results flow through the existing tool_invocations capture path.
- T-71-SC (mcp package install): mitigated -- official Anthropic SDK, opt-in [mcp] extra; bare install pulls zero MCP deps.

## Self-Check: PASSED

- src/horus_os/mcp_client/{__init__,config,sanitize,client,registry}.py: FOUND
- src/horus_os/tools/registry.py (CollisionError + register_namespaced): FOUND
- tests/mcp/{__init__,conftest,test_mcp_config,test_mcp_namespacing,test_mcp_sanitize,test_mcp_trust_gate}.py: FOUND
- pyproject.toml [mcp] extra: FOUND
- 24/24 mcp tests pass; ruff clean.
