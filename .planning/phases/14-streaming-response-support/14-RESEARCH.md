# Phase 14: Streaming Response Support - Research

**Researched:** 2026-05-23
**Domain:** Async streaming, Anthropic SDK streaming, Google GenAI SDK streaming, Python async generators
**Confidence:** HIGH

## Summary

Phase 14 introduces `run_agent_stream`, an async generator that yields incremental text tokens from both Anthropic and Gemini providers. Both SDKs ship native streaming paths (Anthropic 0.96.0 `messages.stream()`, Gemini 1.70.0 `aio.models.generate_content_stream()`), verified against the installed SDK versions in this repo. Neither path requires custom HTTP handling -- the SDKs handle chunked transfer decoding internally.

The key design constraint is that streaming and tool use do not compose in a single pass. When a model returns tool calls mid-stream, you must accumulate the full response before dispatching tools. Phase 14 therefore scopes `run_agent_stream` to text-only streaming (no tool execution in the stream path). The existing `run_agent_loop` handles tool execution and remains unchanged. This is consistent with how most production systems implement streaming.

`run_agent` and `run_agent_loop` must remain 100% backward-compatible. The new function is purely additive.

**Primary recommendation:** Implement `run_agent_stream` as a top-level async generator in `agent.py` that delegates to per-provider async streaming helpers in `_anthropic.py` and `_gemini.py`. Yield `str` tokens. No new type needed for Phase 14 -- tokens are plain strings.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Token streaming (text bytes) | API / Backend (provider module) | -- | SDKs handle chunk framing; logic lives in provider layer |
| Async generator interface | API / Backend (agent.py) | -- | Same layer as run_agent, run_agent_loop |
| CLI display of tokens | CLI surface | -- | Phase 15 concern; out of scope for Phase 14 |
| Dashboard live tokens | Frontend Server | -- | Phase 16 concern; out of scope for Phase 14 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.96.0 | Anthropic SDK with native streaming | Already installed; ships MessageStreamManager |
| google-genai | 1.70.0 | Gemini SDK with async streaming | Already installed; ships aio.models.generate_content_stream |

[VERIFIED: pip show in this repo]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| collections.abc.AsyncGenerator | stdlib | Return type annotation | Annotate run_agent_stream |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| messages.stream() | messages.create(stream=True) | create(stream=True) uses less memory (no accumulation), but also provides no .text_stream convenience -- stream() is clearer for text-only callers |
| AsyncGenerator[str, None] | AsyncIterator[str] | Either works; AsyncGenerator is slightly more precise for a function using `yield` |

**Installation:** No new packages. Both SDKs are already in requirements.

## Architecture Patterns

### System Architecture Diagram

```
caller
  |
  | async for token in run_agent_stream(prompt, provider=...)
  v
agent.py::run_agent_stream
  |-- provider == "anthropic" --> _anthropic.py::stream_anthropic_async
  |       |
  |       | AsyncAnthropic().messages.stream(model, messages, max_tokens)
  |       | async for text in stream.text_stream: yield text
  |
  `-- provider == "gemini"   --> _gemini.py::stream_gemini_async
          |
          | client.aio.models.generate_content_stream(model, contents, config)
          | async for chunk in ...: if chunk.text: yield chunk.text
```

### Recommended Project Structure

No new files needed. Changes touch:

```
src/horus_os/
├── agent.py              # add run_agent_stream
├── _providers/
│   ├── _anthropic.py     # add stream_anthropic_async
│   └── _gemini.py        # add stream_gemini_async
tests/
├── test_agent.py         # add run_agent_stream tests (monkeypatched)
├── test_provider_anthropic.py  # add streaming unit tests
└── test_provider_gemini.py     # add streaming unit tests
```

No new modules, no new types for Phase 14. Additive changes only.

### Pattern 1: Anthropic async streaming

**What:** Use `AsyncAnthropic().messages.stream()` as an async context manager, iterate `stream.text_stream` for plain string deltas.
**When to use:** Any text-only single-turn streaming call to Anthropic.

```python
# Source: Context7 /anthropics/anthropic-sdk-python + SDK introspection (0.96.0)
from anthropic import AsyncAnthropic
from collections.abc import AsyncGenerator

async def stream_anthropic_async(
    prompt: str,
    *,
    model: str,
    max_tokens: int = 1024,
    system: str | None = None,
) -> AsyncGenerator[str, None]:
    client = AsyncAnthropic()
    request: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        request["system"] = system
    async with client.messages.stream(**request) as stream:
        async for text in stream.text_stream:
            yield text
```

### Pattern 2: Gemini async streaming

**What:** Use `client.aio.models.generate_content_stream()`, which returns `AsyncIterator[GenerateContentResponse]`. Each chunk exposes a `.text` property (concatenation of all text parts in the chunk).
**When to use:** Any text-only single-turn streaming call to Gemini.

```python
# Source: SDK introspection (google-genai 1.70.0), method signature verified
from google import genai
from collections.abc import AsyncGenerator

async def stream_gemini_async(
    prompt: str,
    *,
    model: str,
    system: str | None = None,
) -> AsyncGenerator[str, None]:
    api_key = _read_api_key()
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    config_kwargs: dict = {}
    if system:
        config_kwargs["system_instruction"] = system
    from google.genai import types as genai_types
    config = genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
    request: dict = {"model": model, "contents": prompt}
    if config:
        request["config"] = config
    async for chunk in client.aio.models.generate_content_stream(**request):
        if chunk.text:
            yield chunk.text
```

### Pattern 3: Top-level run_agent_stream dispatcher

**What:** Mirrors `run_agent` / `run_agent_async` signature; dispatches to the correct provider streaming helper.

```python
# Source: codebase pattern from agent.py
from collections.abc import AsyncGenerator

async def run_agent_stream(
    prompt: str,
    *,
    provider: str = "anthropic",
    model: str | None = None,
    max_tokens: int = 1024,
    system: str | None = None,
) -> AsyncGenerator[str, None]:
    _check_provider(provider)
    if provider == "anthropic":
        async for token in _anthropic.stream_anthropic_async(
            prompt, model=model or _anthropic.DEFAULT_MODEL,
            max_tokens=max_tokens, system=system,
        ):
            yield token
    else:
        async for token in _gemini.stream_gemini_async(
            prompt, model=model or _gemini.DEFAULT_MODEL, system=system,
        ):
            yield token
```

### Pattern 4: Test pattern for async generators (no real API)

**What:** Monkeypatch the underlying provider helper or SDK class; return a fake async generator.

```python
# Source: existing test_provider_anthropic.py patterns adapted for async generators

import asyncio

async def fake_stream(*args, **kwargs):
    for token in ["Hello", ", ", "world"]:
        yield token

def test_run_agent_stream_anthropic(monkeypatch):
    monkeypatch.setattr(_anthropic, "stream_anthropic_async", fake_stream)
    tokens = asyncio.run(_collect(run_agent_stream("hi", provider="anthropic")))
    assert "".join(tokens) == "Hello, world"

async def _collect(gen):
    return [t async for t in gen]
```

### Anti-Patterns to Avoid

- **Streaming with tool use in one pass:** Do not try to intercept tool_use events inside `run_agent_stream` and dispatch tools. The stream would need to pause, which requires accumulating the full tool_use block before executing -- at that point you have lost the latency benefit and broken the streaming contract. Tool use belongs in `run_agent_loop`.
- **Blocking event loop in async generator:** Never call the sync SDK inside an `async def` function. Use `AsyncAnthropic`, not `Anthropic`, and `client.aio.models.*`, not `client.models.*`.
- **Creating a new Client per token:** Create the client once before entering the streaming loop, not inside the `yield` loop.
- **Catching and swallowing API errors silently:** Let SDK exceptions propagate. Callers (CLI, dashboard) decide how to surface them.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chunked transfer decoding | Custom HTTP streaming | anthropic.messages.stream() | SDK handles SSE framing, reconnects, error events |
| Token accumulation / final message | Custom buffer | stream.get_final_message() (Anthropic) | SDK accumulates internally and provides final Message |
| Gemini chunk text extraction | Custom parts iteration | chunk.text property | SDK provides .text shortcut on GenerateContentResponse |

**Key insight:** Both SDKs already abstract the low-level streaming protocol. The only code to write is the yield loop.

## Common Pitfalls

### Pitfall 1: Returning async generator vs. being one

**What goes wrong:** Writing `async def run_agent_stream(...): return stream_helper(...)` instead of `async def run_agent_stream(...): async for t in stream_helper(...): yield t`. The first form does not make `run_agent_stream` itself a generator -- it's a coroutine that returns an AsyncGenerator object. Both work at call sites, but the form using `yield` keeps the function properly typed as an async generator and allows `_check_provider` to run eagerly on first call.

**Why it happens:** Subtle Python semantics -- any function containing `yield` is a generator; without `yield`, the `return` just returns the object.

**How to avoid:** Always write the dispatcher with `async for ... yield` to keep it a true async generator function.

### Pitfall 2: Forgetting system prompt in Anthropic streaming

**What goes wrong:** The `system` parameter on `messages.stream()` is a top-level field, not a message in the messages list. If you put it in messages with `role: "system"` you get a 400 error.

**Why it happens:** Anthropic API differs from OpenAI's convention where system is a message role.

**How to avoid:** Always pass system as `request["system"] = system_prompt`, not inside the messages array.

### Pitfall 3: Gemini streaming chunk has no candidates when empty

**What goes wrong:** Accessing `chunk.candidates[0]` without checking raises IndexError on empty chunks (keep-alive heartbeats or final usage-only chunks).

**Why it happens:** Gemini streaming may emit chunks with no candidates but with `usage_metadata` populated.

**How to avoid:** Use `chunk.text` (SDK shortcut), which returns `None` (not a string) for empty chunks. Guard with `if chunk.text:`.

### Pitfall 4: Missing `__init__.py` export

**What goes wrong:** `run_agent_stream` is implemented in `agent.py` but not exported from `horus_os/__init__.py`. CLI and test code imports fail or must use full path.

**How to avoid:** Add `run_agent_stream` to `horus_os/__init__.py` alongside `run_agent`, `run_agent_async`, `run_agent_loop`.

## Code Examples

### Verified: Anthropic streaming text_stream

```python
# Source: Context7 /anthropics/anthropic-sdk-python (helpers.md)
async with client.messages.stream(
    max_tokens=1024,
    messages=[{"role": "user", "content": "Say hello there!"}],
    model="claude-sonnet-4-6",
) as stream:
    async for text in stream.text_stream:
        print(text, end="", flush=True)
```

### Verified: Anthropic streaming event iteration

```python
# Source: Context7 /anthropics/anthropic-sdk-python (helpers.md)
async for event in stream:
    if event.type == "text":
        event.text      # delta
        event.snapshot  # accumulated so far
```

### Verified: Gemini async streaming signature

```python
# Source: SDK introspection, google-genai 1.70.0
# client.aio.models.generate_content_stream returns AsyncIterator[GenerateContentResponse]
# GenerateContentResponse.text is a property returning Optional[str]
async for chunk in client.aio.models.generate_content_stream(
    model="gemini-2.5-flash",
    contents="Hello",
    config=None,
):
    if chunk.text:
        print(chunk.text, end="", flush=True)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `messages.create(stream=True)` raw SSE | `messages.stream()` context manager | Anthropic SDK ~0.7+ | Cleaner API; accumulates final message automatically |
| `google-generativeai` (old SDK) | `google-genai` (new unified SDK) | google-genai 0.8+ | New SDK is the current standard; old SDK deprecated |

**Deprecated/outdated:**
- `google.generativeai.GenerativeModel.generate_content_async(stream=True)`: Old SDK pattern. This repo already uses `google-genai` (the new SDK), so the old pattern does not apply.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `run_agent_stream` should not support tool use (text-only streaming only) | Architecture Patterns | If tools are required in the stream, Phase 14 scope must expand |
| A2 | Yielding `str` tokens (not a StreamChunk dataclass) is sufficient for Phase 14 | Standard Stack | Phase 15/16 may need structured events; can add wrapper type later |

## Open Questions

1. **System prompt in `run_agent_stream`**
   - What we know: `run_agent_loop` (Phase 13) adds `system_prompt` param; streaming callers may also want it
   - What's unclear: Whether Phase 14 must expose `system` param or if CLI/dashboard always constructs the prompt inline
   - Recommendation: Include `system: str | None = None` param for consistency with Phase 13 pattern

2. **Max tokens default for streaming**
   - What we know: `call_anthropic` uses `DEFAULT_MAX_TOKENS = 1024`; streaming chat responses may need more
   - Recommendation: Reuse same default; callers can override

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| anthropic | Anthropic streaming path | Yes | 0.96.0 | -- |
| google-genai | Gemini streaming path | Yes | 1.70.0 | -- |
| Python 3.11+ | async generators | Yes | confirmed in CI matrix | -- |

**Missing dependencies with no fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/test_agent.py tests/test_provider_anthropic.py tests/test_provider_gemini.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STREAM-01 | `run_agent_stream` yields tokens from Anthropic | unit | `pytest tests/test_agent.py -k stream -x` | No - Wave 0 |
| STREAM-01 | `run_agent_stream` yields tokens from Gemini | unit | `pytest tests/test_agent.py -k stream -x` | No - Wave 0 |
| STREAM-01 | `run_agent_stream` rejects unknown provider | unit | `pytest tests/test_agent.py -k stream -x` | No - Wave 0 |
| STREAM-01 | Anthropic streaming helper yields text deltas | unit | `pytest tests/test_provider_anthropic.py -k stream -x` | No - Wave 0 |
| STREAM-01 | Gemini streaming helper yields text deltas | unit | `pytest tests/test_provider_gemini.py -k stream -x` | No - Wave 0 |
| STREAM-01 | `run_agent` and `run_agent_loop` still work (regression) | unit | `pytest tests/test_agent.py tests/test_agent_loop.py` | Yes |

### Sampling Rate

- **Per task commit:** `pytest tests/test_agent.py tests/test_provider_anthropic.py tests/test_provider_gemini.py -x -q`
- **Per wave merge:** `pytest`

### Wave 0 Gaps

- [ ] `tests/test_agent.py` needs `run_agent_stream` test cases added (file exists, need new tests)
- [ ] `tests/test_provider_anthropic.py` needs `stream_anthropic_async` test cases (file exists)
- [ ] `tests/test_provider_gemini.py` needs `stream_gemini_async` test cases (file exists)

*(No new test files needed -- extend existing provider and agent test modules)*

## Sources

### Primary (HIGH confidence)

- Context7 `/anthropics/anthropic-sdk-python` - streaming, messages.stream(), text_stream, events
- SDK introspection (anthropic 0.96.0): `AsyncAnthropic().messages.stream` method signature confirmed in REPL
- SDK introspection (google-genai 1.70.0): `client.aio.models.generate_content_stream` returns `AsyncIterator[GenerateContentResponse]`; `GenerateContentResponse.text` property confirmed

### Secondary (MEDIUM confidence)

- Context7 `/anthropics/anthropic-sdk-python` helpers.md examples - streaming event types and .text/.snapshot delta/snapshot fields

### Tertiary (LOW confidence)

- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - both SDKs installed and introspected directly
- Architecture: HIGH - verified SDK APIs; design follows existing codebase patterns
- Pitfalls: MEDIUM - derived from SDK behavior and Anthropic docs; pitfall 2 (system param) is well-documented

**Research date:** 2026-05-23
**Valid until:** 2026-08-23 (SDKs are stable; streaming API unlikely to change, but verify before using)
