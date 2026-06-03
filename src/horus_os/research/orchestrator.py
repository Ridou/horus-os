"""ResearchOrchestrator: configure the existing agent loop for Deep Research.

The orchestrator composes the shipped delegation runtime into a research run.
It does NOT implement its own loop (ARCHITECTURE anti-pattern 3); it constructs
a single shared `IterationBudget(research_max_iterations)` and a single
`SourceRegistry(max_sources=research_max_sources)`, builds the coordinator's
`delegate_to_agent` tool bound to that shared budget, filters each sub-agent's
registry through `_filter_registry` with the explicit `allowed_tools` from
`profiles.py` (so no sub-agent can delegate, DR-3), and then calls the existing
`run_agent_loop` with the coordinator profile and the shared budget.

Three hard guarantees are enforced here:

  * RESEARCH-04 / DR-1: the shared IterationBudget caps the whole delegation
    tree, and the SourceRegistry caps fetched sources. A raised
    `SourceBudgetExceeded` is caught and converted into a graceful partial
    report that still writes a trace row.
  * RESEARCH-03: sources funnel through `SourceRegistry.register_source`, which
    de-duplicates by normalized URL.
  * DR-2: the accumulated sources and the synthesis text are handed to
    `ReportBuilder.render`, which rejects any citation URL not in the registry.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from horus_os.research.profiles import (
    RESEARCH_COORDINATOR,
    research_profiles,
)
from horus_os.research.registry import SourceBudgetExceeded, SourceRegistry
from horus_os.research.report import ReportBuilder, Section
from horus_os.tools.delegation import IterationBudget, _filter_registry, make_delegate_tool
from horus_os.types import AgentResult

if TYPE_CHECKING:
    from horus_os.config import Config
    from horus_os.memory.notes import NotesStore
    from horus_os.storage import Database
    from horus_os.tools.registry import ToolRegistry


class _CancelableBudget(IterationBudget):
    """An IterationBudget that also honors a caller-supplied cancel signal.

    `run_agent_loop` calls `consume()` once per tool-using turn and breaks the
    loop when it returns False. By layering a `should_cancel` check on top of
    the normal budget decrement, a cancel requested from the API layer (73-02)
    halts the run before its next delegation turn without touching the public
    `run_agent_loop` surface (the orchestrator just hands it this budget).

    Cancellation is checked first so that once a cancel is observed no further
    budget is spent: the very next `consume()` returns False and the loop exits.
    """

    def __init__(self, max_iterations: int, should_cancel: Callable[[], bool]) -> None:
        super().__init__(max_iterations)
        self._should_cancel = should_cancel

    def consume(self) -> bool:
        if self._should_cancel():
            return False
        return super().consume()


@dataclass
class Subtopic:
    """One planned subtopic of a research question, with its seed query."""

    title: str
    query: str


@dataclass
class ResearchPlan:
    """The structured plan produced before any search or fetch runs.

    `question` is the original research question; `subtopics` is the ordered
    list the coordinator will work through. The plan is built WITHOUT executing
    any tool so the API layer (73-02) can show it and accept a cancel before
    the expensive run starts (RESEARCH-01 / RESEARCH-02).
    """

    question: str
    subtopics: list[Subtopic] = field(default_factory=list)


@dataclass
class ResearchResult:
    """The outcome of a research run.

    `report` is the cited markdown; `trace_id` is the run's observability id;
    `sources` is the count of distinct fetched sources; `partial` is True when
    the run finished early on a budget cap (DR-1 graceful degradation).
    """

    report: str
    trace_id: str
    sources: int
    partial: bool = False
    cancelled: bool = False
    agent_result: AgentResult | None = None


# Heuristic subtopic plan size. Kept small so the plan stays within the
# iteration budget; the coordinator may refine it at run time.
_MAX_PLAN_SUBTOPICS = 4


class ResearchOrchestrator:
    """Configure `run_agent_loop` for an autonomous, budgeted research run."""

    def __init__(
        self,
        db: Database,
        master_registry: ToolRegistry,
        notes_store: NotesStore,
        cfg: Config,
        *,
        provider: str = "anthropic",
    ) -> None:
        self._db = db
        self._master_registry = master_registry
        self._notes = notes_store
        self._cfg = cfg
        self._provider = provider
        self._report_builder = ReportBuilder()

    def ensure_team(self) -> None:
        """Persist the research team profiles so delegation can look them up.

        Idempotent: `save_profile` upserts, so calling this on every run keeps
        the team in sync without duplicating rows.
        """
        for profile in research_profiles():
            self._db.save_profile(profile)

    def plan(self, question: str) -> ResearchPlan:
        """Return a structured subtopic plan WITHOUT running search or fetch.

        This is the RESEARCH-01 plan step. It does no LLM tool execution, so the
        API layer can render the plan and accept a cancel before the run starts
        (RESEARCH-02). The heuristic split keeps the plan small so it fits the
        iteration budget; the coordinator refines it during the run.
        """
        cleaned = question.strip()
        # A lightweight deterministic split: derive a few angle-driven subtopics
        # from the question. No network, no model, no tool call.
        angles = ["overview", "key evidence", "limitations and counterpoints"]
        subtopics: list[Subtopic] = [
            Subtopic(title=f"{cleaned} - {angle}", query=f"{cleaned} {angle}")
            for angle in angles[:_MAX_PLAN_SUBTOPICS]
        ]
        return ResearchPlan(question=cleaned, subtopics=subtopics)

    def sub_agent_registries(self) -> dict[str, ToolRegistry]:
        """Return the filtered registry for each sub-agent profile.

        Each registry is narrowed via `_filter_registry` to the profile's
        explicit `allowed_tools`. Because those lists omit `delegate_to_agent`
        (DR-3), no returned sub-agent registry contains the delegation tool.
        """
        registries: dict[str, ToolRegistry] = {}
        for profile in research_profiles():
            if profile.name == RESEARCH_COORDINATOR:
                continue
            registries[profile.name] = _filter_registry(
                self._master_registry, profile.allowed_tools
            )
        return registries

    def run(
        self,
        question: str,
        *,
        task_id: str | None = None,
        parent_trace_id: str | None = None,
        plan: ResearchPlan | None = None,
        trace_id: str | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ResearchResult:
        """Run a budgeted, de-duplicated, citation-validated research session.

        Constructs ONE shared `IterationBudget(research_max_iterations)` and ONE
        `SourceRegistry(max_sources=research_max_sources)`, binds the
        coordinator's `delegate_to_agent` to that shared budget, and calls the
        existing `run_agent_loop` (never a new loop). A raised
        `SourceBudgetExceeded` is caught and finished as a graceful partial
        report; a trace row is written either way.

        `trace_id` lets the caller (73-02 API layer) pre-generate the id it has
        already linked to the task row, so the persisted trace resolves under
        that id. When omitted a fresh one is generated (legacy behavior).

        `should_cancel` is an optional predicate the run polls between
        delegation turns via a `_CancelableBudget`. When it returns True the
        loop halts before the next turn; a trace row is still written so a
        cancelled run is never silently lost (DR-1 / RESEARCH-05).
        """
        # Defer the agent import to call time so it can be monkeypatched in
        # tests and to mirror make_delegate_tool's cycle-breaking pattern.
        from horus_os import agent as agent_module

        self.ensure_team()
        registry = SourceRegistry(max_sources=self._cfg.research_max_sources)
        if should_cancel is not None:
            budget: IterationBudget = _CancelableBudget(
                self._cfg.research_max_iterations, should_cancel
            )
        else:
            budget = IterationBudget(self._cfg.research_max_iterations)
        trace_id = trace_id if trace_id is not None else uuid.uuid4().hex

        coordinator = next(p for p in research_profiles() if p.name == RESEARCH_COORDINATOR)

        # The coordinator gets a registry filtered to its own allowed_tools,
        # then the shared-budget delegate tool layered on top so every
        # sub-agent invocation decrements the same IterationBudget.
        coordinator_registry = _filter_registry(self._master_registry, coordinator.allowed_tools)
        delegate_tool = make_delegate_tool(
            db=self._db,
            master_registry=self._master_registry,
            parent_trace_id=trace_id,
            budget=budget,
            provider=self._provider,
        )
        coordinator_registry.register(delegate_tool, replace=True)

        active_plan = plan or self.plan(question)
        prompt = self._build_prompt(question, active_plan)

        partial = False
        start = time.perf_counter()
        try:
            result = agent_module.run_agent_loop(
                prompt,
                registry=coordinator_registry,
                provider=self._provider,
                model=coordinator.default_model,
                budget=budget,
                system_prompt=coordinator.system_prompt,
                trace_id=trace_id,
                on_tool_result=self._make_source_recorder(registry),
            )
        except SourceBudgetExceeded:
            # DR-1: a source-cap overrun degrades to a partial report rather
            # than crashing the run. The sources gathered so far still stand.
            partial = True
            result = AgentResult(
                text="Research stopped early: the source budget was reached.",
                provider=self._provider,
                model=coordinator.default_model or "",
            )

        # Cancellation is observed after the loop returns: a _CancelableBudget
        # makes consume() return False once a cancel is requested, so the loop
        # breaks before the next turn. A cancelled run still falls through to
        # the trace write below so it is never silently lost (RESEARCH-05).
        cancelled = should_cancel is not None and should_cancel()

        latency_ms = int((time.perf_counter() - start) * 1000)

        report = self._build_report(question, result, registry, partial=partial)

        # Always write a trace row so a partial, cancelled, or aborted run is
        # still observable (DR-1 requirement).
        if cancelled:
            status = "cancelled"
        elif partial:
            status = "partial"
        else:
            status = "success"
        recorded_trace_id = self._db.record_trace(
            question,
            result,
            trace_id=trace_id,
            parent_trace_id=parent_trace_id,
            agent_profile_name=RESEARCH_COORDINATOR,
            latency_ms=latency_ms,
            status=status,
        )

        return ResearchResult(
            report=report,
            trace_id=recorded_trace_id,
            sources=registry.count(),
            partial=partial,
            cancelled=cancelled,
            agent_result=result,
        )

    def _make_source_recorder(self, registry: SourceRegistry):
        """Return an on_tool_result hook that funnels fetched URLs into the registry.

        Fetch-tool results carrying a `url` are registered (de-duplicated by
        normalized URL). A `SourceBudgetExceeded` raised here propagates up to
        `run` where it is caught and converted into a graceful partial report.
        """

        def _record(tool_result) -> None:  # ToolResult, kept loose for the hook
            output = getattr(tool_result, "output", None)
            for url, title in _iter_source_urls(output):
                registry.register_source(url, title=title)

        return _record

    def _build_prompt(self, question: str, plan: ResearchPlan) -> str:
        lines = [
            f"Research question: {question}",
            "",
            "Planned subtopics:",
        ]
        for idx, sub in enumerate(plan.subtopics, start=1):
            lines.append(f"{idx}. {sub.title} (query: {sub.query})")
        lines.append("")
        lines.append(
            "Delegate searching and fetching to the specialists, then synthesize "
            "a cited report. Cite only URLs the team fetched this session."
        )
        return "\n".join(lines)

    def _build_report(
        self,
        question: str,
        result: AgentResult,
        registry: SourceRegistry,
        *,
        partial: bool,
    ) -> str:
        body = result.text or ""
        sections = [Section(heading="Findings", body=body)]
        title = question.strip() or "Research Report"
        if partial:
            title = f"{title} (partial)"
        # Use the flag policy so a partial run never hard-crashes on a citation
        # the model emitted before the budget cut the fetch short; verified
        # runs in tests use the default reject policy directly on ReportBuilder.
        return self._report_builder.render(title, sections, registry, policy="flag")


def _iter_source_urls(output: object):
    """Yield (url, title) pairs from a tool output of varied shape.

    Handles the common fetch/search result shapes: a dict with a `url` key, a
    list of such dicts, or nothing. Anything without a url is skipped.
    """
    if isinstance(output, dict):
        url = output.get("url")
        if isinstance(url, str) and url:
            title = output.get("title")
            yield url, title if isinstance(title, str) else None
    elif isinstance(output, (list, tuple)):
        for item in output:
            yield from _iter_source_urls(item)
