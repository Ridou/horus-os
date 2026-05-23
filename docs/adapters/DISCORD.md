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

This pulls in `discord.py>=2.3`. The adapter module loads even
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
2. Under "Scopes" check `bot`
3. Under "Bot Permissions" check:
   - View Channels
   - Send Messages
   - Read Message History
4. Copy the generated URL at the bottom and open it in a browser
5. Pick a server you own and authorize

The bot now appears in the server member list and can be
mentioned in any channel it has read and write access to.

## 5. Configure environment variables

Set these on the machine that runs `horus-os serve`:

```
export HORUS_OS_DISCORD_TOKEN=your-bot-token-here
```

Optional:

```
# Which agent profile to use; defaults to "default".
export HORUS_OS_DISCORD_AGENT_PROFILE=scribe

# Optional cap on the library's internal reconnect backoff in seconds.
# Best-effort; if the installed discord.py version does not accept
# the knob, the library default applies.
export HORUS_OS_DISCORD_RECONNECT_CAP=60
```

Never commit a real token. Use a `.env` file the deploy excludes
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

## What the adapter does NOT do (v0.3)

- Slash commands. Mentions and DMs only
- Voice channels, reactions, file uploads
- Per-channel agent routing. A single profile applies to all
  channels the bot is in
- Streaming token-by-token replies. The full response is awaited
  then chunked
- Outbound notifications (sending without a triggering message).
  Inbound only
