---
title: "MCP servers"
description: "Connect Model Context Protocol servers to horus-os so their tools become agent-callable, under an explicit opt-in trust model."
---

## What MCP gives you

The Model Context Protocol (MCP) is the industry-standard wire protocol for exposing tools to an LLM agent. A server speaks MCP, a client connects, lists the server's tools, and calls them. horus-os ships a single MCP client, so any MCP server in the ecosystem becomes a set of horus-os tools with no fork of the core and no per-server adapter. A filesystem server, a browser-automation server, a database server: each is one configuration block away from being agent-callable.

Once registered, MCP tools are not special. They land in the same tool registry your builtin tools live in, so the agent loop calls them and traces them exactly like a builtin. There is no separate schema and no separate code path.

> [!IMPORTANT]
> A configured MCP server is trusted code, the same as installing a plugin. Read [The trust model](#the-trust-model) and [Threat model](#threat-model) before you add a server you did not author yourself.

## Install the extra

The MCP client depends on the official `mcp` Python SDK, kept fully optional. Install the `mcp` extra (or `all`, which includes it):

```bash
pip install 'horus-os[mcp]'
```

A bare install can import the MCP client package without the SDK present. The SDK is only required when a server actually starts, so installing the extra is what makes a configured server connect.

## The trust model

MCP servers are added only by editing `mcp.toml`. Nothing auto-discovers a server, probes the network, or registers a tool you did not list. An absent or empty `mcp.toml` registers zero MCP tools: the file is the single activation surface. Adding a server block is the one conscious act that turns a server on, the same posture as installing a plugin.

This is a blocking guarantee, not a default you can accidentally weaken. With no `mcp.toml`, horus-os boots with only its builtin tools and the MCP registry registers nothing.

## Configure servers in mcp.toml

`mcp.toml` lives at `<data_dir>/mcp.toml`, the same data directory your `config.toml` and database use (see [Configuration](/getting-started/configuration/)). Each server is one `[[mcp.servers]]` block. Every block needs a `name` and a `transport`.

A stdio server is a subprocess that horus-os spawns. It uses `command`, plus optional `args` and `env`:

```toml
[[mcp.servers]]
name = "filesystem"
transport = "stdio"
command = ["npx", "@modelcontextprotocol/server-filesystem", "/tmp"]

[[mcp.servers]]
name = "playwright"
transport = "stdio"
command = ["npx", "@playwright/mcp@latest"]
```

A remote server connects to a local or remote HTTP endpoint and uses `url`:

```toml
[[mcp.servers]]
name = "remote"
transport = "streamable-http"
url = "http://localhost:8000/mcp"
```

### Supported transports

| transport | shape | fields |
|-----------|-------|--------|
| `stdio` | spawn a subprocess and speak MCP over its stdin/stdout | `command`, `args`, `env` |
| `sse` | connect to a Server-Sent-Events HTTP endpoint | `url` |
| `streamable-http` | connect to a Streamable HTTP endpoint (the current remote default) | `url` |

A block that names any other transport, for example the deprecated `websocket`, is skipped at load time and never reaches the client. A malformed or unreadable `mcp.toml` is treated as "no servers": the trust gate stays closed and horus-os never crashes on a bad file.

> [!TIP]
> Restart `horus-os serve` after editing `mcp.toml`. Server connection and tool registration happen at startup.

## How MCP tools reach your agents

Every discovered MCP tool registers under a server-scoped name, `mcp:{server}:{tool}`. A filesystem server advertising a tool named `read_file` registers as `mcp:filesystem:read_file`, not `read_file`. The prefix is the defense: it keeps an MCP tool from shadowing a horus-os builtin, and it lets two servers advertise the same tool name with no collision. Two servers each exposing `search` register as `mcp:alpha:search` and `mcp:beta:search`.

As with builtin tools, an agent profile must list a tool in its `allowed_tools` before the agent can call it. Use the namespaced `mcp:{server}:{tool}` name there.

### Collision refusal

The tool registry refuses to register any MCP tool whose final name would land on a reserved builtin name. It raises a `CollisionError` rather than silently overwriting the builtin or dropping the MCP tool. The refusal is recorded against that server and surfaced, never swallowed, and one server's collision does not abort registration of your other servers. A configured MCP server can never shadow a builtin like `read_file`.

### Description sanitization

A tool description is metadata that an agent's system prompt usually includes, and an MCP server controls it. A hostile server can hide prompt-injection instructions in a description, or hide them in invisible Unicode tag characters (U+E0000 through U+E007F) that the model reads but a human reviewer does not see. This attack class is called tool poisoning.

Every description from an external server flows through a sanitizer before it reaches the model: Unicode tag characters and other zero-width and format control characters are stripped, and the result is length-capped. Sanitization never raises on malformed input. This removes the invisible-instruction surface, but it does not make an untrusted server safe to configure. Read the description of any tool you enable.

### Tracing

Because an MCP tool is an ordinary registry entry, every MCP tool call publishes a `tool_invocations` trace row identical in shape to a builtin tool call: same fields, same status enum, same `trace_id` threading. An MCP call cannot bypass tracing. The trace row records the `mcp:{server}:{tool}` name, so you can tell MCP calls apart from builtin calls in the dashboard. As with builtin tools, only the exception class name is persisted on a failure, never the message body, so a server-supplied error string cannot leak content into the trace store. See [Traces and observability](/concepts/traces-and-observability/).

### Subprocess teardown

A stdio server is a real child process. horus-os reclaims it on shutdown on every supported OS with an explicit `terminate` then bounded `wait` then `kill` teardown that runs independently of the SDK's own lifespan cleanup. This teardown is idempotent, and a real-subprocess no-zombie test runs on macOS, Ubuntu, and Windows in CI.

## Check your configuration

`horus-os doctor --mcp` reports your configured MCP servers without connecting to them. With no `mcp.toml` it prints the opt-in default and exits 0:

```text
MCP: no servers configured (opt-in via mcp.toml)
```

The opt-in default is healthy, never an error. With servers configured it prints one line per server (name, transport, and the command or url it points at) plus the total count, then reminds you to run the server to register and trace the tools:

```text
MCP: 2 server(s) configured in /Users/you/Library/Application Support/horus-os/mcp.toml
  filesystem: transport=stdio -> npx @modelcontextprotocol/server-filesystem /tmp
  remote: transport=streamable-http -> http://localhost:8000/mcp
  note: run the server (horus-os serve) to register and trace mcp:{server}:{tool} tools.
```

## Threat model

A configured MCP server is trusted by the act of configuring it, exactly like installing a plugin. The act of adding a `[[mcp.servers]]` block is the trust decision. The guarantees below bound what that trusted server can do, they do not make an untrusted server safe.

The client enforces four trust guarantees:

1. **Trust gate (opt-in).** Servers activate only through `mcp.toml`. No file means no servers, no network probe, and zero registered tools. The client never connects to a server you did not list.
2. **Namespacing and collision refusal.** Every MCP tool is `mcp:{server}:{tool}`. The registry refuses any name that would shadow a builtin and surfaces the refusal. A configured server cannot replace `read_file` or any other builtin.
3. **Description sanitization.** Unicode tag characters and zero-width or format control characters are stripped and the description is length-capped before it reaches the model, defending against tool poisoning. Sanitization never crashes registration.
4. **Subprocess teardown.** stdio subprocesses get an explicit, idempotent, cross-OS teardown that does not depend on the SDK lifespan, so no zombie process survives shutdown on any OS, Windows included.

What this does not defend against: a server you configured is trusted code. It can return any tool result, and the agent may act on that result. Description sanitization removes invisible instructions but does not judge the semantics of a visible description, and it does not police tool results. Collision refusal stops a server from shadowing a builtin, but a server can still expose brand-new tools that do whatever the server author wrote. If you do not trust the server author, do not add the server to `mcp.toml`.

## Troubleshooting

When a server fails to connect at startup, the failure is recorded against that server and the rest of your servers still register. One bad server never denies you the others. To diagnose:

- Confirm the `command` for a stdio server is runnable on its own. For example, run the `npx ...` command in a shell and check it starts.
- Confirm the `url` for an `sse` or `streamable-http` server is reachable.
- Re-check the `transport` value. A typo or an unsupported transport silently skips the block at load time, so the server simply will not appear.
- Check the description of each tool the server advertises before relying on it.

## See also

- [Integrations overview](/integrations/overview/)
- [Plugins](/extending/plugins/)
- [Plugin security](/extending/plugin-security/)
- [Traces and observability](/concepts/traces-and-observability/)
