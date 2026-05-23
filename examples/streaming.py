"""Streaming example: consuming `run_agent_stream`.

This example shows how to:

1. Stub the Anthropic streaming helper with an async generator that
   yields tokens followed by a `ToolCallEvent`. This keeps the script
   offline.
2. Consume `run_agent_stream` token by token using `async for`.
3. Treat `str` yields as text deltas and `ToolCallEvent` yields as
   tool requests (which the streaming surface intentionally does not
   execute; that is `run_agent_loop`'s job).

To run against the live Anthropic API instead, delete the stub block
below and set `ANTHROPIC_API_KEY` in your environment. The rest of
the script does not change.

Run it:

    python examples/streaming.py
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from horus_os import ToolCallEvent, run_agent_stream
from horus_os._providers import _anthropic


def _stub_anthropic_stream() -> None:
    """Replace the Anthropic streaming helper with an offline fake.

    The fake yields a few text deltas, then a `ToolCallEvent` so the
    example shows both surfaces a real consumer would handle.
    """

    async def fake_stream(prompt: str, **kwargs: Any) -> Any:
        for token in ["Hello", ", ", "world", "!"]:
            yield token
        yield ToolCallEvent(name="read_file", input={"path": "notes.md"})

    _anthropic.stream_anthropic_async = fake_stream


async def main() -> None:
    _stub_anthropic_stream()

    print("Streaming response: ", end="", flush=True)
    tool_calls: list[ToolCallEvent] = []
    async for chunk in run_agent_stream(
        "Greet the world and ask to read notes.",
        provider="anthropic",
    ):
        if isinstance(chunk, ToolCallEvent):
            tool_calls.append(chunk)
            continue
        # chunk is a str token; write without a newline so the response
        # paints as it arrives.
        print(chunk, end="", flush=True)
    print()  # final newline after the text stream

    if tool_calls:
        print(file=sys.stderr)
        for event in tool_calls:
            print(
                f"[tool-request] {event.name}({event.input})",
                file=sys.stderr,
            )


if __name__ == "__main__":
    asyncio.run(main())
