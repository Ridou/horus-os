"""Email adapter for horus-os.

Polls an IMAP inbox on a configurable interval, runs the
configured agent on each new unread message, and replies via
SMTP with proper RFC 5322 threading headers so the reply lands
in the right thread in the recipient's mail client.

The adapter uses only stdlib `imaplib`, `smtplib`, and `email.*`
modules. No new pip extras. Because those libraries are
synchronous, every blocking IMAP / SMTP call is wrapped in
`asyncio.to_thread` from the poll loop so the FastAPI event
loop is never starved.

Configuration via environment variables:

- `HORUS_OS_EMAIL_IMAP_HOST`: IMAP server. Required.
- `HORUS_OS_EMAIL_IMAP_PORT`: IMAP SSL port. Default 993.
- `HORUS_OS_EMAIL_IMAP_USER`: IMAP login user. Required.
- `HORUS_OS_EMAIL_IMAP_PASSWORD`: IMAP password / app password.
  Required.
- `HORUS_OS_EMAIL_SMTP_HOST`: SMTP server. Required.
- `HORUS_OS_EMAIL_SMTP_PORT`: SMTP SSL port. Default 465.
- `HORUS_OS_EMAIL_SMTP_USER`: SMTP login. Defaults to the IMAP user.
- `HORUS_OS_EMAIL_SMTP_PASSWORD`: SMTP password. Defaults to the
  IMAP password.
- `HORUS_OS_EMAIL_POLL_INTERVAL`: seconds between polls. Default 60.
- `HORUS_OS_EMAIL_AGENT_PROFILE`: agent profile name. Default
  "default". Missing profile is non-fatal.

The adapter satisfies the `Adapter` Protocol (name, bind) and
the `LifecycleAdapter` Protocol (async start, async stop). It is
declared as an entry point in pyproject under
`[project.entry-points."horus_os.adapters"]`.
"""

from __future__ import annotations

import asyncio
import contextlib
import email.policy
import imaplib
import os
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, make_msgid, parseaddr
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.agent import run_agent
from horus_os.config import Config
from horus_os.storage import Database

IMAP_HOST_ENV = "HORUS_OS_EMAIL_IMAP_HOST"
IMAP_PORT_ENV = "HORUS_OS_EMAIL_IMAP_PORT"
IMAP_USER_ENV = "HORUS_OS_EMAIL_IMAP_USER"
IMAP_PASSWORD_ENV = "HORUS_OS_EMAIL_IMAP_PASSWORD"
SMTP_HOST_ENV = "HORUS_OS_EMAIL_SMTP_HOST"
SMTP_PORT_ENV = "HORUS_OS_EMAIL_SMTP_PORT"
SMTP_USER_ENV = "HORUS_OS_EMAIL_SMTP_USER"
SMTP_PASSWORD_ENV = "HORUS_OS_EMAIL_SMTP_PASSWORD"
POLL_INTERVAL_ENV = "HORUS_OS_EMAIL_POLL_INTERVAL"
AGENT_ENV = "HORUS_OS_EMAIL_AGENT_PROFILE"

DEFAULT_IMAP_PORT = 993
DEFAULT_SMTP_PORT = 465
DEFAULT_POLL_INTERVAL = 60
DEFAULT_AGENT = "default"
MAX_BACKOFF_SECONDS = 300

# Lines that mark the start of a quoted prior message.
_QUOTE_PATTERNS = [
    re.compile(r"^On .+ wrote:\s*$", re.MULTILINE),
    re.compile(r"^Le .+ a ecrit\s*:\s*$", re.MULTILINE),
    re.compile(r"^From:.+$", re.MULTILINE),
]


@dataclass(frozen=True)
class EmailConfig:
    """Snapshot of resolved email config read from env vars."""

    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    poll_interval: int


class _MissingEnvError(Exception):
    """Raised by `_load_email_config_from_env` when a required var is missing."""


def _load_email_config_from_env() -> EmailConfig:
    """Read and validate the email configuration from environment variables."""
    imap_host = os.environ.get(IMAP_HOST_ENV)
    if not imap_host:
        raise _MissingEnvError(f"{IMAP_HOST_ENV} is not set")
    imap_user = os.environ.get(IMAP_USER_ENV)
    if not imap_user:
        raise _MissingEnvError(f"{IMAP_USER_ENV} is not set")
    imap_password = os.environ.get(IMAP_PASSWORD_ENV)
    if not imap_password:
        raise _MissingEnvError(f"{IMAP_PASSWORD_ENV} is not set")
    smtp_host = os.environ.get(SMTP_HOST_ENV)
    if not smtp_host:
        raise _MissingEnvError(f"{SMTP_HOST_ENV} is not set")

    imap_port_str = os.environ.get(IMAP_PORT_ENV)
    imap_port = int(imap_port_str) if imap_port_str else DEFAULT_IMAP_PORT
    smtp_port_str = os.environ.get(SMTP_PORT_ENV)
    smtp_port = int(smtp_port_str) if smtp_port_str else DEFAULT_SMTP_PORT
    poll_str = os.environ.get(POLL_INTERVAL_ENV)
    poll_interval = int(poll_str) if poll_str else DEFAULT_POLL_INTERVAL

    smtp_user = os.environ.get(SMTP_USER_ENV) or imap_user
    smtp_password = os.environ.get(SMTP_PASSWORD_ENV) or imap_password

    return EmailConfig(
        imap_host=imap_host,
        imap_port=imap_port,
        imap_user=imap_user,
        imap_password=imap_password,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        poll_interval=poll_interval,
    )


class EmailAdapter:
    """An inbound email adapter: IMAP poll, SMTP reply, threaded headers."""

    name = "email"

    def __init__(self) -> None:
        # Connection state is allocated in `start` so the
        # constructor stays cheap and import-clean.
        self._task: asyncio.Task[Any] | None = None
        self._context: AdapterContext | None = None
        self._email_config: EmailConfig | None = None
        self._poll_interval: int = DEFAULT_POLL_INTERVAL

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": 1,
            "transport": "imap-poll",
            "reply_transport": "smtp",
            "auth": "password",
        }

    def bind(self, app: Any, context: AdapterContext) -> None:
        # Email uses IMAP / SMTP, not HTTP routes on FastAPI.
        return None

    async def start(self, context: AdapterContext) -> None:
        """Spawn the IMAP poll loop in a background task.

        Missing env vars flip the registry entry to `error` with a
        clear message and return without raising so the FastAPI
        lifespan can isolate this adapter from siblings.
        """
        self._context = context
        try:
            email_config = _load_email_config_from_env()
        except _MissingEnvError as exc:
            context.registry.mark_error(self.name, str(exc))
            return
        self._email_config = email_config
        self._poll_interval = email_config.poll_interval
        self._task = asyncio.create_task(self._poll_loop())
        context.registry.mark_running(self.name)

    async def stop(self) -> None:
        """Cancel the poll task. No-op when start never ran."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task

    async def _poll_loop(self) -> None:
        """Run `_poll_once` on a schedule with exponential backoff on failure."""
        backoff = self._poll_interval
        while True:
            try:
                await asyncio.to_thread(self._poll_once)
                backoff = self._poll_interval
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._context is not None:
                    self._context.registry.mark_error(self.name, f"{type(exc).__name__}: {exc}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                continue
            await asyncio.sleep(self._poll_interval)

    def _poll_once(self) -> None:
        """One synchronous poll cycle. Runs inside `asyncio.to_thread`."""
        if self._email_config is None:
            return
        cfg = self._email_config
        imap = imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port)
        try:
            imap.login(cfg.imap_user, cfg.imap_password)
            imap.select("INBOX")
            status, data = imap.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return
            uids = data[0].split()
            for uid in uids:
                self._process_one(imap, uid)
        finally:
            with contextlib.suppress(Exception):
                imap.logout()

    def _process_one(self, imap: Any, uid: bytes) -> None:
        """Fetch one message, dispatch to the agent, send reply, mark seen."""
        status, fetched = imap.fetch(uid, "(BODY.PEEK[])")
        if status != "OK" or not fetched:
            return
        raw = _extract_raw_bytes(fetched)
        if not raw:
            self._mark_seen(imap, uid)
            return
        parser = BytesParser(policy=email.policy.default)
        message = parser.parsebytes(raw)
        if not _should_process(message, self._email_config.smtp_user):
            self._mark_seen(imap, uid)
            return
        body = _extract_plain_text(message)
        prompt = _strip_quoted_reply(body)
        if not prompt.strip():
            self._mark_seen(imap, uid)
            return

        try:
            response = self._dispatch(prompt)
        except Exception as exc:
            # Poison-message safety: mark seen even on agent failure
            # so the loop does not reprocess the same crash forever.
            self._mark_seen(imap, uid)
            if self._context is not None:
                self._context.registry.mark_error(self.name, f"{type(exc).__name__}: {exc}")
            return

        reply = _build_reply(message, response, self._email_config.smtp_user)
        self._send_reply(reply)
        self._mark_seen(imap, uid)
        if self._context is not None:
            self._context.registry.touch(self.name)

    def _mark_seen(self, imap: Any, uid: bytes) -> None:
        with contextlib.suppress(Exception):
            imap.store(uid, "+FLAGS", "(\\Seen)")

    def _send_reply(self, reply: EmailMessage) -> None:
        cfg = self._email_config
        if cfg is None:
            return
        smtp = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port)
        try:
            smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(reply)
        finally:
            with contextlib.suppress(Exception):
                smtp.quit()

    def _dispatch(self, prompt: str) -> str:
        """Run one synchronous agent turn against the configured profile."""
        if self._context is None:
            raise RuntimeError("EmailAdapter._dispatch called before start")
        cfg = self._context.config
        profile_name = os.environ.get(AGENT_ENV, DEFAULT_AGENT)
        profile = None
        if cfg.db_path.exists():
            db = Database(cfg.db_path)
            profile = db.load_profile(profile_name)
        provider = cfg.default_provider
        model = (profile.default_model if profile else None) or _default_model(cfg, provider)
        system_prompt = profile.system_prompt if profile else None
        result = run_agent(
            prompt,
            provider=provider,
            tools=None,
            model=model,
            system_prompt=system_prompt,
        )
        return result.text or "(no response)"


def _extract_raw_bytes(fetched: Any) -> bytes:
    """Pull the raw RFC 822 bytes out of an imaplib FETCH response.

    `imaplib.IMAP4.fetch` returns a list whose elements are either
    tuples `(envelope_bytes, body_bytes)` for a real body or a
    closing parenthesis bytes object. We want the first tuple's
    second element.
    """
    for part in fetched:
        if isinstance(part, tuple) and len(part) >= 2:
            payload = part[1]
            if isinstance(payload, bytes | bytearray):
                return bytes(payload)
    return b""


def _should_process(message: EmailMessage, smtp_user: str) -> bool:
    """Filter out our own messages, autoresponders, and bulk mail."""
    from_header = message.get("From", "")
    _, from_addr = parseaddr(from_header)
    if from_addr and smtp_user and from_addr.lower() == smtp_user.lower():
        return False
    auto = (message.get("Auto-Submitted") or "").strip().lower()
    if auto and auto != "no":
        return False
    precedence = (message.get("Precedence") or "").strip().lower()
    if precedence in {"bulk", "list", "junk"}:
        return False
    return True


def _extract_plain_text(message: EmailMessage) -> str:
    """Return the message body, preferring `text/plain` parts."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not _is_attachment(part):
                payload = part.get_content()
                if isinstance(payload, str):
                    return payload
        # Fallback: any text/* part.
        for part in message.walk():
            if part.get_content_maintype() == "text" and not _is_attachment(part):
                payload = part.get_content()
                if isinstance(payload, str):
                    return payload
        return ""
    payload = message.get_content()
    if isinstance(payload, str):
        return payload
    return ""


def _is_attachment(part: Any) -> bool:
    """Treat any part with an explicit `attachment` disposition as not-body."""
    disp = (part.get("Content-Disposition") or "").lower()
    return "attachment" in disp


def _strip_quoted_reply(text: str) -> str:
    """Truncate `text` at the earliest quoted-reply marker.

    The strip is conservative: when no marker is found the full
    body is returned unchanged. Trailing `>`-prefixed lines (RFC
    1849 quote style) are also dropped from the tail.
    """
    earliest = len(text)
    for pat in _QUOTE_PATTERNS:
        match = pat.search(text)
        if match and match.start() < earliest:
            earliest = match.start()
    out = text[:earliest]
    lines = out.splitlines()
    while lines and lines[-1].startswith(">"):
        lines.pop()
    return "\n".join(lines).strip()


def _build_reply(original: EmailMessage, response_text: str, from_addr: str) -> EmailMessage:
    """Construct an RFC 5322 reply with `In-Reply-To` and `References` set."""
    reply = EmailMessage()
    reply["From"] = from_addr
    recipient = original.get("Reply-To") or original.get("From", "")
    reply["To"] = recipient
    subject = original.get("Subject", "") or ""
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}".rstrip()
    reply["Subject"] = subject
    msg_id = original.get("Message-ID")
    if msg_id:
        reply["In-Reply-To"] = msg_id
        prior = original.get("References", "")
        refs = f"{prior} {msg_id}".strip() if prior else msg_id
        reply["References"] = refs
    reply["Message-ID"] = make_msgid()
    reply["Date"] = formatdate(localtime=False, usegmt=True)
    reply.set_content(response_text or "(no response)")
    return reply


def _default_model(cfg: Config, provider: str) -> str:
    if provider == "anthropic":
        return cfg.anthropic_model
    return cfg.gemini_model
