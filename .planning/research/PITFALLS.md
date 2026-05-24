# Pitfalls Research

**Domain:** Adding cost / latency / tool-reliability / OTel observability to an existing local-first AI agent runtime (horus-os v0.4)
**Researched:** 2026-05-25
**Confidence:** HIGH for the failure modes (cross-referenced against OTel Python issue tracker, OneUptime + maketocreate writeups, Langfuse/Helicone docs, Anthropic + Gemini SDK behaviour, and the v0.3 source-read findings in ARCHITECTURE.md §0). MEDIUM for the precise blast-radius numbers (single-user desktop deployment, hard to source production-scale anecdotes for our shape).

## Scope and Sibling Cross-References

This file ONLY covers v0.4-specific instrumentation pitfalls. Generic FastAPI / SQLite / Python pitfalls are out of scope.

Where a sibling research file has already made a call, this file builds on it instead of re-arguing:

- **ARCHITECTURE.md §0** already names two confirmed v0.3 bugs that v0.4 must fix: (a) the `traces.usage` column reflects only the **final** turn's tokens, not the loop sum, and (b) per-tool latency is computed but never persisted. Both are reframed below as Pitfalls 1 and 6 with the failure-detection angle the architecture doc deliberately did not cover.
- **ARCHITECTURE.md §4.4** flagged the SSE streaming path as a "documented second capture site" where `usage` is structurally unavailable. That's reframed below as Pitfall 2 with the cost-accounting consequences spelled out.
- **STACK.md §"GenAI semconv adoption"** locked the position that `gen_ai.*` attributes are Development-status and must live in our own constants module. That decision is treated as given here; Pitfall 11 covers what happens if a future contributor forgets it.
- **FEATURES.md "Anti-Features"** ruled out cost-budget alerts, multi-tenant attribution, evals, and forced-OTel mode. Pitfalls below assume that boundary holds.

Cited prior art (full URLs at the bottom): OTel Python issues [#3309](https://github.com/open-telemetry/opentelemetry-python/issues/3309) (shutdown-blocks-60s), [#4623](https://github.com/open-telemetry/opentelemetry-python/issues/4623) (no configurable shutdown timeout); OpenLLMetry issue [#3515](https://github.com/traceloop/openllmetry/issues/3515) (`gen_ai.prompt`/`gen_ai.completion` deprecation); OneUptime "Redact Sensitive Prompts" + "Prevent Data Loss in Seven Common OpenTelemetry Scenarios"; maketocreate "OpenTelemetry GenAI: Tracing AI Agents Without Leaking PII"; Last9 "Latency Percentiles are Incorrect P99 of the Times"; Helicone retries doc; Anthropic per-token billing analysis from `implicator.ai`.

## Critical Pitfalls

### Pitfall 1: Per-iteration token totals silently undercount cost

**What goes wrong:**
The agent loop calls `Conversation.send` N times per run (one per iteration). Each call returns its own `usage` dict. A naive implementation writes whichever `usage` it last saw onto the trace row, so a 5-iteration run with 12k input / 800 output per turn is recorded as 12k / 800 instead of 60k / 4000. Cost reported is 1/N of actual. The user sees a $0.07 weekly bill, the Anthropic console shows $0.35, and trust in the dashboard evaporates.

**Why it happens:**
ARCHITECTURE.md §0 confirms this is the live shape of `Database.record_trace` in v0.3 today: the per-iteration `usage` overwrites instead of accumulating. The bug is invisible until the user cross-checks against the provider console, because every individual number looks plausible.

**How to avoid:**
- Capture per-call, sum at the trace level. Persist one row per `Conversation.send` into the new `llm_calls` table; compute `traces.total_input_tokens = SUM(llm_calls.input_tokens WHERE trace_id = ?)` on `RUN_END` (ARCHITECTURE.md §4.1 already mandates this).
- Add an integration test that runs a 3-iteration loop with hand-stubbed `usage` returning `{input: 100, output: 50}` each turn and asserts `trace.total_input_tokens == 300`, not 100. This test is cheap and catches every future regression at the bus-wiring layer.
- Add a nightly comparison harness (optional, but extremely high value): for any user opted in, sum `llm_calls.cost_usd` for the last 24h and write the number to a debug log alongside the user's Anthropic + Gemini console totals (manually entered or scraped from a CSV download). Within 5% means the table is sound; > 5% drift flags a regression. The "implicator.ai" piece on Anthropic billing confirms the per-token rates on the console are exact, so any drift > rounding is a horus-os bug, not a provider bug.

**Warning signs:**
- Dashboard cost-by-agent panel shows much lower numbers than the provider's billing page.
- Multi-iteration runs (delegation chains, tool-heavy loops) show suspiciously similar cost to single-iteration runs.
- The `traces.total_input_tokens` column is null or zero on a run that obviously did multiple turns (turn_count > 1).

**Phase to address:**
v0.4.1 (schema) + v0.4.2 (capture) + v0.4.3 (cost). Bug exists in v0.3 today; v0.4.1 introduces the table that makes the fix possible; v0.4.2 wires the per-call publish that makes the sum correct; v0.4.3 multiplies tokens by price. Owner: METRIC requirement.

---

### Pitfall 2: Streaming path silently records $0.00 runs

**What goes wrong:**
`/api/chat/stream` and CLI streaming runs go through `run_agent_stream`, not `run_agent_loop`. The SSE response shape does not surface the provider's final `usage` to the consumer. If the v0.4 capture only hooks `run_agent_loop`, every streamed run lands in SQLite with `input_tokens=0`, `output_tokens=0`, `cost_usd=0.00`. Two weeks in, the dashboard says "cost: $0.42" while the user has actually spent $7. The numbers are not wrong-by-rounding; they are wrong-by-percentage, and the lower the user's streaming ratio the worse it gets.

**Why it happens:**
The SDK *does* surface usage on the final stream chunk (Anthropic: read `final_message.usage` after the stream drains via `MessageStream.get_final_message()`; Gemini: `response.usage_metadata` after iteration finishes). But the current `_event_stream` handler in `server/api.py` does not call those terminal accessors before closing the response. ARCHITECTURE.md §4.4 flagged this as a "documented gap" and accepted best-effort. That acceptance is wrong if "best effort" silently becomes "zeros." Best effort must surface as a non-zero number plus an honest `streaming_estimated=true` flag, never as silent zeros.

**How to avoid:**
- Always read the terminal `usage` from the stream object before publishing the `LLM_CALL` event. Anthropic exposes `stream.get_final_message().usage` and `stream.get_final_text()`; both are stable accessors on `MessageStream`. Gemini accumulates `response.usage_metadata` on the response object after iteration completes. Both are documented in their respective SDKs and were stable as of May 2026.
- If the stream errors mid-flight (network drop, content filter), the terminal accessor will not have a complete usage. Fallback: estimate output tokens with `len(accumulated_text_chunks) / 4` (rough tokens-per-char heuristic), persist with `estimated=1`, `pricing_missing=0`, and surface a yellow "estimated" badge in the dashboard. NEVER persist `0` for a non-empty stream.
- Add a regression test that hits `/api/chat/stream` with a stubbed Anthropic SDK that yields a stream and a terminal usage; assert the persisted `llm_calls` row has the real numbers, not zeros.
- Add a dashboard tile: "Streaming runs where token count was estimated: N (last 7d)." If N grows unexpectedly the user has visibility, not silent rot.

**Warning signs:**
- The dashboard says cost is much lower than the user's perception.
- A `SELECT COUNT(*) FROM llm_calls WHERE input_tokens=0 AND output_tokens=0` query returns a non-zero count after a real streaming session.
- Any `llm_calls` row exists with all four (input, output, cache_read, cache_creation) at zero.

**Phase to address:**
v0.4.2 (capture). The SSE branch fix is in `server/api.py:_event_stream`. Owner: METRIC requirement. Add to "Looks Done But Isn't" checklist below.

---

### Pitfall 3: Latency measured with wall clock, not monotonic

**What goes wrong:**
Using `time.time()` instead of `time.perf_counter()` to compute durations. NTP adjusts the wall clock mid-call; daylight savings flips it by an hour; a virtualized laptop coming out of sleep can jump by minutes or jump *backwards*. A negative `latency_ms` lands in SQLite. Percentile queries either skip the row, return -200ms as the p50, or (worst case for a UINT column) wrap to a giant positive number. Either way, your latency dashboard is lying.

**Why it happens:**
`time.time()` is the obvious-feeling first choice. It returns a float, it's in the stdlib, every tutorial uses it. The wall-clock semantics aren't visible until you observe the symptom, and the symptom is rare enough to be mistaken for a flake. PEP 418 spelled this out in 2012 and the lesson keeps getting relearned (Ceph's `bluestore` had this exact bug in 2018, see PR #22121 in sources).

**How to avoid:**
- Use `time.perf_counter()` for every duration computation. Document this as a rule in `docs/CODING-STANDARDS.md`. v0.3's `tools/loop.py` already uses `perf_counter()` correctly, so this is a "don't regress" rule, not a "fix bug" rule.
- Use `time.time()` (or `datetime.now(UTC).isoformat()`) ONLY for `created_at` timestamps on rows, where wall-clock semantics are exactly what you want.
- Add a ruff custom rule (or a one-line `grep` CI check) that fails the build if anyone writes `time.time()` inside the `horus_os/observability/` package or the two capture sites in `agent.py` and `tools/loop.py`. Pattern: `grep -rE "time\.time\(\)" src/horus_os/observability src/horus_os/agent.py src/horus_os/tools/loop.py && exit 1`.
- Add a sanity-check assertion in `SQLitePersister.on_event`: `assert event.latency_ms >= 0`. Refuse to insert negative durations. Log the event for triage instead of corrupting the table.

**Warning signs:**
- Any row in `llm_calls` or `tool_invocations` with `latency_ms < 0`.
- p50 latency suddenly jumps to a number that's larger than the wall-clock duration of the whole run.
- Latency p95 hits maxint or shows a huge anomaly after the user's laptop wakes from sleep.

**Phase to address:**
v0.4.2 (capture). Owner: METRIC requirement. Lint rule lands in v0.4.1 alongside the schema migration so it's guarding the right files from day one.

---

### Pitfall 4: Latency excludes the parts users actually feel

**What goes wrong:**
The OTel GenAI metrics spec defines `gen_ai.client.operation.duration` as the duration of "the LLM API call." Cheap interpretation: wrap the SDK's `client.messages.create(...)` line and call it done. The user sees a dashboard showing 800ms p50, but their experience is a 4-second wait. The 3.2 seconds that's missing was: provider rate-limit backoff inside the SDK (1s), retry after a 529 (another 1s), HTTP connect on a cold pool (200ms), token-by-token streaming until completion (1s). None of those land in your number.

**Why it happens:**
The natural instrumentation point feels like "wrap the API call." But for LLMs, retries, backoff, and streaming-to-completion are inside that envelope and are exactly what makes "slow run" investigations actionable. STACK.md and ARCHITECTURE.md both correctly capture `Conversation.send` as the boundary, but a future contributor who instruments OpenAI or another provider might wrap the bare `client.create()` and not the retry-wrapping wrapper.

**How to avoid:**
- Define what `latency_ms` MEANS in a docstring on `ObservationEvent.latency_ms` and in `docs/OBSERVABILITY.md`: "wall-clock elapsed from the moment `Conversation.send` is invoked to the moment the final usable response object is available to the caller, inclusive of all SDK-level retries, backoff, queueing, and stream drain." Anchor the contract in prose so future capture sites have a definition to test against.
- Add a `time_to_first_token_ms` column on `llm_calls` for streaming runs. TTFT is the actual UX number for chat; total `latency_ms` is what matters for cost-per-second-of-compute. Two columns let the dashboard show both honestly without picking one and lying.
- Capture `retry_count` from the SDK when it exposes it (Anthropic's SDK does expose retry counts via response headers in some configurations; document the access path). When a single `conversation.send` includes N retries, persist N as a separate column and surface "runs that retried more than 2x" on the dashboard.

**Warning signs:**
- Dashboard latency p50 is much lower than the user reports their experience to be.
- Provider rate-limit incidents (visible in provider dashboards) do not correlate with a latency spike on the horus-os dashboard.
- Streaming runs all land at the same suspiciously low latency number (only first-byte was captured, not full drain).

**Phase to address:**
v0.4.2 (capture) defines the contract. v0.4.4 (queries) surfaces the columns. Owner: METRIC requirement.

---

### Pitfall 5: `pricing.json` rots silently between releases

**What goes wrong:**
A model releases; its price drops 50% (Sonnet 4.5 → Sonnet 4.6, a normal cadence in 2026); or Anthropic introduces a new tier (prompt-caching write-rate changes from 1.25x to 1.10x of input). Bundled `pricing.json` has the old number. The dashboard reports 50% over the actual bill (acceptable but confusing) or 50% under (catastrophic — user thinks they're spending half what they are). Worse: a new model the user adopts is missing entirely, falls back to the zero-price `fallback` block, and is reported at $0.00 cost forever.

**Why it happens:**
PROJECT.md locks "bundled JSON, refreshed each release." Releases happen every few weeks. Pricing changes faster than release cadence. The release-time refresh process is manual (STACK.md §3 confirms a scrape script is not viable). Manual processes get forgotten. AgentOps's [tokencost](https://github.com/AgentOps-AI/tokencost) and LiteLLM's [model_prices_and_context_window.json](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) exist precisely because everyone hits this.

**How to avoid:**
- **Self-disclosure first.** `pricing.json` MUST carry `version`, `updated_at`, and `release_version` fields (already in ARCHITECTURE.md §3 Pattern 6). The dashboard MUST surface a banner: "Pricing data is N days old (last refreshed YYYY-MM-DD). Override at $HOME/.config/horus-os/pricing.json." Surfacing the staleness is the difference between a silent lie and an honest "this might be slightly off."
- **Refuse silent fallback to zero.** When a model is missing from `pricing.json`, persist the row with `pricing_missing=1`, `cost_usd=NULL`. NULL is honest; 0 is a lie. Dashboard SQL: `SUM(COALESCE(cost_usd, 0))` plus a separate count of "runs with unknown pricing" surfaced as a yellow badge.
- **Sync-against-source contributor doc.** Add `docs/RELEASE.md` (STACK.md §3 already mandates this). Step 1: diff `pricing.json` against the LiteLLM `model_prices_and_context_window.json` raw URL on GitHub (one curl + one diff). Step 2: copy any updates for models we support. Step 3: bump `updated_at`. This makes the refresh a 5-minute mechanical task instead of a research project.
- **CI gate at release-tag time:** the release workflow runs a script that asserts `pricing.json`'s `updated_at` is within 14 days of the tag date. Older than that = release blocked until the contributor refreshes.
- **User override path is documented in the user-facing dashboard staleness banner itself**, not hidden in docs. The cure is one cp-and-edit operation away.

**Warning signs:**
- `SELECT COUNT(*) FROM llm_calls WHERE pricing_missing=1` returns non-zero after a model upgrade.
- The dashboard cost number diverges > 10% from the user's Anthropic / Gemini console totals over the same window.
- A model name appears in `llm_calls` that does not appear in `pricing.json.models`.

**Phase to address:**
v0.4.3 (pricing). Self-disclosure banner in v0.4.5 (dashboard). CI release gate in v0.4.8 (release). Owner: PRICE requirement.

---

### Pitfall 6: OTel exporter blocks the request path or leaks on shutdown

**What goes wrong:**
Two distinct failure modes, same root cause:
1. **Blocking on the hot path.** A naive OTel adapter calls `tracer.start_as_current_span(...)` synchronously, then inside the span context block does an `exporter.export([span])` directly (or uses `SimpleSpanProcessor`). The OTLP HTTP request to the user's collector takes 200ms. Every agent run now has 200ms of OTel overhead added to its latency. If the collector is down, the export times out at 10s and the agent's response is delayed by 10s for every call.
2. **Leaking on shutdown.** `BatchSpanProcessor` runs a daemon thread; `OTLPSpanExporter` holds an HTTP connection pool. If `provider.shutdown()` is not called on app exit, the daemon thread is killed mid-export and the last batch of spans is silently dropped. Worse (per [OTel Python issue #3309](https://github.com/open-telemetry/opentelemetry-python/issues/3309)), if the collector is unreachable at shutdown, the default behavior is to *block for 60 seconds* attempting to flush, and per [issue #4623](https://github.com/open-telemetry/opentelemetry-python/issues/4623) the timeout is not configurable. A user trying to Ctrl-C the server has to wait a minute.

**Why it happens:**
Tutorials show `SimpleSpanProcessor` first because it's simpler to demo. The shutdown path is rarely tested because tests do not exit gracefully. The "wait 60 seconds on shutdown" behavior is genuinely surprising and has bitten OTel users in production (see issues linked above and OneUptime's "Prevent Data Loss" piece).

**How to avoid:**
- **Always use `BatchSpanProcessor`**, never `SimpleSpanProcessor` in production code. Set `max_export_batch_size`, `schedule_delay_millis`, `max_queue_size` explicitly (defaults: 512 / 5000ms / 2048 are sane, but state them so reviewers don't have to know the defaults).
- **Wrap `BatchSpanProcessor.export` with a tight try/except** at the bus-subscriber boundary. The OTel exporter is a bus subscriber (ARCHITECTURE.md §3 Pattern 5); its `on_event` handler is already invoked sync by `ObservationBus.publish`. The handler does `tracer.start_span(...).end()` only — span creation is microsecond-cheap because BSP just enqueues. If BSP's internal queue is full, the span is dropped silently by the SDK (and a metric is incremented internally). That's fine; better to drop spans than to block the agent.
- **Implement `OtelAdapter.stop()` with a bounded timeout.** Call `provider.force_flush(timeout_millis=2000)` first, then `provider.shutdown()`. If the exporter is dead, you lose up to 2s of pending spans but the app exits in 2s, not 60s. Document the tradeoff.
- **Test the shutdown path.** Pytest fixture that starts a FastAPI test app with OTel adapter pointing at a non-existent endpoint, sends one request, then triggers shutdown. Assert shutdown completes in < 3 seconds. This single test catches both the daemon-thread leak and the 60s-block bug.
- **Subscribe via the adapter's `start()` and unsubscribe in `stop()`.** ARCHITECTURE.md §3 Pattern 5 already mandates this. Reinforce: if the user toggles the adapter off via `/api/adapters/otel/disable`, the unsubscribe must happen, otherwise the disabled adapter keeps consuming events (memory leak + zombie work).

**Warning signs:**
- p95 latency increases by 100ms+ the moment the OTel adapter is enabled.
- Server takes more than a few seconds to shut down (Ctrl-C feels stuck).
- The `OtelBatchSpanRecordProcessor` daemon thread name appears in `py-spy dump` output after the server has stopped.
- A unit test that imports the OTel adapter takes > 10 seconds to tear down.

**Phase to address:**
v0.4.7 (OTel adapter). Owner: OTEL requirement. Shutdown timeout test is non-negotiable for this phase.

---

### Pitfall 7: PII leaks through OTel span attributes (the CLAUDE.md zero-PII rule)

**What goes wrong:**
A well-meaning contributor adds `span.set_attribute("gen_ai.input.messages", json.dumps(prompt))` because the GenAI semconv defines that attribute. The user's prompt happens to include "my AWS access key is AKIA...". That key now lives in the user's external OTel collector, possibly forwarded to a SaaS backend (Honeycomb, Datadog, Grafana Cloud), possibly logged to a file the user's IT team has read access to. CLAUDE.md hard rule #1 ("no personal information about any contributor or user in committed text") doesn't cover *runtime* leakage to an *external* sink, but the *spirit* of the rule (the project takes user data seriously) is now broken at the exact moment the user added an opt-in flag they thought was safe.

**Why it happens:**
The GenAI semconv standardizes these attribute names, so they look like the obvious thing to emit. OpenLLMetry's auto-instrumentation libraries default to emitting them. The "maketocreate.com" writeup on PII in GenAI tracing notes the pattern: people paste API keys into chatbots, paste health information, paste internal URLs. The default-on assumption breaks anyone in a regulated industry, anyone with secrets management norms, anyone exporting to a multi-tenant collector.

**How to avoid:**
- **Default-deny content capture.** The `OtelAdapter` does NOT emit prompt or completion bodies. Period. No `gen_ai.input.messages`, no `gen_ai.output.messages`, no `gen_ai.prompt`, no `gen_ai.completion`. Only emit numerical / structural attributes: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens`, `horus_os.cost_usd`, `error.type`. STACK.md §"GenAI semconv adoption" already lists this exact set.
- **Opt-in body capture only with an explicit env var.** `HORUS_OS_OTEL_CAPTURE_CONTENT=true` (mirroring the OneUptime-recommended `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` env var pattern). Default false. Document the risk in the docstring and in `docs/OTEL.md`.
- **When opt-in is on, apply a redaction allowlist BEFORE the span is emitted.** Reuse the patterns from the maketocreate / OneUptime guides: regex-redact `sk-[a-zA-Z0-9]{20,}`, `AKIA[A-Z0-9]{16}`, `ghp_*`, `xoxb-*`, emails, e164 phone numbers, common AWS / Stripe / Google API key prefixes. Implement as `horus_os/observability/redact.py` with a public `redact(text: str) -> str` function and unit tests over a fixture of known-bad strings. Treat the redaction step as a hard barrier — if the redactor raises, the body is dropped, not emitted.
- **Tool call arguments are equally sensitive.** Tool invocation arg dicts often contain file paths, URLs, credentials passed to shell commands. The default `tool_invocations` schema already does NOT persist tool args — keep that. The OTel exporter must apply the same default-deny rule for tool span attributes: emit `tool_name`, `latency_ms`, `status`, `error_type` (class name, NOT message). NEVER `tool_input`, NEVER `tool_output`, unless the same opt-in env var + redaction allowlist is in play.
- **Document in `docs/OTEL.md`:** the exact list of attributes emitted by default, the exact list emitted with content capture on, the redaction set, and a "Threat model" section: "Your OTel collector and any backend it forwards to will receive everything in the default attribute list. If you cannot trust those parties with your token counts and model names, do not enable the OTel adapter."
- **CI test: an OTel adapter test fires a synthetic event with a prompt containing `"my-test-secret-AKIAIOSFODNN7EXAMPLE"`** and asserts that the exported span attributes (captured via `InMemorySpanExporter`) contain `gen_ai.usage.*` numerical attrs but do NOT contain the literal string `AKIAIOSFODNN7EXAMPLE`. This is a non-negotiable test for the OTel phase.

**Warning signs:**
- Code review on the OTel adapter contains `set_attribute("gen_ai.input.messages", ...)` or `set_attribute("gen_ai.prompt", ...)`.
- The docs don't mention what's emitted by default.
- A new contributor opens a PR adding "Capture the user's prompt to the span" without first reading `docs/OTEL.md`.
- `grep -r "gen_ai.input.messages\|gen_ai.output.messages\|gen_ai.prompt\|gen_ai.completion" src/horus_os/` returns anything outside the opt-in code path.

**Phase to address:**
v0.4.7 (OTel adapter). Owner: OTEL requirement. The default-deny rule is the most important single design decision in the whole milestone; getting it wrong creates the worst possible user trust failure (silent data exfiltration). Verify in code review at PR time AND in CI.

---

### Pitfall 8: SQLite write amplification kills the agent loop

**What goes wrong:**
v0.4 adds two new tables that get a row per LLM call and per tool call. A tool-heavy agent run with 8 turns × 4 tool calls = 40 INSERTs per run. At default SQLite settings, each INSERT is its own transaction with `PRAGMA synchronous=FULL`, fsync per insert. On a Mac SSD that's ~5ms per insert; on a slow rotational disk on a Raspberry Pi (a real horus-os deployment target) it's 30-50ms. The agent loop blocks on persistence for 200ms-2s per run, perceived as the system "got slower" with the v0.4 upgrade.

A subtler version: the persister is in the bus dispatch path; ARCHITECTURE.md §3 Pattern 1 explicitly says sync dispatch is the contract because "the row is committed before `record_trace` returns, so a crash mid-loop never loses partial cost data." That's the right design, but it makes write amplification a first-class hot-path concern.

**How to avoid:**
- **WAL + `PRAGMA synchronous=NORMAL`** in the v0.4 storage init. WAL is already on (storage.py:pragmas in v0.3). `synchronous=NORMAL` (instead of FULL) trades a vanishingly small durability risk (the last few INSERTs may be lost on a hard power loss) for ~10x INSERT throughput. This is the documented best practice for SQLite WAL per the SQLite docs and the `phiresky` performance tuning guide cited in sources. Acceptable for an observability database where occasional row loss is preferable to multi-second user-visible latency.
- **Use a per-trace batched insert at `RUN_END` for `tool_invocations`.** Per-LLM-call inserts can stay individual (low frequency, high information density per row); per-tool-call inserts can be queued in the `ObservationBus` and flushed in one `executemany` on `RUN_END`. Trade: lose tool granularity if the process dies mid-run. Acceptable: that's the same trade we already make for the loop's interim state.
- **Index intentionally, not defensively.** Each index adds write amplification. ARCHITECTURE.md §5 already specifies the minimum useful set: `(trace_id)`, `(created_at DESC)`, `(provider, model)` on `llm_calls`; `(trace_id)`, `(tool_name, created_at DESC)`, `(created_at DESC)` on `tool_invocations`. Do not add more "just in case." Each one slows every INSERT.
- **Add a benchmark to the CI matrix** that runs a 5-iteration / 3-tool-call agent run against a stubbed SDK and asserts total wall-clock time is within 50ms of a baseline measured at v0.3 (recorded once at v0.4 start and pinned). If a future PR adds 100ms of v0.4 overhead, the benchmark fails.
- **Document `VACUUM` and `wal_checkpoint(TRUNCATE)` in `docs/MAINTENANCE.md`** for users who run the system for years. WAL files grow without bound under heavy write load until a checkpoint runs. SQLite auto-checkpoints at 1000-page increments by default, but a long-running idle dashboard reader can pin checkpoints. Periodic `pragma wal_checkpoint(TRUNCATE)` at low-traffic times solves it.

**Warning signs:**
- Agent runs are perceptibly slower under v0.4 than under v0.3 with the same workload.
- `db.sqlite3-wal` file is growing larger than `db.sqlite3` itself.
- A user with a slow disk (Raspberry Pi, Windows on HDD) reports the dashboard "feels laggy" after upgrade.
- The v0.4 capture-overhead benchmark fails in CI.

**Phase to address:**
v0.4.1 (schema + persister) sets the pragmas and the indexes. v0.4.2 (capture) adds the benchmark. Owner: STORE requirement.

---

### Pitfall 9: Tool reliability counts the wrong thing

**What goes wrong:**
The naive implementation: `success = 1 if no exception else 0`, count grouped by tool name. The dashboard's "tool error rate" panel says 35%. The user investigates and discovers:
- 20% of those "failures" are actually retries that succeeded on the second attempt (counted once as failure, once as success).
- 10% are intentional `not_found` returns (e.g. a `read_file` for a missing path; the tool worked correctly, the answer was "no such file").
- 5% are real bugs.

The dashboard is now an oracle that's right 14% of the time and wrong 86%. The user stops trusting it within a week.

**Why it happens:**
"Did the tool raise?" is the easy question. "Did the tool produce the intended outcome?" is the hard one. Helicone's docs on retries explicitly call out that each retry is logged as a separate request, which means retry-aware reliability has to be a deliberate aggregate, not a default count.

**How to avoid:**
- **Two distinct columns: `status` and `error_type`.** `status` ∈ {`success`, `error`, `retry_then_success`, `expected_no_result`}. `error_type` is the exception class name when status is `error` (NEVER the error message — messages contain user-supplied paths, URLs, credentials; per Pitfall 7 these don't belong in indexable columns).
- **Tool handlers opt into "expected no-result" semantics.** A tool's `execute` can return `ToolResult(status='expected_no_result', message='no such file')` instead of raising. The reliability panel groups by `status`, so the user sees three numbers per tool: `success_count`, `expected_no_result_count`, `error_count`. Total = denominator; error_count / total = the headline error rate; expected_no_result_count is informational.
- **Retry-aware aggregation.** When the agent loop retries a failed tool, increment a `retry_count` field on the SAME `tool_invocations` row instead of writing a new row. The row's final `status` reflects the eventual outcome. The dashboard shows: "tool X: 95% success, 5% error, 18% of successful calls required retry (median retries: 1)." Now the user sees both reliability AND flakiness as separate signals.
- **"Last-error preview" uses `error_type` + a redacted snippet.** The dashboard tile shows `tool: read_file | status: error | type: FileNotFoundError | last_at: 2 min ago`. Click-through to a redacted message (paths replaced with `<path>`, URLs with `<url>`). NEVER show the raw message inline on a panel that might be screenshotted.
- **Minimum sample threshold for the "most failing tool" callout.** A tool that's been called 2 times with 1 error has a 50% error rate but tells you nothing. Surface "most failing" only when `total_calls >= 5` in the window. Below threshold, surface "insufficient data."

**Warning signs:**
- A tool whose error rate jumps from 5% to 35% after a refactor that added retries.
- A tool that's "always failing" but actually working as designed (the `expected_no_result` case).
- Dashboard tile shows a tool name with `error_rate=100%` and `call_count=1`.
- An error_message column contains user-supplied paths (verify with a regex check at CI time).

**Phase to address:**
v0.4.2 (capture) defines the columns. v0.4.4 (queries) writes the aggregations. v0.4.5 (dashboard) applies the sample threshold. Owner: METRIC requirement, REL category.

---

### Pitfall 10: Percentile math is wrong because the sample is too small or the window is wrong

**What goes wrong:**
The dashboard shows p95 latency = 3.2s for the past hour. The user investigates. The hour had 4 runs. p95 of 4 samples is mathematically undefined or by convention = the max. Tomorrow with 400 samples the same workload shows p95 = 1.1s. The user concludes the system "got faster" when actually the prior number was statistical noise. Or: a default window of 24h is set, but the user wants per-hour granularity for debugging a regression; computing p50 over the last 24h vs the previous 24h smooths out a 4-hour spike that was the actual incident. Either way, the percentile chart is misleading.

The averaging-of-percentiles version (per the Last9 "Latency Percentiles are Incorrect P99 of the Times" piece): if a future contributor adds "per-hour rollups" and the dashboard shows "p95 over 24h" by averaging 24 hourly p95s, the resulting number is mathematically wrong by construction. p95 of a population is NOT the mean of p95s of subgroups.

**Why it happens:**
`NTILE(100)` doesn't complain about small samples. SQL returns what you asked for. Time windows feel like an obvious UI control. The "average of percentiles" trap is one of the most reliable industry mistakes — even mature engineers do it.

**How to avoid:**
- **Always show the sample count alongside the percentile.** Dashboard tile: `p95: 1.2s (n=87 over 7d)`. CLI output column: `p95_ms,sample_count`. If `sample_count < 30`, render the percentile in muted color with a tooltip: "small sample, treat as estimate."
- **Hide percentiles below a minimum sample size.** `n < 10` → render "—" with hover text "need ≥ 10 runs for percentile." Picking 10 not 30 because we're a single-user system, not a production fleet; 30 is unreachable in some legitimate windows.
- **Never aggregate percentiles of percentiles.** All dashboard / CLI percentile computations operate on the raw `latency_ms` column. NEVER pre-aggregate into hourly buckets and then take a percentile of hourly bucket p95s. Document this rule in `observability/queries.py` as a top-of-file comment. If a future contributor proposes rollups for performance, the rollup must store raw samples per bucket (e.g. as a sketch like t-digest), not pre-computed percentiles.
- **Default window = 7d, options = 24h / 7d / 30d.** Default of 7d gives enough samples for stability; 24h is for active debugging (user explicitly accepts noise); 30d shows trend. Do NOT default to 1h.
- **Test: assert that `p95(N runs all at 100ms) == 100`.** Boundary test. Assert that `p95([])` raises or returns None, never 0 or NaN.

**Warning signs:**
- Dashboard p95 wildly fluctuates day to day on similar workloads.
- A new percentile column was added that operates on a `_hourly` table without a comment justifying why aggregating-of-aggregates is okay (hint: it's not).
- The percentile panel renders `p95: 0ms` (n=0 case rendered as 0 instead of "—").

**Phase to address:**
v0.4.4 (queries) implements the SQL correctly. v0.4.5 (dashboard) handles the small-sample render and the n display. Owner: METRIC requirement.

---

### Pitfall 11: Migration breaks v0.3 trace readers

**What goes wrong:**
A user upgrades from v0.3.0 to v0.4.0. The migration runs `ALTER TABLE traces ADD COLUMN turn_count INTEGER NOT NULL`. SQLite refuses (existing rows have no value). Or: the migration runs `DROP COLUMN usage` to "clean up" the old JSON blob now that typed columns exist. The dashboard at v0.4 keeps working; the user's third-party script that read `traces.usage` directly breaks. Or: the dashboard reads from the new typed columns; v0.3 rows have NULL there; the cost panel shows zeros for the user's first month of history and they think v0.4 deleted their data.

**Why it happens:**
Migrations are usually written by someone who has a fresh database in mind. The v0.3-data-in-v0.4-schema case is forgettable. The "rewrite the old data to match the new shape" temptation is strong because it makes the dashboard look cleaner.

**How to avoid:**
- **Every new column is nullable. No exceptions.** ARCHITECTURE.md §3 Pattern 3 already mandates this; reinforce in the migration test.
- **Never DROP any column** in an additive migration. The `traces.usage` JSON blob stays forever. v0.4 readers prefer the typed columns; v0.3 readers (or hand-written user SQL) still see the blob.
- **Migration test against a v0.3 database fixture.** Check in a `tests/fixtures/v0_3_database.sqlite3` with a few real traces. The migration test opens it, runs `Database.init()`, asserts: (a) the new columns exist, (b) the old `traces.usage` column still exists and reads correctly, (c) `SELECT * FROM traces WHERE total_input_tokens IS NULL` returns the pre-v0.4 rows. Run this test on every PR.
- **Dashboard handles NULL gracefully.** Cost panel SQL: `SELECT agent, SUM(COALESCE(total_cost_usd, 0)) AS cost, COUNT(*) FILTER (WHERE total_cost_usd IS NULL) AS uncosted_runs FROM traces ...`. Surface "uncosted_runs" as "N runs from before v0.4 with no cost data" — explains the missing dollars without hiding them.
- **Rollback survival.** A user who installs v0.4.0, runs for a week, then `pip install horus-os==0.3.0` must keep reading their database. Because we only ADD, not RENAME or DROP, this works. Validate it: a test that installs v0.3.0 in a separate venv and opens a v0.4-written database.
- **Migration is idempotent.** Use `ALTER TABLE ... ADD COLUMN` wrapped in `try/except sqlite3.OperationalError` (the exact pattern at v0.3 `storage.py:137-146`). Running `Database.init()` twice on a v5 schema must be a no-op.

**Warning signs:**
- A PR adds `ALTER TABLE ... DROP COLUMN` or `RENAME COLUMN`.
- A new column declared `NOT NULL` without a `DEFAULT`.
- The migration test against the v0.3 fixture is missing or skipped.
- Schema version logic uses `==` instead of `<` (skipping a migration step when the user upgrades from a much older version).

**Phase to address:**
v0.4.1 (schema). Owner: STORE requirement and MIG continuation category. The v0.3 fixture test is the single highest-leverage check for this whole pitfall class.

---

### Pitfall 12: OTel adapter pulls in `opentelemetry-*` even without the `[otel]` extra

**What goes wrong:**
A contributor adds `from opentelemetry import trace` at the top of `horus_os/adapters/otel_adapter.py`. `pip install horus-os` (without the `[otel]` extra) installs cleanly, but `python -c "import horus_os"` crashes with `ModuleNotFoundError: No module named 'opentelemetry'`. The whole local-first promise breaks for everyone who doesn't want OTel — which is most users by definition (it's an opt-in extra).

Or, subtler: the entry-point discovery for adapters happens at `create_app` time. Even if individual file imports are lazy, the entry-point machinery imports the module to register it. If that import fails, FastAPI startup fails.

**Why it happens:**
The "import at top of file" reflex is universal. Optional dependencies require deliberate care. STACK.md §"What NOT to Use" called out that `opentelemetry-instrumentation-*` auto-patches at import time and is therefore banned; same reasoning applies to the adapter's own imports.

**How to avoid:**
- **Lazy import inside `start()`.** ARCHITECTURE.md §3 Pattern 5 already mandates this; reinforce. The module-top imports are only stdlib + typing. All `opentelemetry.*` imports live inside the async `start(self, context)` body. If the user doesn't enable the adapter, the imports never execute.
- **Entry-point registration uses string paths.** `pyproject.toml`'s `[project.entry-points."horus_os.adapters"]` block points at `horus_os.adapters.otel_adapter:OtelAdapter`. Python's entry-point machinery only resolves this when a discovery call asks for it. `AdapterRegistry.discover()` should catch `ImportError` per-entry-point and mark the adapter as `status=unavailable` with a clear message, not crash the whole app.
- **Top-of-file `from __future__ import annotations`** plus type-only imports in `if TYPE_CHECKING:` blocks. Adapter type signatures can reference `opentelemetry` symbols without importing the package at runtime.
- **CI test variant: install matrix.** Run two parallel jobs: (a) `pip install -e ".[dev]"` (no otel) — assert `python -c "import horus_os; from horus_os.adapters.otel_adapter import OtelAdapter"` works AND `OtelAdapter().start(ctx)` raises a clean "OTel extra not installed" error, not `ModuleNotFoundError`. (b) `pip install -e ".[dev,otel]"` — assert `start(ctx)` succeeds when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- **Graceful runtime check.** Inside `start()`, before importing OTel symbols: `try: import opentelemetry; except ImportError: raise RuntimeError("OTel adapter requires 'pip install horus-os[otel]'") from None`. The user sees a clear message in the Adapters tab status pill, not a confusing import traceback in the server logs.

**Warning signs:**
- `grep -E "^from opentelemetry|^import opentelemetry" src/horus_os/adapters/otel_adapter.py` returns matches at module top (anything outside `start()` or a `TYPE_CHECKING` block).
- The (no-otel) install-smoke CI variant fails with `ModuleNotFoundError`.
- A user reports the app won't start after upgrading; logs show `opentelemetry` import error and they never installed `[otel]`.

**Phase to address:**
v0.4.7 (OTel adapter). Owner: OTEL requirement. The two-variant install-smoke matrix lands in v0.4.8 (release gate).

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store the SDK's `usage` dict as a JSON blob and parse on read | One column, no migration, "we'll add typed columns later" | Every query parses JSON in SQL, percentiles can't use an index, dashboards stay slow forever. Already the source of Pitfall 1 in v0.3. | Never for v0.4. The whole point is typed columns. |
| `synchronous=FULL` for "safety" | Survives hard power loss | 10x INSERT latency, every agent run waits on fsync | Never. WAL + `synchronous=NORMAL` is the documented best practice. We're an observability table, not a financial ledger. |
| Hardcode `pricing.json` defaults in `cost.py` as a fallback for tests | Tests stop touching the package data file | Real bugs from typos in test fixtures hide bugs in `pricing.json`; release-time pricing-refresh test can't run against real data | Never. Tests should use a tiny fixture `pricing.json` placed via `monkeypatch` of `cfg.pricing_path`. |
| Skip the v0.3-database migration fixture test "because it's annoying to maintain" | One less test file | Migrations break on upgrade; user data appears lost; recovery cost is HIGH (Pitfall 11) | Never. This is the highest-leverage single test in the milestone. |
| Use `time.time()` for latency "just this once" | One line of code | Negative durations corrupt percentiles; bug hides for months until laptop NTP-skews | Never. (Pitfall 3.) |
| Add an in-memory ring buffer "for fast dashboard response" | Dashboard feels snappy on first load | Restart loses data; CLI and dashboard show different numbers; violates SQLite-as-source-of-truth | Never. ARCHITECTURE.md §7 Anti-Pattern 3 already forbids it. |
| Capture prompt/completion bodies "for debugging, off by default in prod" | Easier to diagnose user-reported issues | One config flag flip + one outbound OTel connection = secret leak. (Pitfall 7.) | Acceptable only under the explicit env var + redactor gate documented in Pitfall 7. Never as a "just turn this on for a sec" debug aid. |
| Use `SimpleSpanProcessor` in tests "because BSP is harder to flush deterministically" | Tests are easier to write | Tests pass with semantics that don't match production; production deploys hit Pitfall 6 | Acceptable in dedicated unit tests of the exporter ONLY (with `InMemorySpanExporter`). Integration tests use BSP. |
| Skip retry-count tracking on tool invocations "we'll add it later" | One less column, one less code path | Pitfall 9 ships as a feature; user trust in the reliability panel collapses | Acceptable only if the panel surfaces "retry semantics not tracked, error counts include retried-then-succeeded calls" in the dashboard help text. Better to ship it right. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Anthropic SDK streaming | Reading `usage` from the first chunk (it's not there) or from any intermediate chunk | Call `stream.get_final_message().usage` after the stream is drained. Both `input_tokens` and `output_tokens` are populated on the terminal message object. Documented and stable. |
| Anthropic SDK prompt-caching | Treating `cache_creation_input_tokens` and `cache_read_input_tokens` as part of `input_tokens` (double-counts) or ignoring them (under-costs by up to 90% on cached reads) | They are distinct counters. The Anthropic SDK returns all four (input, output, cache_creation, cache_read) on `usage`. Persist all four. Price each at its model-specific rate per `pricing.json` (cache_read is ~10% of input, cache_creation is ~125% of input). |
| Gemini SDK streaming | Same as Anthropic — assuming usage is in stream chunks | `response.usage_metadata` is populated on the response object after iterating to completion. Read after the loop, not during. |
| Gemini SDK `cached_content_token_count` | Treating it as part of `prompt_token_count` (Gemini's own semantics differ from Anthropic's) | Per [Gemini docs](https://ai.google.dev/gemini-api/docs/tokens), `prompt_token_count` is the *total* input including cache; `cached_content_token_count` is the cached *subset*. The non-cached input is `prompt_token_count - cached_content_token_count`. Pricing math differs from Anthropic; document both formulas in `cost.py`. |
| OTel collector (any backend) | Hardcoding `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces` (trailing path) when the user actually wants base URL; or omitting the path when the SDK appends it; or appending `/v1/traces` twice | The OTLP HTTP exporter defaults to appending `/v1/traces` to whatever `OTEL_EXPORTER_OTLP_ENDPOINT` is set to. Document this clearly: "Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` (base URL only). The exporter appends `/v1/traces`." Pass through to the SDK and let it handle the suffix logic. |
| OTel collector authentication | Putting bearer tokens in a config file, then accidentally committing it | Use `OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer%20xyz` env var. Document in `docs/OTEL.md` with explicit "do not commit" warning. The adapter reads from env, not from config files. |
| OTLP gRPC vs HTTP | Choosing gRPC because tutorials show it | STACK.md §"What NOT to Use" already forbids gRPC: `grpcio` has Windows-wheel gaps on fresh Pythons. Use HTTP. Reinforce in code review. |
| OTel resource attributes | Forgetting `service.name` so every span shows up as "unknown_service" in the backend | Set `service.name = "horus-os"`, `service.version = <pkg version>`, `host.name = socket.gethostname()` at `TracerProvider` creation time. Documented in STACK.md §1 integration example. |
| LiteLLM pricing JSON | Adopting it as the bundled file (it's MIT) | STACK.md §"Alternatives Considered" already rejects this — too big, models we don't support, schema churn. We curate our own small file, optionally diff against LiteLLM at release time to catch missed updates. |
| Anthropic billing endpoint | Trying to call it from our app to verify token counts in real time | There is no public Anthropic billing endpoint that returns per-key token totals. Cross-checking is a manual process or a CSV download — codify in `docs/RELEASE.md` and `docs/COST-VERIFICATION.md`. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous OTel export on the agent's hot path | Each LLM call adds 100-500ms; with a downed collector, adds the export timeout (~10s) per call | Always `BatchSpanProcessor`; never `SimpleSpanProcessor` in production. Bus subscriber handler does span-creation only, lets BSP enqueue. (Pitfall 6) | The moment OTel is enabled, especially if collector is misconfigured or slow. |
| Computing percentiles in Python over fetched-all-rows lists | Dashboard pages take seconds to render; memory spikes per request | SQLite-side `NTILE(100) OVER (...)` (ARCHITECTURE.md §3 Pattern 4); pure-SQL aggregation, no Python data manipulation | At ~10k rows the dashboard is noticeably slow; at ~100k it OOMs the dev box. |
| Per-row INSERT under `synchronous=FULL` | Agent runs feel slow under v0.4 compared to v0.3 | `synchronous=NORMAL` + WAL; consider per-trace batched insert for tool_invocations (Pitfall 8) | At ~3-4 tool calls per turn on a slow disk, the marginal latency is user-visible. |
| Dashboard polls without `?since=` filter | Query scans whole `llm_calls` table; gets slower over time | `?since=24h|7d|30d` always required; queries always include a `WHERE created_at >= ?` clause; an index on `(created_at DESC)` exists (ARCHITECTURE.md §5) | At ~50k LLM calls (mid-second-year of heavy use), unfiltered queries take seconds. |
| `pricing.json` reload on every cost computation | Disk I/O per LLM call; cost annotator becomes the bottleneck | Load once at `create_app` startup, hold in module-level `PricingTable` instance; reload only on `cfg.pricing_path` mtime change (Pitfall 5 prevention) | Within hours of v0.4 enablement under any meaningful load. |
| WAL file grows unbounded | `db.sqlite3-wal` is 10x the size of `db.sqlite3`; first dashboard query after a long idle takes seconds | Periodic `PRAGMA wal_checkpoint(TRUNCATE)`; document in `docs/MAINTENANCE.md`; consider a cron-friendly `horus-os maintain` subcommand later | Heavy continuous writes for weeks without a checkpoint. Common on Raspberry-Pi-like deployments. |
| Span attribute cardinality explosion | OTel backend bills per unique attribute combination; user is surprised by collector storage costs | Cap attribute values to known low-cardinality sets: `gen_ai.system` ∈ {anthropic, google_genai}, `gen_ai.request.model` ∈ pricing.json keys, NEVER set per-user-id or per-trace-id as a span attribute (use span.id which the backend already indexes) | Anytime a contributor adds a per-request unique attribute (request UUID, prompt hash). Within days the user's backend gets noisy and expensive. |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Emit `gen_ai.input.messages` / `gen_ai.output.messages` / `gen_ai.prompt` / `gen_ai.completion` by default in the OTel exporter | User prompts (which may contain API keys, secrets, PII) flow to whatever backend the user's OTLP endpoint points at | Default-deny. Numerical attributes only. Body capture requires `HORUS_OS_OTEL_CAPTURE_CONTENT=true` + the redactor allowlist. (Pitfall 7) |
| Persist raw tool-invocation arguments to `tool_invocations.error_message` for "debug context" | Tool args contain file paths, shell commands, credentials passed as arguments; the column is indexed and queryable | Persist `error_type` (exception class) only; never `error_message` content. If users genuinely need full args for debugging, expose via `HORUS_OS_DEBUG_TOOL_ARGS=true` with the same opt-in pattern as OTel content capture. |
| Log the prompt to `horus.err` (Python logging) for "easier debugging" | Logs end up on the filesystem (Pitfall 7 scope), often with weaker access controls than the SQLite db | Logging discipline: log structural info (trace_id, model, latency, status), never bodies. Add a CI grep check: `grep -rE "log.*(prompt|completion|messages)" src/horus_os/observability/` returns nothing. |
| Include `error_message` text in the dashboard's "last error preview" tile, unredacted | Errors often quote user input back; screenshotting the dashboard leaks the input | Redact through the same `redact()` function as Pitfall 7. Truncate to 200 chars. Show `error_type` prominently, message in a click-to-reveal tooltip. |
| Use the OTel adapter's status output (in the Adapters tab) to display the configured `OTEL_EXPORTER_OTLP_HEADERS` for "verification" | The Authorization bearer token shows up in the dashboard UI, screenshots, browser cache | Display ONLY the endpoint URL and the names of headers configured (not values). Adapter health endpoint never returns secret values. |
| Cache the `pricing.json` user-override file in a world-readable directory | Custom rates for negotiated enterprise pricing become readable by other users on a shared system | Default override path is `$XDG_CONFIG_HOME/horus-os/pricing.json` (mode 0600 on creation); document the file mode expectation. Reject world-readable override files with a warning in the dashboard, allowing the user to override the warning with an explicit flag. |
| Pricing-file override pulled from a network URL "for convenience" | A compromised pricing source = a misreporting cost dashboard, or worse, a code-injection vector if YAML/pickle were used | JSON only; load only from local filesystem paths; never `requests.get` from a remote URL in the cost path. |
| Allow the OTel adapter to attach the span body via a query param on `/api/observability/llm-calls` | Anyone with localhost access (browser plugin, local malware) can scrape bodies | All `/api/observability/*` endpoints return only the same fields the dashboard shows: numerical metrics, no bodies. To inspect bodies, the user uses SQLite directly (where the local OS file permissions are the trust boundary). |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Dashboard shows "Total cost: $0.42" with no time window indication | User thinks that's lifetime cost when it's actually last-7d; or vice versa | Always render with explicit window label: "Total cost: $0.42 (last 7 days)". Window selector is prominent, not hidden in a dropdown. |
| Pre-v0.4 trace rows render as "Cost: $0.00" alongside v0.4 rows showing real cost | User panics that v0.4 deleted their cost data | Render pre-v0.4 rows as "—" with hover "no cost data captured before v0.4". A separate dashboard tile shows "N runs from before v0.4 with no cost data" to set expectation. (Pitfall 11 prevention) |
| Tool error rate panel renders "100% errors" for a tool with 1 invocation | User thinks the tool is fully broken when it's a single noisy datapoint | Sample threshold (`call_count >= 5` for headline); below threshold render "—" with tooltip "insufficient data." (Pitfall 9 prevention) |
| Latency p95 shows `0ms` for an empty window | User reads "0ms = perfect performance" instead of "no data" | Empty window renders "—" not 0; p95 only renders with `n` count alongside. (Pitfall 10 prevention) |
| OTel adapter status shows "running" even when collector is unreachable and spans are silently dropping | User assumes export is healthy when it isn't | Adapter status reflects exporter health: track BSP's internal counters (spans queued, spans dropped, last successful export); surface `last_export_at`, `spans_dropped_last_hour`. If dropped > 0, status = `degraded` not `running`. |
| `horus-os usage --format table` truncates long agent names mid-word | User can't tell which agent is which in the table | Use the existing CLI table formatter from `horus-os traces` (already handles truncation with ellipsis). Add `--no-truncate` flag for piping to `less -S`. |
| `pricing.json` staleness banner reads as scary alarm even at 7-day staleness | User panics, files an issue, asks "is my cost data wrong?" | Banner copy is precise: "Pricing data is N days old. Most rates change quarterly. Override at $HOME/.config/horus-os/pricing.json if you need newer rates." Color: yellow at 30-60 days, red only at 90+. |
| Streaming runs and non-streaming runs are visually identical in the dashboard, but streaming runs have estimated tokens | User sees `Cost: $0.03` for a streaming run and `Cost: $0.04` for an identical non-streaming run, thinks the dashboard is broken | Streaming runs render with an `~` prefix or a "streaming (est.)" badge. (Pitfall 2 prevention) |
| `horus-os usage --format json` includes float-precision noise (`0.04200000000000001`) | User pipes to `jq`, the noise breaks downstream tools | Round costs to 6 decimal places (sub-cent precision is meaningless), durations to integer ms, in the JSON serializer. Document the precision contract in `docs/CLI.md`. |

## "Looks Done But Isn't" Checklist

Run before declaring v0.4 ready. Each item is something that often passes review but fails in the wild.

- [ ] **Streaming cost capture:** every streaming run produces a non-zero `llm_calls` row with the terminal `usage` read from `stream.get_final_message()`. Verify by hitting `/api/chat/stream` then `SELECT input_tokens, output_tokens FROM llm_calls ORDER BY id DESC LIMIT 1`. (Pitfall 2)
- [ ] **Per-iteration token sum:** a 3-iteration agent run shows `traces.total_input_tokens` equal to the SUM of the iteration `llm_calls.input_tokens`, not just the last iteration's. (Pitfall 1)
- [ ] **`time.perf_counter` everywhere:** grep `src/horus_os/observability/`, `agent.py`, `tools/loop.py` for `time.time()` — should be empty. (Pitfall 3)
- [ ] **Negative-latency guard:** unit test inserting a `latency_ms=-100` event triggers an assertion failure in `SQLitePersister`, not a corrupt row. (Pitfall 3)
- [ ] **OTel default-deny content:** unit test that fires an event with a prompt containing `AKIAIOSFODNN7EXAMPLE` and verifies the exported span (via `InMemorySpanExporter`) does NOT contain that string. (Pitfall 7)
- [ ] **OTel shutdown bound:** unit test that starts the adapter pointing at `http://127.0.0.1:1` (closed port), sends one event, calls `OtelAdapter.stop()`, asserts wall-clock < 3 seconds. (Pitfall 6)
- [ ] **OTel adapter without `[otel]` extra:** in a venv with `pip install -e ".[dev]"` (no otel), `from horus_os.adapters.otel_adapter import OtelAdapter` succeeds AND `await adapter.start(ctx)` raises a clean RuntimeError with a "pip install horus-os[otel]" hint. (Pitfall 12)
- [ ] **v0.3 database fixture migrates cleanly:** test runs `Database.init()` against `tests/fixtures/v0_3_database.sqlite3`, asserts new columns exist, old `traces.usage` blob still readable, pre-v0.4 rows have NULL on new columns. (Pitfall 11)
- [ ] **Pricing staleness banner renders:** dashboard shows the `updated_at` from `pricing.json`. Test with a fixture where `updated_at` is 60 days old, assert the banner appears. (Pitfall 5)
- [ ] **Pricing fallback is NULL not zero:** unit test that records a call to a model NOT in `pricing.json`, asserts `llm_calls.cost_usd IS NULL` and `pricing_missing = 1`. Dashboard query separates these from costed runs. (Pitfall 5)
- [ ] **Tool reliability ignores small samples:** dashboard renders "—" not "100%" for a tool with `call_count=1`. (Pitfall 9)
- [ ] **Percentile small-sample handling:** `p95` over an empty window returns NULL / "—", not 0. Over n=5 returns the value with a sample-count badge. (Pitfall 10)
- [ ] **OTel HTTP exporter, not gRPC:** `pyproject.toml`'s `[otel]` extra lists `opentelemetry-exporter-otlp-proto-http`, NOT `*-grpc`. (STACK.md, reinforced here.)
- [ ] **No `gen_ai.input.messages` or `gen_ai.output.messages` in default OTel output:** `grep -E "(input|output)\.messages|gen_ai\.(prompt|completion)" src/horus_os/adapters/` returns matches ONLY inside the explicit opt-in code path. (Pitfall 7, OpenLLMetry issue #3515 awareness)
- [ ] **Capture-overhead benchmark:** v0.4 end-to-end time for a fixture 5-iteration / 3-tool-call run is within 50ms of the recorded v0.3 baseline. (Pitfall 8)

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cost drift discovered (Pitfall 1, 2, 5) | LOW | Bug-fix release. Document on the changelog that prior costs were under/over by N%. Add a "data may be inaccurate before vX.Y.Z" footnote to dashboard for historical periods. SQLite rows stay; the dashboard query gets a sub-window exclusion or a recompute path. |
| Negative latency rows in SQLite (Pitfall 3) | LOW | One-time cleanup query: `DELETE FROM llm_calls WHERE latency_ms < 0; DELETE FROM tool_invocations WHERE latency_ms < 0;`. Ship as a migration helper or a `horus-os maintain --fix-latency` subcommand. Document the cause. |
| Streaming runs at $0.00 (Pitfall 2) | MEDIUM | Forward-fix only; cannot back-fill (the usage data wasn't captured). Dashboard adds a tooltip on streaming rows: "estimated; not captured before vX.Y.Z." User-visible explanation > silent gap. |
| OTel exporter leaked process / 60s shutdowns (Pitfall 6) | LOW | Hotfix release with bounded `force_flush` timeout. Document the change. No data loss (BSP queue dropped is acceptable; the SQLite source of truth is intact). |
| PII leaked through OTel span attributes (Pitfall 7) | HIGH | Patch release immediately. Public security advisory. Contact affected users via release notes and (if known) directly. Users must rotate any credentials that may have been in prompts. Add a CHANGELOG entry under a `### Security` heading per the keep-a-changelog convention. This is the highest-stakes failure mode in the milestone — the recovery cost is mostly reputational and is paid in user trust. |
| Migration broke v0.3 readers (Pitfall 11) | HIGH | Emergency release that re-adds whatever was DROP-ed or RENAME-d. Users who already upgraded may need to restore from backup. The fix is so painful that it's why the rule is "never DROP, never RENAME, period." |
| `pricing.json` rotted, costs systematically wrong (Pitfall 5) | LOW | Ship a patch release with refreshed `pricing.json`. Users who care can override locally. No data loss; cost numbers are derived, not stored as ground truth (we store token counts, the derived cost is a property of the join with pricing). Future dashboard queries can recompute against fresher pricing. |
| Tool reliability panel misleading (Pitfall 9) | MEDIUM | Add the missing columns (`status`, `retry_count`, `expected_no_result`); migrate is additive; backfill via UPDATE for the recoverable cases (success/error binary at minimum). Until the backfill, surface a tooltip "reliability data before vX.Y.Z is approximate." |
| Write amplification regression (Pitfall 8) | LOW | Audit recent PRs for added indexes, added pragmas, changed batching. Roll back or fix. The benchmark in CI should have caught it; add the benchmark if not present. |
| OTel adapter broke `pip install horus-os` (no extra) (Pitfall 12) | LOW | Hotfix release with lazy import. The two-variant CI install matrix should have caught it; verify the matrix is actually running. |

## Pitfall-to-Phase Mapping

How v0.4 phases prevent each pitfall. (Roadmap phase numbering per ARCHITECTURE.md §9; final phase numbers will be assigned by the roadmap.)

| # | Pitfall | Prevention Phase | Verification |
|---|---------|------------------|--------------|
| 1 | Per-iteration token undercount | v0.4.1 (schema) + v0.4.2 (capture) + v0.4.3 (cost) | 3-iter test asserts `SUM(llm_calls.input_tokens) == traces.total_input_tokens` |
| 2 | Streaming records $0.00 | v0.4.2 (capture, SSE branch) | Streaming-path integration test reads terminal usage; assert non-zero |
| 3 | Wall-clock latency | v0.4.1 (lint rule) + v0.4.2 (capture) | Ruff/grep rule, negative-latency assertion test |
| 4 | Latency excludes retries / queue / streaming | v0.4.2 (capture) defines contract; v0.4.4 (queries) surfaces TTFT + retry_count columns | Contract docstring on `ObservationEvent.latency_ms`; columns exist; docs reference |
| 5 | `pricing.json` rot | v0.4.3 (pricing fields) + v0.4.5 (banner) + v0.4.8 (release CI gate) | Banner renders on stale fixture; release CI fails on 14d+ staleness |
| 6 | OTel blocks request / leaks on shutdown | v0.4.7 (OTel adapter) | Shutdown-timeout test (< 3s with closed-port collector) |
| 7 | OTel PII leak | v0.4.7 (OTel adapter) | InMemorySpanExporter test asserts no AKIAI* string in default-mode output |
| 8 | SQLite write amplification | v0.4.1 (pragmas + indexes) + v0.4.2 (benchmark) | Capture-overhead benchmark in CI; WAL + synchronous=NORMAL set |
| 9 | Tool reliability counts wrong | v0.4.2 (capture status enum + retry_count) + v0.4.4 (queries) + v0.4.5 (dashboard threshold) | Test for retry-then-success case; dashboard renders "—" for n<5 |
| 10 | Percentile math wrong | v0.4.4 (queries) + v0.4.5 (dashboard rendering) | Test for empty window (returns NULL), small-sample (returns with badge), no aggregate-of-aggregates SQL |
| 11 | Migration breaks v0.3 readers | v0.4.1 (schema, additive only) | v0.3 fixture database migration test in CI |
| 12 | OTel adapter import without `[otel]` extra | v0.4.7 (lazy imports) + v0.4.8 (install matrix) | Two-variant install-smoke CI; clean RuntimeError on `start()` without extra |

## Sources

OpenTelemetry Python SDK behaviour and known issues:
- [opentelemetry-python issue #3309 — Exporters shutdown takes longer than a minute when failing to send](https://github.com/open-telemetry/opentelemetry-python/issues/3309) (the 60s-shutdown-block bug behind Pitfall 6)
- [opentelemetry-python issue #4623 — tracer_provider.shutdown() does not provide a configurable timeout](https://github.com/open-telemetry/opentelemetry-python/issues/4623) (configurability gap)
- [OpenTelemetry SDK trace export module docs](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html) (BatchSpanProcessor API)
- [OneUptime: How to Handle OpenTelemetry SDK Shutdown in Python with atexit Hooks](https://oneuptime.com/blog/post/2026-02-06-otel-sdk-shutdown-python-atexit-sigterm/view) (signal-handler shutdown patterns)
- [OneUptime: How to Prevent Data Loss in Seven Common OpenTelemetry Scenarios](https://oneuptime.com/blog/post/2026-02-06-prevent-data-loss-opentelemetry-scenarios/view) (drop / leak failure modes)
- [OneUptime: How to Create OpenTelemetry Batch Span Processor](https://oneuptime.com/blog/post/2026-01-30-opentelemetry-batch-span-processor/view) (BSP config)

GenAI semantic conventions and PII risk:
- [OpenLLMetry issue #3515 — `gen_ai.prompt` and `gen_ai.completion` deprecated in latest semconv](https://github.com/traceloop/openllmetry/issues/3515) (informs attribute-naming decisions, cross-referenced from FEATURES.md)
- [maketocreate: OpenTelemetry GenAI — Tracing AI Agents Without Leaking PII](https://maketocreate.com/opentelemetry-genai-tracing-ai-agents-without-leaking-pii/) (Pitfall 7 grounding)
- [OneUptime: How to Redact Sensitive User Prompts in GenAI OpenTelemetry Traces](https://oneuptime.com/blog/post/2026-02-06-redact-sensitive-prompts-genai-opentelemetry-traces/view) (redaction approach)
- [OneUptime: How to Capture GenAI Prompt and Completion Events in OpenTelemetry Traces](https://oneuptime.com/blog/post/2026-02-06-capture-genai-prompt-completion-events-opentelemetry/view) (the opt-in env-var pattern)
- [OTel GenAI semantic conventions index](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (cross-referenced from STACK.md / FEATURES.md)

Percentile and aggregation traps:
- [Last9: Latency Percentiles are Incorrect P99 of the Times](https://last9.io/blog/your-percentiles-are-incorrect-p99-of-the-times/) (averaging-of-percentiles antipattern, Pitfall 10)
- [TheAIOps: What is Latency p95/p99? Meaning, Examples, Use Cases](https://www.theaiops.com/latency-p95-p99/) (small-sample bias)
- [CloudOpsNow: What is p95 latency?](https://www.cloudopsnow.in/p95-latency/) (time-window aggregation tradeoffs)

SQLite WAL and write amplification:
- [phiresky: SQLite performance tuning — Scaling SQLite databases to 100k SELECTs/s](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/) (WAL + synchronous=NORMAL rationale)
- [DEV: SQLite WAL Mode: 10x Performance for Python Apps](https://dev.to/lumin-playstar/sqlite-wal-mode-10x-performance-for-python-apps-4ic) (per-row INSERT performance under WAL)
- [SQLite Forum: WAL Checkpoints and Performance Tuning](https://www.sqliteforum.com/p/checkpoint-algorithms-and-wal-performance) (checkpoint cadence)

Streaming token-usage capture (Anthropic + Gemini):
- [Anthropic Python SDK — Streaming docs](https://docs.anthropic.com/en/api/messages-streaming) (`MessageStream.get_final_message()` shape; cross-referenced from STACK.md)
- [Gemini API token-counting docs](https://ai.google.dev/gemini-api/docs/tokens) (`usage_metadata` after stream completion; cross-referenced from STACK.md)
- [Traceloop: From Bills to Budgets — Tracking LLM Token Usage and Cost Per User](https://www.traceloop.com/blog/from-bills-to-budgets-how-to-track-llm-token-usage-and-cost-per-user) (streaming gotchas)

Clock semantics:
- [PEP 418 — Add monotonic time, performance counter, and process time functions](https://peps.python.org/pep-0418/) (monotonic vs wall-clock spec; Pitfall 3)
- [Python docs: time.perf_counter()](https://docs.python.org/3/library/time.html#time.perf_counter)
- [Ceph PR #22121 — Use monotonic clock for perf counters latencies](https://github.com/ceph/ceph/pull/22121) (real-world bug exemplar)

Pricing data sources:
- [LiteLLM `model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) (the community canonical pricing dataset; informs Pitfall 5 sync strategy)
- [tokencost — AgentOps-AI/tokencost](https://github.com/AgentOps-AI/tokencost) (sibling project, same pricing-rot problem)
- [implicator.ai: Anthropic Usage-Based Billing Is Exact, Plan Limits Are Not](https://www.implicator.ai/anthropics-usage-based-billing-is-exact-its-plan-limits-are-vague-by-design/) (per-token rates are exact, no provider-side rounding to mask drift)

Retry / reliability metric pitfalls:
- [Helicone docs: Retries](https://docs.helicone.ai/features/advanced-usage/retries) (each retry logged separately; informs Pitfall 9)

Direct source reads (already cross-referenced in ARCHITECTURE.md):
- `/Users/santino/Projects/horus-os/src/horus_os/agent.py` — `run_agent_loop` capture site for Pitfall 1
- `/Users/santino/Projects/horus-os/src/horus_os/tools/loop.py` — `_execute_one` capture site for Pitfall 9
- `/Users/santino/Projects/horus-os/src/horus_os/server/api.py` — `_event_stream` SSE branch for Pitfall 2
- `/Users/santino/Projects/horus-os/src/horus_os/storage.py` — migration pattern for Pitfall 11

---
*Pitfalls research for: v0.4 Observability instrumentation on horus-os*
*Researched: 2026-05-25*
