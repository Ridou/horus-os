"""Native Deep Research engine for horus-os (v0.8 flagship).

This package composes the shipped delegation primitives (IterationBudget,
make_delegate_tool, run_agent_loop) and the NotesStore into an autonomous
multi-agent research capability. The three non-negotiable guarantees are:

  1. Hard budget enforcement: a single shared IterationBudget caps the whole
     delegation tree and a SourceRegistry caps fetched sources (RESEARCH-04).
  2. Source de-duplication by normalized URL so a source is never counted
     twice (RESEARCH-03).
  3. Zero hallucinated citations: the ReportBuilder validates every cited URL
     against the session SourceRegistry before rendering (DR-2).

License note (SEED-004): this engine is built NATIVE on the horus-os
delegation runtime. It is NOT ported from Alibaba-NLP/DeepResearch, which
avoids that project's port-license entanglement.

The HTTP surface (the FastAPI APIRouter for POST /api/research and the
progress / report / cancel routes) lives in `horus_os.research.api`. It is
deliberately NOT re-exported here so importing this package stays free of the
optional fastapi dependency; `server.api` imports the router directly from
`horus_os.research.api`.
"""

from __future__ import annotations

from horus_os.research.orchestrator import (
    ResearchOrchestrator,
    ResearchPlan,
    ResearchResult,
    Subtopic,
)
from horus_os.research.profiles import (
    FETCH_AGENT,
    RESEARCH_COORDINATOR,
    RESEARCH_TEAM,
    SEARCH_AGENT,
    SYNTHESIS_AGENT,
    research_profiles,
)
from horus_os.research.registry import Source, SourceBudgetExceeded, SourceRegistry
from horus_os.research.report import ReportBuilder, UnverifiedCitation

__all__ = [
    "FETCH_AGENT",
    "RESEARCH_COORDINATOR",
    "RESEARCH_TEAM",
    "SEARCH_AGENT",
    "SYNTHESIS_AGENT",
    "ReportBuilder",
    "ResearchOrchestrator",
    "ResearchPlan",
    "ResearchResult",
    "Source",
    "SourceBudgetExceeded",
    "SourceRegistry",
    "Subtopic",
    "UnverifiedCitation",
    "research_profiles",
]
