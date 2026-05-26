---
phase: 38-opentelemetry-adapter
plan: "01"
verified: 2026-05-26T00:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 38 Plan 01: OpenTelemetry Adapter Verification Report

**Phase Goal:** Opt-in `[otel]` extra, default-deny content capture, bounded shutdown, TEST-13/14/15 non-negotiable.
**Verified:** 2026-05-26
**Status:** PASSED
**Re-verification:** No (initial verification)

## Goal Achievement

### Observable Truths (Load-Bearing)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | OTEL-01/07/Pitfall 12: module-top has zero `import opentelemetry`; `start()` without otel installed raises `RuntimeError`, NEVER `ModuleNotFoundError`; error message contains literal `pip install horus-os[otel]` | VERIFIED | `grep -cE "^from opentelemetry\|^import opentelemetry" src/horus_os/adapters/otel_adapter.py` = 0. `test_module_imports_cleanly_when_opentelemetry_absent` PASSED. `test_start_raises_runtime_error_with_install_hint_when_otel_missing` PASSED (asserts `excinfo.type is RuntimeError` AND `"pip install horus-os[otel]" in str(excinfo.value)`). Adapter source line 78: `OTEL_EXTRA_HINT = "OTel adapter requires 'pip install horus-os[otel]'"`. Adapter line 154-156: `except ImportError as exc: ... raise RuntimeError(OTEL_EXTRA_HINT) from exc`. |
| 2 | OTEL-02/06/TEST-14/Pitfall 6: `SimpleSpanProcessor` count = 0 in adapter source; `BatchSpanProcessor` count >= 1; `force_flush(timeout_millis=2000)` literal present; bounded-shutdown test asserts < 3s against closed port | VERIFIED | `grep -c "SimpleSpanProcessor" src/horus_os/adapters/otel_adapter.py` = **0**. `grep -c "BatchSpanProcessor"` = **3**. `grep -cE "force_flush.*2000\|FORCE_FLUSH_TIMEOUT_MS"` = **4**. Constant defined line 81: `FORCE_FLUSH_TIMEOUT_MS = 2000`. Adapter line 217: `self._provider.force_flush(timeout_millis=FORCE_FLUSH_TIMEOUT_MS)`. `test_stop_completes_within_3s_against_closed_port` PASSED with measured 0.08s wall-clock (budget < 3.0s). Test uses `time.perf_counter()` per spec. |
| 3 | OTEL-03/04/TEST-13/Pitfall 7: default-mode AND opt-in-mode tests both assert `AKIAIOSFODNN7EXAMPLE` substring NOT in exported spans; tests use `InMemorySpanExporter` | VERIFIED | `test_default_mode_strips_aws_key_literal` PASSED (asserts literal absent everywhere; deprecated body-capture keys absent). `test_opt_in_mode_still_redacts_aws_key_literal` PASSED (asserts literal absent even with body attr attached; `[REDACTED]` present). Both tests import `InMemorySpanExporter` from `opentelemetry.sdk.trace.export.in_memory_span_exporter` (test file line 30-32, grep returns 3 occurrences). Helper `_assert_literal_absent_everywhere` checks every key AND value. |
| 4 | OTEL-05: 8 canonical constants exist with exact OTel-canonical names; default-mode lines never emit deprecated keys; `gen_ai.output.messages` appears exactly once (opt-in body-attach) | VERIFIED | `test_eight_constants_exist_with_canonical_string_values` PASSED. semconv.py lines 25-32 declare all 8: `GEN_AI_SYSTEM="gen_ai.system"`, `GEN_AI_OPERATION_NAME="gen_ai.operation.name"`, `GEN_AI_REQUEST_MODEL="gen_ai.request.model"`, `GEN_AI_USAGE_INPUT_TOKENS="gen_ai.usage.input_tokens"`, `GEN_AI_USAGE_OUTPUT_TOKENS="gen_ai.usage.output_tokens"`, `GEN_AI_USAGE_CACHED_TOKENS="gen_ai.usage.cached_tokens"`, `HORUS_OS_COST_USD="horus_os.cost_usd"`, `ERROR_TYPE="error.type"`. `grep -cE "gen_ai\\.prompt\|gen_ai\\.completion\|gen_ai\\.input\\.messages" src/horus_os/adapters/otel_adapter.py` = **0**. `grep -c "gen_ai.output.messages"` = **1** (line 293, inside opt-in body-attach body). `test_grep_gate_body_attach_appears_exactly_once_in_adapter_source` PASSED. |
| 5 | TEST-15: CI has both `install-smoke-no-otel` and `install-smoke-with-otel` jobs; no-otel job asserts ModuleNotFoundError guard via runtime-error helper | VERIFIED | `.github/workflows/ci.yml` line 91: `install-smoke-no-otel:` (lines 91-124). Line 130: `install-smoke-with-otel:` (lines 130-159). Both run on 3-OS x 2-python matrix. No-otel job line 118 asserts `importlib.util.find_spec('opentelemetry') is None`, line 121 asserts adapter imports cleanly, line 124 runs `scripts/_ci_assert_otel_runtime_error.py` to enforce RuntimeError-not-ModuleNotFoundError contract at OS level. |
| 6 | pyproject.toml has `otel = [...]` extra with `opentelemetry-sdk>=1.42,<2.0` + `opentelemetry-exporter-otlp-proto-http>=1.42,<2.0`; zero grpc; entry-point registered | VERIFIED | pyproject.toml lines 36-39: `otel = ["opentelemetry-sdk>=1.42,<2.0", "opentelemetry-exporter-otlp-proto-http>=1.42,<2.0"]`. Line 69: `otel = "horus_os.adapters.otel_adapter:OtelAdapter"` under `[project.entry-points."horus_os.adapters"]`. `grep -c "grpc" pyproject.toml` = **0**. Entry-point discovery confirmed: `entry_points(group='horus_os.adapters')` includes 'otel'. |
| 7 | Anti-scope held: zero touches to bus.py/persist.py/cost.py/pricing.py/queries.py/agent.py/tools/loop.py/storage.py/discord_adapter.py/slack_adapter.py/email_adapter.py/calendar_adapter.py/webhook.py; `server/api.py` also not modified | VERIFIED | `git diff f506108..HEAD --name-only \| grep -E "(bus\|persist\|cost\|pricing\|queries\|agent\|tools/loop\|storage\|discord_adapter\|slack_adapter\|email_adapter\|calendar_adapter\|webhook)\\.py"` returns **empty**. `server/api.py` also absent from diff. Only the 17 expected files changed (1 CI workflow, 1 SUMMARY, 1 doc, 1 pyproject, 2 CI scripts, 2 _observability files, 1 adapter, 2 observability files (`__init__.py` + `redact.py`), 6 test files). |
| 8 | docs/OTEL.md contains `## Threat model` section; documents `HORUS_OS_OTEL_CAPTURE_CONTENT` opt-in flag | VERIFIED | docs/OTEL.md line 67: `## Threat model`. `HORUS_OS_OTEL_CAPTURE_CONTENT` mentioned 2 times (configuration table line 40, opt-in section line 86). 141 lines total; >= 80-line minimum. Lists 8 canonical attrs, redactor allowlist patterns, trust statement, TEST-13/14/15 references by ID. |
| 9 | Rule 2 deviation: `OTLPSpanExporter(timeout=1.0)` cap is present in source (required for TEST-14 to actually bound) | VERIFIED | Adapter line 183: `exporter = OTLPSpanExporter(timeout=OTLP_EXPORT_TIMEOUT_S)`. Constant defined line 87: `OTLP_EXPORT_TIMEOUT_S = 1.0` with comment "caps each export attempt so the exporter's internal retry loop cannot blow past the force_flush budget". Documented in SUMMARY under "Deviations from plan" and in docs/OTEL.md "Bounded shutdown" section. |
| 10 | Full pytest 708+ passing | VERIFIED | `.venv/bin/python -m pytest tests/ -q` returns `708 passed in 19.69s`. Matches SUMMARY claim exactly (644 baseline + 64 new). |
| 11 | No em-dashes in SUMMARY.md body | VERIFIED | `grep -nE "[—–]" .planning/phases/38-opentelemetry-adapter/38-01-SUMMARY.md` returns empty. Zero em-dashes and zero en-dashes in entire file. |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `src/horus_os/_observability/semconv.py` | 8 canonical constants, ABSENCE of deprecated body-capture constants | VERIFIED | 44 lines; 8 constants defined; 4 deprecated absent; `test_eight_constants_exist_with_canonical_string_values` + `test_deprecated_attribute_constants_absent` PASSED |
| `src/horus_os/_observability/__init__.py` | Re-exports 8 constants | VERIFIED | Re-exports verified by `test_package_init_reexports_eight_constants` |
| `src/horus_os/observability/redact.py` | Public `redact(text)` with 7 regex patterns (AWS, sk-, ghp_, xoxb-, email, e164, gcp-) | VERIFIED | 67 lines; 7 patterns present (file has gcp- regex); idempotence test passes; 11 unit tests in test_observability_redact.py all pass |
| `src/horus_os/adapters/otel_adapter.py` | OtelAdapter class, lazy import, RuntimeError on missing otel, BatchSpanProcessor, bounded force_flush(2000), default-deny content | VERIFIED | 296 lines; all 5 grep gates pass; all 12 contract tests pass |
| `pyproject.toml` | `[otel]` extra (HTTP not gRPC), entry-point registered | VERIFIED | otel extra at line 36-39; entry-point at line 69; grpc count = 0; entry-point discoverable via importlib.metadata |
| `.github/workflows/ci.yml` | Two new jobs install-smoke-no-otel + install-smoke-with-otel | VERIFIED | Both jobs present on 3-OS x 2-python matrix; existing lint-and-test and install-smoke jobs unchanged |
| `docs/OTEL.md` | 80+ lines with Threat model section | VERIFIED | 141 lines; Threat model section at line 67 |
| `tests/test_adapters_otel_pii_redaction.py` | TEST-13 default + opt-in mode pinned | VERIFIED | 17 tests collected, all PASS; uses InMemorySpanExporter; AKIAIOSFODNN7EXAMPLE literal present in fixture |
| `tests/test_adapters_otel_bounded_shutdown.py` | TEST-14 < 3s wall-clock | VERIFIED | 10 tests collected, all PASS; measured 0.08s actual elapsed against closed port |
| `tests/test_adapters_otel_install_smoke.py` | TEST-15 substrate | VERIFIED | 10 tests, all PASS; runtime-error contract + entry-point discovery + pyproject parsing |
| `tests/test_observability_redact.py` | One test per pattern + idempotence | VERIFIED | 11 tests, all PASS |
| `tests/test_observability_semconv.py` | 4 constants tests | VERIFIED | 4 tests, all PASS |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `otel_adapter.py` | `observability/__init__.py` (`get_observation_bus`) | `get_observation_bus().subscribe(self._on_event)` in `start()` line 196 | WIRED | Subscription happens inside `start()`, lazy after provider mounted |
| `otel_adapter.py` | `_observability/semconv.py` | `from horus_os._observability.semconv import (...)` line 55-64 | WIRED | 8 constants imported at module top (stdlib-clean import) |
| `otel_adapter.py` | `observability/redact.py` | `from horus_os.observability.redact import redact` line 71 | WIRED | Only invoked inside opt-in gate (line 292: `redacted = redact(event.error_message)`) |
| `pyproject.toml` | `otel_adapter.py:OtelAdapter` | Entry-point registration line 69 | WIRED | Discovery confirmed via `importlib.metadata.entry_points(group='horus_os.adapters')` |
| `ci.yml` (install-smoke-no-otel) | `scripts/_ci_assert_otel_runtime_error.py` | Job step "Assert start raises clean RuntimeError" | WIRED | CI job calls the script at line 124 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|---|
| `otel_adapter.py` `_on_event` | `event` (ObservationEvent) | `get_observation_bus().subscribe(self._on_event)` (line 196) | Real LLMCallEvent flows from bus (Phase 33 publishers) | FLOWING |
| `otel_adapter.py` `_on_event` | span attributes (token counts, cost) | `event.input_tokens`, `event.cost_usd`, etc. | Real values from LLMCallEvent dataclass; verified by `test_default_span_attributes_match_canonical_set` | FLOWING |
| Opt-in body attach | `event.error_message` | LLMCallEvent.error_message field | Real value flows through `redact()` then `set_attribute` | FLOWING (when opt-in flag set) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 38 tests pass | `pytest tests/test_adapters_otel*.py tests/test_observability_*.py -v` | 64 passed in 8.89s | PASS |
| Full suite passes 708+ | `pytest tests/ -q` | `708 passed in 19.69s` | PASS |
| Bounded shutdown actually bounds | `pytest tests/test_adapters_otel_bounded_shutdown.py::test_stop_completes_within_3s_against_closed_port --durations=1` | 0.08s wall-clock (budget 3.0s) | PASS |
| Entry-point discoverable | `python -c "from importlib.metadata import entry_points; print('otel' in [ep.name for ep in entry_points(group='horus_os.adapters')])"` | `True`; full list `['calendar', 'discord', 'email', 'otel', 'slack', 'webhook']` | PASS |
| Adapter imports stdlib-clean | `python -c "from horus_os.adapters.otel_adapter import OtelAdapter; print(OtelAdapter().name)"` | `otel` (no opentelemetry import triggered) | PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| OTEL-01 | Bare pip install pulls zero opentelemetry-* | SATISFIED | Module-top grep = 0; CI no-otel job asserts `find_spec('opentelemetry') is None` |
| OTEL-02 | BatchSpanProcessor + bounded force_flush(2000) + shutdown() | SATISFIED | `test_stop_completes_within_3s_against_closed_port` + grep gate; `force_flush(timeout_millis=FORCE_FLUSH_TIMEOUT_MS)` at line 217 |
| OTEL-03 | Default-deny content capture | SATISFIED | `test_default_mode_strips_aws_key_literal` PASSED; deprecated body-capture keys ABSENT from default-mode span |
| OTEL-04 | Opt-in via exact lowercase 'true' + redactor | SATISFIED | `test_opt_in_mode_still_redacts_aws_key_literal` PASSED; parametrized test over 7 alternate flag values all stay default-deny |
| OTEL-05 | 8 canonical GenAI attribute keys from semconv.py | SATISFIED | `test_default_span_attributes_match_canonical_set` + `test_eight_constants_exist_with_canonical_string_values` PASS |
| OTEL-06 | BatchSpanProcessor always, never Simple in adapter source | SATISFIED | `grep -c SimpleSpanProcessor src/horus_os/adapters/otel_adapter.py` = 0 |
| OTEL-07 | Clean RuntimeError with install hint, never ModuleNotFoundError | SATISFIED | `test_start_raises_runtime_error_with_install_hint_when_otel_missing` PASSED with `excinfo.type is RuntimeError` |
| TEST-13 | PII not leaked (AKIAIOSFODNN7EXAMPLE absent in both modes) | SATISFIED | Both default-mode + opt-in-mode tests pin the literal absence |
| TEST-14 | stop() < 3s against closed-port endpoint | SATISFIED | Measured 0.08s wall-clock |
| TEST-15 | Two-variant install-smoke CI matrix | SATISFIED | Both `install-smoke-no-otel` and `install-smoke-with-otel` jobs on 3-OS x 2-python in ci.yml |

### Anti-Patterns Found

None. Scan of all 17 changed files found no debt markers (TBD/FIXME/XXX/TODO) in production code beyond test-fixture references.

### Anti-Scope Held

| Forbidden path | Touched in diff? |
|----------------|---|
| bus.py / persist.py / cost.py / pricing.py / queries.py | NO |
| agent.py / tools/loop.py / storage.py | NO |
| server/api.py | NO |
| discord_adapter.py / slack_adapter.py / email_adapter.py / calendar_adapter.py / webhook.py | NO |

### Human Verification Required

None. All 11 load-bearing truths are verifiable programmatically and all checks passed live in this verification pass.

### Gaps Summary

No gaps. Phase 38 goal achieved end-to-end:

- Lazy-import contract held (module-top opentelemetry imports = 0; clean RuntimeError fires).
- Bounded shutdown contract held (0.08s actual vs 3s budget; OTLPSpanExporter timeout=1.0s cap present per Rule 2 deviation, documented).
- Default-deny PII contract held (AKIAIOSFODNN7EXAMPLE absent in default AND opt-in modes; deprecated body-capture constants absent from semconv.py; redactor allowlist applied as defence-in-depth).
- Canonical attribute set contract held (8 constants, no deprecated keys in default-mode lines, `gen_ai.output.messages` appears exactly once in opt-in branch).
- Two-variant install-smoke CI matrix in place.
- Anti-scope completely held (zero touches to all 15 forbidden production paths).
- Full pytest 708 passing (matches SUMMARY claim).
- Zero em-dashes in SUMMARY body.

---

_Verified: 2026-05-26_
_Verifier: Claude (gsd-verifier)_
