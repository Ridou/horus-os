# Discord adapter

The Discord adapter connects horus-os to a Discord bot, listens for
mentions in guild channels and direct messages, runs the configured
agent profile, and replies in-channel. It uses the gateway
connection from `discord.py`, not webhooks.

## 1. Install the optional extra

The Discord SDK is not a core dependency. Install the extra:

```
pip install 'horus-os[discord]'
```

This pulls in `discord.py>=2.4`. The adapter module loads even
without this extra installed, but `start` then records a clear
"discord.py is not installed" error in the adapter registry and
the adapter stays offline. Other adapters continue to run.

## 2. Create a Discord application and bot

1. Sign in at https://discord.com/developers/applications
2. Click "New Application", give it a name (for example,
   "horus-os-bot"), and accept the developer terms
3. In the left sidebar select "Bot"
4. Click "Reset Token" and copy the token. Treat it like a
   password. You will paste it into an environment variable in
   step 5; the value must never land in source control

## 3. Enable the Message Content Intent

In the "Bot" tab, scroll to "Privileged Gateway Intents" and
toggle on:

- "Message Content Intent"
- "Server Members Intent" (optional, only if you want member
  metadata)

Without "Message Content Intent" the bot connects but every
inbound `message.content` is an empty string. This is the single
most common gotcha. The adapter also requests `guilds`,
`guild_messages`, and `dm_messages` intents which are not
privileged and need no portal toggle.

## 4. Generate an invite URL

1. In the left sidebar select "OAuth2", then "URL Generator"
2. Under "Scopes" check `bot` and `applications.commands`
3. Under "Bot Permissions" check:
   - View Channels
   - Send Messages
   - Read Message History
   - Add Reactions
   - Embed Links
   - Manage Messages
   - Create Public Threads
   - Send Messages in Threads
4. Copy the generated URL at the bottom and open it in a browser
5. Pick a server you own and authorize

**IMPORTANT: Do NOT grant Administrator permission.** The minimal
permission integer for the control bot is `292057869376`. Using that
integer directly in the URL (append `&permissions=292057869376` to the
base OAuth URL) is the safest approach. Granting Administrator is
unnecessary and significantly widens the blast radius if the bot token
is ever compromised.

The bot now appears in the server member list and can be
mentioned in any channel it has read and write access to.

## 5. Configure environment variables

Set these on the machine that runs `horus-os serve`:

```
export HORUS_OS_DISCORD_TOKEN=your-bot-token-here
```

For v0.7 control-bot features (guild slash commands, thread dispatch,
admin-gated setup), also set:

```
# The numeric ID of your Discord server (guild).
# Right-click the server name in Discord with Developer Mode on and
# copy the server ID.
export HORUS_OS_DISCORD_GUILD_ID=your-guild-id-here

# The numeric role ID that gates /horus-setup.
# Right-click the role in Server Settings > Roles with Developer Mode on
# and copy the role ID.
export HORUS_OS_DISCORD_ADMIN_ROLE_ID=your-admin-role-id-here
```

Optional:

```
# Name of the control category created by /horus-setup.
# Defaults to "horus-os".
export HORUS_OS_DISCORD_CATEGORY=horus-os

# Which agent profile to use; defaults to "default".
export HORUS_OS_DISCORD_AGENT_PROFILE=writer
```

Never commit a real token or ID. Use a `.env` file the deploy excludes
from git, or your platform's secrets manager.

## 6. Run the server

```
horus-os serve
```

You should see the bot show up as online in your server's member
list. The first request after server start fires the FastAPI
lifespan, which calls the adapter's `start` and opens the gateway
connection.

## 7. Verify

In a guild channel where the bot can see messages:

```
@your-bot-name hello
```

In a direct message to the bot, send any message at all. The bot
replies in the same channel or DM. For responses longer than 2000
characters, the adapter splits the reply into multiple sequential
messages.

You can confirm adapter status without leaving Discord by hitting
`GET /api/adapters` on the local dashboard. The `discord` entry
shows `status: running` and a recent `last_activity_at`.

## Troubleshooting

### The bot is online but every message body is empty

The Message Content Intent is off. Toggle it on in the developer
portal under Bot, then restart `horus-os serve`. Discord caches
intent state per-connection, so the bot must reconnect to pick up
the new toggle.

### The bot does not respond at all

Check that the bot has "Send Messages" permission in the channel.
Right-click the channel, Edit Channel, Permissions. If the channel
has a permission overwrite that denies the bot's role, the gateway
event still fires but the reply send fails silently. The adapter
suppresses the exception so the connection stays open.

### 401 Unauthorized on connect

The token is wrong or was rotated. Mint a new one in the developer
portal (Bot tab, Reset Token), update `HORUS_OS_DISCORD_TOKEN`,
and restart.

### The bot reconnects in a loop

`discord.py` retries with exponential backoff on transient
network failures. If the reconnect attempts never succeed, look
at the server log for the underlying transport error. Common
causes: outbound firewall blocking the gateway WebSocket
(`wss://gateway.discord.gg`), a token that was rotated mid-run,
or rate limiting from too many recent reconnects (Discord
returns a 4014 close code and the library backs off).

### Status endpoint shows error: discord.py is not installed

You installed `horus-os` without the `discord` extra. Run
`pip install 'horus-os[discord]'` and restart the server.

### Adapter status stays at error: HORUS_OS_DISCORD_TOKEN is not set

The env var is empty or unset in the process that started
`horus-os serve`. If you exported it in your shell after launching
the server, the existing server process did not inherit it.
Restart the server.

## What the base adapter does NOT do (v0.3)

This list describes the v0.3 message adapter only. The v0.7 control-bot
extension below supersedes several items: it adds slash commands,
reaction-based feedback, and outbound status-card posts into dispatch
threads.

- Per-channel agent routing. A single profile applies to all
  channels the bot is in
- Streaming token-by-token replies. The full response is awaited
  then chunked
- Voice channels and file uploads

---

## v0.7 Control-Bot Extension

The control-bot extension (Phase 64) adds guild-scoped slash commands,
thread-based task dispatch from a dedicated `#horus` control channel,
task status cards (rich Embeds), and reaction-based feedback. All
control-bot features require `HORUS_OS_DISCORD_GUILD_ID` and
`HORUS_OS_DISCORD_ADMIN_ROLE_ID` in addition to `HORUS_OS_DISCORD_TOKEN`.

### Bot creation notes for v0.7

When creating the bot in the Developer Portal (step 2 above), ensure:

- Under "OAuth2 > URL Generator", add the `applications.commands` scope
  alongside `bot`. This scope is required for slash command registration.
- The bot token (`HORUS_OS_DISCORD_TOKEN`) is still the only
  credential; `applications.commands` is a scope, not a separate key.

### Message Content Intent (required, v0.7)

The `message_content` privileged intent is set in code
(`intents.message_content = True`), but this is a necessary condition,
not a sufficient one. You must also toggle it in the Developer Portal:

1. Go to https://discord.com/developers/applications
2. Select your application
3. In the left sidebar, select "Bot"
4. Scroll to "Privileged Gateway Intents"
5. Toggle on "Message Content Intent"
6. Save changes

Without this portal toggle, the bot connects and appears online, but
every inbound `message.content` is an empty string. The bot will not
respond to any message typed in `#horus` or other channels.

### Minimal-permission invite URL (v0.7)

The permission integer for the full control-bot feature set is
`292057869376`. This covers:

- View Channels (`1 << 10`)
- Send Messages (`1 << 11`)
- Embed Links (`1 << 14`)
- Read Message History (`1 << 16`)
- Add Reactions (`1 << 6`)
- Manage Messages (`1 << 13`)
- Create Public Threads (`1 << 34`)
- Send Messages in Threads (`1 << 38`)

To use this integer, construct the invite URL manually:

```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot+applications.commands&permissions=292057869376
```

Replace `YOUR_CLIENT_ID` with the Application ID from your Developer
Portal Overview page.

**Never use the Administrator permission (`1 << 3`, integer 8).** It
grants the bot full control over the server. If the token is
compromised, an attacker gains complete server admin access. The
minimal integer above covers everything the control bot needs.

### The #horus control channel and thread-dispatch flow

After running `/horus-setup` (see Slash commands below), the bot
creates (or confirms the existence of) a `#horus` text channel inside
a `horus-os` category (configurable via `HORUS_OS_DISCORD_CATEGORY`).

Thread-dispatch flow:

1. A guild member types a prompt in `#horus` (plain message, no
   mention required)
2. The bot creates a public thread named after the first few words of
   the prompt
3. The agent runs inside `asyncio.to_thread` (non-blocking)
4. When complete, the bot posts a status card (Embed) into the thread
   with the result, model used, and latency
5. Guild members react with thumbs-up or thumbs-down to record feedback
6. The bot reads raw reaction events (`on_raw_reaction_add`) so
   feedback works even after the internal message cache expires

### Slash commands

All slash commands are guild-scoped (instant registration, no 1-hour
delay). They are available only in the guild specified by
`HORUS_OS_DISCORD_GUILD_ID`.

| Command | Permission gate | Description |
|---------|----------------|-------------|
| `/horus-setup` | Admin role required | Idempotent channel bootstrap: creates the `horus-os` category and `#horus` text channel if absent. Safe to run multiple times; never deletes existing channels. |

### Admin-role requirement

`HORUS_OS_DISCORD_ADMIN_ROLE_ID` must be set to the numeric ID of a
role in your server. Only members with this role can run `/horus-setup`.

To find the role ID: enable Developer Mode in Discord user settings
(Settings > Advanced > Developer Mode), then go to Server Settings >
Roles, right-click the desired role, and select "Copy Role ID".

If `HORUS_OS_DISCORD_ADMIN_ROLE_ID` is not set, the adapter records an
error at startup and the control-bot features remain offline. The v0.3
mention/DM functionality is unaffected.
