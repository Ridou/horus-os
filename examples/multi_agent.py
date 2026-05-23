"""Multi-agent example: coordinator delegating to a named sub-agent.

This example shows how to:

1. Initialize a horus-os SQLite database in a temp directory.
2. Save a named `AgentProfile` ("summarizer") alongside the bootstrapped
   "default" profile.
3. Build a `delegate_to_agent` tool via `make_delegate_tool` and register
   it on a master `ToolRegistry`.
4. Invoke the tool's handler directly to simulate the coordinator
   calling the sub-agent.
5. Read back the resulting parent/child trace linkage.

The example runs offline. The provider call inside `make_delegate_tool`
goes through `run_agent_loop`, which we stub to a function that returns
a canned `AgentResult`. To use a real provider instead, remove the stub
block and set `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` in your
environment. The rest of the script does not change.

Run it:

    python examples/multi_agent.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from horus_os import (
    AgentProfile,
    AgentResult,
    Database,
    ToolRegistry,
)
from horus_os import agent as agent_module
from horus_os.tools.delegation import IterationBudget, make_delegate_tool


def _stub_run_agent_loop() -> None:
    """Replace `run_agent_loop` with an offline fake.

    The real `run_agent_loop` would call Anthropic or Gemini through
    their SDKs. For an offline, network-free example we hand back a
    deterministic `AgentResult` so the delegation path exercises the
    storage and trace linkage code without any provider configuration.
    """

    def fake_run_agent_loop(prompt: str, **kwargs: Any) -> AgentResult:
        profile_hint = kwargs.get("system_prompt", "")
        return AgentResult(
            text=(
                f"[stub sub-agent] received task: {prompt!r}; "
                f"running with system prompt prefix {profile_hint[:30]!r}"
            ),
            provider="stub",
            model=kwargs.get("model") or "stub-model",
            usage={"input_tokens": 0, "output_tokens": 0},
        )

    agent_module.run_agent_loop = fake_run_agent_loop


def main() -> None:
    _stub_run_agent_loop()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "horus.db"
        db = Database(db_path)
        db.init()  # bootstraps the default profile and schema v4

        db.save_profile(
            AgentProfile(
                name="summarizer",
                system_prompt=("You are a terse summarizer. Reply in one sentence."),
                default_model=None,
                allowed_tools=None,
                memory_scope=None,
            )
        )

        # The coordinator's master registry. A real script would also
        # register tools like read_file_tool or the notes tools here.
        master = ToolRegistry()

        # The coordinator already has its own trace row in storage. For
        # the example we synthesize a parent trace so the child rows
        # have something to point at.
        parent_id = db.record_trace(
            "Summarize today's notes.",
            AgentResult(
                text="(coordinator turn; would normally come from a real run)",
                provider="stub",
                model="stub-model",
            ),
        )

        delegate_tool = make_delegate_tool(
            db=db,
            master_registry=master,
            parent_trace_id=parent_id,
            budget=IterationBudget(10),
            provider="anthropic",
        )
        master.register(delegate_tool)

        # Invoke the delegate tool the same way the coordinator would
        # invoke it after the model emits a tool_use block.
        assert delegate_tool.handler is not None
        result_text = delegate_tool.handler(
            agent_name="summarizer",
            task="Summarize: rain at 11am, sun at 3pm, dinner at 7pm.",
        )

        print("Coordinator received from summarizer:")
        print(f"  {result_text}")
        print()

        children = db.list_child_traces(parent_id)
        print(f"Parent trace {parent_id} now has {len(children)} child trace(s):")
        for child in children:
            print(
                f"  trace_id={child.trace_id} "
                f"agent={child.agent_profile_name} "
                f"prompt={child.prompt!r}"
            )


if __name__ == "__main__":
    main()
