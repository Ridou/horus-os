# Slack adapter

The Slack adapter connects horus-os to a Slack app, listens for
mentions and direct messages via Slack's Events API, optionally
handles slash commands, and replies in-channel. Unlike the
Discord adapter, this one uses HTTP webhooks rather than a
persistent gateway connection, so the machine running `horus-os
serve` must be reachable from Slack at a public URL.

## 1. Install the optional extra

The Slack SDK is not a core dependency. Install the extra:

```
pip install 'horus-os[slack]'
```

This pulls in `slack-sdk>=3.27`. The adapter module loads even
without this extra installed, but every request to the Slack
routes then returns 503 with a clear "slack-sdk is not installed"
body, and the adapter's registry status stays at `error`.

## 2. Create a Slack app

1. Sign in at https://api.slack.com/apps
2. Click "Create New App", choose "From scratch"
3. Name the app (for example, "horus-os") and pick the workspace
   you want it installed in
4. After creation you land on the app's "Basic Information" page

## 3. Add bot scopes

In the left sidebar, open "OAuth and Permissions" and add the
following Bot Token Scopes under "Scopes":

- `chat:write` (post messages back as the bot)
- `app_mentions:read` (receive `app_mention` events)
- `im:history` (read DM message bodies)
- `im:read` (see DM channels exist)
- `commands` (only if you plan to register slash commands)

Without `chat:write` the adapter can receive events but every
reply call fails. The adapter suppresses post failures so the
HTTP route still returns 200, but the user sees no reply.

## 4. Install the app to the workspace

Still under "OAuth and Permissions", click "Install to Workspace"
and approve. Copy the "Bot User OAuth Token" that appears (begins
with `xoxb-`). You will set it as `HORUS_OS_SLACK_BOT_TOKEN` in
step 7.

## 5. Copy the signing secret

In the left sidebar, open "Basic Information" and scroll to "App
Credentials". Copy the "Signing Secret" (a 32-character hex
string). You will set it as `HORUS_OS_SLACK_SIGNING_SECRET` in
step 7.

## 6. Expose horus-os on a public URL

Slack's Events API delivers events over HTTP, so `horus-os serve`
must be reachable from the internet on HTTPS. For local
development, `ngrok http 8000` gives you a public
`https://xxxx.ngrok.app`. For a server deployment, put the
process behind a reverse proxy that terminates TLS (Caddy,
nginx, Cloudflare Tunnel).

## 7. Enable Events API and subscribe to events

In the Slack app left sidebar:

1. Open "Event Subscriptions" and toggle "Enable Events" on
2. In "Request URL" paste your public URL followed by the path:
   `https://your-public-host/api/adapters/slack/events`
3. Slack sends a one-time `url_verification` challenge to that
   URL. The adapter responds with the challenge string. The
   "Request URL" field turns green ("Verified") once Slack is
   satisfied
4. Under "Subscribe to bot events" add:
   - `app_mention`
   - `message.im`
5. Click "Save Changes"

If verification fails, the most common cause is that your URL
does not return 200 within 3 seconds, or the signing secret in
the env var does not match the value in "Basic Information". See
the troubleshooting section.

## 8. (Optional) Register a slash command

In "Slash Commands", click "Create New Command":

- Command: `/horus` (pick whatever you want)
- Request URL: `https://your-public-host/api/adapters/slack/commands`
- Short Description: "Ask horus-os"
- Usage Hint: `<your prompt>`

Save. After re-installing the app to the workspace (Slack prompts
you), the slash command is available in any channel the bot is in.

## 9. Configure environment variables

Set these on the machine that runs `horus-os serve`:

```
export HORUS_OS_SLACK_BOT_TOKEN=xoxb-your-bot-token
export HORUS_OS_SLACK_SIGNING_SECRET=your-signing-secret
```

Optional:

```
# Which agent profile to use; defaults to "default".
export HORUS_OS_SLACK_AGENT_PROFILE=scribe
```

Never commit a real token or signing secret. Use a `.env` file
the deploy excludes from git, or your platform's secrets manager.
Rotate both immediately if either value ever appears in source
control.

## 10. Run the server

```
horus-os serve
```

Hit `GET /api/adapters` on the dashboard URL to confirm the
`slack` entry shows `status: running`.

## 11. Verify

- Invite the bot to a channel (`/invite @your-bot-name`), then
  `@your-bot hello`. The bot should reply in the same channel
- Open a direct message with the bot and send any text. The bot
  should reply in the DM
- If you registered a slash command, run `/horus what time is it`
  in any channel the bot is in. The bot replies inline

You can confirm the adapter's `last_activity_at` is bumped via
`GET /api/adapters` after each interaction.

## Troubleshooting

### Signature mismatch

Slack rejects every request with 401 from your URL. Causes:

- `HORUS_OS_SLACK_SIGNING_SECRET` is wrong. Copy it again from
  the app's Basic Information page. Watch for leading or trailing
  whitespace.
- The reverse proxy in front of `horus-os serve` is rewriting or
  re-encoding the request body. Slack signs the raw bytes; any
  middleware that JSON-parses and re-serializes will break the
  HMAC. Configure the proxy to pass the body through untouched.
- System clock drift. The adapter rejects timestamps older than
  300 seconds. If your server's clock is off by more than 5
  minutes the signature itself is fine but replay protection
  kicks in. Run `chronyd` or `ntpd`.

### Missing scopes

The bot can receive events but cannot reply. Re-check that
`chat:write` is in the Bot Token Scopes list. After adding
scopes, click "Reinstall to Workspace" so the existing token
picks up the new permissions, then copy the refreshed token into
`HORUS_OS_SLACK_BOT_TOKEN`.

### Slack shows "Your URL did not respond with the value of the challenge parameter"

The Events API verification handshake failed. Common causes:

- Public URL is not actually reachable; test it with `curl -X POST
  https://your-public-host/api/adapters/slack/events -d '{"type":"url_verification","challenge":"test"}'`
  from somewhere outside your network. You should see a 401
  (no signature) rather than a connection error.
- `HORUS_OS_SLACK_SIGNING_SECRET` is unset; the route returns 503
  in that case, which Slack reads as "did not respond".

### Slack 3-second timeout

If your agent takes more than 3 seconds, Slack retries the same
event up to 3 times. The adapter de-duplicates by `event_id` so
each event runs the agent only once, but the user may see slow
replies. Deferred replies via `response_url` are a planned
enhancement.

### Status endpoint shows error: slack-sdk is not installed

You installed `horus-os` without the `slack` extra. Run
`pip install 'horus-os[slack]'` and restart the server.

### Adapter status stays at error: HORUS_OS_SLACK_SIGNING_SECRET is not set

The env var is empty or unset in the process that started
`horus-os serve`. If you exported it in your shell after launching
the server, the existing server process did not inherit it.
Restart the server.

## What the adapter does NOT do (v0.3)

- Socket Mode (persistent WebSocket via an `xapp-` token). v0.3
  ships HTTP-only
- Interactive components: buttons, modals, view submissions
- `response_url` deferred replies for slash commands (Slack's
  3-second window applies)
- File uploads, attachments, reactions
- Per-channel agent routing; a single configured profile applies
  to every inbound event
- Streaming responses; the full agent response is posted as one
  message
- Outbound notifications; the adapter is inbound-only
