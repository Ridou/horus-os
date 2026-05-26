"""Phase 33 Task 2 tests: run_agent_loop publishes LLMCallEvent per iteration.

The runner is the primary capture site for METRIC-01 (token usage per
LLM call). These tests pin down the contract:

1. One LLMCallEvent per Conversation.send call (Pitfall 1 substrate).
2. Anthropic usage keys (input_tokens, output_tokens, cache_*) flow
   through unchanged.
3. Gemini usage keys (prompt_token_count, candidates_token_count) get
   normalized into the Anthropic-shaped LLMCallEvent fields with cache_*
   zeroed.
4. Omitted trace_id yields an auto-generated 32-char hex.
5. A Conversation.send exception publishes a status="error" event and
   re-raises (capture is observability, never error handling).

The runner does NOT publish RunEndEvent; that is the caller's job (see
test_run_end_rollup_integration.py for the wired contract).
"""

from __future__ import annotations

from typing import Any

from horus_os import agent as agent_module
from horus_os.agent import run_agent_loop
from horus_os.observability import (
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.observability.bus import (
    LLMCallEvent,
    ObservationEvent,
    RunEndEvent,
)
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolUse


class _StubConversation:
    """Configurable stub Conversation matching the runner's call surface.

    `usage_per_call` is consumed left to right, one entry per send().
    `tool_uses_per_call` mirrors the cadence: first N-1 calls return a
    tool_use, the last returns no tool_uses so the loop terminates.
    """

    def __init__(
        self,
        usage_per_call: list[dict[str, Any]],
        provider: str = "stub",
        model_name: str = "stub-model",
        raise_on_call: int | None = None,
    ) -> None:
        self._usage_per_call = usage_per_call
        self._provider = provider
        self.model = model_name
        self._calls = 0
        self._raise_on_call = raise_on_call

    def send(self, prompt=None, tool_results=None, tools=None):
        del prompt, tool_results, tools
        if self._raise_on_call is not None and self._calls == self._raise_on_call:
            self._calls += 1
            raise ValueError("boom")
        usage = self._usage_per_call[self._calls] if self._calls < len(self._usage_per_call) else {}
        is_last = self._calls >= len(self._usage_per_call) - 1
        tool_uses = [] if is_last else [ToolUse(id=f"tu-{self._calls}", name="noop", input={})]
        text = "final" if is_last else ""
        self._calls += 1
        return AgentResult(
            text=text,
            tool_uses=tool_uses,
            provider=self._provider,
            model=self.model,
            usage=usage,
        )


def _noop_handler() -> str:
    return "noop-result"


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool for runner capture tests.",
            parameters={"type": "object", "properties": {}},
            handler=_noop_handler,
        )
    )
    return registry


def _install_stub(stub: _StubConversation, monkeypatch) -> None:
    """Monkey-patch the provider boundary to return the stub Conversation."""

    def factory(provider, model, *, system_prompt=None):
        del provider, model, system_prompt
        return stub

    monkeypatch.setattr(agent_module, "_new_conversation", factory)


def _collect_events(events: list[ObservationEvent]):
    def _on(event: ObservationEvent) -> None:
        events.append(event)

    return _on


def test_run_agent_loop_publishes_llm_call_per_iteration(monkeypatch) -> None:
    reset_observation_bus_for_tests()
    events: list[ObservationEvent] = []
    get_observation_bus().subscribe(_collect_events(events))
    usage = [
        {"input_tokens": 100, "output_tokens": 50},
        {"input_tokens": 100, "output_tokens": 50},
        {"input_tokens": 100, "output_tokens": 50},
    ]
    stub = _StubConversation(usage_per_call=usage)
    _install_stub(stub, monkeypatch)
    trace_id = "deadbeefcafebabe1234567890abcdef"

    run_agent_loop(
        "prompt",
        registry=_build_registry(),
        provider="anthropic",
        trace_id=trace_id,
    )

    llm_events = [e for e in events if isinstance(e, LLMCallEvent)]
    run_end_events = [e for e in events if isinstance(e, RunEndEvent)]
    assert len(llm_events) == 3
    assert [e.iteration_idx for e in llm_events] == [0, 1, 2]
    for e in llm_events:
        assert e.trace_id == trace_id
        assert e.provider == "anthropic"
        assert e.model == "stub-model"
        assert e.status == "success"
        assert e.latency_ms >= 0
    # Runner does NOT publish RunEndEvent; that is the caller's job.
    assert run_end_events == []


def test_run_agent_loop_extracts_anthropic_usage(monkeypatch) -> None:
    reset_observation_bus_for_tests()
    events: list[ObservationEvent] = []
    get_observation_bus().subscribe(_collect_events(events))
    usage = [
        {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 25,
            "cache_creation_input_tokens": 10,
        }
    ]
    stub = _StubConversation(usage_per_call=usage)
    _install_stub(stub, monkeypatch)
    run_agent_loop(
        "prompt",
        registry=_build_registry(),
        provider="anthropic",
        trace_id="t-anthropic",
    )
    llm_events = [e for e in events if isinstance(e, LLMCallEvent)]
    assert len(llm_events) == 1
    e = llm_events[0]
    assert e.input_tokens == 100
    assert e.output_tokens == 50
    assert e.cache_read_input_tokens == 25
    assert e.cache_creation_input_tokens == 10


def test_run_agent_loop_extracts_gemini_usage(monkeypatch) -> None:
    reset_observation_bus_for_tests()
    events: list[ObservationEvent] = []
    get_observation_bus().subscribe(_collect_events(events))
    usage = [{"prompt_token_count": 200, "candidates_token_count": 80}]
    stub = _StubConversation(usage_per_call=usage, provider="gemini")
    _install_stub(stub, monkeypatch)
    run_agent_loop(
        "prompt",
        registry=_build_registry(),
        provider="gemini",
        trace_id="t-gemini",
    )
    llm_events = [e for e in events if isinstance(e, LLMCallEvent)]
    assert len(llm_events) == 1
    e = llm_events[0]
    assert e.input_tokens == 200
    assert e.output_tokens == 80
    assert e.cache_read_input_tokens == 0
    assert e.cache_creation_input_tokens == 0


def test_run_agent_loop_generates_trace_id_when_omitted(monkeypatch) -> None:
    reset_observation_bus_for_tests()
    events: list[ObservationEvent] = []
    get_observation_bus().subscribe(_collect_events(events))
    usage = [{"input_tokens": 1, "output_tokens": 1}]
    _install_stub(_StubConversation(usage_per_call=usage), monkeypatch)
    run_agent_loop("prompt", registry=_build_registry(), provider="anthropic")
    llm_events = [e for e in events if isinstance(e, LLMCallEvent)]
    assert len(llm_events) == 1
    tid = llm_events[0].trace_id
    assert isinstance(tid, str)
    assert len(tid) == 32
    int(tid, 16)  # raises if not pure hex


def test_run_agent_loop_publishes_error_event_and_reraises(monkeypatch) -> None:
    reset_observation_bus_for_tests()
    events: list[ObservationEvent] = []
    get_observation_bus().subscribe(_collect_events(events))
    # Raise on the very first call (call index 0).
    stub = _StubConversation(usage_per_call=[{}], raise_on_call=0)
    _install_stub(stub, monkeypatch)
    raised = False
    try:
        run_agent_loop(
            "prompt",
            registry=_build_registry(),
            provider="anthropic",
            trace_id="t-err",
        )
    except ValueError:
        raised = True
    assert raised
    llm_events = [e for e in events if isinstance(e, LLMCallEvent)]
    assert len(llm_events) == 1
    e = llm_events[0]
    assert e.status == "error"
    assert e.error_type == "ValueError"
    assert e.input_tokens == 0
    assert e.output_tokens == 0
    assert e.latency_ms >= 0
