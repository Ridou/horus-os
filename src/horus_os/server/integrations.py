"""Registry of integration connectors and live configured-status detection.

Defines the INTEGRATION_REGISTRY list (one entry per connector) and the
compute_status() helper that derives a status string from env var presence
only. The registry is a plain list-of-dicts so it is importable and testable
without any FastAPI or database dependency.

Security: compute_status() uses only bool(os.environ.get(var)) and never
captures the value. No env var value is ever stored, logged, or returned.
"""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from horus_os.storage import Database

INTEGRATION_REGISTRY: list[dict] = [
    {
        "id": "anthropic",
        "name": "Anthropic",
        "category": "AI Provider",
        "description": "Powers the default agent runtime. Required for Claude-based agents.",
        "env_var": "ANTHROPIC_API_KEY",
        "required_vars": ["ANTHROPIC_API_KEY"],
        "credential_portal_url": "https://console.anthropic.com/settings/keys",
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "category": "AI Provider",
        "description": "Powers Gemini-based agents. Required for Google model support.",
        "env_var": "GEMINI_API_KEY",
        "required_vars": ["GEMINI_API_KEY"],
        "credential_portal_url": "https://aistudio.google.com/apikey",
    },
    {
        "id": "discord",
        "name": "Discord",
        "category": "Communication",
        "description": (
            "Runs an optional Discord control bot: thread-based dispatch from a control"
            " channel, guild-scoped slash commands (/horus setup, /status, /cancel),"
            " task status cards, and reaction feedback. Required for the Discord"
            " control bot."
        ),
        "env_var": "HORUS_OS_DISCORD_TOKEN",
        "required_vars": [
            "HORUS_OS_DISCORD_TOKEN",
            "HORUS_OS_DISCORD_GUILD_ID",
            "HORUS_OS_DISCORD_ADMIN_ROLE_ID",
        ],
        "credential_portal_url": "https://discord.com/developers/applications",
    },
    {
        "id": "slack",
        "name": "Slack",
        "category": "Communication",
        "description": "Posts messages and handles events via a Slack app. Required for Slack adapter.",
        "env_var": "HORUS_OS_SLACK_BOT_TOKEN",
        "required_vars": ["HORUS_OS_SLACK_BOT_TOKEN", "HORUS_OS_SLACK_SIGNING_SECRET"],
        "credential_portal_url": "https://api.slack.com/apps",
    },
    {
        "id": "email",
        "name": "Email",
        "category": "Communication",
        "description": "Reads and sends email via IMAP and SMTP. Required for Email adapter.",
        "env_var": "HORUS_OS_EMAIL_IMAP_HOST",
        "required_vars": [
            "HORUS_OS_EMAIL_IMAP_HOST",
            "HORUS_OS_EMAIL_IMAP_USER",
            "HORUS_OS_EMAIL_IMAP_PASSWORD",
            "HORUS_OS_EMAIL_SMTP_HOST",
        ],
        "credential_portal_url": "",
    },
    {
        "id": "calendar",
        "name": "Calendar",
        "category": "Productivity",
        "description": "Reads and writes Google Calendar events via OAuth. Required for Calendar adapter.",
        "env_var": "HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH",
        "required_vars": ["HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH"],
        "credential_portal_url": "https://console.cloud.google.com/apis/credentials",
    },
    {
        "id": "github",
        "name": "GitHub",
        "category": "Developer",
        "description": "Queries repos, issues, and pull requests via the GitHub API.",
        "env_var": "GITHUB_TOKEN",
        "required_vars": ["GITHUB_TOKEN"],
        "credential_portal_url": "https://github.com/settings/tokens",
    },
    {
        "id": "supabase",
        "name": "Supabase",
        "category": "Database",
        "description": "Syncs agent state and traces to a remote Supabase Postgres instance.",
        "env_var": "SUPABASE_URL",
        "required_vars": ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"],
        "credential_portal_url": "https://supabase.com/dashboard",
    },
    {
        "id": "vercel",
        "name": "Vercel",
        "category": "Deploy",
        "description": "Deploys the horus-os dashboard to Vercel. Required for cloud hosting.",
        "env_var": "HORUS_OS_VERCEL_TOKEN",
        "required_vars": ["HORUS_OS_VERCEL_TOKEN"],
        "credential_portal_url": "https://vercel.com/account/tokens",
    },
    {
        "id": "tailscale",
        "name": "Tailscale",
        "category": "Network",
        "description": "Exposes the horus-os API securely over a private Tailscale network.",
        "env_var": "HORUS_OS_TAILSCALE_API_KEY",
        "required_vars": ["HORUS_OS_TAILSCALE_API_KEY"],
        "credential_portal_url": "https://login.tailscale.com/admin/settings/keys",
    },
]


def compute_status(entry: dict, *, db: Database | None = None) -> str:
    """Return status string derived from env var presence and optional SQLite verification state.

    When db is None (backward-compatible path used by Phase 61 tests), only env var
    presence is checked and the result is 'missing' or 'configured-unverified'.

    When db is provided and the primary env var is present, the SQLite verification row
    is consulted. If verified=1 AND the current key hash matches the stored hash, 'verified'
    is returned. A hash mismatch (rotation) returns 'configured-unverified' so the green
    light is invalidated without requiring a probe re-run.

    Security: the env var VALUE is only used to compute a hash; it is never stored or
    returned directly.
    """
    required_vars = entry.get("required_vars", [entry["env_var"]])
    all_present = all(bool(os.environ.get(v)) for v in required_vars)
    if not all_present:
        return "missing"
    if db is None:
        return "configured-unverified"
    row = db.get_integration_verification(entry["id"])
    if row is None:
        return "configured-unverified"
    if row["verified"]:
        current_hash = hashlib.sha256(
            os.environ.get(entry["env_var"], "").encode("utf-8")
        ).hexdigest()
        if current_hash != row["key_hash"]:
            return "configured-unverified"
        return "verified"
    return "configured-unverified"
