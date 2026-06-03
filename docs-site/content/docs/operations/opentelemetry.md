---
title: "OpenTelemetry"
description: "Export horus-os agent spans to any OTLP collector with the opt-in OTel adapter, default-deny content capture, and a bounded shutdown."
---

## Overview

The OpenTelemetry adapter is an opt-in OTLP-HTTP exporter for horus-os agent runs. SQLite stays the source of truth for cost, latency, and tool-reliability data; this adapter is the bridge to whatever OTel collector you already run (Grafana Tempo, Honeycomb, SigNoz, Datadog, Jaeger, and so on).

It is built as a lifecycle adapter discovered through entry points, so there is no hardcoded wiring in the server. Uninstalling the `otel` extra fully detaches the adapter.

> [!NOTE]
> If you do not run a collector, you do not need this page. SQLite plus the `/observability` dashboard plus the `horus-os usage` CLI is the local-first path. See [Observability](/operations/observability/).

## Installation

The adapter ships in the `otel` extra. A bare `pip install horus-os` does NOT install OpenTelemetry.

```bash
pip install "horus-os[otel]"
```

The `otel` extra adds two pure-Python packages: `opentelemetry-sdk` and `opentelemetry-exporter-otlp-proto-http`. The HTTP exporter (not gRPC) is a deliberate choice to keep the cross-OS install matrix working.

If you try to start the adapter without the extra installed, you get a clean error pointing at the install command rather than a raw import failure:

```text
RuntimeError: OTel adapter requires 'pip install horus-os[otel]'
```

## Configuration

The adapter is configured entirely through environment variables. It does not start unless you point it at a collector endpoint.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (unset) | OTLP HTTP collector URL, for example `http://localhost:4318`. Required for the adapter to start. |
| `OTEL_EXPORTER_OTLP_HEADERS` | (unset) | Optional auth headers in `key=value,key2=value2` form, passed through to the OTLP SDK. |
| `OTEL_SERVICE_NAME` | `horus-os` | Resource `service.name` attribute. |
| `HORUS_OS_OTEL_CAPTURE_CONTENT` | `false` (default-deny) | Set exactly to the lowercase literal `true` to opt in to body content capture. Any other value leaves default-deny in place. |

A minimal local setup that exports to a collector listening on the default OTLP-HTTP port:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="horus-os"
horus-os serve
```

The adapter binds the OTel env vars verbatim. There is no auth on the adapter itself; auth is configured at the collector through `OTEL_EXPORTER_OTLP_HEADERS` and your collector's own controls.

## Attribute schema

The adapter emits one span per LLM call. The span name follows the OTel GenAI convention `chat {model}` (for example `chat claude-sonnet-4-6`).

| Attribute | Source | Notes |
|-----------|--------|-------|
| `gen_ai.system` | `anthropic` or `google_genai` | Normalized at the OTel boundary; SQLite stores the `gemini` short form. |
| `gen_ai.operation.name` | `chat` | The only operation emitted today. |
| `gen_ai.request.model` | model name string | The exact value sent to the SDK. |
| `gen_ai.usage.input_tokens` | int | From the SDK response. |
| `gen_ai.usage.output_tokens` | int | From the SDK response. |
| `gen_ai.usage.cached_tokens` | int (omitted when 0) | Anthropic `cache_read_input_tokens` or Gemini `cached_content_token_count`. |
| `horus_os.cost_usd` | float (omitted when unknown) | Omitted, not zeroed, for models with no known price. |
| `error.type` | exception class name (omitted on success) | The class name only, never the formatted message, which can carry user content. |

Resource attributes `service.name` and `service.version` are attached to every span. Per-tool spans are not emitted in the current version.

> [!NOTE]
> The OTel GenAI semantic conventions are still in `Development` status upstream. horus-os owns the attribute-key constants internally, so when the spec stabilizes the change is localized.

## Default mode: what your collector receives

In default mode (`HORUS_OS_OTEL_CAPTURE_CONTENT` unset, or set to anything other than the exact lowercase literal `true`), the adapter emits only the canonical metadata keys above.

The collector receives:

- Numerical metadata: `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens` (omitted when 0), and `horus_os.cost_usd` (omitted for unknown models).
- Structural metadata: `gen_ai.system`, `gen_ai.operation.name`, `gen_ai.request.model`.
- On failure: `error.type` (the exception class name only).
- The span name, for example `chat claude-sonnet-4-6`.
- Resource attributes: `service.name`, `service.version`.

The collector does NOT receive:

- Prompt content.
- Completion content.
- User identifiers.
- Tool input arguments.
- Tool output content.
- Error messages (only exception class names).

## Opt-in content capture

The opt-in flag is checked for exact lowercase equality. Only the literal string `true` enables body content capture. Variants such as `1`, `yes`, `TRUE`, `True`, `on`, and `enabled` all stay default-deny, and a regression test pins this contract.

```bash
export HORUS_OS_OTEL_CAPTURE_CONTENT=true
```

The primary safety guarantee is not the redactor; it is the absence of the body-capture attribute names from the internal constants layer. A contributor who wants to add body capture has to write those literal strings by hand, which surfaces in code review. The redactor is defence-in-depth on top of that.

When opt-in mode is active, the adapter may attach a redacted attribute before export. The redactor allowlist strips these patterns and replaces matches with the literal `[REDACTED]`:

- `AKIA[A-Z0-9]{16}` (AWS access key IDs).
- `sk-[A-Za-z0-9_-]{20,}` (Anthropic and OpenAI keys).
- `ghp_[A-Za-z0-9]{36,}` (GitHub personal tokens).
- `xox[abpre]-[A-Za-z0-9_-]+` (Slack tokens).
- Email-shaped strings.
- `gcp-[A-Za-z0-9_-]+` (GCP API key prefix).
- E.164 phone numbers (deliberately over-matching bare integers).

> [!WARNING]
> Content capture is best-effort redaction. Novel secret formats may slip past the allowlist until it is extended. Leave default-deny enabled unless you specifically need body content for replay debugging AND your collector and downstream backends are inside your trust boundary.

## Trust statement

If you cannot trust your OTel collector and any backend it forwards to with the default-mode metadata above, do not enable the OTel adapter.

If you enable opt-in content capture, you accept that the redactor is a best-effort allowlist. SQLite remains the source of truth; the current version does not export bodies in default mode.

The adapter holds its own `TracerProvider` and does not call `trace.set_tracer_provider()`. Disabling it cleanly drops its provider without touching other tracers you may add separately, such as `opentelemetry-instrumentation-*` auto-instrumentation.

## Bounded shutdown

On stop, the adapter calls `force_flush(timeout_millis=2000)` and then `shutdown()`. The OTLP HTTP exporter is also configured with a per-export timeout of one second, so its internal retry loop cannot exceed the force-flush budget.

If the collector is unreachable, you lose up to two seconds of pending spans, but the app still exits in under three seconds rather than hanging on the upstream OTel Python retry behavior. A `BatchSpanProcessor` is used; the synchronous-export variant is forbidden in the adapter source.

## When to use this adapter

- You already run an OTel collector, Grafana Tempo, Honeycomb, SigNoz, Datadog, or Jaeger and want horus-os spans in the same backend.
- You want vendor-neutral export and your collector can route anywhere.

## When NOT to use this adapter

- You do not run a collector. Use the local-first observability path instead.
- You want prompt or completion archival without trusting the collector. SQLite is the source of truth and default mode does not export bodies.
- You need auth on the adapter itself. The adapter binds your OTel env vars verbatim; auth lives at the collector.

## See also

- [Observability](/operations/observability/)
- [Traces and observability](/concepts/traces-and-observability/)
- [Security](/operations/security/)
- [Environment variables](/reference/environment-variables/)
