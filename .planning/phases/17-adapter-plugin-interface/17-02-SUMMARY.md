# Phase 17 Plan 02 Summary

**Status:** Shipped
**Commit:** feat(17): reference HTTP webhook adapter with HMAC-SHA256 signing
**Date:** 2026-05-23

## What shipped

The first concrete adapter built on the Plan 01 contract: an HTTP
webhook receiver that validates an HMAC-SHA256 signature on every
request and routes the payload to one `run_agent` turn against a
configured agent profile. ADAPT-02 ("One reference adapter ships:
HTTP webhook receiver") is satisfied.

### New module: `horus_os.adapters.webhook`

| Symbol | Purpose |
|--------|---------|
| `WebhookAdapter` | The reference adapter class. `name = "webhook"`, `bind(app, context)` mounts the route, `describe()` returns static metadata |
| `WEBHOOK_SECRET_ENV` | Module constant: `"HORUS_OS_WEBHOOK_SECRET"` |
| `SIGNATURE_HEADER` | Module constant: `"X-Horus-Signature"` |
| `SIGNATURE_PREFIX` | Module constant: `"sha256="` |

### Behavior locked in

- **Auth:** every request must carry `X-Horus-Signature: sha256=<hex>`
  where `<hex>` is `hmac.sha256(secret, raw_body).hexdigest()`.
  Comparison uses `hmac.compare_digest` to avoid timing oracles
- **Safe by default:** the handler refuses to operate (503) when
  `HORUS_OS_WEBHOOK_SECRET` is unset or empty. There is no path to
  an open webhook
- **Status codes:** 503 (no secret), 401 (missing, malformed, or
  invalid signature), 400 (bad JSON, missing prompt, unknown
  provider), 404 (unknown agent), 500 (run_agent crashed; trace id
  returned in detail), 200 (success)
- **Agent routing:** an optional `agent` field in the JSON body
  loads the corresponding `AgentProfile` (404 on unknown) and
  forwards its `system_prompt` and `default_model` to `run_agent`.
  The recorded trace row is tagged with `agent_profile_name`
- **Model precedence:** request `model` field wins; then profile
  `default_model`; then the config default for the provider
- **Trace recording:** every request (success or run_agent failure)
  writes a trace row via `db.record_trace`. The error path uses
  `status="error"` with the exception type and message
- **Response shape:** `{ "trace_id": "...", "text": "...", "latency_ms": N }`

### Entry-point declaration

`pyproject.toml` registers the adapter:

```
[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
```

After `pip install -e .`, `discover_adapters()` finds the adapter
and `create_app` binds it automatically. A new test asserts the
entry point resolves to `WebhookAdapter` from the live importlib
metadata.

### Test surface

| File | Tests | Covers |
|------|-------|--------|
| `tests/test_adapters_webhook.py` | 14 | 503 when secret unset, 401 missing/wrong-scheme/invalid signature, 400 invalid JSON, 400 missing prompt, 404 unknown agent, 400 unknown provider, happy-path trace persistence, agent profile forwarding (system_prompt + default_model), user model wins, describe metadata, run_agent exception recorded as error trace, entry-point registered in pyproject |

14 net new tests. Full suite: 302 passed (275 baseline + 13 from
Plan 01 + 14 from Plan 02).

## Files touched

- `src/horus_os/adapters/webhook.py` (new): WebhookAdapter class plus
  helpers
- `src/horus_os/adapters/__init__.py`: re-exports `WebhookAdapter`
  alongside the contract symbols
- `pyproject.toml`: declares the entry-point under
  `[project.entry-points."horus_os.adapters"]`
- `tests/test_adapters_webhook.py` (new): 14 cases

## Lint status

`ruff check .` clean. `ruff format --check .` clean across all 61
formatted files.

## Notable / deferred

- The `from __future__ import annotations` directive forces FastAPI
  to resolve `Request` as a string at route registration. Lazy
  imports inside `bind()` solve the optional-dependency story
  (FastAPI is not required at package import time) but the future
  annotations stringification meant FastAPI could not find `Request`
  in the function's closure. The fix is to write the live class
  binding back onto module globals at bind time. Documented inline
- The webhook drives `run_agent` (single-turn), not
  `run_agent_loop` (multi-turn with tools). The reference adapter is
  intentionally narrow: a stateless HTTP endpoint. Tool dispatch is
  available via the dashboard chat surface and the CLI, and a
  future "advanced webhook" adapter can wire run_agent_loop if there
  is demand
- HMAC SHA-256 hex matches the GitHub, Stripe, and Slack conventions
  so external services already configured for one of those formats
  can sign horus-os payloads with no glue code
- Replay protection (timestamp + nonce) is deferred. A captured
  signed request remains valid until the secret rotates. A future
  revision can layer a `X-Horus-Timestamp` header and a sliding
  window check; the reference adapter ships with signature
  validation only
- The adapter constructs a fresh `Database` per request and the
  trace row is the only persistent side effect. There is no
  long-lived connection held during `run_agent` execution
- `describe()` returns a static metadata dict that a future
  `/api/adapters` diagnostics route can surface verbatim
