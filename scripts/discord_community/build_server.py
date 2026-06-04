#!/usr/bin/env python3
"""Idempotent builder for the Horus-OS community Discord server.

This is community-ops tooling, not a shipped product feature. It talks to the
Discord REST API as the Horus bot and creates the server structure: roles,
categories, channels, forum channels with tags, custom emoji, the server icon,
AutoMod rules, a hardened verification posture, native Onboarding, and the
pinned welcome / start-here / forum-guideline content.

It is safe to re-run. Everything is create-if-missing, and the brittle bits
(role ordering, onboarding, AutoMod) degrade to a warning plus a manual
instruction instead of aborting the build.

Credentials are read from an env file, never hardcoded and never printed:
    DISCORD_COMMUNITY_TOKEN   the bot token (secret)
    DISCORD_GUILD_ID          the target server (guild) id
Default env file: ~/.config/horus-os/community.env  (override with
$HORUS_COMMUNITY_ENV). The token never enters this repo.

Usage:
    python build_server.py --check     # preview only, no changes
    python build_server.py             # build / reconcile the server
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from pathlib import Path

import requests

API = "https://discord.com/api/v10"
HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
CONTENT = HERE / "content"
BRAND_CYAN = 0x00D4FF

# --- Discord permission bit positions (NEVER grant ADMINISTRATOR to a role) ---
BIT = {
    "CREATE_INSTANT_INVITE": 0,
    "KICK_MEMBERS": 1,
    "BAN_MEMBERS": 2,
    "ADMINISTRATOR": 3,
    "MANAGE_CHANNELS": 4,
    "MANAGE_GUILD": 5,
    "ADD_REACTIONS": 6,
    "VIEW_AUDIT_LOG": 7,
    "PRIORITY_SPEAKER": 8,
    "STREAM": 9,
    "VIEW_CHANNEL": 10,
    "SEND_MESSAGES": 11,
    "SEND_TTS_MESSAGES": 12,
    "MANAGE_MESSAGES": 13,
    "EMBED_LINKS": 14,
    "ATTACH_FILES": 15,
    "READ_MESSAGE_HISTORY": 16,
    "MENTION_EVERYONE": 17,
    "USE_EXTERNAL_EMOJIS": 18,
    "VIEW_GUILD_INSIGHTS": 19,
    "CONNECT": 20,
    "SPEAK": 21,
    "MUTE_MEMBERS": 22,
    "DEAFEN_MEMBERS": 23,
    "MOVE_MEMBERS": 24,
    "USE_VAD": 25,
    "CHANGE_NICKNAME": 26,
    "MANAGE_NICKNAMES": 27,
    "MANAGE_ROLES": 28,
    "MANAGE_WEBHOOKS": 29,
    "MANAGE_GUILD_EXPRESSIONS": 30,
    "USE_APPLICATION_COMMANDS": 31,
    "REQUEST_TO_SPEAK": 32,
    "MANAGE_EVENTS": 33,
    "MANAGE_THREADS": 34,
    "CREATE_PUBLIC_THREADS": 35,
    "CREATE_PRIVATE_THREADS": 36,
    "USE_EXTERNAL_STICKERS": 37,
    "SEND_MESSAGES_IN_THREADS": 38,
    "USE_EMBEDDED_ACTIVITIES": 39,
    "MODERATE_MEMBERS": 40,
}


def perms(*names: str) -> int:
    total = 0
    for n in names:
        total |= 1 << BIT[n]
    return total


# Channel types
TYPE_TEXT, TYPE_VOICE, TYPE_CATEGORY, TYPE_ANNOUNCEMENT, TYPE_FORUM = 0, 2, 4, 5, 15
FLAG_REQUIRE_TAG = 1 << 4

POST_PERMS = (
    "SEND_MESSAGES",
    "SEND_MESSAGES_IN_THREADS",
    "EMBED_LINKS",
    "ATTACH_FILES",
    "ADD_REACTIONS",
    "READ_MESSAGE_HISTORY",
    "CREATE_PUBLIC_THREADS",
    "USE_APPLICATION_COMMANDS",
)
VIEW_PERMS = ("VIEW_CHANNEL", "READ_MESSAGE_HISTORY")

# --- Roles. Order is low -> high; positions assigned accordingly. ---
SELF_ASSIGN_ROLES = [
    ("notify-release", 0),
    ("notify-announcements", 0),
    ("agents", 0),
    ("voice", 0),
    ("dashboard", 0),
    ("self-hosting", 0),
    ("models-local", 0),
    ("can-help", 0),
    ("looking-for-help", 0),
]
STAFF_ROLES = [
    # name, color, hoist, mentionable, guild-permission bundle
    ("Contributor", 0x22C55E, True, False, 0),
    ("Maintainer", 0x00D4FF, True, True, 0),
    (
        "Moderator",
        0xF59E0B,
        True,
        True,
        perms(
            "MANAGE_MESSAGES",
            "MANAGE_THREADS",
            "KICK_MEMBERS",
            "BAN_MEMBERS",
            "MODERATE_MEMBERS",
            "MANAGE_NICKNAMES",
            "VIEW_AUDIT_LOG",
            "MUTE_MEMBERS",
            "DEAFEN_MEMBERS",
            "MOVE_MEMBERS",
        ),
    ),
    (
        "Admin",
        0xEF4444,
        True,
        True,
        perms(
            "MANAGE_GUILD",
            "MANAGE_ROLES",
            "MANAGE_CHANNELS",
            "MANAGE_WEBHOOKS",
            "MANAGE_GUILD_EXPRESSIONS",
            "MANAGE_MESSAGES",
            "MANAGE_THREADS",
            "KICK_MEMBERS",
            "BAN_MEMBERS",
            "MODERATE_MEMBERS",
            "MANAGE_NICKNAMES",
            "VIEW_AUDIT_LOG",
            "MENTION_EVERYONE",
            "MUTE_MEMBERS",
            "DEAFEN_MEMBERS",
            "MOVE_MEMBERS",
            "MANAGE_EVENTS",
        ),
    ),
]

# --- Forum tag taxonomies. moderated=True means staff-only. ---
HELP_TAGS = [
    ("install-setup", False, "🧰"),
    ("agent-runtime", False, "🤖"),
    ("dashboard", False, "📊"),
    ("integrations", False, "🔌"),
    ("models-providers", False, "🧠"),
    ("config-doctor", False, "🩺"),
    ("self-host-deploy", False, "🏠"),
    ("docs", False, "📖"),
    ("needs-info", True, "❔"),
    ("solved", True, "✅"),
]
BUG_TAGS = [
    ("open", True, "🆕"),
    ("investigating", True, "🔎"),
    ("confirmed", True, "✅"),
    ("fixed", True, "🛠️"),
    ("wontfix", True, "🚫"),
    ("duplicate", True, "🔁"),
]
TROUBLESHOOT_TAGS = [
    ("install", False, "🧰"),
    ("runtime-crash", False, "💥"),
    ("adapter-error", False, "🔌"),
    ("performance", False, "🐢"),
    ("needs-info", True, "❔"),
    ("solved", True, "✅"),
]

EMOJI = ["horus", "shipped", "researching", "bug"]


def server_map():
    """The full category + channel layout. mode controls permission overwrites."""
    help_topic = (
        "Ask one question per post. Search first, pick a tag, use code "
        "blocks, and include your version, OS, and Python version. "
        "Mark Solved when answered. Redact all secrets."
    )
    bug_topic = (
        "Confirmed defects only. New posts start as open and a maintainer "
        "triages weekly (allow up to 7 days). Reproduced, in-scope reports "
        "move to a GitHub issue. Use the pinned template. Redact secrets."
    )
    return [
        (
            "📜 INFO",
            "readonly",
            [
                {
                    "name": "📌-welcome",
                    "type": TYPE_TEXT,
                    "rules": True,
                    "topic": "Rules, Code of Conduct, and key links. Start here.",
                    "content": "welcome.md",
                    "pin": True,
                },
                {
                    "name": "📣-announcements",
                    "type": TYPE_ANNOUNCEMENT,
                    "topic": "Official Horus-OS updates. Follow this channel to mirror it into your own server.",
                },
                {
                    "name": "🚀-releases",
                    "type": TYPE_TEXT,
                    "webhook": "releases",
                    "topic": "Automated feed of new Horus-OS releases from GitHub.",
                },
                {
                    "name": "📖-start-here",
                    "type": TYPE_TEXT,
                    "topic": "How this server works and how to pick your roles.",
                    "content": "start-here.md",
                    "pin": True,
                },
            ],
        ),
        (
            "💬 COMMUNITY",
            "open",
            [
                {
                    "name": "👋-introductions",
                    "type": TYPE_TEXT,
                    "topic": "Say hi. Tell us what you are building with Horus-OS.",
                },
                {
                    "name": "💬-general",
                    "type": TYPE_TEXT,
                    "topic": "On-topic Horus-OS chat that is not a support question.",
                },
                {
                    "name": "🛠️-showcase",
                    "type": TYPE_TEXT,
                    "topic": "Show what you built: agent configs, automations, dashboards.",
                },
                {
                    "name": "🏆-build-of-the-month",
                    "type": TYPE_TEXT,
                    "mode": "readonly",
                    "topic": "Curated highlights from showcase.",
                },
                {
                    "name": "🎲-off-topic",
                    "type": TYPE_TEXT,
                    "topic": "Everything else. Keep it friendly.",
                },
            ],
        ),
        (
            "🆘 SUPPORT",
            "open",
            [
                {
                    "name": "❓-help",
                    "type": TYPE_FORUM,
                    "topic": help_topic,
                    "tags": HELP_TAGS,
                    "require_tag": True,
                    "pin_doc": "help-guidelines.md",
                    "pin_title": "How to ask a good question",
                },
                {
                    "name": "🩺-troubleshooting",
                    "type": TYPE_FORUM,
                    "topic": "Runtime and self-host failures. Include logs, stack traces, version, OS, and Python version.",
                    "tags": TROUBLESHOOT_TAGS,
                    "require_tag": True,
                },
                {
                    "name": "🐛-bug-reports",
                    "type": TYPE_FORUM,
                    "topic": bug_topic,
                    "tags": BUG_TAGS,
                    "require_tag": False,
                    "pin_doc": "bug-template.md",
                    "pin_title": "[TEMPLATE] Copy this format for bug reports",
                    "pin_doc2": "bug-guidelines.md",
                    "pin_title2": "How bug reports work (read first)",
                },
            ],
        ),
        (
            "🧠 AGENTS & MODELS",
            "open",
            [
                {
                    "name": "🤖-agents-runtime",
                    "type": TYPE_TEXT,
                    "topic": "Agent behavior, scheduling, autonomy, and guardrails.",
                },
                {
                    "name": "⏰-automations-and-crons",
                    "type": TYPE_TEXT,
                    "topic": "Recurring tasks, scheduled runs, and automation recipes.",
                },
                {
                    "name": "🧩-prompt-and-agent-recipes",
                    "type": TYPE_TEXT,
                    "topic": "Share system prompts, agent profiles, and task templates.",
                },
                {
                    "name": "🔌-models-and-providers",
                    "type": TYPE_TEXT,
                    "topic": "Anthropic, Gemini, Ollama, local inference, and hardware.",
                },
                {
                    "name": "🏠-self-hosting",
                    "type": TYPE_TEXT,
                    "topic": "Deployment, Docker, Tailscale, SQLite, and OS-specific setup.",
                },
            ],
        ),
        (
            "🧱 CONTRIBUTORS",
            "open",
            [
                {
                    "name": "🧱-contributing",
                    "type": TYPE_TEXT,
                    "topic": "Good first issues, the contributing guide, and PR coordination.",
                },
                {
                    "name": "💡-feature-requests",
                    "type": TYPE_TEXT,
                    "topic": "Concrete proposals. Open-ended design goes to GitHub Discussions, concrete proposals to GitHub Issues.",
                },
                {
                    "name": "📊-dev-activity",
                    "type": TYPE_TEXT,
                    "mode": "readonly",
                    "webhook": "dev-activity",
                    "topic": "Automated feed of GitHub issues, pull requests, and pushes.",
                },
                {
                    "name": "⚙️-dev-chat",
                    "type": TYPE_TEXT,
                    "mode": "contributor",
                    "topic": "Deeper implementation talk. Visible to Contributors and up.",
                },
                {
                    "name": "🔒-maintainers",
                    "type": TYPE_TEXT,
                    "mode": "maintainers",
                    "topic": "Private maintainer coordination.",
                },
            ],
        ),
        (
            "🛡️ STAFF",
            "staff",
            [
                {
                    "name": "👁️-audit-log",
                    "type": TYPE_TEXT,
                    "mode": "owner_only",
                    "topic": "Private owner-only history: message edits and deletes, plus name and nickname changes. Populated by the audit logger.",
                },
                {
                    "name": "🛡️-mod-log",
                    "type": TYPE_TEXT,
                    "topic": "AutoMod alerts, join and role logging, and the raid runbook.",
                },
                {"name": "🗒️-staff-chat", "type": TYPE_TEXT, "topic": "Private staff coordination."},
            ],
        ),
        (
            "🔊 VOICE",
            "open",
            [
                {"name": "🎙️ Office Hours", "type": TYPE_VOICE, "topic": ""},
            ],
        ),
    ]


# ----------------------------- HTTP plumbing --------------------------------
class Discord:
    def __init__(self, token: str, dry: bool):
        self.s = requests.Session()
        self.s.headers.update(
            {
                "Authorization": f"Bot {token}",
                "User-Agent": "horus-os-community-builder (https://github.com/Ridou/horus-os, 1.0)",
                "Content-Type": "application/json",
            }
        )
        self.dry = dry

    def req(self, method: str, path: str, mutating: bool = False, **kw):
        if mutating and self.dry:
            print(f"   [check] would {method} {path}")
            return None
        for _attempt in range(6):
            r = self.s.request(method, f"{API}{path}", **kw)
            if r.status_code == 429:
                wait = float(r.json().get("retry_after", 1.0)) + 0.2
                print(f"   rate limited, waiting {wait:.1f}s")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
            if mutating:
                time.sleep(0.4)  # be gentle
            return r.json() if r.text else {}
        raise RuntimeError(f"{method} {path} kept rate limiting")


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def load_env() -> tuple[str, str]:
    env_path = Path(
        os.environ.get("HORUS_COMMUNITY_ENV", str(Path.home() / ".config/horus-os/community.env"))
    )
    values = dict(os.environ)
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    token = values.get("DISCORD_COMMUNITY_TOKEN") or values.get("DISCORD_TOKEN")
    guild = values.get("DISCORD_GUILD_ID")
    if not token or not guild:
        sys.exit(
            f"Missing DISCORD_COMMUNITY_TOKEN or DISCORD_GUILD_ID. Looked in {env_path} and the environment."
        )
    return token, guild


# ----------------------------- build steps ----------------------------------
def overwrites(mode: str, ids: dict, everyone: str) -> list | None:
    """Permission overwrite array for a given mode, or None to inherit."""
    admin, mod = ids.get("Admin"), ids.get("Moderator")
    if mode == "open":
        return None
    if mode == "readonly":
        ow = [
            {
                "id": everyone,
                "type": 0,
                "allow": str(perms("VIEW_CHANNEL", "READ_MESSAGE_HISTORY", "ADD_REACTIONS")),
                "deny": str(
                    perms(
                        "SEND_MESSAGES",
                        "SEND_MESSAGES_IN_THREADS",
                        "CREATE_PUBLIC_THREADS",
                        "CREATE_PRIVATE_THREADS",
                    )
                ),
            }
        ]
        for rid in (admin, mod):
            if rid:
                ow.append({"id": rid, "type": 0, "allow": str(perms(*POST_PERMS)), "deny": "0"})
        return ow
    if mode == "owner_only":
        # Only the guild owner can see it (the owner bypasses all overwrites), and
        # the admin bot can post to it (Administrator bypasses too). Everyone else,
        # including Admin and Moderator roles, is denied view.
        deny_view = str(perms("VIEW_CHANNEL"))
        ow = [{"id": everyone, "type": 0, "allow": "0", "deny": deny_view}]
        for rid in (admin, mod):
            if rid:
                ow.append({"id": rid, "type": 0, "allow": "0", "deny": deny_view})
        return ow
    # hidden categories / channels: deny @everyone view, allow named roles
    allowed = {
        "staff": ["Admin", "Moderator"],
        "contributor": ["Contributor", "Maintainer", "Admin", "Moderator"],
        "maintainers": ["Maintainer", "Admin", "Moderator"],
    }[mode]
    ow = [{"id": everyone, "type": 0, "allow": "0", "deny": str(perms("VIEW_CHANNEL"))}]
    grant = perms(*VIEW_PERMS, *POST_PERMS, "CONNECT", "SPEAK")
    for name in allowed:
        if ids.get(name):
            ow.append({"id": ids[name], "type": 0, "allow": str(grant), "deny": "0"})
    return ow


def ensure_roles(d: Discord, guild: str, existing: list) -> dict:
    by_name = {r["name"]: r["id"] for r in existing}
    ids = dict(by_name)
    print("\n== Roles ==")
    wanted = [(n, 0, False, True, 0) for n, _ in SELF_ASSIGN_ROLES] + [
        (n, c, h, m, p) for n, c, h, m, p in STAFF_ROLES
    ]
    for name, color, hoist, mentionable, perm in wanted:
        if name in by_name:
            print(f"   ok   {name}")
            continue
        body = {
            "name": name,
            "permissions": str(perm),
            "mentionable": mentionable,
            "hoist": hoist,
            "color": color,
        }
        res = d.req("POST", f"/guilds/{guild}/roles", mutating=True, json=body)
        print(f"   +    {name}")
        if res:
            ids[name] = res["id"]
    # best-effort relative ordering, all below the bot's managed role
    try:
        order = [n for n, _ in SELF_ASSIGN_ROLES] + [
            "Contributor",
            "Maintainer",
            "Moderator",
            "Admin",
        ]
        payload = [{"id": ids[n], "position": i + 1} for i, n in enumerate(order) if ids.get(n)]
        if payload and not d.dry:
            d.req("PATCH", f"/guilds/{guild}/roles", mutating=True, json=payload)
            print("   ordered role hierarchy")
    except Exception as e:
        print(f"   warn: could not reorder roles ({e}). Drag them in Server Settings > Roles.")
    return ids


def find_channel(channels: list, name: str, ctype: int, parent: str | None = None):
    for c in channels:
        if (
            c.get("name") == name
            and c.get("type") == ctype
            and (parent is None or c.get("parent_id") == parent)
        ):
            return c
    return None


def ensure_community(d: Discord, guild: str, gobj: dict, channels: list):
    print("\n== Community mode + hardened verification ==")
    features = set(gobj.get("features", []))
    rules = find_channel(channels, "📌-welcome", TYPE_TEXT)
    updates = find_channel(channels, "🛡️-mod-log", TYPE_TEXT)
    if "COMMUNITY" in features:
        print("   ok   Community already enabled")
    elif rules and updates:
        body = {
            "features": sorted(features | {"COMMUNITY"}),
            "rules_channel_id": rules["id"],
            "public_updates_channel_id": updates["id"],
            "verification_level": 3,
            "explicit_content_filter": 2,
            "default_message_notifications": 1,
        }
        try:
            d.req("PATCH", f"/guilds/{guild}", mutating=True, json=body)
            print("   +    Community enabled (verification HIGH, scan all messages)")
        except Exception as e:
            print(f"   warn: could not enable Community via API ({e}).")
            print(
                "         Enable it in Server Settings > Enable Community, then re-run for forums."
            )
    else:
        print("   warn: rules/updates channels not found yet; will settle on next run")
    # hardened posture even if community was already on
    try:
        d.req(
            "PATCH",
            f"/guilds/{guild}",
            mutating=True,
            json={"verification_level": 3, "explicit_content_filter": 2},
        )
    except Exception as e:
        print(f"   warn: could not set verification posture ({e})")


def build_channels(d: Discord, guild: str, ids: dict, everyone: str):
    channels = d.req("GET", f"/guilds/{guild}/channels")
    name_index = {(c["name"], c["type"]): c for c in channels}
    created: dict = {}
    for cat_name, cat_mode, chans in server_map():
        print(f"\n== {cat_name} ==")
        cat = name_index.get((cat_name, TYPE_CATEGORY))
        if cat:
            print(f"   ok   category {cat_name}")
        else:
            ow = overwrites(cat_mode, ids, everyone)
            body = {"name": cat_name, "type": TYPE_CATEGORY}
            if ow:
                body["permission_overwrites"] = ow
            try:
                cat = d.req("POST", f"/guilds/{guild}/channels", mutating=True, json=body) or {
                    "id": None
                }
                print(f"   +    category {cat_name}")
            except Exception as e:
                print(f"   warn: category {cat_name} failed ({e}); skipping its channels this pass")
                continue
        parent = cat.get("id")
        for spec in chans:
            existing = name_index.get((spec["name"], spec["type"]))
            if existing:
                print(f"   ok   {spec['name']}")
                created[spec["name"]] = existing
                continue
            body = {"name": spec["name"], "type": spec["type"], "parent_id": parent}
            if spec.get("topic"):
                body["topic"] = spec["topic"]
            ch_mode = spec.get("mode")
            ow = overwrites(ch_mode, ids, everyone) if ch_mode else None
            if ow:
                body["permission_overwrites"] = ow
            if spec["type"] == TYPE_FORUM:
                body["available_tags"] = [
                    {"name": n, "moderated": mod, "emoji_name": em, "emoji_id": None}
                    for n, mod, em in spec.get("tags", [])
                ]
                body["default_sort_order"] = 0
                body["default_forum_layout"] = 1
                # NOTE: REQUIRE_TAG (flags) is NOT accepted on channel create; it is
                # applied later via PATCH in ensure_forum_require_tag(), after the
                # pinned template threads are posted (those would fail tag-required).
            try:
                res = d.req("POST", f"/guilds/{guild}/channels", mutating=True, json=body)
                print(f"   +    {spec['name']}")
                if res:
                    created[spec["name"]] = res
            except Exception as e:
                hint = (
                    " (forums need Community mode; retried after it is enabled)"
                    if spec["type"] == TYPE_FORUM
                    else ""
                )
                print(f"   warn: {spec['name']} not created{hint}: {e}")
    return created


def ensure_emoji(d: Discord, guild: str):
    print("\n== Custom emoji ==")
    existing = {e["name"] for e in d.req("GET", f"/guilds/{guild}/emojis")}
    for name in EMOJI:
        png = ASSETS / "emoji" / f"{name}.png"
        if name in existing:
            print(f"   ok   :{name}:")
            continue
        if not png.is_file():
            print(f"   skip :{name}: (missing {png.name})")
            continue
        try:
            d.req(
                "POST",
                f"/guilds/{guild}/emojis",
                mutating=True,
                json={"name": name, "image": data_uri(png)},
            )
            print(f"   +    :{name}:")
        except Exception as e:
            print(f"   warn: :{name}: failed ({e})")


def ensure_icon(d: Discord, guild: str, gobj: dict):
    print("\n== Server icon ==")
    icon = ASSETS / "icon.png"
    if not icon.is_file():
        print("   skip (no icon.png)")
        return
    if gobj.get("icon"):
        print("   ok   icon already set (re-applying brand icon)")
    try:
        d.req("PATCH", f"/guilds/{guild}", mutating=True, json={"icon": data_uri(icon)})
        print("   +    icon applied")
    except Exception as e:
        print(f"   warn: could not set icon ({e})")


def ensure_automod(d: Discord, guild: str, channels_by_name: dict):
    print("\n== AutoMod ==")
    mod_log = channels_by_name.get("🛡️-mod-log", {}).get("id")
    try:
        existing = {r["name"] for r in d.req("GET", f"/guilds/{guild}/auto-moderation/rules")}
    except Exception as e:
        print(f"   warn: cannot read AutoMod rules ({e}); skipping")
        return
    block = [{"type": 1}]
    alert = block + ([{"type": 2, "metadata": {"channel_id": mod_log}}] if mod_log else [])
    rules = [
        {
            "name": "Block flagged words",
            "event_type": 1,
            "trigger_type": 4,
            "trigger_metadata": {"presets": [1, 2, 3]},
            "actions": block,
            "enabled": True,
        },
        {
            "name": "Block spam",
            "event_type": 1,
            "trigger_type": 3,
            "trigger_metadata": {},
            "actions": block,
            "enabled": True,
        },
        {
            "name": "Block mention spam",
            "event_type": 1,
            "trigger_type": 5,
            "trigger_metadata": {"mention_total_limit": 6},
            "actions": block,
            "enabled": True,
        },
        {
            "name": "Block scam phrases",
            "event_type": 1,
            "trigger_type": 1,
            "trigger_metadata": {
                "keyword_filter": [
                    "free nitro",
                    "*steamcommunity*gift*",
                    "discord-gift*",
                    "discordapp-gift*",
                    "crypto airdrop",
                    "*claim your*reward*",
                    "dm me to earn",
                ]
            },
            "actions": alert,
            "enabled": True,
        },
    ]
    for rule in rules:
        if rule["name"] in existing:
            print(f"   ok   {rule['name']}")
            continue
        try:
            d.req("POST", f"/guilds/{guild}/auto-moderation/rules", mutating=True, json=rule)
            print(f"   +    {rule['name']}")
        except Exception as e:
            print(f"   warn: {rule['name']} failed ({e})")


def ensure_onboarding(d: Discord, guild: str, ids: dict, chans: dict):
    print("\n== Onboarding ==")

    def cid(name):
        return chans.get(name, {}).get("id")

    # Discord enforces: >= 7 default channels, and >= 5 of them must let @everyone
    # SEND messages. List the sendable channels first, then the read-only ones.
    sendable = [
        cid(n)
        for n in (
            "💬-general",
            "👋-introductions",
            "🛠️-showcase",
            "🎲-off-topic",
            "🤖-agents-runtime",
        )
    ]
    readonly = [cid(n) for n in ("📌-welcome", "📣-announcements", "❓-help")]
    sendable = [c for c in sendable if c]
    defaults = sendable + [c for c in readonly if c]

    # Prompt/option ids must be snowflake-shaped strings (not "0"/"1"); pass fresh
    # nonexistent snowflakes so Discord treats them as new.
    counter = [1_000_000_000_000_000_000]

    def new_id():
        counter[0] += 1
        return str(counter[0])

    def opt(title, role=None, emoji=None):
        o = {
            "id": new_id(),
            "title": title,
            "role_ids": [ids[role]] if role and ids.get(role) else [],
            "channel_ids": [],
        }
        if emoji:  # emoji must be flat fields on create, not a nested object
            o["emoji_name"] = emoji
            o["emoji_id"] = None
            o["emoji_animated"] = False
        return o

    def prompt(title, options, single_select=False):
        return {
            "id": new_id(),
            "type": 0,
            "title": title,
            "single_select": single_select,
            "required": False,
            "in_onboarding": True,
            "options": options,
        }

    prompts = [
        prompt(
            "Which areas interest you?",
            [
                opt("Agents & runtime", "agents", "🤖"),
                opt("Models & local inference", "models-local", "🧠"),
                opt("Self-hosting", "self-hosting", "🏠"),
                opt("Dashboard", "dashboard", "📊"),
                opt("Voice", "voice", "🎙️"),
            ],
        ),
        prompt(
            "Want to be pinged?",
            [
                opt("New releases", "notify-release", "🚀"),
                opt("Announcements", "notify-announcements", "📣"),
            ],
        ),
        prompt(
            "You are mainly here to...",
            [
                opt("Use Horus-OS", emoji="✅"),
                opt("Help others / contribute", "can-help", "🤝"),
            ],
            single_select=True,
        ),
    ]

    if len(defaults) < 7 or len(sendable) < 5:
        print(
            "   warn: need >=7 default channels with >=5 sendable; finish Onboarding in Server Settings"
        )
        return
    try:
        d.req(
            "PUT",
            f"/guilds/{guild}/onboarding",
            mutating=True,
            json={"enabled": True, "mode": 0, "default_channel_ids": defaults, "prompts": prompts},
        )
        print("   +    Onboarding configured (default channels + 3 prompts)")
    except Exception as e:
        print(f"   warn: Onboarding via API failed ({e}).")
        print("         Set it in Server Settings > Onboarding (defaults + the 3 prompts above).")


def chunk(text: str, size: int = 4000):
    while text:
        yield text[:size]
        text = text[size:]


def post_content(d: Discord, guild: str, chans: dict):
    print("\n== Pinned content ==")
    try:
        active_threads = d.req("GET", f"/guilds/{guild}/threads/active").get("threads", [])
    except Exception:
        active_threads = []

    def has_pins(ch_id) -> bool:
        try:
            return bool(d.req("GET", f"/channels/{ch_id}/pins"))
        except Exception:
            return False

    def thread_exists(forum_id, title) -> bool:
        return any(
            t.get("parent_id") == forum_id and t.get("name") == title[:100] for t in active_threads
        )

    def embed_post(name, title, md_file):
        ch = chans.get(name)
        if not ch:
            print(f"   skip {name} (channel missing)")
            return
        if not d.dry and has_pins(ch["id"]):
            print(f"   ok   {name} already has pinned content")
            return
        body = (CONTENT / md_file).read_text()
        first = None
        for i, part in enumerate(chunk(body)):
            emb = {"description": part, "color": BRAND_CYAN}
            if i == 0:
                emb["title"] = title
            try:
                msg = d.req(
                    "POST", f"/channels/{ch['id']}/messages", mutating=True, json={"embeds": [emb]}
                )
                first = first or (msg or {}).get("id")
            except Exception as e:
                print(f"   warn: post to {name} failed ({e})")
                return
        if first and not d.dry:
            try:  # current pins path; falls back to the deprecated one if needed
                d.req("PUT", f"/channels/{ch['id']}/messages/pins/{first}", mutating=True)
            except Exception:
                try:
                    d.req("PUT", f"/channels/{ch['id']}/pins/{first}", mutating=True)
                except Exception:
                    pass
        print(f"   +    posted + pinned in {name}")

    def forum_thread(name, title, md_file, pin=True):
        ch = chans.get(name)
        if not ch:
            return
        if not d.dry and thread_exists(ch["id"], title):
            print(f"   ok   '{title[:40]}' already in {name}")
            return
        body = (CONTENT / md_file).read_text()[:1990]
        try:
            res = d.req(
                "POST",
                f"/channels/{ch['id']}/threads",
                mutating=True,
                json={"name": title[:100], "message": {"content": body}},
            )
            print(f"   +    forum post '{title[:40]}' in {name}")
            if pin and res and res.get("id") and not d.dry:
                try:
                    d.req("PATCH", f"/channels/{res['id']}", mutating=True, json={"flags": 1 << 1})
                except Exception:
                    pass
        except Exception as e:
            print(f"   warn: forum post in {name} failed ({e})")

    embed_post("📌-welcome", "Welcome to Horus-OS", "welcome.md")
    embed_post("📖-start-here", "How this server works", "start-here.md")
    forum_thread("❓-help", "How to ask a good question", "help-guidelines.md")
    forum_thread("🐛-bug-reports", "How bug reports work (read first)", "bug-guidelines.md")
    forum_thread("🐛-bug-reports", "[TEMPLATE] Copy this format for bug reports", "bug-template.md")


def ensure_forum_require_tag(d: Discord, guild: str, chans: dict):
    """Set REQUIRE_TAG via PATCH. Must run AFTER pinned threads are posted, since a
    require-tag forum rejects new threads that carry no tag."""
    print("\n== Forum require-tag ==")
    for _cat_name, _cat_mode, specs in server_map():
        for spec in specs:
            if spec.get("type") == TYPE_FORUM and spec.get("require_tag"):
                ch = chans.get(spec["name"])
                if not ch:
                    continue
                try:
                    d.req(
                        "PATCH",
                        f"/channels/{ch['id']}",
                        mutating=True,
                        json={"flags": FLAG_REQUIRE_TAG},
                    )
                    print(f"   +    require-tag on {spec['name']}")
                except Exception as e:
                    print(f"   warn: require-tag on {spec['name']} failed ({e})")


MANUAL_STEPS = """
================ MANUAL FOLLOW-UPS (need your own accounts) ================
1. GitHub release feed -> #releases:
   - In #releases: Edit channel > Integrations > Webhooks > New Webhook, copy URL.
   - Append /github to the URL.
   - GitHub repo > Settings > Webhooks > Add webhook: paste URL, content-type
     application/json, choose "Let me select" > Releases only.
2. GitHub dev-activity feed -> #dev-activity:
   - Same as above for #dev-activity, but select Issues, Pull requests, Pushes.
3. Answer Overflow (Q&A web indexing):
   - Install from https://answeroverflow.com , authorize the server, then enable
     indexing on #help (and #troubleshooting) in its dashboard.
4. Wick anti-raid (you chose the hardened/public posture):
   - Install from https://wickbot.com , run /setup, enable raid + anti-spam,
     point logs at #mod-log. Keep native AutoMod on alongside it.
5. Audit logger (the private #audit-log channel is created, but a live process
   fills it): either run scripts/discord_community/audit_logger.py with its own
   token, or call register_audit_handlers(bot) inside the bot you already run.
   Enable the Message Content and Server Members intents in the Developer Portal.
6. FAQ slash commands (/docs /install /links /faq): handled as a separate step,
   since they need a live handler. We will wire these next.
7. Optional: enable a Stage channel for Office Hours once there is an audience.
===========================================================================
"""


def main():
    ap = argparse.ArgumentParser(description="Build the Horus-OS community Discord server.")
    ap.add_argument("--check", action="store_true", help="preview only; make no changes")
    args = ap.parse_args()

    token, guild = load_env()
    d = Discord(token, dry=args.check)

    me = d.req("GET", "/users/@me")
    print(
        f"Authenticated as bot: {me.get('username')}#{me.get('discriminator', '0')} (id {me.get('id')})"
    )
    gobj = d.req("GET", f"/guilds/{guild}?with_counts=true")
    print(
        f"Target guild: {gobj.get('name')} (id {guild}), members ~{gobj.get('approximate_member_count', '?')}"
    )
    if args.check:
        print("\n*** CHECK MODE: no changes will be made ***")

    existing_roles = d.req("GET", f"/guilds/{guild}/roles")
    ids = ensure_roles(d, guild, existing_roles)
    everyone = guild  # @everyone role id == guild id

    # First pass: create categories + text/voice channels (forums skipped until Community is on)
    build_channels(d, guild, ids, everyone)
    current = d.req("GET", f"/guilds/{guild}/channels")
    ensure_community(d, guild, gobj, current)
    # Second pass now that Community is enabled: forums get created
    build_channels(d, guild, ids, everyone)

    by_name = {c["name"]: c for c in d.req("GET", f"/guilds/{guild}/channels")}
    ensure_icon(d, guild, gobj)
    ensure_emoji(d, guild)
    ensure_automod(d, guild, by_name)
    ensure_onboarding(d, guild, ids, by_name)
    post_content(d, guild, by_name)
    ensure_forum_require_tag(d, guild, by_name)

    print("\nDone." if not args.check else "\nCheck complete (no changes made).")
    if not args.check:
        print(MANUAL_STEPS)


if __name__ == "__main__":
    main()
