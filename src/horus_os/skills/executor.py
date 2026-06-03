"""SkillExecutor: progressive-disclosure body load and the three skill gates.

A skill is invoked through `use_skill` (plan 74-03). The level-1 menu carries
only names and descriptions; the full body is loaded here, on demand, when the
agent calls use_skill with a name. The executor enforces the three
Odysseus-derived skill pitfalls:

  SK-1 (capability gate): a skill declared `kind: code` refuses to run unless
       the invoking agent profile holds the SKILL_EXEC grant. Prompt-template
       skills run for any agent. The grant set is default-deny: an empty set
       blocks every code skill.
  SK-3 (no trusted bypass): the skill body runs as a scoped sub-loop against a
       registry filtered to the invoking agent's allowed_tools (intersected
       with the skill's own allowed_tools). A sub-tool absent from that
       filtered registry raises a KeyError out of the registry, never a silent
       success. The skill can never widen the agent's tool reach.

The skill body is executed through `run_agent_loop` against the filtered
registry, reusing the shared `IterationBudget` so a skill cannot escape the
run-level budget (the same safety valve delegation uses against runaway
recursion).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from horus_os.plugins.capability_catalog import Capability
from horus_os.skills.types import KIND_CODE

if TYPE_CHECKING:
    from collections.abc import Set

    from horus_os.skills.store import SkillStore
    from horus_os.tools.delegation import IterationBudget
    from horus_os.tools.registry import ToolRegistry


class SkillAuthorizationError(Exception):
    """Raised when a skill is not authorized to run as requested.

    Covers SK-1 (a code-bearing skill invoked without the SKILL_EXEC grant).
    Surfaced as an exception so the caller decides whether to capture it as a
    tool error string or let it propagate.
    """


def _intersect_allowed_tools(
    agent_allowed: list[str] | None,
    skill_allowed: list[str] | None,
) -> list[str] | None:
    """Compute the effective allowed_tools for a skill sub-loop.

    None on either side means "no extra restriction from that side"; the agent
    restriction is the security floor (SK-3): a skill can never widen the
    agent's tool set. The rules:

      - agent None, skill None   -> None (unrestricted, inherits the master).
      - agent None, skill list   -> the skill's list (a skill may narrow).
      - agent list, skill None   -> the agent's list (the floor).
      - agent list, skill list   -> the intersection, preserving agent order.
    """
    if agent_allowed is None:
        return list(skill_allowed) if skill_allowed is not None else None
    if skill_allowed is None:
        return list(agent_allowed)
    skill_set = set(skill_allowed)
    return [name for name in agent_allowed if name in skill_set]


class SkillExecutor:
    """Load and run a discovered skill under the three skill gates.

    Binds a `SkillStore` (the source of truth for skill bodies), the master
    `ToolRegistry`, the invoking agent's `allowed_tools` (None means
    unrestricted), the set of capabilities granted to the invoking agent
    profile (default-deny, an empty set blocks code skills), and the provider.
    `run(name, args, ...)` performs the progressive-disclosure body load, the
    SK-1 capability gate, and the SK-3 scoped sub-loop dispatch.
    """

    def __init__(
        self,
        *,
        store: SkillStore,
        master_registry: ToolRegistry,
        agent_allowed_tools: list[str] | None,
        granted_capabilities: Set[str],
        provider: str = "anthropic",
    ) -> None:
        self.store = store
        self.master_registry = master_registry
        self.agent_allowed_tools = agent_allowed_tools
        self.granted_capabilities = granted_capabilities
        self.provider = provider

    def run(
        self,
        name: str,
        args: dict | None = None,
        *,
        trace_id: str | None = None,
        budget: IterationBudget | None = None,
        model: str | None = None,
    ) -> str:
        """Load and run the named skill body, returning the sub-loop final text.

        Raises SkillAuthorizationError when the skill is `kind: code` and the
        invoking agent does not hold the SKILL_EXEC grant (SK-1). The sub-loop
        runs against a registry filtered to the effective allowed_tools so a
        sub-tool outside the agent's reach raises a KeyError out of the
        registry (SK-3). The shared `budget` bounds the whole tree.
        """
        # Local import breaks the agent <-> skills import cycle at module load
        # time: agent imports nothing from skills, but run_agent_loop pulls in
        # the tool loop, so we defer the import to call time exactly as the
        # delegation factory does.
        from horus_os.agent import run_agent_loop
        from horus_os.tools.delegation import _filter_registry

        skill = self.store.get_skill(name)
        if skill is None:
            raise KeyError(f"Skill {name!r} is not registered")

        # SK-1: a code-bearing skill is the high-risk class. It refuses to run
        # unless the invoking agent holds the SKILL_EXEC grant. Default-deny:
        # an empty grant set blocks every code skill and runs nothing.
        if skill.kind == KIND_CODE and Capability.SKILL_EXEC not in self.granted_capabilities:
            raise SkillAuthorizationError(
                f"Skill {name!r} is code-bearing and requires the "
                f"{Capability.SKILL_EXEC} capability grant; it was not run."
            )

        # SK-3: the agent's allowed_tools is the security floor. The skill may
        # narrow it but never widen it. The filtered registry omits any tool
        # outside that intersection, so a sub-tool call to it raises a KeyError
        # out of the registry rather than silently succeeding.
        effective_allowed = _intersect_allowed_tools(self.agent_allowed_tools, skill.allowed_tools)
        scoped_registry = _filter_registry(self.master_registry, effective_allowed)

        result = run_agent_loop(
            skill.body,
            registry=scoped_registry,
            provider=self.provider,
            model=model,
            budget=budget,
            trace_id=trace_id,
        )
        return result.text
