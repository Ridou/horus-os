"""The `use_skill` tool: progressive disclosure with the skill gates.

`use_skill_tool` builds a `use_skill` Tool bound to a SkillStore, the master
registry, the invoking agent's allowed_tools, the agent's granted-capabilities
set, and the run trace context. The tool's description is the LEVEL-1 menu:
only skill names and descriptions, never bodies (progressive disclosure,
SKILL-02). The full body loads only when the agent calls use_skill(name), which
the bound SkillExecutor handles.

The handler returns an error STRING for the recoverable cases (an unknown skill
name, a code-bearing skill the agent may not run) so `execute_tool_uses`
captures the outcome and the surrounding loop trace_id still produces one
tool_invocations row (SKILL-02 "traced"). The SK-3 path is intentionally NOT
caught: a sub-tool call to a tool outside the agent's allowed_tools raises a
KeyError out of the filtered registry so the authorization failure is loud, not
silent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from horus_os.skills.executor import SkillAuthorizationError, SkillExecutor
from horus_os.tools.registry import CollisionError, ToolRegistry
from horus_os.types import Tool

if TYPE_CHECKING:
    from collections.abc import Set

    from horus_os.skills.store import SkillStore
    from horus_os.tools.delegation import IterationBudget

_USE_SKILL_NAME = "use_skill"


def _build_menu(store: SkillStore) -> str:
    """Render the level-1 menu: skill names and descriptions only, no bodies.

    This text becomes the use_skill tool description the model sees at turn
    start. The body is never included; it loads only on use_skill(name).
    """
    summaries = store.list_skill_summaries()
    if not summaries:
        return "Run a named skill (a reusable instruction unit). No skills are available yet."
    lines = [
        "Run a named skill (a reusable instruction unit). Available skills:",
    ]
    for summary in summaries:
        description = summary.get("description") or "(no description)"
        lines.append(f"  - {summary['name']}: {description}")
    return "\n".join(lines)


def use_skill_tool(
    *,
    store: SkillStore,
    master_registry: ToolRegistry,
    agent_allowed_tools: list[str] | None,
    granted_capabilities: Set[str],
    provider: str = "anthropic",
    parent_trace_id: str | None = None,
    budget: IterationBudget | None = None,
    model: str | None = None,
) -> Tool:
    """Build a `use_skill` Tool bound to a SkillStore and the run context.

    The description is the level-1 menu (names + descriptions only). The
    handler closes over a SkillExecutor and calls `.run(name, args, ...)` with
    the run trace_id and the shared budget so a skill invocation traces as a
    tool_invocations row and is bounded by the run-level budget.
    """
    executor = SkillExecutor(
        store=store,
        master_registry=master_registry,
        agent_allowed_tools=agent_allowed_tools,
        granted_capabilities=granted_capabilities,
        provider=provider,
    )

    def _use_skill(name: str, args: dict | None = None) -> str:
        try:
            return executor.run(
                name,
                args,
                trace_id=parent_trace_id,
                budget=budget,
                model=model,
            )
        except KeyError:
            # Unknown skill name: recoverable, returned as a string so the loop
            # keeps going and the invocation still traces.
            return f"Error: skill {name!r} not found"
        except SkillAuthorizationError as exc:
            # SK-1: a code-bearing skill the agent may not run. Recoverable,
            # returned as a string; nothing was executed.
            return f"Error: {exc}"

    return Tool(
        name=_USE_SKILL_NAME,
        description=_build_menu(store),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the skill to run.",
                },
                "args": {
                    "type": "object",
                    "description": "Optional arguments to pass to the skill.",
                },
            },
            "required": ["name"],
        },
        handler=_use_skill,
    )


def register_use_skill(
    registry: ToolRegistry,
    *,
    store: SkillStore,
    agent_allowed_tools: list[str] | None,
    granted_capabilities: Set[str],
    provider: str = "anthropic",
    parent_trace_id: str | None = None,
    budget: IterationBudget | None = None,
    model: str | None = None,
    reserved_names: Set[str] | None = None,
) -> bool:
    """Register `use_skill` into `registry` when at least one skill exists.

    Returns True when the tool was registered, False when there are no skills
    (the install behaves exactly as before, no use_skill tool). This is the
    single place use_skill is added so the CLI and dashboard surfaces match.

    SK-2: a skill must not shadow a builtin or plugin tool name. Before
    exposing use_skill, every discovered skill name is checked against the
    names already registered in `registry` AND any additional `reserved_names`
    (discovered plugins). A skill whose name collides is refused: registration
    raises CollisionError naming the skill and the tool it would shadow, so the
    untrusted skill never silently shadows a real tool.
    """
    skills = store.list_skills()
    if not skills:
        return False

    reserved = set(reserved_names) if reserved_names is not None else set()
    existing = {tool.name for tool in registry.list()} | reserved
    for skill in skills:
        if skill.name in existing:
            raise CollisionError(
                f"Skill {skill.name!r} would shadow tool {skill.name!r}; refusing to register"
            )

    registry.register(
        use_skill_tool(
            store=store,
            master_registry=registry,
            agent_allowed_tools=agent_allowed_tools,
            granted_capabilities=granted_capabilities,
            provider=provider,
            parent_trace_id=parent_trace_id,
            budget=budget,
            model=model,
        )
    )
    return True
