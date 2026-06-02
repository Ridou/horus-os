"""Research agent team for a native Deep Research run.

`RESEARCH_TEAM` is a list of dict entries shaped exactly like the
`STARTER_TEAM` in `horus_os.seed` (name, color, description, system_prompt,
plus an explicit `allowed_tools` list). `research_profiles()` maps each entry
to an `AgentProfile` so the orchestrator and the seeding path can bootstrap
the team the same way init does for the starter team.

Four roles, with stable module-level name constants so the orchestrator can
look them up:

  * RESEARCH_COORDINATOR: plans subtopics, delegates to the specialists, and
    synthesizes the cited report. It is the ONLY profile whose allowed_tools
    include `delegate_to_agent`.
  * SEARCH_AGENT: issues web searches and records candidate sources.
  * FETCH_AGENT: fetches and reads candidate pages (web + PDF/image).
  * SYNTHESIS_AGENT: reads the saved notes and drafts the report body.

DR-3 decision: every sub-agent profile sets an EXPLICIT, non-None
`allowed_tools` list that OMITS `delegate_to_agent`. `_filter_registry` only
narrows a registry when `allowed_tools` is not None, so a sub-agent with
`allowed_tools=None` would inherit the coordinator's delegation tool and could
recursively re-enter Deep Research. Pinning explicit lists here makes a
recursive research run impossible (a regression test asserts the omission).

DR-2 decision: the coordinator system prompt instructs the model to cite ONLY
URLs that the team actually fetched in this session (the source registry).
Fabricated, training-memory URLs are forbidden, and the report builder rejects
any that slip through.
"""

from __future__ import annotations

from horus_os.types import AgentProfile

# Stable profile names. The orchestrator and tests pin these so a rename never
# silently breaks delegation lookups.
RESEARCH_COORDINATOR = "Research Coordinator"
SEARCH_AGENT = "Research Searcher"
FETCH_AGENT = "Research Fetcher"
SYNTHESIS_AGENT = "Research Synthesizer"

# The delegation tool name the coordinator (and only the coordinator) may hold.
_DELEGATE_TOOL = "delegate_to_agent"

# Note tools the specialists use to persist what they find. These names match
# the registered builtins from the memory layer (search_notes, read_note,
# create_note, append_note). Sources fetched in a run are written to notes so
# the synthesis agent can read them back without re-fetching.
_NOTE_WRITE_TOOLS = ["create_note", "append_note"]
_NOTE_READ_TOOLS = ["search_notes", "read_note", "list_notes"]


RESEARCH_TEAM: list[dict[str, object]] = [
    {
        "name": RESEARCH_COORDINATOR,
        "color": "#00d4ff",
        "description": "Plans subtopics, delegates research, and synthesizes the cited report",
        "system_prompt": (
            "You are the Research Coordinator for a Deep Research run. Break the "
            "question into a few focused subtopics. Delegate searching to the "
            "Research Searcher, page fetching to the Research Fetcher, and "
            "drafting to the Research Synthesizer using the delegate_to_agent "
            "tool. You are the only agent permitted to delegate. When you write "
            "the final report you MUST cite only URLs that the team actually "
            "fetched in this session; never cite a URL from memory and never "
            "invent a source. If a claim has no fetched source, say so plainly "
            "rather than fabricating a citation."
        ),
        # The coordinator is the sole delegator (DR-3); it also reads notes the
        # specialists wrote so it can synthesize.
        "allowed_tools": [_DELEGATE_TOOL, *_NOTE_READ_TOOLS],
    },
    {
        "name": SEARCH_AGENT,
        "color": "#ec4899",
        "description": "Runs web searches and records candidate sources",
        "system_prompt": (
            "You are the Research Searcher. Given a subtopic, run focused web "
            "searches and report the most relevant result URLs and titles. Do "
            "not fetch full pages and do not delegate; just surface candidate "
            "sources for the Fetcher to read."
        ),
        # Explicit list, no delegate_to_agent (DR-3): search plus note writing.
        "allowed_tools": ["web_search", *_NOTE_WRITE_TOOLS],
    },
    {
        "name": FETCH_AGENT,
        "color": "#f59e0b",
        "description": "Fetches and reads candidate pages, including PDFs and images",
        "system_prompt": (
            "You are the Research Fetcher. Given candidate URLs, read each page "
            "(including PDFs and images via analyze_file) and write the key "
            "facts to a note, recording the exact source URL you read. Never "
            "delegate. Only report content you actually fetched in this session."
        ),
        # Explicit list, no delegate_to_agent (DR-3): fetch/read plus note write.
        "allowed_tools": ["analyze_file", "read_file", *_NOTE_WRITE_TOOLS],
    },
    {
        "name": SYNTHESIS_AGENT,
        "color": "#a78bfa",
        "description": "Reads the gathered notes and drafts the cited report body",
        "system_prompt": (
            "You are the Research Synthesizer. Read the notes the team gathered "
            "and draft a structured report body. Attach an inline citation to "
            "every factual claim, citing only the source URLs recorded in this "
            "session. Never delegate and never invent a URL; if the notes do "
            "not support a claim, leave it out."
        ),
        # Explicit list, no delegate_to_agent (DR-3): read-only over notes.
        "allowed_tools": list(_NOTE_READ_TOOLS),
    },
]


def research_profiles() -> list[AgentProfile]:
    """Map each RESEARCH_TEAM entry to an AgentProfile.

    Mirrors the starter-team bootstrap shape so the orchestrator and any
    seeding path build the profiles identically. `default_model` is left unset
    so a seeded profile inherits the configured provider and model.
    """
    profiles: list[AgentProfile] = []
    for entry in RESEARCH_TEAM:
        profiles.append(
            AgentProfile(
                name=str(entry["name"]),
                system_prompt=str(entry["system_prompt"]),
                default_model=None,
                allowed_tools=list(entry["allowed_tools"]),  # type: ignore[arg-type]
                color=str(entry["color"]),
                description=str(entry["description"]),
            )
        )
    return profiles
