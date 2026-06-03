---
title: "Environment variables"
description: "Complete reference for every environment variable horus-os reads, what each controls, and which ones are secrets that must stay server-side."
---

## Overview

horus-os reads configuration from two places: the `config.toml` file in your
[data directory](/reference/configuration/) and process environment variables.
Environment variables hold everything that should never be written to a file:
API keys, tokens, passwords, and runtime gates. The general rule in this repo
is that secrets live in the environment, while durable settings live in
`config.toml`.

This page lists every variable horus-os reads, what it does, and whether it is
a secret. A variable marked **Secret: yes** grants access to a provider account,
mailbox, or remote service. Keep those values out of committed files, shell
history, and any browser-facing surface. See
[Security](/operations/security/) for the threat model behind these rules.

> [!IMPORTANT]
> Variables prefixed with `NEXT_PUBLIC_` are the only ones that are safe to
> expose to a browser. Every other variable on this page is read by the Python
> backend and must stay server-side. Never put a provider key, token, or
> password behind a `NEXT_PUBLIC_` name.

## Core runtime

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_DATA_DIR` | No | Overrides the default data directory. When set, horus-os stores `config.toml`, `horus.sqlite`, the vault (`notes/`), `skills/`, `models/`, and `vectors.sqlite` here instead of the platform default. The path is expanded (`~` is resolved). |
| `HORUS_OS_PRICING_PATH` | No | Path to a custom `pricing.json` for cost accounting. Overrides the `[pricing] path` key in `config.toml` and the bundled pricing table. The env var wins over the TOML value. |
| `HORUS_OS_DISABLE_SCHEDULER` | No | When set to the exact string `true`, the scheduler does not start. `start()` becomes a silent no-op and the runtime boots cleanly with a passing health check. Use this for deployments that must never run scheduled tasks. |
| `HORUS_TZ` | No | IANA timezone name (for example `America/New_York`) used to resolve cron schedules. When unset, horus-os falls back to the system local timezone via `zoneinfo`. |
| `HORUS_OS_DISABLE_PLUGINS` | No | When set to `true`, all plugin discovery and loading is skipped globally. `horus-os serve --disable-all-plugins` sets this internally; you can also set it yourself to run with plugins off. |
| `HORUS_OS_PLUGIN_DIR` | No | Overrides the directory horus-os scans for installed plugins. |
| `HORUS_OS_DEMO` | No | When set to `1`, the server runs in demo mode: integration write endpoints return `403` before performing any write. Used to host a read-only public dashboard. |

> [!NOTE]
> Installing a plugin outside a virtualenv is not gated by an environment
> variable. By default `horus-os plugins install` refuses to run against a
> system (non-virtualenv) Python interpreter. Pass the `--allow-system-python`
> flag to override that check; there is no equivalent env var.

The default data directory (when `HORUS_OS_DATA_DIR` is unset) is platform
specific:

- macOS: `~/Library/Application Support/horus-os`
- Linux: `$XDG_DATA_HOME/horus-os`, or `~/.local/share/horus-os`
- Windows: `%APPDATA%\horus-os`

## Provider keys

These keys authenticate horus-os to the model providers. They are secrets.
The CLI and the dashboard read them straight from the environment and never
persist them.

| Variable | Secret | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Yes | API key for the Anthropic provider. Required when `default = "anthropic"` (the default). |
| `GEMINI_API_KEY` | Yes | API key for the Google Gemini provider. Required when the Gemini provider is selected. |
| `GOOGLE_API_KEY` | Yes | Fallback for the Gemini provider. horus-os reads `GEMINI_API_KEY` first, then `GOOGLE_API_KEY`. |
| `HORUS_OS_LOCAL_API_KEY` | Yes | API key sent to a local OpenAI-compatible model server. Defaults to the literal `horus-local` when unset, which is fine for servers that ignore the key. |
| `HORUS_OS_LOCAL_BASE_URL` | No | Overrides the base URL of the local OpenAI-compatible provider (for example an Ollama endpoint). Takes precedence over the `[local] base_url` value in `config.toml`. |

> [!TIP]
> Set provider keys in your shell profile or a process manager environment,
> not in `config.toml`. If a key is missing, [`horus-os run`](/reference/cli-reference/)
> tells you exactly which variable to set for the selected provider before it
> makes any model call.

## Web search and research

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_WEB_SEARCH_KEY` | Yes | API key for the configured web-search provider (`brave` or `tavily`). Read at tool-registration time and never persisted to `config.toml`. Not required for a self-hosted SearXNG instance. |

The web-search provider and base URL themselves are stored in `config.toml`
under `[tools.web_search]`, not in the environment. See
[Web access](/integrations/web-access/) and
[Autonomous research](/guides/autonomous-research/).

## Shell tool

The shell tool is gated by a runtime environment variable so toggling it never
requires rewriting `config.toml`.

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_SHELL_ENABLED` | No | The runtime gate for the `shell_exec` tool. The tool is registered only when this equals the exact string `true` AND `[shell] enabled` is true in `config.toml`. Both conditions must hold. |

> [!CAUTION]
> Enabling the shell tool lets agents execute commands on the host. Treat
> `HORUS_OS_SHELL_ENABLED=true` as a deliberate, scoped decision. The remaining
> shell limits (timeout, output cap, working directory, type, confirmation) are
> configured in the `[shell]` table of `config.toml`.

## Webhooks and remote triggers

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_WEBHOOK_SECRET` | Yes | HMAC signing secret for the webhook adapter. The adapter refuses to run when this is unset. Inbound requests must carry an `X-Horus-Signature: sha256=<hex>` header where the digest is HMAC-SHA256 of the raw body keyed with this secret. |

See [Remote access](/guides/remote-access/) for how remote triggers are
authenticated.

## Discord

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_DISCORD_TOKEN` | Yes | Discord bot token. Required to start the Discord adapter. |
| `HORUS_OS_DISCORD_GUILD_ID` | No | The Discord server (guild) ID the bot operates in. |
| `HORUS_OS_DISCORD_ADMIN_ROLE_ID` | No | Role ID whose members are treated as admins. |
| `HORUS_OS_DISCORD_CATEGORY` | No | Category name under which managed channels are created. |
| `HORUS_OS_DISCORD_AGENT_PROFILE` | No | Agent profile name the Discord adapter loads. |

See [Discord](/integrations/discord/).

## Slack

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_SLACK_BOT_TOKEN` | Yes | Slack bot token. Required to start the Slack adapter. |
| `HORUS_OS_SLACK_SIGNING_SECRET` | Yes | Slack request-signing secret used to verify inbound events. Required. |
| `HORUS_OS_SLACK_AGENT_PROFILE` | No | Agent profile name the Slack adapter loads. |

See [Slack](/integrations/slack/).

## Email

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_EMAIL_IMAP_HOST` | No | IMAP server hostname. Required to start the email adapter. |
| `HORUS_OS_EMAIL_IMAP_USER` | No | IMAP login username. |
| `HORUS_OS_EMAIL_IMAP_PASSWORD` | Yes | IMAP password or app password. |
| `HORUS_OS_EMAIL_IMAP_PORT` | No | IMAP SSL port. Defaults to `993`. |
| `HORUS_OS_EMAIL_SMTP_HOST` | No | SMTP server hostname for sending. |
| `HORUS_OS_EMAIL_SMTP_USER` | No | SMTP login username. Defaults to the IMAP user. |
| `HORUS_OS_EMAIL_SMTP_PASSWORD` | Yes | SMTP password. Defaults to the IMAP password. |
| `HORUS_OS_EMAIL_SMTP_PORT` | No | SMTP SSL port. Defaults to `465`. |
| `HORUS_OS_EMAIL_POLL_INTERVAL` | No | Seconds between mailbox polls. Defaults to `60`. |
| `HORUS_OS_EMAIL_AGENT_PROFILE` | No | Agent profile name the email adapter loads. |

See [Email](/integrations/email/).

## Calendar

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH` | No | Path to the Google OAuth client JSON file. Required to start the calendar adapter. |
| `HORUS_OS_CALENDAR_WRITE_ALLOWED` | No | When set to the exact string `true`, the create-event tool is registered. Unset or any other value keeps the calendar read-only. The handler re-checks this at call time, so flipping it off mid-run denies writes. |

See [Calendar](/integrations/calendar/).

## GitHub

| Variable | Secret | Purpose |
| --- | --- | --- |
| `GITHUB_TOKEN` | Yes | GitHub personal access token. Optional for public, read-only access, but raises the rate limit and is required to read private repositories. Read server-side only. |

See [GitHub](/integrations/github/).

## Supabase (server-side backend)

These variables configure the Supabase adapter and `horus-os doctor --supabase`.
They are read only by the Python backend and must never reach the browser. The
adapter stays a silent no-op until both are present.

| Variable | Secret | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | No | Your Supabase project URL the backend connects to. |
| `SUPABASE_SERVICE_KEY` | Yes | The Supabase service role key. It bypasses row-level security, so keep it server-side only and never expose it through a `NEXT_PUBLIC_` name. |

The browser-facing Supabase keys (`NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_ANON_KEY`) are separate and documented under
[Dashboard](#dashboard-next_public_). See [Supabase](/integrations/supabase/).

## Vercel and Tailscale

| Variable | Secret | Purpose |
| --- | --- | --- |
| `HORUS_OS_VERCEL_TOKEN` | Yes | Vercel API token. The server uses it to call the Vercel REST API; the token value is never returned to clients. |
| `HORUS_OS_VERCEL_PROJECT_ID` | No | Vercel project ID the deployment status calls target. |
| `HORUS_OS_TAILSCALE_API_KEY` | Yes | Tailscale API key used for the Tailscale integration. |

See [Deploy to Vercel](/operations/deploy-to-vercel/) and
[Remote access](/guides/remote-access/).

## OpenTelemetry

The OTel adapter reads standard OpenTelemetry SDK variables directly, plus one
horus-os-specific gate.

| Variable | Secret | Purpose |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | OTLP collector endpoint the span exporter sends to. Read by the OpenTelemetry SDK. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Sometimes | Headers for the OTLP exporter. May carry an auth token for a hosted backend; treat as a secret in that case. Read by the OpenTelemetry SDK. |
| `HORUS_OS_OTEL_CAPTURE_CONTENT` | No | When set to `true`, opts into capturing message content on spans. Off by default so prompt and response bodies are not exported. |

See [OpenTelemetry](/operations/opentelemetry/) and
[Observability](/operations/observability/).

## Dashboard (NEXT_PUBLIC_*)

These are read by the Next.js dashboard at build time and are baked into the
browser bundle. They are public by design. Never put a secret behind a
`NEXT_PUBLIC_` name.

| Variable | Secret | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE` | No | Backend origin the dashboard fetches `/api` from. Leave unset for same-origin. It is an origin, not a secret. |
| `NEXT_PUBLIC_SUPABASE_URL` | No | Your Supabase project URL for the anon read path. The browser counterpart of the server-side `SUPABASE_URL`. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | No | The Supabase anon key for browser reads. Safe to publish; row-level security is enforced. Never put the service key (`SUPABASE_SERVICE_KEY`) here. |
| `NEXT_PUBLIC_HORUS_DEMO` | No | When `1`, the dashboard renders the public marketing view at `/`. |

> [!WARNING]
> Only the Supabase anon key, never the service key, may be exposed through a
> `NEXT_PUBLIC_` variable. Anyone who can load the dashboard can read these
> values. See [Supabase](/integrations/supabase/) for the row-level-security
> details.

## Secrets at a glance

Treat every variable below as a credential. Keep it out of committed files,
shell history, screenshots, and any browser-facing surface:

- `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `HORUS_OS_LOCAL_API_KEY`
- `HORUS_OS_WEB_SEARCH_KEY`
- `HORUS_OS_WEBHOOK_SECRET`
- `HORUS_OS_DISCORD_TOKEN`
- `HORUS_OS_SLACK_BOT_TOKEN`, `HORUS_OS_SLACK_SIGNING_SECRET`
- `HORUS_OS_EMAIL_IMAP_PASSWORD`, `HORUS_OS_EMAIL_SMTP_PASSWORD`
- `GITHUB_TOKEN`
- `SUPABASE_SERVICE_KEY`
- `HORUS_OS_VERCEL_TOKEN`, `HORUS_OS_TAILSCALE_API_KEY`
- `OTEL_EXPORTER_OTLP_HEADERS` (when it carries an auth token)

## See also

- [Configuration reference](/reference/configuration/)
- [Security](/operations/security/)
- [Integrations overview](/integrations/overview/)
- [CLI reference](/reference/cli-reference/)
