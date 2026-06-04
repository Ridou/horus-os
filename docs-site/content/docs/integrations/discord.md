---
title: "Discord"
description: "Connect horus-os to a Discord bot for mention and DM replies, plus a control channel with slash commands and thread-based task dispatch."
---

## Overview

The Discord integration connects horus-os to a Discord bot. The base adapter listens for mentions in guild channels and direct messages, runs your configured agent profile, and replies in-channel. It uses the gateway connection from `discord.py`, not webhooks.

A control-bot extension adds guild-scoped slash commands, a managed set of control channels, thread-based task dispatch, status cards (rich embeds), and reaction-based feedback. The control-bot features require two extra environment variables on top of the bot token.

This guide takes you from zero to an agent answering you in your own server. Follow the steps in order. For how integrations fit together, see [Integrations overview](/integrations/overview/).

> [!NOTE]
> This is the opt-in adapter that connects horus-os to a Discord server you run. For project help and discussion, join the [community Discord](https://discord.gg/vwX9WvwQhp), where `#help` is a searchable forum.

## 1. Install the optional extra

The Discord SDK is not a core dependency. Install the optional extra:

```bash
pip install 'horus-os[discord]'
```

This pulls in `discord.py>=2.4`. The adapter module loads even without this extra, but `start` then records a clear "discord.py is not installed" error in the adapter registry and the adapter stays offline. Other adapters continue to run.

## 2. Create a Discord application and bot

1. Sign in at https://discord.com/developers/applications
2. Click "New Application", give it a name (for example, `horus-os-bot`), and accept the developer terms.
3. From the application's "Overview" page, copy the "Application ID". You need it in step 4 to build the invite URL.
4. In the left sidebar select "Bot".
5. Click "Reset Token" and copy the token. Treat it like a password. You paste it into an environment variable later, and the value must never land in source control.

> [!WARNING]
> The bot token is the only credential the integration needs. Treat it like a password and never commit it. If it leaks, reset it in the Developer Portal (Bot tab, Reset Token).

## 3. Enable the Privileged Gateway Intents

The adapter requests four gateway intents in code: `guilds`, `guild_messages`, `dm_messages`, and `message_content`. Each earns its place:

- `guilds` lets the bot see the servers it is in and their channels, which `/horus-setup` needs to find or create the managed channels.
- `guild_messages` delivers the message events that the `#horus` thread-dispatch flow listens for.
- `dm_messages` delivers direct messages so the base adapter can answer you in a DM.
- `message_content` is the privileged one. Without it the bot connects and shows as online, but every inbound `message.content` is an empty string, so it will not respond to anything you type. This is the single most common gotcha.

The first three intents are not privileged and need no portal toggle. The `message_content` intent is privileged, so even though the adapter sets `intents.message_content = True` in code, you must also turn it on by hand:

1. Go to https://discord.com/developers/applications
2. Select your application.
3. In the left sidebar, select "Bot".
4. Scroll to "Privileged Gateway Intents".
5. Toggle on "Message Content Intent".
6. (Optional) Toggle on "Server Members Intent" only if you want member metadata. The adapter does not require it.
7. Save changes.

> [!IMPORTANT]
> Discord caches intent state per-connection. After toggling the Message Content Intent, restart `horus-os serve` so the bot reconnects and picks up the new setting.

## 4. Build the OAuth2 invite URL

The bot needs enough permission to read messages, reply, manage the control channels, and post in threads, so it can act as a channel admin for the layout it manages. Do not grant Administrator.

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

The fastest way is to build the URL by hand with the integer already set:

```text
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot+applications.commands&permissions=292057869376
```

Replace `YOUR_CLIENT_ID` with the Application ID you copied in step 2. The `applications.commands` scope is required for slash command registration. The token stays the only credential; `applications.commands` is a scope, not a separate key.

If you prefer the portal, select "OAuth2" then "URL Generator" in the left sidebar, check `bot` and `applications.commands` under "Scopes", and check View Channels, Send Messages, Read Message History, Add Reactions, Embed Links, Manage Messages, Create Public Threads, and Send Messages in Threads under "Bot Permissions". Copy the generated URL at the bottom.

Either way, open the URL in a browser, pick a server you own, and authorize. The bot then appears in the server member list and can be mentioned in any channel where it has read and write access.

> [!WARNING]
> Never grant the Administrator permission (`1 << 3`, integer `8`). It gives the bot full control over the server. If the token is ever compromised, an attacker gains complete server admin access. The minimal integer above already covers everything the control bot needs, including managing the control channels.

## 5. Configure environment variables

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

# Which agent profile answers. Defaults to "default". See "Choosing which agent answers" below.
export HORUS_OS_DISCORD_AGENT_PROFILE=Atlas
```

To find IDs, enable Developer Mode in Discord under Settings > Advanced > Developer Mode. You can then right-click a server, role, or channel and copy its numeric ID.

> [!CAUTION]
> Never commit a real token or ID. Use a `.env` file that your deploy excludes from git, or your platform's secrets manager.

## 6. Run the server

Start the server:

```bash
horus-os serve
```

The bot should show as online in your server's member list. The first request after server start fires the FastAPI lifespan, which calls the adapter's `start` and opens the gateway connection.

You can confirm adapter status without leaving Discord by hitting `GET /api/adapters` on the local dashboard. The `discord` entry shows `status: running` and a recent `last_activity_at`.

## 7. Bootstrap the channel layout with /horus-setup

In your server, run the slash command:

```text
/horus-setup
```

Only a member who holds the role you set in `HORUS_OS_DISCORD_ADMIN_ROLE_ID` can run it. Anyone else gets an ephemeral "You do not have the required admin role" reply.

The command is an idempotent, create-only bootstrap. It finds or creates a category (named `horus-os` by default, or whatever you set in `HORUS_OS_DISCORD_CATEGORY`) and then creates these channels if they are absent: `#horus` (the control channel for thread dispatch), `#horus-tasks`, and `#horus-activity`. It only creates channels that do not already exist and never deletes any channel, so it is safe to run again at any time.

## 8. Talk to the agent in #horus

Type a prompt in `#horus` as a plain message, with no mention required:

```text
Plan a two-day trip to Kyoto.
```

The bot then:

1. Creates a public thread named after the first few words of your prompt.
2. Posts a "Processing..." placeholder in the thread.
3. Runs the agent inside `asyncio.to_thread`, so it does not block the gateway.
4. Edits the placeholder into a status card (an embed) with three fields: the status, the agent (the provider name, or `unknown` if none is set), and the result.
5. Records your thumbs-up or thumbs-down reaction as feedback. The bot reads raw reaction events (`on_raw_reaction_add`), so feedback works even after the internal message cache expires.

You can also mention the bot in any channel it can read, or send it a direct message, to use the base mention and DM path. For replies longer than 2000 characters, the adapter splits the message into multiple sequential posts.

## Choosing which agent answers

`HORUS_OS_DISCORD_AGENT_PROFILE` selects which agent profile answers. On each turn the adapter loads the profile by that exact name and uses its system prompt and recommended model. If the value is unset it defaults to `default`, and a missing profile is non-fatal: the agent still runs with the runtime defaults.

Point it at an installed store agent to give the bot a persona. The store ships three featured agents: Atlas (a travel planner), Vitriol, and Sol (a reflective companion). Installing a bundle creates a database profile keyed by its display name, so once you install Atlas you set:

```bash
export HORUS_OS_DISCORD_AGENT_PROFILE=Atlas
```

The value must match the profile name exactly (for example `Atlas`, not `atlas`). Restart `horus-os serve` after changing it so the new value is in the server process environment.

## Running more than one agent

Today one profile answers per configured instance. The value of `HORUS_OS_DISCORD_AGENT_PROFILE` applies to every message that instance handles, whether it arrives in `#horus`, as a mention, or as a DM.

If you want a second persona, run a second horus-os instance with a different `HORUS_OS_DISCORD_AGENT_PROFILE` (and typically its own bot token and channel). Per-channel routing inside a single instance, where different channels map to different profiles, is on the roadmap and not available yet.

## Slash commands

All slash commands are guild-scoped, which means instant registration with no one-hour delay. They are available only in the guild specified by `HORUS_OS_DISCORD_GUILD_ID`.

| Command | Permission gate | Description |
|---------|-----------------|-------------|
| `/horus-setup` | Admin role required | Idempotent channel bootstrap. Creates the `horus-os` category and the `#horus`, `#horus-tasks`, and `#horus-activity` text channels if absent. Safe to run multiple times, and never deletes existing channels. |

### Admin-role gate

`HORUS_OS_DISCORD_ADMIN_ROLE_ID` must be set to the numeric ID of a role in your server. Only members who hold that role can run `/horus-setup`.

If `HORUS_OS_DISCORD_ADMIN_ROLE_ID` is not set, the adapter records an error at startup and the control-bot features stay offline. The base mention and DM functionality is unaffected.

## Scope and limitations

The base adapter does not do per-channel agent routing (a single profile applies to every channel the bot handles), token-by-token streaming (the full response is awaited then chunked), or voice channels and file uploads. The control-bot extension adds slash commands, reaction-based feedback, and outbound status cards posted into dispatch threads.

## Troubleshooting

### The bot is online but every message body is empty

The Message Content Intent is off. Toggle it on in the Developer Portal under Bot, then restart `horus-os serve`. Discord caches intent state per-connection, so the bot must reconnect to pick up the new toggle.

### The bot does not respond at all

Check that the bot has "Send Messages" permission in the channel. Right-click the channel, choose Edit Channel, then Permissions. If a permission overwrite denies the bot's role, the gateway event still fires but the reply send fails silently, because the adapter suppresses the exception to keep the connection open.

### /horus-setup says I lack the admin role

The caller must hold the role whose ID is in `HORUS_OS_DISCORD_ADMIN_ROLE_ID`. Confirm the env var holds the numeric role ID (not the role name) and that your account has that role assigned.

### 401 Unauthorized on connect

The token is wrong or was rotated. Mint a new one in the Developer Portal (Bot tab, Reset Token), update `HORUS_OS_DISCORD_TOKEN`, and restart.

### The bot reconnects in a loop

`discord.py` retries with exponential backoff on transient network failures. If the attempts never succeed, check the server log for the underlying transport error. Common causes are an outbound firewall blocking the gateway WebSocket (`wss://gateway.discord.gg`), a token rotated mid-run, or rate limiting from too many recent reconnects (Discord returns a 4014 close code and the library backs off).

### Status endpoint shows error: discord.py is not installed

You installed `horus-os` without the `discord` extra. Run `pip install 'horus-os[discord]'` and restart the server.

### Adapter status stays at error: HORUS_OS_DISCORD_TOKEN is not set

The env var is empty or unset in the process that started `horus-os serve`. If you exported it after launching the server, the existing process did not inherit it. Restart the server.

### Adapter status stays at error: HORUS_OS_DISCORD_GUILD_ID is not set

The control-bot path needs a numeric guild ID. Set `HORUS_OS_DISCORD_GUILD_ID` to your server's snowflake and restart. Without it the v0.7 control bot stays offline, though the base mention and DM path still works.

### Adapter status stays at error: HORUS_OS_DISCORD_ADMIN_ROLE_ID is not set

The control-bot path also needs a numeric admin role ID to gate `/horus-setup`. Set `HORUS_OS_DISCORD_ADMIN_ROLE_ID` and restart. A non-numeric value is treated as deny-all and also records an error.

## See also

- [Integrations overview](/integrations/overview/)
- [Slack](/integrations/slack/)
- [Environment variables](/reference/environment-variables/)
- [Running as a service](/guides/running-as-a-service/)
