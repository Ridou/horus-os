---
title: "Discord"
description: "Connect horus-os to a Discord bot for mention and DM replies, plus a control channel with slash commands and thread-based task dispatch."
---

## Overview

The Discord integration connects horus-os to a Discord bot. The base adapter listens for mentions in guild channels and direct messages, runs your configured agent profile, and replies in-channel. It uses the gateway connection from `discord.py`, not webhooks.

A control-bot extension adds guild-scoped slash commands, a dedicated set of control channels, thread-based task dispatch, status cards (rich embeds), and reaction-based feedback. The control-bot features require two extra environment variables on top of the bot token.

For how integrations fit together, see [Integrations overview](/integrations/overview/).

## Prerequisites

The Discord SDK is not a core dependency. Install the optional extra:

```bash
pip install 'horus-os[discord]'
```

This pulls in `discord.py>=2.4`. The adapter module loads even without this extra, but `start` then records a clear "discord.py is not installed" error in the adapter registry and the adapter stays offline. Other adapters continue to run.

## Create a Discord application and bot

1. Sign in at https://discord.com/developers/applications
2. Click "New Application", give it a name (for example, `horus-os-bot`), and accept the developer terms.
3. In the left sidebar select "Bot".
4. Click "Reset Token" and copy the token. Treat it like a password. You paste it into an environment variable later, and the value must never land in source control.

> [!WARNING]
> The bot token is the only credential the integration needs. Treat it like a password and never commit it. If it leaks, reset it in the Developer Portal (Bot tab, Reset Token).

## Enable the Message Content intent

In the "Bot" tab, scroll to "Privileged Gateway Intents" and toggle on:

- "Message Content Intent"
- "Server Members Intent" (optional, only if you want member metadata)

The adapter sets `intents.message_content = True` in code, but that is a necessary condition, not a sufficient one. You must also toggle the intent in the Developer Portal:

1. Go to https://discord.com/developers/applications
2. Select your application.
3. In the left sidebar, select "Bot".
4. Scroll to "Privileged Gateway Intents".
5. Toggle on "Message Content Intent".
6. Save changes.

Without this portal toggle, the bot connects and appears online, but every inbound `message.content` is an empty string, and the bot will not respond to any message. This is the single most common gotcha.

> [!IMPORTANT]
> Discord caches intent state per-connection. After toggling the Message Content Intent, restart `horus-os serve` so the bot reconnects and picks up the new setting.

The adapter also requests the `guilds`, `guild_messages`, and `dm_messages` intents. Those are not privileged and need no portal toggle.

## Generate a minimal-permission invite

The bot needs only the permissions required to read and reply, manage threads, and add reactions. Do not grant Administrator.

The permission integer for the full control-bot feature set is `292057869376`. It covers:

| Permission | Bit |
|------------|-----|
| View Channels | `1 << 10` |
| Send Messages | `1 << 11` |
| Add Reactions | `1 << 6` |
| Manage Messages | `1 << 13` |
| Embed Links | `1 << 14` |
| Read Message History | `1 << 16` |
| Create Public Threads | `1 << 34` |
| Send Messages in Threads | `1 << 38` |

The safest approach is to construct the invite URL manually with this integer:

```text
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot+applications.commands&permissions=292057869376
```

Replace `YOUR_CLIENT_ID` with the Application ID from your Developer Portal Overview page. The `applications.commands` scope is required for slash command registration. The token stays the only credential; `applications.commands` is a scope, not a separate key.

Open the URL in a browser, pick a server you own, and authorize. The bot then appears in the server member list and can be mentioned in any channel where it has read and write access.

> [!WARNING]
> Never grant the Administrator permission (`1 << 3`, integer `8`). It gives the bot full control over the server. If the token is ever compromised, an attacker gains complete server admin access. The minimal integer above covers everything the control bot needs.

## Configure environment variables

Set these on the machine that runs `horus-os serve`.

The base adapter (mentions and DMs) needs only the token:

```bash
export HORUS_OS_DISCORD_TOKEN=your-bot-token-here
```

The control-bot features (guild slash commands, thread dispatch, admin-gated setup) also need the guild ID and the admin role ID:

```bash
# The numeric ID of your Discord server (guild).
# With Developer Mode on, right-click the server name and copy the server ID.
export HORUS_OS_DISCORD_GUILD_ID=your-guild-id-here

# The numeric role ID that gates /horus-setup.
# With Developer Mode on, right-click the role in Server Settings > Roles
# and copy the role ID.
export HORUS_OS_DISCORD_ADMIN_ROLE_ID=your-admin-role-id-here
```

Optional settings:

```bash
# Name of the control category created by /horus-setup. Defaults to "horus-os".
export HORUS_OS_DISCORD_CATEGORY=horus-os

# Which agent profile to use. Defaults to "default".
export HORUS_OS_DISCORD_AGENT_PROFILE=writer
```

> [!CAUTION]
> Never commit a real token or ID. Use a `.env` file that your deploy excludes from git, or your platform's secrets manager.

To find IDs, enable Developer Mode in Discord under Settings > Advanced > Developer Mode. You can then right-click a server, role, or channel and copy its numeric ID.

## Run and verify

Start the server:

```bash
horus-os serve
```

The bot should show as online in your server's member list. The first request after server start fires the FastAPI lifespan, which calls the adapter's `start` and opens the gateway connection.

In a guild channel where the bot can see messages:

```text
@your-bot-name hello
```

In a direct message to the bot, send any message at all. The bot replies in the same channel or DM. For responses longer than 2000 characters, the adapter splits the reply into multiple sequential messages.

You can confirm adapter status without leaving Discord by hitting `GET /api/adapters` on the local dashboard. The `discord` entry shows `status: running` and a recent `last_activity_at`.

## The control channels and thread dispatch

After you run `/horus-setup` (see [Slash commands](#slash-commands)), the bot creates, or confirms the existence of, three text channels inside a `horus-os` category: `#horus`, `#horus-tasks`, and `#horus-activity`. The category name is configurable via `HORUS_OS_DISCORD_CATEGORY`. The thread-dispatch flow described below runs from the `#horus` channel.

The thread-dispatch flow:

1. A guild member types a prompt in `#horus` as a plain message, with no mention required.
2. The bot creates a public thread named after the first few words of the prompt.
3. The agent runs inside `asyncio.to_thread`, so it does not block the gateway.
4. When the run completes, the bot posts a status card (an embed) into the thread. The embed has three fields: the status, the agent (the provider name, or `unknown` if none is set), and the result.
5. Guild members react with thumbs-up or thumbs-down to record feedback.
6. The bot reads raw reaction events (`on_raw_reaction_add`), so feedback works even after the internal message cache expires.

## Slash commands

All slash commands are guild-scoped, which means instant registration with no one-hour delay. They are available only in the guild specified by `HORUS_OS_DISCORD_GUILD_ID`.

| Command | Permission gate | Description |
|---------|-----------------|-------------|
| `/horus-setup` | Admin role required | Idempotent channel bootstrap. Creates the `horus-os` category and the `#horus`, `#horus-tasks`, and `#horus-activity` text channels if absent. Safe to run multiple times, and never deletes existing channels. |

### Admin-role gate

`HORUS_OS_DISCORD_ADMIN_ROLE_ID` must be set to the numeric ID of a role in your server. Only members who hold that role can run `/horus-setup`.

If `HORUS_OS_DISCORD_ADMIN_ROLE_ID` is not set, the adapter records an error at startup and the control-bot features stay offline. The base mention and DM functionality is unaffected.

## Scope and limitations

The base adapter does not do per-channel agent routing (a single profile applies to all channels), token-by-token streaming (the full response is awaited then chunked), or voice channels and file uploads. The control-bot extension adds slash commands, reaction-based feedback, and outbound status cards posted into dispatch threads.

## Troubleshooting

### The bot is online but every message body is empty

The Message Content Intent is off. Toggle it on in the Developer Portal under Bot, then restart `horus-os serve`. Discord caches intent state per-connection, so the bot must reconnect to pick up the new toggle.

### The bot does not respond at all

Check that the bot has "Send Messages" permission in the channel. Right-click the channel, choose Edit Channel, then Permissions. If a permission overwrite denies the bot's role, the gateway event still fires but the reply send fails silently, because the adapter suppresses the exception to keep the connection open.

### 401 Unauthorized on connect

The token is wrong or was rotated. Mint a new one in the Developer Portal (Bot tab, Reset Token), update `HORUS_OS_DISCORD_TOKEN`, and restart.

### The bot reconnects in a loop

`discord.py` retries with exponential backoff on transient network failures. If the attempts never succeed, check the server log for the underlying transport error. Common causes are an outbound firewall blocking the gateway WebSocket (`wss://gateway.discord.gg`), a token rotated mid-run, or rate limiting from too many recent reconnects (Discord returns a 4014 close code and the library backs off).

### Status endpoint shows error: discord.py is not installed

You installed `horus-os` without the `discord` extra. Run `pip install 'horus-os[discord]'` and restart the server.

### Adapter status stays at error: HORUS_OS_DISCORD_TOKEN is not set

The env var is empty or unset in the process that started `horus-os serve`. If you exported it after launching the server, the existing process did not inherit it. Restart the server.

## See also

- [Integrations overview](/integrations/overview/)
- [Slack](/integrations/slack/)
- [Environment variables](/reference/environment-variables/)
- [Running as a service](/guides/running-as-a-service/)
