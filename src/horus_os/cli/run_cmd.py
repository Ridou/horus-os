"""`horus-os run <prompt>` subcommand."""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from typing import TextIO

from horus_os.agent import SUPPORTED_PROVIDERS, run_agent_loop, run_agent_stream
from horus_os.config import Config
from horus_os.memory import NotesStore
from horus_os.memory.tools import (
    append_note_tool,
    create_note_tool,
    list_notes_tool,
    read_note_tool,
    search_notes_tool,
)
from horus_os.storage import Database
from horus_os.tools import ToolRegistry, make_github_read_tool, read_file_tool
from horus_os.types import AgentProfile, AgentResult, ToolCallEvent, ToolResult

ENV_KEY_FOR = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def run_run(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    prompt: str = args.prompt
    config = Config.load(getattr(args, "data_dir", None))
    provider: str = getattr(args, "provider", None) or config.default_provider
    if provider not in SUPPORTED_PROVIDERS:
        stderr.write(
            f"Unknown provider {provider!r}. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}\n"
        )
        return 2

    if not _api_key_for(provider):
        stderr.write(
            f"No API key found for {provider}. Set {ENV_KEY_FOR[provider]} in your environment.\n"
        )
        if provider == "gemini":
            stderr.write("GOOGLE_API_KEY is accepted as a fallback.\n")
        return 2

    if not config.db_path.exists():
        stderr.write(f"No database at {config.db_path}. Run `horus-os init` first.\n")
        return 1

    db = Database(config.db_path)

    agent_name: str | None = getattr(args, "agent", None)
    profile: AgentProfile | None = None
    system_prompt: str | None = None
    if agent_name:
        profile = db.load_profile(agent_name)
        if profile is None:
            stderr.write(f"No agent profile named {agent_name!r}.\n")
            return 1
        system_prompt = profile.system_prompt

    model = (
        getattr(args, "model", None)
        or (profile.default_model if profile else None)
        or _model_for(config, provider)
    )
    max_iterations: int = getattr(args, "max_iterations", 10)
    record: bool = not getattr(args, "no_record", False)
    no_stream: bool = getattr(args, "no_stream", False)

    notes_store = NotesStore(config.notes_dir, on_write=lambda w: _record_note_write(db, w))
    registry = _build_default_registry(config, notes_store)

    if no_stream:
        return _run_buffered(
            prompt,
            provider=provider,
            model=model,
            max_iterations=max_iterations,
            record=record,
            system_prompt=system_prompt,
            agent_name=agent_name,
            registry=registry,
            db=db,
            stdout=stdout,
            stderr=stderr,
        )
    return _run_streaming(
        prompt,
        provider=provider,
        model=model,
        record=record,
        system_prompt=system_prompt,
        agent_name=agent_name,
        db=db,
        stdout=stdout,
        stderr=stderr,
    )


def _run_buffered(
    prompt: str,
    *,
    provider: str,
    model: str,
    max_iterations: int,
    record: bool,
    system_prompt: str | None,
    agent_name: str | None,
    registry: ToolRegistry,
    db: Database,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    tool_log: list[ToolResult] = []
    start = time.perf_counter()
    try:
        result = run_agent_loop(
            prompt,
            registry=registry,
            provider=provider,
            model=model,
            max_iterations=max_iterations,
            system_prompt=system_prompt,
            on_tool_result=tool_log.append,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        if record:
            db.record_trace(
                prompt,
                result,
                latency_ms=latency_ms,
                agent_profile_name=agent_name,
            )
        _print_result(stdout, result, latency_ms, tool_log)
        return 0
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        if record:
            db.record_trace(
                prompt,
                AgentResult(text="", tool_uses=[], provider=provider, model=model, usage={}),
                latency_ms=latency_ms,
                status="error",
                error_message=f"{type(exc).__name__}: {exc}",
                agent_profile_name=agent_name,
            )
        stderr.write(f"Agent run failed: {type(exc).__name__}: {exc}\n")
        return 1


def _run_streaming(
    prompt: str,
    *,
    provider: str,
    model: str,
    record: bool,
    system_prompt: str | None,
    agent_name: str | None,
    db: Database,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    text_parts: list[str] = []
    start = time.perf_counter()
    try:
        asyncio.run(
            _consume_stream(
                prompt,
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                text_parts=text_parts,
                stdout=stdout,
                stderr=stderr,
            )
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        stdout.write(f"\n\n[{provider}/{model}, {latency_ms}ms, streamed]\n")
        if record:
            db.record_trace(
                prompt,
                AgentResult(
                    text="".join(text_parts),
                    tool_uses=[],
                    provider=provider,
                    model=model,
                    usage={},
                ),
                latency_ms=latency_ms,
                agent_profile_name=agent_name,
            )
        return 0
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        if record:
            db.record_trace(
                prompt,
                AgentResult(
                    text="".join(text_parts),
                    tool_uses=[],
                    provider=provider,
                    model=model,
                    usage={},
                ),
                latency_ms=latency_ms,
                status="error",
                error_message=f"{type(exc).__name__}: {exc}",
                agent_profile_name=agent_name,
            )
        stderr.write(f"Agent run failed: {type(exc).__name__}: {exc}\n")
        return 1


async def _consume_stream(
    prompt: str,
    *,
    provider: str,
    model: str,
    system_prompt: str | None,
    text_parts: list[str],
    stdout: TextIO,
    stderr: TextIO,
) -> None:
    async for chunk in run_agent_stream(
        prompt,
        provider=provider,
        model=model,
        system=system_prompt,
    ):
        if isinstance(chunk, ToolCallEvent):
            stderr.write(f"[tool-request] {chunk.name}({chunk.input})\n")
            continue
        text_parts.append(chunk)
        stdout.write(chunk)
        stdout.flush()


def _api_key_for(provider: str) -> str | None:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _model_for(config: Config, provider: str) -> str:
    if provider == "anthropic":
        return config.anthropic_model
    return config.gemini_model


def _build_default_registry(config: Config, notes_store: NotesStore) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(read_file_tool(base_dir=config.notes_dir))
    registry.register(list_notes_tool(notes_store))
    registry.register(search_notes_tool(notes_store))
    registry.register(read_note_tool(notes_store))
    registry.register(create_note_tool(notes_store))
    registry.register(append_note_tool(notes_store))
    registry.register(make_github_read_tool())
    return registry


def _record_note_write(db: Database, write) -> None:
    db.record_note_write(
        operation=write.operation,
        rel_path=write.rel_path,
        bytes_before=write.bytes_before,
        bytes_after=write.bytes_after,
        content=write.content,
    )


def _print_result(
    stdout: TextIO,
    result: AgentResult,
    latency_ms: int,
    tool_log: list[ToolResult],
) -> None:
    stdout.write(result.text.rstrip() + "\n")
    stdout.write("\n")
    stdout.write(
        f"[{result.provider}/{result.model}, {latency_ms}ms, {len(tool_log)} tool calls]\n"
    )
    if tool_log:
        for r in tool_log:
            status = "ok" if r.error is None else r.error
            stdout.write(f"  - {r.name} ({r.latency_ms}ms): {status}\n")
