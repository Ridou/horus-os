"""Seed content shipped with horus-os for a non-empty first run.

A fresh `horus-os init` bootstraps a starter team of five agents, an
example vault of generic markdown notes, and one demo trace so the CLI
and dashboard are not empty on first launch. Everything here is generic
example content the user can delete.

The starter team lives in `STARTER_TEAM` (name, color, description, and
a concise system prompt per agent). The agent persona files (SOUL.md)
and the example vault notes ship as package data and are located at
runtime via `importlib.resources`, the same mechanism the bundled
`pricing.json` uses (see `horus_os.observability.pricing`).
"""

from __future__ import annotations

from importlib import resources
from importlib.resources.abc import Traversable

# The single template placeholder allowed inside a seed SOUL.md. It is
# substituted at init time with how the persona should address the human
# owner (the CLI passes "you").
USER_NAME_PLACEHOLDER = "{{USER_NAME}}"

# Canonical H2 sections every seed SOUL.md carries, in order. Tests pin
# this ordering; keep it in sync with the seed files under seed/agents/.
SOUL_SECTIONS = (
    "## Identity",
    "## Principles",
    "## Voice",
    "## Boundaries",
    "## Workflow",
)

# The five starter agents. `name` is the display name and the unique
# profile key; the SOUL.md for each lives under seed/agents/<name-lower>/.
# `default_model` is intentionally left unset so a seeded profile inherits
# the configured provider and model, which keeps a Gemini-only install
# from being pinned to Anthropic models.
STARTER_TEAM: list[dict[str, str]] = [
    {
        "name": "Coordinator",
        "color": "#00d4ff",
        "description": (
            "Orchestrator that routes work to the right specialist and synthesizes results"
        ),
        "system_prompt": (
            "You are the Coordinator, the orchestrator of a personal team of "
            "AI agents. You break a request into steps, delegate each to the "
            "right specialist with the delegate_to_agent tool, then synthesize "
            "the results for the user. Keep the user informed and never act "
            "outside an approved plan."
        ),
    },
    {
        "name": "Engineer",
        "color": "#22c55e",
        "description": "Code and technical implementation, small verifiable steps",
        "system_prompt": (
            "You are the Engineer. You handle code and technical "
            "implementation: reading files, proposing changes, and explaining "
            "tradeoffs. Prefer small verifiable steps, and always state what "
            "you changed and why."
        ),
    },
    {
        "name": "Researcher",
        "color": "#ec4899",
        "description": "Deep dives, analysis, and citation-aware summaries",
        "system_prompt": (
            "You are the Researcher. You gather and analyze information and "
            "summarize it clearly, citing sources even briefly. Prefer primary "
            "references, never fabricate citations, and never claim certainty "
            "beyond the evidence."
        ),
    },
    {
        "name": "Writer",
        "color": "#f59e0b",
        "description": "Clear docs, summaries, and content",
        "system_prompt": (
            "You are the Writer. You turn raw material into clear docs, "
            "summaries, and content. Match the requested voice, keep it "
            "concise, and never pad."
        ),
    },
    {
        "name": "Operator",
        "color": "#a78bfa",
        "description": "Watches runtime, schedules, errors, and system health",
        "system_prompt": (
            "You are the Operator. You watch the running system: tasks, "
            "schedules, errors, and health. Surface what needs attention, "
            "suggest next actions, and escalate anything risky before acting."
        ),
    },
]


def agent_slug(name: str) -> str:
    """Return the lowercase slug used for an agent's seed directory."""
    return name.lower()


def soul_rel_path(name: str) -> str:
    """Return the notes_dir-relative path of an agent's persona file."""
    return f"agents/{name}/SOUL.md"


def agents_dir() -> Traversable:
    """Return the packaged seed agents directory as a Traversable."""
    return resources.files("horus_os.seed").joinpath("agents")


def vault_dir() -> Traversable:
    """Return the packaged seed vault directory as a Traversable."""
    return resources.files("horus_os.seed").joinpath("vault")


def read_soul(name: str) -> str:
    """Return the raw SOUL.md text for a starter agent by display name."""
    return agents_dir().joinpath(agent_slug(name)).joinpath("SOUL.md").read_text(encoding="utf-8")


def vault_notes() -> list[tuple[str, str]]:
    """Return the packaged vault notes as (filename, content) pairs.

    Sorted by filename for a deterministic seeding order.
    """
    notes: list[tuple[str, str]] = []
    for entry in vault_dir().iterdir():
        if entry.name.endswith(".md"):
            notes.append((entry.name, entry.read_text(encoding="utf-8")))
    notes.sort(key=lambda item: item[0])
    return notes
