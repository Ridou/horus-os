# Horus-OS community Discord builder

Community-ops tooling that builds and reconciles the Horus-OS community Discord
server over the Discord REST API. It is not a shipped product feature, and it is
separate from the product's Discord adapter in `src/horus_os/adapters/`.

It creates: roles + hierarchy, categories and channels, forum channels with tag
taxonomies, custom brand emoji, the server icon, AutoMod rules, a hardened
verification posture, native Onboarding, and the pinned welcome / start-here /
forum-guideline content.

## Credentials (never committed)

The script reads two values from an env file, defaulting to
`~/.config/horus-os/community.env` (override with `$HORUS_COMMUNITY_ENV`):

```
DISCORD_COMMUNITY_TOKEN=<the Horus bot token>
DISCORD_GUILD_ID=<the community server id>
```

The token never enters this repo. The bot must be in the server with Manage
Server, Manage Channels, Manage Roles, and Manage Expressions (Administrator
covers all of these).

## Run

```sh
# from the repo root, with the project venv
.venv/bin/python scripts/discord_community/build_server.py --check   # preview, no changes
.venv/bin/python scripts/discord_community/build_server.py           # build / reconcile
```

It is idempotent and safe to re-run: every object is create-if-missing, and the
brittle steps (role ordering, Onboarding, AutoMod) degrade to a warning plus a
manual instruction rather than aborting.

Forum channels require Community mode, which the script tries to enable
automatically; if Discord rejects that over the API, enable it once in Server
Settings and re-run.

## Audit logger (private owner-only history)

`audit_logger.py` is a reusable, self-host-friendly moderation logger. It mirrors
message edits and deletes, plus username and nickname changes (and joins/leaves),
into one private channel (`👁️-audit-log`, created by the builder and visible only
to the server owner). It is generic, with no private or project-specific logic.

It runs two ways, because a bot token can hold only ONE gateway connection at a
time:

- Standalone, with its OWN token (one a running bot is not already using):
  `pip install discord.py && python audit_logger.py`
- Attached to a bot you already run (shares one connection, no conflict):
  `from audit_logger import register_audit_handlers; register_audit_handlers(bot)`

Needs the Message Content and Server Members privileged intents (Developer Portal
> Bot). Config via the same env file (`DISCORD_AUDIT_CHANNEL`, `DISCORD_AUDIT_LOG_ALL`).

## Recipe: run on your PC and attach the logger to your existing bot

This is the single-token setup: scaffold the server with the REST script, then add
the logger to the bot you already run (one gateway connection, no conflict).

1. Put the token where this machine can read it:

   ```sh
   mkdir -p ~/.config/horus-os
   printf 'DISCORD_COMMUNITY_TOKEN=%s\nDISCORD_GUILD_ID=%s\n' '<bot-token>' '<guild-id>' \
     > ~/.config/horus-os/community.env
   chmod 600 ~/.config/horus-os/community.env
   ```

2. Scaffold the server (preview first, then for real):

   ```sh
   pip install requests
   python scripts/discord_community/build_server.py --check
   python scripts/discord_community/build_server.py
   ```

3. Attach the audit logger to your bot. Where you build the bot, register the
   listeners and make sure the two privileged intents are on:

   ```python
   from scripts.discord_community.audit_logger import register_audit_handlers
   # or: import sys; sys.path.append("scripts/discord_community"); from audit_logger import register_audit_handlers

   intents.message_content = True   # privileged
   intents.members = True           # privileged
   # ... create your bot/client with those intents ...
   register_audit_handlers(bot, audit_channel_name="👁️-audit-log")
   ```

   Then enable Message Content Intent and Server Members Intent in the Developer
   Portal > your app > Bot. Restart the bot. Edits, deletes, and name changes now
   land in the owner-only `👁️-audit-log` channel.

## Layout

- `build_server.py`   the builder
- `audit_logger.py`   reusable moderation audit logger
- `assets/icon.png`   1024x1024 server icon rasterized from `assets/favicon.svg`
- `assets/emoji/`     128x128 brand emoji (horus, shipped, researching, bug)
- `content/`          markdown posted as pinned messages and forum guidelines

After a run the script prints the manual follow-ups that need your own accounts
(GitHub webhooks, Answer Overflow, Wick, FAQ slash commands, and starting the
audit logger).
