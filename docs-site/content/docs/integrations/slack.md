---
title: "Slack"
description: "Connect horus-os to a Slack app so it answers mentions, direct messages, and slash commands over Slack's Events API."
---

## Overview

The Slack adapter connects horus-os to a Slack app. It listens for mentions and direct messages through Slack's Events API, optionally handles slash commands, and replies in-channel.

Unlike the [Discord](/integrations/discord/) adapter, which holds a persistent gateway connection, Slack delivers events over HTTP webhooks. That means the machine running `horus-os serve` must be reachable from Slack at a public HTTPS URL.

This adapter is inbound-only: it responds to events Slack sends it. For the full list of integrations, see the [integrations overview](/integrations/overview/).

> [!NOTE]
> The adapter ships HTTP-only. Socket Mode (a persistent WebSocket via an `xapp-` token), interactive components (buttons, modals), file uploads, reactions, and streaming responses are not supported. See [Limitations](#limitations).

## Install the optional extra

The Slack SDK is not a core dependency. Install the extra:

```bash
pip install 'horus-os[slack]'
```

This pulls in `slack-sdk`. The adapter module loads even without this extra installed, but every request to the Slack routes then returns `503` with a clear `slack-sdk is not installed` body, and the adapter's registry status stays at `error`.

## Create a Slack app

1. Sign in at https://api.slack.com/apps
2. Click "Create New App", then choose "From scratch".
3. Name the app (for example, `horus-os`) and pick the workspace you want it installed in.
4. After creation you land on the app's "Basic Information" page.

## Add bot scopes

In the left sidebar, open "OAuth and Permissions" and add the following Bot Token Scopes under "Scopes":

| Scope | Purpose |
| --- | --- |
| `chat:write` | Post messages back as the bot |
| `app_mentions:read` | Receive `app_mention` events |
| `im:history` | Read DM message bodies |
| `im:read` | See that DM channels exist |
| `commands` | Only if you plan to register slash commands |

> [!WARNING]
> Without `chat:write` the adapter can receive events but every reply call fails. The adapter suppresses post failures so the HTTP route still returns `200`, but the user sees no reply.

## Install the app to the workspace

Still under "OAuth and Permissions", click "Install to Workspace" and approve. Copy the "Bot User OAuth Token" that appears (it begins with `xoxb-`). You set it as `HORUS_OS_SLACK_BOT_TOKEN` later.

## Copy the signing secret

In the left sidebar, open "Basic Information" and scroll to "App Credentials". Copy the "Signing Secret" (a 32-character hex string). You set it as `HORUS_OS_SLACK_SIGNING_SECRET` later.

## Expose horus-os on a public URL

Slack's Events API delivers events over HTTP, so `horus-os serve` must be reachable from the internet over HTTPS.

- For local development, a tunneling tool gives you a public URL (for example, `ngrok http 8765` produces a `https://xxxx.ngrok.app` address). Point the tunnel at the port `horus-os serve` listens on.
- For a server deployment, put the process behind a reverse proxy that terminates TLS (Caddy, nginx, or Cloudflare Tunnel).

> [!IMPORTANT]
> Slack signs the raw request body. Configure any reverse proxy to pass the body through untouched. Middleware that JSON-parses and re-serializes the body breaks the signature check. See [Signature mismatch](#signature-mismatch).

For background on exposing the server safely, see [remote access](/guides/remote-access/) and [running as a service](/guides/running-as-a-service/).

## Enable the Events API

In the Slack app left sidebar:

1. Open "Event Subscriptions" and toggle "Enable Events" on.
2. In "Request URL" paste your public URL followed by the path `/api/adapters/slack/events`, for example:

   ```text
   https://your-public-host/api/adapters/slack/events
   ```

3. Slack sends a one-time `url_verification` challenge to that URL. The adapter responds with the challenge string. The "Request URL" field turns green ("Verified") once Slack is satisfied.
4. Under "Subscribe to bot events" add:
   - `app_mention`
   - `message.im`
5. Click "Save Changes".

If verification fails, the most common cause is that your URL does not return `200` within 3 seconds, or the signing secret in the env var does not match the value in "Basic Information". See [Troubleshooting](#troubleshooting).

## Register a slash command (optional)

In "Slash Commands", click "Create New Command":

- **Command:** `/horus` (pick whatever you want)
- **Request URL:** `https://your-public-host/api/adapters/slack/commands`
- **Short Description:** "Ask horus-os"
- **Usage Hint:** `<your prompt>`

Save. After re-installing the app to the workspace (Slack prompts you), the slash command is available in any channel the bot is in.

## Configure environment variables

Set these on the machine that runs `horus-os serve`:

```bash
export HORUS_OS_SLACK_BOT_TOKEN=xoxb-your-bot-token
export HORUS_OS_SLACK_SIGNING_SECRET=your-signing-secret
```

Optional:

```bash
# Which agent profile to use. Defaults to "default".
export HORUS_OS_SLACK_AGENT_PROFILE=writer
```

| Variable | Required | Description |
| --- | --- | --- |
| `HORUS_OS_SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token (`xoxb-...`) used to post replies. |
| `HORUS_OS_SLACK_SIGNING_SECRET` | Yes | Signing secret used to verify inbound requests. |
| `HORUS_OS_SLACK_AGENT_PROFILE` | No | Agent profile name to load. Defaults to `default`. |

> [!CAUTION]
> Never commit a real token or signing secret. Use a `.env` file your deploy excludes from git, or your platform's secrets manager. Rotate both immediately if either value ever appears in source control.

See [environment variables](/reference/environment-variables/) for the full list.

## Run the server

```bash
horus-os serve
```

Request `GET /api/adapters` on the dashboard URL to confirm the `slack` entry shows `status: running`.

## Verify

- Invite the bot to a channel (`/invite @your-bot-name`), then send `@your-bot hello`. The bot should reply in the same channel.
- Open a direct message with the bot and send any text. The bot should reply in the DM.
- If you registered a slash command, run `/horus what time is it` in any channel the bot is in. The bot replies inline.

You can confirm the adapter's `last_activity_at` is bumped through `GET /api/adapters` after each interaction.

## Troubleshooting

### Signature mismatch

Slack rejects every request with `401` from your URL. Causes:

- `HORUS_OS_SLACK_SIGNING_SECRET` is wrong. Copy it again from the app's Basic Information page. Watch for leading or trailing whitespace.
- The reverse proxy in front of `horus-os serve` is rewriting or re-encoding the request body. Slack signs the raw bytes, so any middleware that JSON-parses and re-serializes breaks the HMAC. Configure the proxy to pass the body through untouched.
- System clock drift. The adapter rejects timestamps older than 300 seconds. If your server's clock is off by more than 5 minutes the signature itself is fine but replay protection kicks in. Run a time-sync daemon such as `chronyd` or `ntpd`.

### Missing scopes

The bot can receive events but cannot reply. Re-check that `chat:write` is in the Bot Token Scopes list. After adding scopes, click "Reinstall to Workspace" so the existing token picks up the new permissions, then copy the refreshed token into `HORUS_OS_SLACK_BOT_TOKEN`.

### "Your URL did not respond with the value of the challenge parameter"

The Events API verification handshake failed. Common causes:

- The public URL is not actually reachable. Test it from outside your network:

  ```bash
  curl -X POST https://your-public-host/api/adapters/slack/events \
    -d '{"type":"url_verification","challenge":"test"}'
  ```

  You should see a `401` (no signature) rather than a connection error.
- `HORUS_OS_SLACK_SIGNING_SECRET` is unset, which makes the route return `503`. Slack reads that as "did not respond".

### Slack 3-second timeout

If your agent takes more than 3 seconds, Slack retries the same event up to 3 times. The adapter de-duplicates by `event_id` so each event runs the agent only once, but the user may see slow replies.

### Status endpoint shows `error: slack-sdk is not installed`

You installed `horus-os` without the `slack` extra. Run `pip install 'horus-os[slack]'` and restart the server.

### Adapter status stays at `error: HORUS_OS_SLACK_SIGNING_SECRET is not set`

The env var is empty or unset in the process that started `horus-os serve`. If you exported it in your shell after launching the server, the existing server process did not inherit it. Restart the server.

## Limitations

The Slack adapter does not currently support:

- Socket Mode (a persistent WebSocket via an `xapp-` token). The adapter is HTTP-only.
- Interactive components: buttons, modals, and view submissions.
- `response_url` deferred replies for slash commands (Slack's 3-second window applies).
- File uploads, attachments, and reactions.
- Per-channel agent routing. A single configured profile applies to every inbound event.
- Streaming responses. The full agent response is posted as one message.
- Outbound notifications. The adapter is inbound-only.

## See also

- [Integrations overview](/integrations/overview/)
- [Discord integration](/integrations/discord/)
- [Remote access](/guides/remote-access/)
- [Environment variables](/reference/environment-variables/)
