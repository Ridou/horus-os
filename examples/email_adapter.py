"""Email adapter example: one `_poll_once` against a fake IMAP and SMTP.

This example shows how to:

1. Replace `imaplib.IMAP4_SSL` and `smtplib.SMTP_SSL` on the adapter
   module with `_FakeIMAP` / `_FakeSMTP` stand-ins. The same shape
   the adapter tests use.
2. Set the required `HORUS_OS_EMAIL_*` env vars to placeholder values
   so `start` resolves a valid `EmailConfig` without any real account.
3. Drive one `_poll_once()` iteration directly (not the loop) so the
   example does not sleep or spawn a background task.
4. Show what IMAP saw (search, fetch, store), what the agent received,
   and what the SMTP reply looks like, including `In-Reply-To` and
   `References` so the RFC 5322 threading proof is visible.

The script runs end to end with no real IMAP or SMTP account, no
network, and uses only stdlib modules. The Email adapter never needed
an optional extra; v0.3 keeps it stdlib-only. `run_agent` is
monkeypatched at the adapter module level to return a canned reply.

For a live run set:

    HORUS_OS_EMAIL_IMAP_HOST=imap.example.com
    HORUS_OS_EMAIL_IMAP_PORT=993                       # optional, default 993
    HORUS_OS_EMAIL_IMAP_USER=bot@example.com
    HORUS_OS_EMAIL_IMAP_PASSWORD=your-imap-password-here
    HORUS_OS_EMAIL_SMTP_HOST=smtp.example.com
    HORUS_OS_EMAIL_SMTP_PORT=465                       # optional, default 465
    HORUS_OS_EMAIL_SMTP_USER=bot@example.com           # optional, defaults to IMAP user
    HORUS_OS_EMAIL_SMTP_PASSWORD=your-smtp-password-here  # optional, defaults to IMAP pwd
    HORUS_OS_EMAIL_POLL_INTERVAL=60                    # optional, default 60s
    HORUS_OS_EMAIL_AGENT_PROFILE=default               # optional

then `horus-os serve`. No pip extra is needed. See
`docs/adapters/EMAIL.md` for the full setup walkthrough.

Run it:

    python examples/email_adapter.py
"""

from __future__ import annotations

import os
import tempfile
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from horus_os import (
    AdapterContext,
    AdapterRegistry,
    Config,
    Database,
)
from horus_os.adapters import EmailAdapter
from horus_os.adapters import email_adapter as email_adapter_module
from horus_os.types import AgentResult


class _FakeIMAP:
    """Stand-in for `imaplib.IMAP4_SSL`. Records every call."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.login_calls: list[tuple[str, str]] = []
        self.select_calls: list[str] = []
        self.search_calls: list[tuple[Any, ...]] = []
        self.fetch_calls: list[tuple[bytes, str]] = []
        self.store_calls: list[tuple[bytes, str, str]] = []
        self.logout_calls = 0
        # Configurable per-test via class-level state.
        self.search_uids: list[bytes] = []
        self.messages: dict[bytes, bytes] = {}

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
    """Stand-in for `smtplib.SMTP_SSL`. Records every `send_message`."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.login_calls: list[tuple[str, str]] = []
        self.sent: list[EmailMessage] = []
        self.quit_calls = 0

    def login(self, user: str, password: str) -> None:
        self.login_calls.append((user, password))

    def send_message(self, msg: EmailMessage) -> None:
        self.sent.append(msg)

    def quit(self) -> None:
        self.quit_calls += 1


def _stub_run_agent() -> None:
    def fake_run_agent(prompt: str, **kwargs: Any) -> AgentResult:
        return AgentResult(
            text=f"[stub agent] you asked: {prompt!r}",
            provider="stub",
            model="stub-model",
            usage={"input_tokens": 0, "output_tokens": 0},
        )

    email_adapter_module.run_agent = fake_run_agent


def _build_unread_message() -> bytes:
    msg = EmailMessage()
    msg["From"] = "sender@example.test"
    msg["To"] = "bot@example.test"
    msg["Subject"] = "weather?"
    msg["Message-ID"] = "<original-1@example.test>"
    msg.set_content("Hi bot, what is the weather today?")
    return msg.as_bytes()


def main() -> None:
    _stub_run_agent()

    # Required env vars; placeholders are fine offline.
    os.environ["HORUS_OS_EMAIL_IMAP_HOST"] = "imap.example.test"
    os.environ["HORUS_OS_EMAIL_IMAP_USER"] = "bot@example.test"
    os.environ["HORUS_OS_EMAIL_IMAP_PASSWORD"] = "your-imap-password-here"
    os.environ["HORUS_OS_EMAIL_SMTP_HOST"] = "smtp.example.test"

    # Track every fake instance so we can inspect them after `_poll_once`.
    imap_instances: list[_FakeIMAP] = []
    smtp_instances: list[_FakeSMTP] = []

    raw = _build_unread_message()

    def _make_imap(host: str, port: int) -> _FakeIMAP:
        fake = _FakeIMAP(host, port)
        fake.search_uids = [b"1"]
        fake.messages = {b"1": raw}
        imap_instances.append(fake)
        return fake

    def _make_smtp(host: str, port: int) -> _FakeSMTP:
        fake = _FakeSMTP(host, port)
        smtp_instances.append(fake)
        return fake

    # Direct setattr is the same pattern the adapter tests use through
    # `monkeypatch.setattr`; we just apply it inline here.
    email_adapter_module.imaplib.IMAP4_SSL = _make_imap
    email_adapter_module.smtplib.SMTP_SSL = _make_smtp

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        config = Config.with_defaults(data_dir)
        config.save()
        Database(config.db_path).init()

        registry = AdapterRegistry()
        registry.register("email")
        ctx = AdapterContext(config=config, data_dir=data_dir, registry=registry)

        adapter = EmailAdapter()
        # Resolve the EmailConfig from the env vars above without
        # actually spinning up the poll loop background task.
        adapter._context = ctx
        adapter._email_config = email_adapter_module._load_email_config_from_env()

        adapter._poll_once()

        imap = imap_instances[0]
        smtp = smtp_instances[0]
        reply = smtp.sent[0]

        print("IMAP calls captured:")
        print(f"  login   {imap.login_calls}")
        print(f"  select  {imap.select_calls}")
        print(f"  search  {imap.search_calls}")
        print(f"  fetch   {imap.fetch_calls}")
        print(f"  store   {imap.store_calls}")
        print(f"  logout  {imap.logout_calls}")
        print()
        print("SMTP reply captured:")
        print(f"  From:           {reply['From']}")
        print(f"  To:             {reply['To']}")
        print(f"  Subject:        {reply['Subject']}")
        print(f"  In-Reply-To:    {reply['In-Reply-To']}")
        print(f"  References:     {reply['References']}")
        print(f"  Message-ID:     {reply['Message-ID']}")
        print(f"  Body:           {reply.get_content().strip()!r}")
        print()
        entry = registry.get("email")
        print(f"Registry entry: status={entry.status} last_activity_at={entry.last_activity_at}")


if __name__ == "__main__":
    main()
