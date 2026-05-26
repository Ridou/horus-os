# OpenTelemetry adapter (opt-in)

The OpenTelemetry adapter is an opt-in OTLP-HTTP exporter for horus-os
agent runs. SQLite remains the source of truth for cost, latency, and
tool-reliability data; this adapter is the bridge to whatever OTel
collector you already run (Grafana Tempo, Honeycomb, SigNoz, Datadog,
Jaeger, etc.). Shipped in the v0.4 Observability milestone as a
v0.3-style lifecycle adapter (see `src/horus_os/adapters/base.py`:
`LifecycleAdapter`).

## Installation

```bash
pip install "horus-os[otel]"
```

A bare `pip install horus-os` does NOT install OpenTelemetry. The
`[otel]` extra adds two pure-Python packages: `opentelemetry-sdk` and
`opentelemetry-exporter-otlp-proto-http`. The HTTP exporter (NOT gRPC)
is the deliberate choice; STACK.md §3-OS CI Compatibility documents
why (Windows wheel gaps on `grpcio` would break the install matrix).

If you forget the extra and try to start the adapter, you get a clean
error message pointing to the install command:

```
RuntimeError: OTel adapter requires 'pip install horus-os[otel]'
```

NEVER `ModuleNotFoundError` (the lazy-import contract; see
`src/horus_os/adapters/otel_adapter.py` and Pitfall 12).

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (unset) | OTLP HTTP collector URL, for example `http://localhost:4318`. REQUIRED for the adapter to start. |
| `OTEL_EXPORTER_OTLP_HEADERS` | (unset) | Optional auth headers in `key=value,key2=value2` form. Passed through to the OTLP SDK. |
| `OTEL_SERVICE_NAME` | `horus-os` | Resource `service.name` attribute. |
| `HORUS_OS_OTEL_CAPTURE_CONTENT` | `false` (default-deny) | Set EXACTLY to lowercase `true` to opt in to body content capture (still redactor-gated; see Threat model section). Any other value (including `1`, `yes`, `TRUE`) leaves default-deny in place. |

## Attribute schema

The adapter emits ONE span per `LLMCallEvent` (one LLM call). Default-
mode attribute keys are sourced from `src/horus_os/_observability/semconv.py`:

| Attribute | Source | Notes |
|-----------|--------|-------|
| `gen_ai.system` | "anthropic" or "google_genai" | Normalized at the OTel boundary; SQLite stores "gemini" short-form. |
| `gen_ai.operation.name` | "chat" | Only operation v0.4 emits. |
| `gen_ai.request.model` | model name string | Exact value sent to the SDK. |
| `gen_ai.usage.input_tokens` | int | From SDK response. |
| `gen_ai.usage.output_tokens` | int | From SDK response. |
| `gen_ai.usage.cached_tokens` | int (omitted when 0) | Anthropic `cache_read_input_tokens` or Gemini `cached_content_token_count`. |
| `horus_os.cost_usd` | float (omitted when None) | Phase 34 cost annotation; omitted (NOT zero) for unknown models. |
| `error.type` | exception class name (omitted on success) | NEVER the error message which can carry user content. |

Span name follows OTel GenAI convention: `chat {model}`.

Per-tool spans are NOT emitted by Phase 38 (Phase 38 emits ONLY
LLMCallEvent). v0.5 may extend.

GenAI semantic conventions are in `Development` status per the OTel
spec as of May 2026; we own the constants in `_observability/semconv.py`
so when the spec stabilizes one file changes.

## Threat model

What an OTel collector receives in DEFAULT mode:

- Numerical metadata: `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens`, `horus_os.cost_usd`
- Structural metadata: `gen_ai.system`, `gen_ai.operation.name`, `gen_ai.request.model`
- On failure: `error.type` (exception CLASS NAME ONLY, never the message)
- Span name (e.g. `chat claude-sonnet-4-6`)
- Resource attributes: `service.name`, `service.version`

What the collector DOES NOT receive in default mode:

- Prompt content (NEVER)
- Completion content (NEVER)
- User identifiers (NEVER)
- Tool input args (NEVER)
- Tool output content (NEVER)
- Error messages (NEVER; only exception class names)

What changes when `HORUS_OS_OTEL_CAPTURE_CONTENT=true` (opt-in mode):

- The adapter MAY attach a redacted `gen_ai.output.messages` attribute carrying the `LLMCallEvent.error_message` (which today is class-name-only per Phase 33's capture contract, so the redactor runs as a defence-in-depth layer rather than the primary safety guarantee).
- The redactor allowlist (defined in `src/horus_os/observability/redact.py`) strips these patterns BEFORE attribute attachment:
  - `AKIA[A-Z0-9]{16}` (AWS access key IDs)
  - `sk-[A-Za-z0-9_-]{20,}` (Anthropic / OpenAI keys)
  - `ghp_[A-Za-z0-9]{36,}` (GitHub personal tokens)
  - `xox[abpre]-[A-Za-z0-9_-]+` (Slack tokens)
  - email-shaped strings
  - E.164 phone numbers
  - `gcp-[A-Za-z0-9_-]+` (GCP API key prefix)
- Matched secrets are replaced with the literal `[REDACTED]`.

Trust statement: if you cannot trust your OTel collector AND any
backend it forwards to with the metadata listed above, do NOT enable
the OTel adapter. If you enable opt-in content capture you accept that
the redactor is a best-effort allowlist; novel secret formats may slip
past until the allowlist is extended.

## Bounded shutdown

The adapter calls `provider.force_flush(timeout_millis=2000)` then
`provider.shutdown()` in `stop()`. The OTLP HTTP exporter is also
configured with a per-export timeout of 1 second so its internal
retry loop cannot blow past the force-flush budget. If the collector
is unreachable, you lose up to 2 seconds of pending spans but the app
exits in under 3 seconds (NOT 60 seconds; see
[OTel Python issue #3309](https://github.com/open-telemetry/opentelemetry-python/issues/3309)
for the upstream bug we work around). `BatchSpanProcessor` is used in
production; the synchronous-export span processor variant is forbidden
in the adapter source (grep gate enforces).

## Regression coverage

Three non-negotiable tests guard the adapter (named by ID so future
contributors can find the regression coverage quickly):

- **TEST-13 (PII-not-leaked):** `tests/test_adapters_otel_pii_redaction.py` asserts `AKIAIOSFODNN7EXAMPLE` literal never appears in exported span attributes in either default or opt-in mode.
- **TEST-14 (bounded-shutdown):** `tests/test_adapters_otel_bounded_shutdown.py` asserts `stop()` against a closed-port endpoint completes in less than 3 seconds.
- **TEST-15 (two-variant install-smoke):** `.github/workflows/ci.yml` `install-smoke-no-otel` AND `install-smoke-with-otel` jobs on the 3-OS x 2-python matrix.

## When to use this adapter

- You already run an OTel collector / Grafana Tempo / Honeycomb / SigNoz / Datadog / Jaeger and want horus-os spans in the same backend.
- You want vendor-neutral export and your collector can route to anywhere.

## When NOT to use this adapter

- You do not run a collector. SQLite + `/observability` dashboard + `horus-os usage` CLI is the local-first path.
- You want prompt / completion archival without trust in the collector. SQLite is the source of truth; v0.4 does not export bodies.
- You need auth on the adapter itself. The adapter binds the user's OTel env vars verbatim; auth is configured at the collector.

Phase 39 (REL-09) will polish this doc as part of the v0.4.0 release
docs trio (`MIGRATION-v0.3-to-v0.4.md`, `OBSERVABILITY.md`, `OTEL.md`).
The Threat model section above already meets the REL-09 contract from
ROADMAP §Phase 39.
