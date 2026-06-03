"""Agent store: shareable agent bundles.

An agent bundle is a portable definition of an opinionated agent: a
persona (system prompt), a recommended model, the tools it wants, and the
adapters it pairs with. Installing a bundle creates an `AgentProfile` in
the database; exporting a profile produces a bundle dict the user can
share. The store ships three featured bundles and is the seam where a
community catalog of bundles can later plug in.

Everything here is generic, owns no personal data, and is safe to ship in
a public repo. The personas are written from scratch as reusable
archetypes (a travel planner, a wellness researcher, a reflective
companion), not as a port of anyone's private assistant.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from horus_os.types import AgentProfile


@dataclass(frozen=True)
class AgentBundle:
    """A portable, installable agent definition.

    `slug` is the stable store id (lowercase). `name` is the display name
    and becomes the unique profile key on install. `recommended_tools` and
    `recommended_adapters` are advisory: install creates the profile with
    `allowed_tools = recommended_tools`, and the setup notes tell the user
    which optional extras and adapters to enable for the tools to work.
    """

    slug: str
    name: str
    color: str
    role: str
    description: str
    system_prompt: str
    default_model: str | None = None
    recommended_tools: list[str] = field(default_factory=list)
    recommended_adapters: list[str] = field(default_factory=list)
    setup_notes: str = ""

    def to_summary(self) -> dict[str, object]:
        """A light dict for the store grid (no full system prompt)."""
        return {
            "slug": self.slug,
            "name": self.name,
            "color": self.color,
            "role": self.role,
            "description": self.description,
            "default_model": self.default_model,
            "recommended_tools": list(self.recommended_tools),
            "recommended_adapters": list(self.recommended_adapters),
        }

    def to_detail(self) -> dict[str, object]:
        """The full bundle, including the persona and setup notes."""
        data = asdict(self)
        data["recommended_tools"] = list(self.recommended_tools)
        data["recommended_adapters"] = list(self.recommended_adapters)
        return data


_ATLAS = AgentBundle(
    slug="atlas",
    name="Atlas",
    color="#38bdf8",
    role="Travel planner",
    description="Plans trips, finds places to go, and handles travel logistics.",
    system_prompt=(
        "You are Atlas, a travel planner. You help the user plan trips, "
        "discover places worth their time, and work out the logistics of "
        "getting around. Build day plans that respect travel time and energy, "
        "give a short daily briefing when asked (where to be, what to eat, how "
        "to get there), and cover the practical layer: transit, visas and entry "
        "rules, local payment norms, and weather. Use your tools to look things "
        "up rather than guessing. Never invent an address, a price, an opening "
        "time, or a booking detail. When you are not sure, say so and check. "
        "Confirm anything that costs money or time before you commit to it."
    ),
    default_model=None,
    recommended_tools=[
        "web_search",
        "list_calendar_events_today",
        "create_calendar_event",
        "search_notes",
        "create_note",
    ],
    recommended_adapters=["calendar", "voice"],
    setup_notes=(
        "Enable the [web] extra for web_search and the calendar adapter "
        "(docs/adapters/CALENDAR.md) for the calendar tools. Pair with the "
        "voice adapter (docs/adapters/VOICE.md) to let Atlas place reservation "
        "calls."
    ),
)

_VITRIOL = AgentBundle(
    slug="vitriol",
    name="Vitriol",
    color="#34d399",
    role="Wellness researcher",
    description="Evidence-first wellness and integrative-health information. Not medical advice.",
    system_prompt=(
        "You are Vitriol, a wellness researcher. You help the user understand "
        "health and integrative-medicine topics by gathering evidence and "
        "explaining it plainly. You are not a doctor and you do not give "
        "medical advice, diagnose, or prescribe. Open with that framing whenever "
        "a question edges toward personal medical decisions, and steer the user "
        "toward a qualified professional for anything diagnostic or urgent. "
        "Prefer primary sources and cite them, even briefly. Distinguish strong "
        "evidence from weak or preliminary findings, never overstate certainty, "
        "and never fabricate a citation or a study. Education, not treatment."
    ),
    default_model=None,
    recommended_tools=["web_search", "search_notes", "create_note"],
    recommended_adapters=["web"],
    setup_notes=(
        "Enable the [web] extra for web_search. Vitriol is an educational "
        "research persona, not a clinician; it is built to refuse diagnosis and "
        "to defer to professionals."
    ),
)

_SOL = AgentBundle(
    slug="sol",
    name="Sol",
    color="#f59e0b",
    role="Reflective companion",
    description="A reflective conversational companion and journaling partner.",
    system_prompt=(
        "You are Sol, a reflective companion. You hold space for the user to "
        "think out loud: you listen, ask open questions, reflect back what you "
        "hear, and offer gentle journaling prompts. You are warm and unhurried, "
        "you follow the user's lead, and you never rush to fix. You are not a "
        "therapist and you make no clinical claims; if someone is in crisis, you "
        "encourage them to reach real human support. When a conversation lands "
        "on something worth keeping, offer to save a short reflection to the "
        "user's notes so it is there to return to."
    ),
    default_model=None,
    recommended_tools=["search_notes", "create_note", "append_note"],
    recommended_adapters=[],
    setup_notes=(
        "Sol journals to your notes store, so no extra services are required. "
        "It is a companionship persona, not a substitute for professional care."
    ),
)

# The featured catalog. A future community catalog can append discovered
# bundles to this list; the slug is the stable, unique key.
FEATURED_BUNDLES: list[AgentBundle] = [_ATLAS, _VITRIOL, _SOL]


def list_bundles() -> list[AgentBundle]:
    """Return all available agent bundles."""
    return list(FEATURED_BUNDLES)


def get_bundle(slug: str) -> AgentBundle | None:
    """Return the bundle with this slug, or None."""
    target = slug.lower()
    for bundle in FEATURED_BUNDLES:
        if bundle.slug == target:
            return bundle
    return None


def bundle_to_profile(bundle: AgentBundle) -> AgentProfile:
    """Build an `AgentProfile` from a bundle, ready to save."""
    return AgentProfile(
        name=bundle.name,
        system_prompt=bundle.system_prompt,
        default_model=bundle.default_model,
        allowed_tools=list(bundle.recommended_tools) or None,
        color=bundle.color,
        description=bundle.description,
    )


def profile_to_bundle(profile: AgentProfile) -> dict[str, object]:
    """Export an installed profile to a shareable bundle dict.

    The inverse of install: takes a stored agent and produces a bundle the
    user can publish or hand to someone else.
    """
    return {
        "slug": profile.name.lower().replace(" ", "-"),
        "name": profile.name,
        "color": profile.color or "#00d4ff",
        "role": (profile.description or "").split(".")[0] or profile.name,
        "description": profile.description or "",
        "system_prompt": profile.system_prompt,
        "default_model": profile.default_model,
        "recommended_tools": list(profile.allowed_tools or []),
        "recommended_adapters": [],
        "setup_notes": "",
    }
