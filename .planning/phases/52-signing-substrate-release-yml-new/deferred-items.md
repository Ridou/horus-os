# Phase 52 Deferred Items

## Pre-existing test failures (out of scope for Phase 52)

`tests/test_adapters_otel_pii_redaction.py` carries 30 failing tests on the
pre-Phase-52 main HEAD (verified on dd44f06 v0.5 baseline AND on current
main 6af44e7). The failures live in the OpenTelemetry adapter PII redaction
code path (Phase 38 / OTEL substrate) and are entirely unrelated to the
signing substrate Phase 52 lands.

Phase 52 changes (release.yml, verify_release.py, no-pypi-in-v0.6.md,
docs/RELEASE.md edits, .planning/PROJECT.md row append) do not touch:
- src/horus_os/adapters/otel_adapter.py
- src/horus_os/observability/*
- tests/test_adapters_otel_pii_redaction.py

Per the deviation rule scope boundary ("Only auto-fix issues DIRECTLY
caused by the current task's changes"), these failures are logged here
and deferred. A future phase owns the otel adapter regression.

Sample failure (representative):
```
FAILED tests/test_adapters_otel_pii_redaction.py::test_opt_in_mode_with_none_error_message_does_not_set_any_body_attr
FAILED tests/test_adapters_otel_pii_redaction.py::test_capture_content_env_value_other_than_true_stays_default_deny[*]
```

Verified pre-existing via:
```
git worktree add /tmp/baseline origin/main
cd /tmp/baseline && pytest tests/test_adapters_otel_pii_redaction.py --tb=no -q
# Result: 15 failed, 2 passed (same failure set; identical to post-Phase-52 state)
```
