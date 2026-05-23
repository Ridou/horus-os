"""Tests for the Email adapter.

All tests run with `imaplib.IMAP4_SSL` and `smtplib.SMTP_SSL`
mocked at the adapter module level via monkeypatch. No live IMAP
or SMTP connection is opened in any test.

`run_agent` is monkeypatched at the adapter module level so no
provider SDK is required and no network call happens.
"""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from horus_os import Config, Database
from horus_os.adapters import (
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    AdapterContext,
    AdapterRegistry,
    EmailAdapter,
)
from horus_os.adapters import email_adapter as email_adapter_module
from horus_os.types import AgentResult

# -- env var helpers ----------------------------------------------------------

REQUIRED_ENV = {
    "HORUS_OS_EMAIL_IMAP_HOST": "imap.example.test",
    "HORUS_OS_EMAIL_IMAP_USER": "bot@example.test",
    "HORUS_OS_EMAIL_IMAP_PASSWORD": "imap-app-password",
    "HORUS_OS_EMAIL_SMTP_HOST": "smtp.example.test",
}

# Vars that may be present in the test environment and would
# otherwise pollute the missing-env tests.
ALL_EMAIL_ENV = [
    "HORUS_OS_EMAIL_IMAP_HOST",
    "HORUS_OS_EMAIL_IMAP_PORT",
    "HORUS_OS_EMAIL_IMAP_USER",
    "HORUS_OS_EMAIL_IMAP_PASSWORD",
    "HORUS_OS_EMAIL_SMTP_HOST",
    "HORUS_OS_EMAIL_SMTP_PORT",
    "HORUS_OS_EMAIL_SMTP_USER",
    "HORUS_OS_EMAIL_SMTP_PASSWORD",
    "HORUS_OS_EMAIL_POLL_INTERVAL",
    "HORUS_OS_EMAIL_AGENT_PROFILE",
]


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ALL_EMAIL_ENV:
        monkeypatch.delenv(key, raising=False)


def _set_all_required(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


# -- IMAP / SMTP fakes --------------------------------------------------------


class _FakeIMAP:
    """Minimal stand-in for imaplib.IMAP4_SSL.

    Records every call. SEARCH returns the configured UIDs. FETCH
    returns the raw bytes for the matching UID. STORE records the
    UID + flags. LOGIN, SELECT, LOGOUT all return ("OK", [b""]).
    """

    instances: ClassVar[list[_FakeIMAP]] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.login_calls: list[tuple[str, str]] = []
        self.select_calls: list[str] = []
        self.search_calls: list[tuple[Any, ...]] = []
        self.fetch_calls: list[tuple[bytes, str]] = []
        self.store_calls: list[tuple[bytes, str, str]] = []
        self.logout_calls = 0
        # Configurable per-test via class state.
        self.search_uids: list[bytes] = []
        self.messages: dict[bytes, bytes] = {}
        _FakeIMAP.instances.append(self)

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        self.login_calls.append((user, password))
        return ("OK", [b""])

    def select(self, mailbox: str) -> tuple[str, list[bytes]]:
        self.select_calls.append(mailbox)
        return ("OK", [b"1"])

    def search(self, charset: Any, criteria: str) -> tuple[str, list[bytes]]:
        self.search_calls.append((charset, criteria))
        if not self.search_uids:
            return ("OK", [b""])
        return ("OK", [b" ".join(self.search_uids)])

    def fetch(self, uid: bytes, parts: str) -> tuple[str, list[Any]]:
        self.fetch_calls.append((uid, parts))
        raw = self.messages.get(uid, b"")
        if not raw:
            return ("OK", [None])
        return ("OK", [(b"1 (UID 1 BODY[] {%d}" % len(raw), raw), b")"])

    def store(self, uid: bytes, command: str, flags: str) -> tuple[str, list[bytes]]:
        self.store_calls.append((uid, command, flags))
        return ("OK", [b""])

    def logout(self) -> tuple[str, list[bytes]]:
        self.logout_calls += 1
        return ("BYE", [b""])


class _FakeSMTP:
    """Minimal stand-in for smtplib.SMTP_SSL. Records send_message calls."""

    instances: ClassVar[list[_FakeSMTP]] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.login_calls: list[tuple[str, str]] = []
        self.sent: list[EmailMessage] = []
        self.quit_calls = 0
        _FakeSMTP.instances.append(self)

    def login(self, user: str, password: str) -> None:
        self.login_calls.append((user, password))

    def send_message(self, msg: EmailMessage) -> None:
        self.sent.append(msg)

    def quit(self) -> None:
        self.quit_calls += 1


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install fake IMAP and SMTP classes on the adapter module."""
    _FakeIMAP.instances = []
    _FakeSMTP.instances = []
    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", _FakeIMAP)
    monkeypatch.setattr(email_adapter_module.smtplib, "SMTP_SSL", _FakeSMTP)


# -- fixtures -----------------------------------------------------------------


def _make_context(tmp_path: Path) -> AdapterContext:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    reg = AdapterRegistry()
    reg.register("email")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)


def _raw_message(
    *,
    subject: str = "Hello",
    from_addr: str = "sender@example.test",
    to_addr: str = "bot@example.test",
    body: str = "Hi bot, what's the weather?",
    message_id: str = "<original-1@example.test>",
    references: str | None = None,
    reply_to: str | None = None,
    auto_submitted: str | None = None,
    precedence: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    if references:
        msg["References"] = references
    if reply_to:
        msg["Reply-To"] = reply_to
    if auto_submitted:
        msg["Auto-Submitted"] = auto_submitted
    if precedence:
        msg["Precedence"] = precedence
    if extra_headers:
        for key, value in extra_headers.items():
            msg[key] = value
    msg.set_content(body)
    return msg.as_bytes()


def _fake_run_agent(text: str = "the weather is sunny") -> MagicMock:
    return MagicMock(return_value=AgentResult(text=text, provider="anthropic", model="m"))


# -- construction -------------------------------------------------------------


def test_construct_clean() -> None:
    adapter = EmailAdapter()
    assert adapter.name == "email"
    assert adapter._task is None
    assert adapter._context is None


def test_bind_is_noop(tmp_path: Path) -> None:
    adapter = EmailAdapter()
    ctx = _make_context(tmp_path)
    assert adapter.bind(MagicMock(), ctx) is None


# -- start error paths --------------------------------------------------------


async def test_start_missing_imap_host_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_env(monkeypatch)
    # Set all but IMAP_HOST.
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_USER", "x")
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_PASSWORD", "y")
    monkeypatch.setenv("HORUS_OS_EMAIL_SMTP_HOST", "smtp.example.test")
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("email")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_EMAIL_IMAP_HOST" in (entry.error_message or "")
    assert adapter._task is None


async def test_start_missing_imap_user_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_HOST", "imap.example.test")
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_PASSWORD", "y")
    monkeypatch.setenv("HORUS_OS_EMAIL_SMTP_HOST", "smtp.example.test")
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("email")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_EMAIL_IMAP_USER" in (entry.error_message or "")


async def test_start_missing_imap_password_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_HOST", "imap.example.test")
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_USER", "bot@example.test")
    monkeypatch.setenv("HORUS_OS_EMAIL_SMTP_HOST", "smtp.example.test")
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("email")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_EMAIL_IMAP_PASSWORD" in (entry.error_message or "")


async def test_start_missing_smtp_host_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_HOST", "imap.example.test")
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_USER", "bot@example.test")
    monkeypatch.setenv("HORUS_OS_EMAIL_IMAP_PASSWORD", "y")
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("email")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_EMAIL_SMTP_HOST" in (entry.error_message or "")


# -- start happy path ---------------------------------------------------------


async def test_start_with_valid_env_schedules_task_and_marks_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_all_required(monkeypatch)
    _install_fakes(monkeypatch)
    # Stop the loop's first iteration before it does real work.
    monkeypatch.setattr(email_adapter_module.EmailAdapter, "_poll_once", lambda self: None)
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    try:
        entry = ctx.registry.get("email")
        assert entry.status == ADAPTER_STATUS_RUNNING
        assert adapter._task is not None
        assert not adapter._task.done()
    finally:
        await adapter.stop()


async def test_start_honors_poll_interval_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_all_required(monkeypatch)
    monkeypatch.setenv("HORUS_OS_EMAIL_POLL_INTERVAL", "5")
    _install_fakes(monkeypatch)
    monkeypatch.setattr(email_adapter_module.EmailAdapter, "_poll_once", lambda self: None)
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    try:
        assert adapter._poll_interval == 5
    finally:
        await adapter.stop()


# -- _poll_once: end-to-end happy path ---------------------------------------


def _build_adapter_with_config(tmp_path: Path) -> tuple[EmailAdapter, AdapterContext]:
    """Build an EmailAdapter with `_email_config` set, bypassing `start`."""
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    adapter._context = ctx
    adapter._email_config = email_adapter_module.EmailConfig(
        imap_host="imap.example.test",
        imap_port=993,
        imap_user="bot@example.test",
        imap_password="imap-app-password",
        smtp_host="smtp.example.test",
        smtp_port=465,
        smtp_user="bot@example.test",
        smtp_password="smtp-app-password",
        poll_interval=60,
    )
    return adapter, ctx


def test_poll_once_fetches_and_replies_and_marks_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch)
    fake_run = _fake_run_agent("the weather is sunny")
    monkeypatch.setattr(email_adapter_module, "run_agent", fake_run)
    adapter, ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message(
        subject="weather?",
        from_addr="sender@example.test",
        body="Hi bot, what's the weather?",
        message_id="<original-1@example.test>",
    )

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    # IMAP side.
    assert len(_FakeIMAP.instances) == 1
    fake_imap = _FakeIMAP.instances[0]
    assert fake_imap.login_calls == [("bot@example.test", "imap-app-password")]
    assert fake_imap.select_calls == ["INBOX"]
    assert fake_imap.search_calls == [(None, "UNSEEN")]
    assert fake_imap.fetch_calls == [(b"1", "(BODY.PEEK[])")]
    assert fake_imap.store_calls == [(b"1", "+FLAGS", "(\\Seen)")]
    assert fake_imap.logout_calls == 1

    # Agent side.
    assert fake_run.call_count == 1
    assert "what's the weather?" in fake_run.call_args.args[0]

    # SMTP side.
    assert len(_FakeSMTP.instances) == 1
    fake_smtp = _FakeSMTP.instances[0]
    assert fake_smtp.login_calls == [("bot@example.test", "smtp-app-password")]
    assert len(fake_smtp.sent) == 1
    reply = fake_smtp.sent[0]
    assert reply["From"] == "bot@example.test"
    assert reply["To"] == "sender@example.test"
    assert reply["Subject"] == "Re: weather?"
    assert reply.get_content().strip() == "the weather is sunny"
    assert ctx.registry.get("email").last_activity_at is not None


# -- reply header correctness (MAIL-02) --------------------------------------


def test_reply_threading_headers_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    monkeypatch.setattr(email_adapter_module, "run_agent", _fake_run_agent("ok"))
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message(
        subject="weather?",
        message_id="<original-99@example.test>",
        references="<thread-root@example.test>",
    )

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"7"]
        fake.messages = {b"7": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    reply = _FakeSMTP.instances[0].sent[0]
    assert reply["In-Reply-To"] == "<original-99@example.test>"
    refs = reply["References"]
    assert "<thread-root@example.test>" in refs
    assert "<original-99@example.test>" in refs
    # Fresh Message-ID assigned to the reply.
    assert reply["Message-ID"] != "<original-99@example.test>"
    assert reply["Date"]


def test_reply_subject_no_double_re_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    monkeypatch.setattr(email_adapter_module, "run_agent", _fake_run_agent("ok"))
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message(subject="Re: weather?")

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    reply = _FakeSMTP.instances[0].sent[0]
    # Subject must not be `Re: Re: weather?`.
    assert reply["Subject"] == "Re: weather?"


def test_reply_uses_reply_to_over_from(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    monkeypatch.setattr(email_adapter_module, "run_agent", _fake_run_agent("ok"))
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message(
        from_addr="sender@example.test",
        reply_to="reply-here@example.test",
    )

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    reply = _FakeSMTP.instances[0].sent[0]
    assert "reply-here@example.test" in reply["To"]


# -- body parsing -------------------------------------------------------------


def test_quoted_reply_stripping_before_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch)
    fake_run = _fake_run_agent("ok")
    monkeypatch.setattr(email_adapter_module, "run_agent", fake_run)
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    body = (
        "Yes please give me the forecast.\n"
        "\n"
        "On 2026-01-01, foo@bar.example wrote:\n"
        "> previous text from the bot\n"
        "> more previous text\n"
    )
    raw = _raw_message(body=body)

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    forwarded = fake_run.call_args.args[0]
    assert "Yes please give me the forecast." in forwarded
    assert "previous text from the bot" not in forwarded
    assert "On 2026-01-01" not in forwarded


def test_extract_plain_text_prefers_text_plain(tmp_path: Path) -> None:
    # Build a multipart message: text/html and text/plain alternates.
    msg = EmailMessage()
    msg["From"] = "a@example.test"
    msg["To"] = "b@example.test"
    msg["Subject"] = "alts"
    msg.set_content("plain body wins")
    msg.add_alternative("<p>html body loses</p>", subtype="html")
    extracted = email_adapter_module._extract_plain_text(msg)
    assert "plain body wins" in extracted
    assert "html body loses" not in extracted


# -- filters ------------------------------------------------------------------


def test_skip_own_messages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    fake_run = _fake_run_agent("ok")
    monkeypatch.setattr(email_adapter_module, "run_agent", fake_run)
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message(from_addr="bot@example.test")  # matches SMTP user

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    # Agent never called.
    assert fake_run.call_count == 0
    # SMTP never engaged.
    assert _FakeSMTP.instances == []
    # But the message IS marked seen so we do not reprocess it.
    fake_imap = _FakeIMAP.instances[0]
    assert fake_imap.store_calls == [(b"1", "+FLAGS", "(\\Seen)")]


def test_skip_autoresponders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    fake_run = _fake_run_agent("ok")
    monkeypatch.setattr(email_adapter_module, "run_agent", fake_run)
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message(auto_submitted="auto-replied")

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    assert fake_run.call_count == 0
    assert _FakeSMTP.instances == []
    assert _FakeIMAP.instances[0].store_calls == [(b"1", "+FLAGS", "(\\Seen)")]


def test_skip_bulk_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    fake_run = _fake_run_agent("ok")
    monkeypatch.setattr(email_adapter_module, "run_agent", fake_run)
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message(precedence="bulk")

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    assert fake_run.call_count == 0
    assert _FakeSMTP.instances == []


# -- profile routing ----------------------------------------------------------


def test_profile_routing_uses_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    monkeypatch.setenv("HORUS_OS_EMAIL_AGENT_PROFILE", "scribe")
    fake_run = _fake_run_agent("ok")
    monkeypatch.setattr(email_adapter_module, "run_agent", fake_run)
    adapter, ctx = _build_adapter_with_config(tmp_path)

    # Seed a `scribe` profile.
    db = Database(ctx.config.db_path)
    from horus_os.types import AgentProfile

    db.save_profile(
        AgentProfile(
            name="scribe",
            system_prompt="you are scribe",
            default_model="claude-test",
        )
    )

    raw = _raw_message(body="please write a note")

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    kwargs = fake_run.call_args.kwargs
    assert kwargs["system_prompt"] == "you are scribe"
    assert kwargs["model"] == "claude-test"


# -- idle sleep ---------------------------------------------------------------


def test_idle_sleep_when_no_messages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fakes(monkeypatch)
    fake_run = _fake_run_agent("ok")
    monkeypatch.setattr(email_adapter_module, "run_agent", fake_run)
    adapter, _ctx = _build_adapter_with_config(tmp_path)

    # Empty search result.
    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = []
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    # Must not raise; agent not called; SMTP not engaged.
    adapter._poll_once()
    assert fake_run.call_count == 0
    assert _FakeSMTP.instances == []
    # IMAP was logged out cleanly.
    assert _FakeIMAP.instances[0].logout_calls == 1


async def test_poll_loop_sleeps_configured_interval_between_polls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_all_required(monkeypatch)
    monkeypatch.setenv("HORUS_OS_EMAIL_POLL_INTERVAL", "999")  # large so we never get there
    _install_fakes(monkeypatch)

    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep

    async def recording_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        # Yield to the loop without actually waiting.
        await original_sleep(0)

    monkeypatch.setattr(email_adapter_module.asyncio, "sleep", recording_sleep)

    call_count = {"n": 0}

    def fake_poll_once(self: EmailAdapter) -> None:
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(email_adapter_module.EmailAdapter, "_poll_once", fake_poll_once)

    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    # Let the loop run.
    try:
        await asyncio.wait_for(adapter._task, timeout=2.0)
    except (asyncio.CancelledError, TimeoutError):
        pass
    # The configured interval (999) appears among the sleep arguments.
    assert 999 in sleep_calls


# -- poison message -----------------------------------------------------------


def test_run_agent_failure_marks_seen_and_logs_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch)

    def boom(*args: Any, **kwargs: Any) -> AgentResult:
        raise RuntimeError("provider down")

    monkeypatch.setattr(email_adapter_module, "run_agent", boom)
    adapter, ctx = _build_adapter_with_config(tmp_path)

    raw = _raw_message()

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)

    adapter._poll_once()

    # SMTP never engaged.
    assert _FakeSMTP.instances == []
    # Message marked seen anyway so we do not reprocess the crash.
    assert _FakeIMAP.instances[0].store_calls == [(b"1", "+FLAGS", "(\\Seen)")]
    # Error recorded.
    entry = ctx.registry.get("email")
    assert entry.error_count >= 1
    assert "RuntimeError" in (entry.error_message or "")


# -- connection backoff -------------------------------------------------------


async def test_connection_failure_triggers_backoff_then_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_all_required(monkeypatch)
    _install_fakes(monkeypatch)

    attempt = {"n": 0}

    def setup_imap(host: str, port: int) -> _FakeIMAP:
        attempt["n"] += 1
        if attempt["n"] == 1:
            raise OSError("first connect fails")
        fake = _FakeIMAP(host, port)
        fake.search_uids = []
        return fake

    monkeypatch.setattr(email_adapter_module.imaplib, "IMAP4_SSL", setup_imap)
    monkeypatch.setattr(email_adapter_module, "run_agent", _fake_run_agent("ok"))

    sleeps: list[float] = []
    original_sleep = asyncio.sleep

    async def recording_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        # On the second sleep, cancel the loop to end the test.
        if len(sleeps) >= 2:
            raise asyncio.CancelledError()
        await original_sleep(0)

    monkeypatch.setattr(email_adapter_module.asyncio, "sleep", recording_sleep)

    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.wait_for(adapter._task, timeout=2.0)
    except (asyncio.CancelledError, TimeoutError):
        pass

    # First call raised, second succeeded.
    assert attempt["n"] >= 2
    entry = ctx.registry.get("email")
    # The first failure was recorded.
    assert entry.error_count >= 1
    assert "OSError" in (entry.error_message or "")


# -- stop ---------------------------------------------------------------------


async def test_stop_cancels_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _set_all_required(monkeypatch)
    _install_fakes(monkeypatch)
    monkeypatch.setattr(email_adapter_module.EmailAdapter, "_poll_once", lambda self: None)
    ctx = _make_context(tmp_path)
    adapter = EmailAdapter()
    await adapter.start(ctx)
    task = adapter._task
    assert task is not None
    await adapter.stop()
    assert task.cancelled() or task.done()


async def test_stop_is_noop_when_start_never_ran() -> None:
    adapter = EmailAdapter()
    await adapter.stop()  # Must not raise.


# -- helper unit tests --------------------------------------------------------


def test_strip_quoted_reply_helpers() -> None:
    strip = email_adapter_module._strip_quoted_reply
    assert strip("hello") == "hello"
    assert strip("hello\nOn 2026-01-01, foo wrote:\n> q") == "hello"
    assert strip("hello\n> quoted\n> more") == "hello"
    # Outlook-style citation.
    assert strip("hello\nFrom: someone@example.test\nSubject: prior") == "hello"
    # Nothing left after strip is empty string.
    assert strip("> only quoted") == ""


def test_should_process_filter() -> None:
    should = email_adapter_module._should_process

    msg = EmailMessage()
    msg["From"] = "sender@example.test"
    assert should(msg, "bot@example.test") is True

    own = EmailMessage()
    own["From"] = "bot@example.test"
    assert should(own, "bot@example.test") is False

    auto = EmailMessage()
    auto["From"] = "vacation@example.test"
    auto["Auto-Submitted"] = "auto-generated"
    assert should(auto, "bot@example.test") is False

    bulk = EmailMessage()
    bulk["From"] = "list@example.test"
    bulk["Precedence"] = "bulk"
    assert should(bulk, "bot@example.test") is False
