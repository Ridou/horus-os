"""Tests for the RESEARCH_TEAM agent profiles.

Covers DR-3: every research sub-agent profile has an explicit, non-None
allowed_tools list that omits delegate_to_agent, so no sub-agent can re-enter
the research coordinator. The coordinator is the only delegator.
"""

from __future__ import annotations

from horus_os.research.profiles import (
    FETCH_AGENT,
    RESEARCH_COORDINATOR,
    SEARCH_AGENT,
    SYNTHESIS_AGENT,
    research_profiles,
)
from horus_os.types import AgentProfile

_DELEGATE = "delegate_to_agent"


def _by_name() -> dict[str, AgentProfile]:
    return {p.name: p for p in research_profiles()}


def test_four_distinct_stable_profile_names() -> None:
    names = [RESEARCH_COORDINATOR, SEARCH_AGENT, FETCH_AGENT, SYNTHESIS_AGENT]
    assert len(set(names)) == 4
    profiles = _by_name()
    for name in names:
        assert name in profiles


def test_subagents_have_explicit_allowed_tools_without_delegation() -> None:
    profiles = _by_name()
    for name in (SEARCH_AGENT, FETCH_AGENT, SYNTHESIS_AGENT):
        prof = profiles[name]
        assert prof.allowed_tools is not None, f"{name} must not be unrestricted (DR-3)"
        assert _DELEGATE not in prof.allowed_tools, f"{name} must not delegate (DR-3)"
        assert len(prof.allowed_tools) > 0


def test_coordinator_may_delegate() -> None:
    coordinator = _by_name()[RESEARCH_COORDINATOR]
    assert coordinator.allowed_tools is not None
    assert _DELEGATE in coordinator.allowed_tools


def test_coordinator_prompt_forbids_uncited_urls() -> None:
    coordinator = _by_name()[RESEARCH_COORDINATOR]
    prompt = coordinator.system_prompt.lower()
    # DR-2 anti-hallucination instruction must be present.
    assert "cite only" in prompt or "only url" in prompt or "only cite" in prompt
    assert "fetched" in prompt


def test_profiles_map_to_agentprofile_instances() -> None:
    profiles = research_profiles()
    assert len(profiles) == 4
    for prof in profiles:
        assert isinstance(prof, AgentProfile)
        assert prof.default_model is None  # inherits configured provider/model
        assert prof.color
        assert prof.description
