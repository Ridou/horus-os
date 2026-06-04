---
title: "Your own Discord command center"
description: "End-to-end walkthrough: create a Discord bot, connect horus-os, and drive your agents from anywhere over Tailscale. The full self-host experience, start to finish."
---

## What you will have at the end

A self-hosted command center you run on a machine you own (a home PC, a mini server, a spare laptop) and talk to from anywhere through Discord. You type a request in a channel on your phone, an agent runs on your hardware, and the answer comes back in a thread. Nothing is exposed to the public internet: your tailnet is the only door in.

This guide is the connective tissue. It walks the whole journey in order and links to the deep reference for each step:

1. Create a Discord bot and get its credentials.
2. Connect horus-os to it.
3. Reach it from anywhere over Tailscale, and keep it running.

Plug in your own values at each step and it is the same setup, on your own server.

## Prerequisites

- horus-os installed. See [Installation](/getting-started/installation/).
- A Discord account and a server (guild) you own, with Developer Mode on (User Settings > Advanced > Developer Mode) so you can copy IDs.
- A [Tailscale](https://tailscale.com/) account (free tier is fine) for remote access.

## Part 1: Create your Discord bot

1. Sign in at [discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**. Name it (for example `my-horus-bot`).
2. On the **Overview** page, copy the **Application ID**. You need it to build the invite link.
3. In the left sidebar open **Bot**, click **Reset Token**, and copy the token. Treat it like a password. It goes into an environment variable later and must never be committed.
4. Still on **Bot**, scroll to **Privileged Gateway Intents** and turn on **Message Content Intent** (required, or the bot sees empty messages). Turn on **Server Members Intent** too if you want member and name-change features.

For the full version of these steps, with every intent explained, see [Integrations: Discord](/integrations/discord/#2-create-a-discord-application-and-bot).

### Understanding the credentials

The Developer Portal shows several values. Here is what each is for, so you know which ones matter:

| Credential | What it is | Does horus-os need it? |
|------------|------------|------------------------|
| **Application ID** (Client ID) | Public identifier for the app. Used to build the invite link. | Yes, to invite the bot and as the guild client ID. Not secret. |
| **Bot token** | The bot's password. Authenticates every API and gateway call. | **Yes. This is the one secret you provide.** Never commit it. |
| **Public Key** | Verifies HTTP interaction payloads (only for the HTTP-interactions model). | No. horus-os uses a gateway connection, not an interactions endpoint. |
| **Client Secret** | OAuth2 secret for "Log in with Discord" authorization-code flows. | No. The bot does not use an OAuth2 login flow, so you never need it here. |

In short: the **bot token** is the only secret, and the **Application ID** is the only other value you handle. Skip the Public Key and Client Secret.

### Invite the bot to your server

Build an invite link with the least-privilege permission set already applied (do **not** grant Administrator):

```text
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&scope=bot+applications.commands&permissions=292057869376
```

Replace `YOUR_APPLICATION_ID`, open the link, pick your server, and authorize. The `applications.commands` scope lets the bot register slash commands. The permission integer covers reading and sending messages, managing the control channels, embeds, reactions, and threads, and nothing more. See [why Administrator is dangerous](/integrations/discord/#4-build-the-oauth2-invite-url).

## Part 2: Connect horus-os

Install the optional Discord extra and set the environment variables on the machine that will run the bot:

```bash
pip install 'horus-os[discord]'

export HORUS_OS_DISCORD_TOKEN=your-bot-token          # the secret from Part 1
export HORUS_OS_DISCORD_GUILD_ID=your-server-id       # right-click the server, Copy Server ID
export HORUS_OS_DISCORD_ADMIN_ROLE_ID=your-role-id    # gates the /horus-setup command
```

Keep these in a `.env` file your deploy excludes from git, never in source control. Then start the server and bootstrap the channels:

```bash
horus-os serve
# then, in Discord, as a member holding the admin role:
/horus-setup
```

`/horus-setup` is an idempotent, create-only bootstrap of the control channels. Now type a request in `#horus` and the agent answers in a thread. The full reference, including how to pick which agent answers and every optional variable, is in [Integrations: Discord](/integrations/discord/) and [Environment variables](/reference/environment-variables/).

## Part 3: Reach it from anywhere

This is what turns a local install into a command center you drive from your phone. The bot keeps running on your home machine and you reach the dashboard, and a shell, over your tailnet. The tailnet is the authentication boundary, so nothing is published to the public internet.

```bash
# On the host machine, once:
tailscale up

# Run horus-os on loopback (the safe default). Tailscale proxies to it.
horus-os serve

# Expose the dashboard to your tailnet over HTTPS (tailnet-only, not public):
tailscale serve 8765
```

From any device on the same tailnet, open `https://your-machine.your-tailnet.ts.net`. To get a shell on the host for editing env vars or reading logs, use SSH over the tailnet (on Windows, the built-in OpenSSH server). The complete remote-access setup, including the security rationale and the difference between `tailscale serve` and `tailscale funnel`, is in [Remote access](/guides/remote-access/).

> [!CAUTION]
> Never bind the dashboard to `0.0.0.0` or expose it with `tailscale funnel`. horus-os ships no app-level login, so the tailnet must be the only way in. See [Remote access](/guides/remote-access/) and [Security](/operations/security/).

### Keep it always on

So the bot survives reboots and crashes, supervise it with your platform's service manager (systemd, launchd, or a Windows service or scheduled task). See [Running as a service](/guides/running-as-a-service/).

At this point you have the full experience: agents running on your own hardware, reachable from your phone in Discord, from anywhere, with no public exposure.

## Optional: a full community server layout

The steps above give you a private control surface. If you instead want a polished, public community server (categories, forum channels with tags, roles and onboarding, AutoMod, branding, and an owner-only moderation audit log), the repo ships an idempotent builder under `scripts/discord_community/`. It reads your bot token from a local env file and never commits it. Read its `README.md` for the run steps. Treat it as community-ops tooling, separate from the product adapter above.

## Troubleshooting

- **Bot is online but ignores you.** The Message Content Intent is off, or the bot was not restarted after you toggled it. See [the Discord troubleshooting list](/integrations/discord/#troubleshooting).
- **`/horus-setup` says you lack the admin role.** `HORUS_OS_DISCORD_ADMIN_ROLE_ID` must be the numeric role ID, and your account must hold that role.
- **Cannot reach the dashboard remotely.** Confirm Tailscale is up on both devices (`tailscale status`) and that `tailscale serve 8765` is running on the host.

## See also

- [Integrations: Discord](/integrations/discord/)
- [Remote access](/guides/remote-access/)
- [Running as a service](/guides/running-as-a-service/)
- [Environment variables](/reference/environment-variables/)
- [Security](/operations/security/)
