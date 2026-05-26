"""Tests for src/horus_os/observability/redact.py (Phase 38, Pitfall 7).

One test per allowlist pattern plus idempotence and the empty-string
edge case. The literal-substring-absence assertions are the
load-bearing TEST-13 substrate; the OTel adapter's TEST-13 test
re-asserts the same contract via the InMemorySpanExporter.
"""

from __future__ import annotations

from horus_os.observability.redact import redact


def test_redacts_aws_access_key() -> None:
    text = "my key is AKIAIOSFODNN7EXAMPLE rotate today"
    result = redact(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "[REDACTED]" in result


def test_redacts_anthropic_style_api_key() -> None:
    fake = "sk-ant-api03-" + "a" * 40
    text = f"please rotate {fake} when done"
    result = redact(text)
    assert fake not in result
    assert "[REDACTED]" in result


def test_redacts_openai_style_api_key() -> None:
    fake = "sk-proj-" + "b" * 40
    text = f"key was {fake} oops"
    result = redact(text)
    assert fake not in result
    assert "[REDACTED]" in result


def test_redacts_github_personal_token() -> None:
    fake = "ghp_" + "c" * 36
    text = f"committed {fake} by accident"
    result = redact(text)
    assert fake not in result
    assert "[REDACTED]" in result


def test_redacts_slack_bot_token() -> None:
    fake = "xoxb-fake-slack-token-body"
    text = f"bot token {fake} leaked"
    result = redact(text)
    assert fake not in result
    assert "[REDACTED]" in result


def test_redacts_email_address() -> None:
    text = "contact user@example.com for details"
    result = redact(text)
    assert "user@example.com" not in result
    assert "[REDACTED]" in result


def test_redacts_e164_phone_number() -> None:
    text = "call +18582260766 please"
    result = redact(text)
    assert "+18582260766" not in result
    assert "[REDACTED]" in result


def test_redacts_gcp_api_key_prefix() -> None:
    fake = "gcp-fake-api-key-body"
    text = f"gcp key {fake} leaked"
    result = redact(text)
    assert fake not in result
    assert "[REDACTED]" in result


def test_redact_is_idempotent() -> None:
    text = (
        "user contact: user@example.com, aws AKIAIOSFODNN7EXAMPLE, "
        "phone +18582260766, github ghp_" + "x" * 36
    )
    once = redact(text)
    twice = redact(once)
    assert once == twice


def test_redact_preserves_safe_text() -> None:
    # Innocent prose with no secret patterns and no leading-digit
    # integers; the E.164 regex requires `[1-9]` as the FIRST digit
    # so plain words pass through unchanged.
    text = "just normal user prose with no secrets"
    assert redact(text) == text


def test_redact_handles_empty_string() -> None:
    assert redact("") == ""
