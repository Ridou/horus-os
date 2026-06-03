---
title: "Web access"
description: "Give agents a bring-your-own web_search tool with SearXNG, Brave, or Tavily; off by default, enabled per provider, with the API key supplied only by env var."
---

## Overview

horus-os ships no built-in search engine and no default network reach for the agent. Web access is opt-in: the `web_search` tool is absent from the agent registry until you configure a provider. This is default-deny. A fresh install cannot search the web until you add a `[tools.web_search]` block to your `config.toml`.

When you do enable it, you bring your own provider. horus-os supports three: a self-hosted SearXNG instance, the Brave Search API, and the Tavily API. The provider API key is read from an environment variable at runtime and is never written to disk.

> [!NOTE]
> Web access requires the `web` extra. Install it with `pip install 'horus-os[web]'`, or pick it up as part of `pip install 'horus-os[all]'`. See [Installation](/getting-started/installation/).

## Enable web search

Add a `[tools.web_search]` block to `<data_dir>/config.toml`. The `provider` key is required and must be one of `searxng`, `brave`, or `tavily`. The `base_url` key is required for SearXNG (it points at your instance) and optional for the hosted providers.

```toml
[tools.web_search]
provider = "searxng"
base_url = "http://localhost:8888"
```

With this block present and a valid configuration, the `web_search` tool registers and the agent can search. Remove the block (or leave it out) and the tool disappears entirely. There is no partial state: the agent either has the tool or it does not.

> [!IMPORTANT]
> The provider API key is never stored in `config.toml`. Set it with the `HORUS_OS_WEB_SEARCH_KEY` environment variable. horus-os reads the key at tool-registration time and keeps it out of all committed text.

## Providers

### SearXNG

SearXNG is the default and recommended provider. It is a self-hosted metasearch engine, so no API key is involved. Point `base_url` at your running instance.

```toml
[tools.web_search]
provider = "searxng"
base_url = "http://localhost:8888"
```

The `base_url` is required for SearXNG. Without it the provider cannot reach an instance.

### Brave

The Brave Search API. The `base_url` is optional and defaults to the public Brave endpoint, so you usually omit it. Supply your key via the environment variable.

```toml
[tools.web_search]
provider = "brave"
```

```bash
export HORUS_OS_WEB_SEARCH_KEY="your-brave-api-key"
```

### Tavily

The Tavily API. As with Brave, `base_url` is optional and defaults to the public Tavily endpoint, and the key comes from the environment.

```toml
[tools.web_search]
provider = "tavily"
```

```bash
export HORUS_OS_WEB_SEARCH_KEY="your-tavily-api-key"
```

## Result shape

Every provider returns results normalized to the same shape, so the agent sees one consistent format regardless of which backend you chose:

```json
{
  "title": "...",
  "url": "...",
  "snippet": "..."
}
```

## Configuration reference

The web-search settings live under `[tools.web_search]` in `<data_dir>/config.toml`.

| Key | Required | Maps to | Description |
| --- | --- | --- | --- |
| `provider` | yes | `web_search_provider` | One of `searxng`, `brave`, `tavily`. Its presence is what registers the tool. |
| `base_url` | SearXNG only | `web_search_base_url` | Your SearXNG instance URL. Optional (and defaults to the public endpoint) for Brave and Tavily. |

The API key is supplied separately via the `HORUS_OS_WEB_SEARCH_KEY` environment variable and is not a config key. See [Environment variables](/reference/environment-variables/) and [Configuration](/reference/configuration/) for the full picture.

> [!TIP]
> Find your data directory and `config.toml` location with the defaults documented in [Configuration](/getting-started/configuration/). On macOS it is `~/Library/Application Support/horus-os`, on Linux `~/.local/share/horus-os` (or `$XDG_DATA_HOME/horus-os`), and on Windows `%APPDATA%\horus-os`. Override it with `HORUS_OS_DATA_DIR`.

## Security

### Default-deny

Web access starts off. Until you add a `[tools.web_search]` block, the registry has no `web_search` entry and the agent has no way to reach the web. Enabling a provider is a deliberate, single edit you make.

### SSRF guard

Every outbound web-search request runs its URL through an SSRF (server-side request forgery) guard before a socket opens, and the guard re-checks on every redirect hop. A provider URL or redirect that resolves to a loopback, private, link-local, or cloud-metadata address is refused. The cloud-metadata address `169.254.169.254` and private network ranges are blocked on the search fetch path.

### Secrets stay out of config

The provider key is read from `HORUS_OS_WEB_SEARCH_KEY` at runtime and is never persisted to `config.toml`. Keep the key in your shell environment, a secrets manager, or a `.env` file you do not commit. Rotating the key means changing the environment variable, not editing the config.

For the broader security model, see [Security](/operations/security/).

## Use it in autonomous research

The `web_search` tool is the foundation for autonomous research runs, where an agent fans out searches, gathers sources, and synthesizes findings. Research has its own hard caps (`max_sources` and `max_iterations` under a `[research]` config section) and is documented separately.

See [Autonomous research](/guides/autonomous-research/) for the full workflow.

## Next steps

- [Autonomous research](/guides/autonomous-research/) walks through multi-source research runs that build on `web_search`.
- [Environment variables](/reference/environment-variables/) lists `HORUS_OS_WEB_SEARCH_KEY` and the rest.
- [Configuration](/getting-started/configuration/) explains the `config.toml` layout and data directory.
- [Integrations overview](/integrations/overview/) covers the other opt-in capabilities.
