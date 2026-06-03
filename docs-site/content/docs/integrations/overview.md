---
title: "Integrations overview"
description: "How horus-os integrations work, why every one is opt-in and configured by environment variables, and how to check status from the dashboard."
---

## What an integration is

An integration connects horus-os to a service you already use: an AI provider, a chat surface, your inbox, your calendar, a code host, or a database. Each one is a small, self-contained connector that the runtime discovers and wires in at startup.

Every integration is opt-in. horus-os starts and runs the full local stack (the CLI, the agent loop, SQLite storage, the markdown vault, and traces) with zero cloud configuration. Nothing reaches a third party until you turn an integration on. You turn one on by setting its environment variables; horus-os never requires an account, a hosted backend, or a sign-up to run.

> [!NOTE]
> Installing a pip extra (for example `discord` or `slack`) only makes that integration's dependency available. It does not activate the integration. You still enable a feature with environment variables or config. See [Configuration](/getting-started/configuration/) for the full picture.

## Configuration is environment variables only

You configure every integration with environment variables. The runtime reads them from the process environment, so you can export them in your shell, place them in a `.env` file inside your data directory, or supply them through your platform's secrets manager.

```bash
# Two AI providers (set at least one)
export ANTHROPIC_API_KEY=your-anthropic-key
export GEMINI_API_KEY=your-gemini-key

# Example of one opt-in integration: Discord
export HORUS_OS_DISCORD_TOKEN=your-bot-token
export HORUS_OS_DISCORD_GUILD_ID=your-guild-id
export HORUS_OS_DISCORD_ADMIN_ROLE_ID=your-admin-role-id
```

> [!IMPORTANT]
> Credentials are never committed and never stored in `config.toml`. Keep tokens out of source control. The dashboard, when you save a key from a loopback request, writes it to a `.env` file in your data directory at mode 0600 on POSIX systems, and only ever stores a hash of the value, never the value itself.

## The integration registry

horus-os ships a fixed registry of integration connectors. Each entry declares an id, a display name, a category, a short description, the primary environment variable, the full set of variables it requires, and the URL where you obtain a credential. The registry is the single source of truth behind the dashboard Integrations page.

| Integration | Category | Primary variable | Also requires |
|-------------|----------|------------------|---------------|
| Anthropic | AI Provider | `ANTHROPIC_API_KEY` | (none) |
| Gemini | AI Provider | `GEMINI_API_KEY` | (none) |
| Discord | Communication | `HORUS_OS_DISCORD_TOKEN` | `HORUS_OS_DISCORD_GUILD_ID`, `HORUS_OS_DISCORD_ADMIN_ROLE_ID` |
| Slack | Communication | `HORUS_OS_SLACK_BOT_TOKEN` | `HORUS_OS_SLACK_SIGNING_SECRET` |
| Email | Communication | `HORUS_OS_EMAIL_IMAP_HOST` | `HORUS_OS_EMAIL_IMAP_USER`, `HORUS_OS_EMAIL_IMAP_PASSWORD`, `HORUS_OS_EMAIL_SMTP_HOST` |
| Calendar | Productivity | `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH` | (none) |
| GitHub | Developer | `GITHUB_TOKEN` | (none) |
| Supabase | Database | `SUPABASE_URL` | `SUPABASE_SERVICE_KEY` |
| Vercel | Deploy | `HORUS_OS_VERCEL_TOKEN` | (none) |
| Tailscale | Network | `HORUS_OS_TAILSCALE_API_KEY` | (none) |

The two AI providers are first-class: you need at least one provider key for agents to call a model. The rest are pure opt-in connectors that add a surface or a tool. For full per-integration setup, see the dedicated pages below.

## Integration status on the dashboard

Open the dashboard with `horus-os serve` (default http://127.0.0.1:8765) and go to the Integrations page. It lists every registry entry with a live status derived only from environment variable presence and an optional verification record. The status is computed on each request from `bool(os.environ.get(var))`; the value of a variable is never read into the response, logged, or stored.

Each integration shows one of three statuses:

- **missing**: One or more of the integration's required variables is not set. The integration is off.
- **configured-unverified**: Every required variable is set, but the credential has not been verified (or was changed since the last verification). The integration is configured but its credential has not been confirmed to work.
- **verified**: Every required variable is set and a verification probe confirmed the credential. If you later rotate the key, the status falls back to `configured-unverified` automatically, because the stored hash no longer matches.

> [!TIP]
> Because status is recomputed from the environment on every request, you do not need to restart anything for the dashboard to reflect a newly set variable in a freshly launched process. Note that a long-running `horus-os serve` process only sees variables that were present when it started, so export your variables before launching, or save them from the dashboard.

## Verifying a configured integration

Setting variables turns an integration on. Verifying confirms the credential actually works. The dashboard can run a verification probe for the integrations that have one, and records the result so the status becomes `verified`.

Verification probes exist for these integrations:

- **Anthropic**: makes a minimal Claude API call.
- **Gemini**: makes a minimal Gemini API call.
- **GitHub**: calls the GitHub API to confirm the token.

Other integrations report `configured-unverified` once their variables are set, since they have no probe; verify them by exercising the integration directly (for example, mention your Discord bot, or send the calendar adapter a request).

> [!NOTE]
> The save-key and verify endpoints are loopback-only. They accept requests only from a loopback address (decided from the TCP socket peer, never from a forwarded header), and they refuse to run when `HORUS_OS_DEMO=1`. A probe error returns only the exception class name, never the credential.

You can also check whether an adapter actually came online. Adapter-backed integrations register on startup and surface a per-adapter status snapshot:

```bash
curl http://127.0.0.1:8765/api/adapters
```

A successfully started adapter shows `status: running` with a recent `last_activity_at`. A misconfiguration (for example a missing token, or a missing pip extra) shows `status: error` with a message, while every other adapter keeps running. See [Traces and observability](/concepts/traces-and-observability/) and [Dashboard](/guides/dashboard/) for more on reading status.

## Per-integration guides

- [Discord](/integrations/discord/): control bot with thread dispatch, slash commands, and reaction feedback.
- [Slack](/integrations/slack/): post messages and handle events via a Slack app.
- [Email](/integrations/email/): read and send mail over IMAP and SMTP.
- [Calendar](/integrations/calendar/): read and write Google Calendar events.
- [MCP](/integrations/mcp/): connect Model Context Protocol servers as tools.
- [Web access](/integrations/web-access/): bring-your-own web search and guarded fetch.
- [GitHub](/integrations/github/): query repositories, issues, and pull requests.
- [Supabase](/integrations/supabase/): mirror agent state and traces to a remote Postgres instance.

## Next steps

- [Configuration](/getting-started/configuration/): where horus-os reads variables and config from.
- [Environment variables](/reference/environment-variables/): the full variable reference.
- [Plugins](/extending/plugins/): add third-party tools and adapters beyond the built-in registry.
- [Writing an adapter](/extending/writing-an-adapter/): build your own integration.
