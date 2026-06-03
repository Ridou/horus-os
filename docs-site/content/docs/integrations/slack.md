---
title: "Slack"
description: "Connect horus-os to a Slack app so it answers mentions, direct messages, and slash commands over Slack's Events API."
---

## Overview

The Slack adapter connects horus-os to a Slack app. It listens for mentions and direct messages through Slack's Events API, optionally handles slash commands, and replies in-channel.

Unlike the [Discord](/integrations/discord/) adapter, which holds a persistent gateway connection, Slack delivers events over HTTP webhooks. That means the machine running `horus-os serve` must be reachable from Slack at a public HTTPS URL.

This adapter is inbound-only: it responds to events Slack sends it. For the full list of integrations, see the [integrations overview](/integrations/overview/).

This page is a complete, numbered walkthrough. Follow the eleven steps in order. By the end, an installed horus-os agent replies when you `@mention` it in a Slack channel, send it a direct message, or invoke a slash command. The adapter exposes two routes:

- `POST /api/adapters/slack/events` receives mentions and direct messages from Slack's Events API.
- `POST /api/adapters/slack/commands` receives slash commands.

Both routes verify every inbound request with Slack's signing-secret HMAC-SHA256 scheme over the raw request body, so a correct signing secret is mandatory for any traffic to get through.

> [!NOTE]
> The adapter ships HTTP-only. Socket Mode (a persistent WebSocket via an `xapp-` token), interactive components (buttons, modals), file uploads, reactions, and streaming responses are not supported. See [Limitations](#limitations).

## 1. Install the optional extra

The Slack SDK is not a core dependency. Install the extra:

```bash
pip install 'horus-os[slack]'
```

This pulls in `slack-sdk`. The adapter module loads even without this extra installed, but every request to the Slack routes then returns `503` with a clear `slack-sdk is not installed` body, and the adapter's registry status stays at `error`.

## 2. Create a Slack app

1. Sign in at https://api.slack.com/apps
2. Click "Create New App", then choose "From scratch".
3. Name the app (for example, `horus-os`) and pick the workspace you want it installed in.
4. After creation you land on the app's "Basic Information" page.

## 3. Add bot scopes

In the left sidebar, open "OAuth and Permissions" and scroll to "Scopes". Under "Bot Token Scopes", click "Add an OAuth Scope" and add each of the following:

| Scope | Purpose |
| --- | --- |
| `app_mentions:read` | Receive `app_mention` events when someone `@mentions` the bot |
| `chat:write` | Post the agent's reply back into the channel or DM as the bot |
| `commands` | Register and receive slash commands (add this if you plan to use the slash command route in step 8) |
| `im:history` | Read the text of direct messages sent to the bot |
| `im:read` | See that DM channels with the bot exist |

`app_mentions:read` and `chat:write` are the minimum for the mention flow. Add `im:history` and `im:read` for direct messages, and `commands` for slash commands.

> [!WARNING]
> Without `chat:write` the adapter can receive events but every reply call fails. The adapter suppresses post failures so the HTTP route still returns `200`, but the user sees no reply.

## 4. Install the app to the workspace

Still under "OAuth and Permissions", click "Install to Workspace" and approve. Copy the "Bot User OAuth Token" that appears (it begins with `xoxb-`). You set it as `HORUS_OS_SLACK_BOT_TOKEN` in step 9.

## 5. Copy the signing secret

In the left sidebar, open "Basic Information" and scroll to "App Credentials". Copy the "Signing Secret" (a 32-character hex string). You set it as `HORUS_OS_SLACK_SIGNING_SECRET` in step 9.

## 6. Expose horus-os on a public URL

Slack's Events API delivers events over HTTP, so `horus-os serve` must be reachable from the internet over HTTPS. Slack will not accept an `http://` or `localhost` request URL.

1. Start the server locally so the tunnel has something to point at: `horus-os serve`. Note the port it listens on (8000 by default).
2. For local development, open a tunnel to that port. With ngrok, run `ngrok http 8000` and copy the `https://xxxx.ngrok.app` address it prints. That is your public host for steps 7 and 8.
3. For a server deployment instead, put the process behind a reverse proxy that terminates TLS (Caddy, nginx, or Cloudflare Tunnel) and use its public hostname.

> [!IMPORTANT]
> Slack signs the raw request body. Configure any reverse proxy to pass the body through untouched. Middleware that JSON-parses and re-serializes the body breaks the signature check. See [Signature mismatch](#signature-mismatch).

For background on exposing the server safely, see [remote access](/guides/remote-access/) and [running as a service](/guides/running-as-a-service/).

## 7. Enable the Events API

In the Slack app left sidebar:

1. Open "Event Subscriptions" and toggle "Enable Events" on.
2. In "Request URL" paste the public host from step 6 followed by the path `/api/adapters/slack/events`, for example:

   ```text
   https://your-public-host/api/adapters/slack/events
   ```

   For this to verify, your server must already be running with `HORUS_OS_SLACK_SIGNING_SECRET` set (step 9). You can set the env vars and start the server before this step if you prefer.
3. Slack sends a one-time `url_verification` challenge to that URL. The adapter echoes the challenge string straight back. The "Request URL" field turns green ("Verified") once Slack is satisfied.
4. Under "Subscribe to bot events" add:
   - `app_mention`
   - `message.im` (only if you want direct-message support; it pairs with the `im:history` and `im:read` scopes from step 3)
5. Click "Save Changes".

If verification fails, the most common cause is that your URL does not return `200` within 3 seconds, or the signing secret in the env var does not match the value in "Basic Information". See [Troubleshooting](#troubleshooting).

## 8. Register a slash command (optional)

Skip this step if you only want mentions and direct messages. To add a slash command, open "Slash Commands" and click "Create New Command":

- **Command:** `/horus` (pick whatever you want)
- **Request URL:** the public host from step 6 followed by `/api/adapters/slack/commands`, for example `https://your-public-host/api/adapters/slack/commands`
- **Short Description:** "Ask horus-os"
- **Usage Hint:** `<your prompt>`

Save. After re-installing the app to the workspace (Slack prompts you), the slash command is available in any channel the bot is in. The slash command route requires the `commands` scope from step 3.

## 9. Configure environment variables

Set these on the machine that runs `horus-os serve`:

```bash
export HORUS_OS_SLACK_BOT_TOKEN=xoxb-your-bot-token
export HORUS_OS_SLACK_SIGNING_SECRET=your-signing-secret
```

Optional:

```bash
# Which installed agent answers Slack traffic. Defaults to "default".
export HORUS_OS_SLACK_AGENT_PROFILE=atlas
```

| Variable | Required | Description |
| --- | --- | --- |
| `HORUS_OS_SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token (`xoxb-...`) used to post replies. |
| `HORUS_OS_SLACK_SIGNING_SECRET` | Yes | Signing secret used to verify inbound requests. |
| `HORUS_OS_SLACK_AGENT_PROFILE` | No | Name of the installed agent profile that answers Slack traffic. Defaults to `default`. |

`HORUS_OS_SLACK_AGENT_PROFILE` is the name of an agent profile in your horus-os database. The adapter loads that profile on every inbound message and runs the agent with its `system_prompt` and `default_model`. List the profiles you have installed with `horus-os agents list`, and create one with `horus-os agents create <name> --system-prompt "..."`. Set this variable to the profile name you want answering Slack.

If you leave it unset the adapter uses the profile named `default`. If the named profile does not exist, that is non-fatal: the adapter falls back to the server's default model with no custom system prompt, so the bot still replies as a plain agent.

> [!CAUTION]
> Never commit a real token or signing secret. Use a `.env` file your deploy excludes from git, or your platform's secrets manager. Rotate both immediately if either value ever appears in source control.

See [environment variables](/reference/environment-variables/) for the full list.

## 10. Run the server

```bash
horus-os serve
```

Request `GET /api/adapters` on the dashboard URL to confirm the `slack` entry shows `status: running`. If it shows `error`, the message tells you what is missing (the `slack` extra, the bot token, or the signing secret).

## 11. Talk to the agent

You are wired up. Now hold a conversation with the agent from Slack:

- Invite the bot to a channel (`/invite @your-bot-name`), then send `@your-bot hello`. The agent selected by `HORUS_OS_SLACK_AGENT_PROFILE` runs your prompt and replies in the same channel. When you mention the bot inside an existing thread, the reply lands in that thread.
- Open a direct message with the bot and send any text. No mention is needed in a DM; the agent replies in the DM.
- If you registered a slash command, run `/horus what time is it` in any channel the bot is in. The agent replies inline.

The adapter strips the leading `<@bot-id>` mention token before handing your text to the agent, so the agent sees just the natural-language prompt. You can confirm the adapter's `last_activity_at` is bumped through `GET /api/adapters` after each interaction.

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
