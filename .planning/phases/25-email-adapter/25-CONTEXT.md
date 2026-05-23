# Phase 25 Context: Email adapter

**Date:** 2026-05-24
**Phase:** 25
**Status:** Context captured

## Domain

Phase 25 ships the third v0.3 adapter and the second
long-running one (after Discord). EmailAdapter polls an IMAP
inbox on a configurable interval, runs the configured agent on
each new message, and replies via SMTP with proper RFC 5322
threading headers (`In-Reply-To`, `References`, `Re:` subject).

Like the Discord adapter, EmailAdapter implements both the
`Adapter` Protocol (with a no-op `bind`) and the
`LifecycleAdapter` Protocol. `start` spawns an
`asyncio.create_task(self._poll_loop())`; `stop` cancels it.

Unlike Discord, the underlying libraries (`imaplib`,
`smtplib`) are stdlib and synchronous. The adapter wraps each
blocking IMAP/SMTP call in `asyncio.to_thread` so the event
loop stays responsive. This keeps Phase 25 dependency-free.

## Canonical refs

- `.planning/ROADMAP.md` Phase 25 success criteria
- `.planning/REQUIREMENTS.md` MAIL-01, MAIL-02, MAIL-03
- `src/horus_os/adapters/base.py` LifecycleAdapter Protocol,
  AdapterRegistry
- `src/horus_os/adapters/discord_adapter.py` reference shape for
  background-task adapters (lazy import is the pattern, but
  the SDK here is stdlib so no `ImportError` branch is needed)
- `src/horus_os/agent.py` `run_agent` (sync)
- `src/horus_os/storage.py` `Database.load_profile`
- Python stdlib: `imaplib.IMAP4_SSL`, `smtplib.SMTP_SSL`,
  `email.message.EmailMessage`, `email.parser.BytesParser`,
  `email.utils.{parseaddr, formatdate, make_msgid}`

## Decisions

### 1. Stdlib only, no new dependencies

`imaplib`, `smtplib`, `email.message`, `email.parser`,
`email.utils` are all stdlib. No new pip extras, no optional
dependency group in pyproject.toml. The adapter ships
discoverable out of the box; whether it runs depends only on
whether the IMAP and SMTP env vars are set.

The tradeoff is a synchronous API. We mitigate by running every
blocking call inside `asyncio.to_thread(...)` from the poll
loop so the event loop is never starved.

### 2. Adapter shape

`EmailAdapter` implements `Adapter` + `LifecycleAdapter`.
`bind(app, ctx)` is a no-op (no HTTP routes). `start(ctx)` reads
env vars, validates required ones present, and spawns the
poll task. `stop()` cancels the task.

If required env vars are missing, `start` flips the registry
entry to `error` with a clear message and returns without
raising. Other adapters keep running. Same pattern as Phase 23.

### 3. Poll loop

```
async def _poll_loop(self):
    backoff = self._poll_interval
    while True:
        try:
            await asyncio.to_thread(self._poll_once)
            backoff = self._poll_interval
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._context.registry.mark_error(self.name, f"{type(exc).__name__}: {exc}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue
        await asyncio.sleep(self._poll_interval)
```

`_poll_once` is fully synchronous and does the IMAP connect,
login, fetch-unseen, dispatch, reply, logout. Errors inside
trigger exponential backoff capped at 5 minutes; recovery
resets the backoff to the configured interval.

### 4. Fetch and mark-seen ordering

The IMAP search uses `UNSEEN` to find new messages. We
deliberately fetch with `BODY.PEEK[]` so the fetch itself does
NOT flip the `\Seen` flag. We only flip `\Seen` via
`STORE +FLAGS (\Seen)` AFTER the agent has produced a reply
and SMTP has accepted it. That way a transient network or
agent failure leaves the message unread for the next poll.

The exception: if `run_agent` raises a non-transient error
(e.g., the agent always crashes on this specific message), the
adapter would loop forever. We document this tradeoff: errors
during `run_agent` are caught, the message is marked seen
anyway to prevent infinite reprocessing, and the error is
logged via `registry.mark_error`. SMTP send failures, by
contrast, leave the message unread for retry.

### 5. Reply threading (MAIL-02)

Per RFC 5322 / RFC 2822, a reply must set:

- `In-Reply-To: <original-message-id>`
- `References: <prior-references> <original-message-id>`
- `Subject: Re: <original-subject>` (no double-`Re:` if
  the original already starts with `Re:`)

The adapter reads the inbound `Message-ID` header (or
synthesizes one with `make_msgid` if absent, though every
real mail server stamps one), sets `In-Reply-To` to exactly
that value, and appends it to any existing `References`
header. The outgoing message gets a fresh `Message-ID` via
`make_msgid()`.

The recipient (`To`) is the original `From` address parsed
via `email.utils.parseaddr`. If the original had a
`Reply-To` header we honor that instead, per RFC convention.

### 6. Body parsing and quote stripping

The adapter walks the inbound message via
`email_message.walk()`, prefers the `text/plain` part, and
falls back to `text/html` stripped to text only if no plain
part exists. v0.3 ships `text/plain` only; HTML fallback is
deferred.

Before forwarding to `run_agent`, the body is run through
`_strip_quoted_reply()` which truncates at common
quoted-reply markers:

- A line matching `^On .+ wrote:$` (English Gmail style)
- A line matching `^Le .+ a ecrit\s*:` (French, common
  in European email)
- A line matching `^>From: .+` (Outlook reply citation)
- Lines starting with `>` (RFC 1849 quote prefix) trim the
  remainder

This prevents the agent from seeing its own prior reply
echoed back, which would otherwise inflate token costs and
confuse the agent. The strip is conservative: if no marker
is found, the full body is forwarded unchanged.

### 7. Sender and autoresponder filtering

`_should_process(message)` returns `False` when:

- `From` matches the configured SMTP user (no echo loop)
- `Auto-Submitted` header is `auto-replied`, `auto-generated`,
  or any value other than `no` (RFC 3834 autoresponder
  signal)
- `Precedence` header is `bulk`, `list`, or `junk` (legacy
  mailing-list / bulk-mail signal)

Skipped messages are still marked seen so they do not
accumulate in `UNSEEN` forever.

### 8. Configuration via env vars

| Env var | Purpose | Default |
|---------|---------|---------|
| `HORUS_OS_EMAIL_IMAP_HOST` | IMAP server | required |
| `HORUS_OS_EMAIL_IMAP_PORT` | IMAP SSL port | 993 |
| `HORUS_OS_EMAIL_IMAP_USER` | IMAP login user | required |
| `HORUS_OS_EMAIL_IMAP_PASSWORD` | IMAP password | required |
| `HORUS_OS_EMAIL_SMTP_HOST` | SMTP server | required |
| `HORUS_OS_EMAIL_SMTP_PORT` | SMTP SSL port | 465 |
| `HORUS_OS_EMAIL_SMTP_USER` | SMTP login user | IMAP user |
| `HORUS_OS_EMAIL_SMTP_PASSWORD` | SMTP password | IMAP password |
| `HORUS_OS_EMAIL_POLL_INTERVAL` | seconds between polls | 60 |
| `HORUS_OS_EMAIL_AGENT_PROFILE` | profile name | `default` |

The minimum config is the four IMAP vars plus SMTP host (and
optionally distinct SMTP creds for accounts that separate
inbound and outbound auth). The setup guide explains how to
mint an app-password for Gmail, iCloud, and Fastmail.

### 9. Test strategy

All tests offline. Mock `imaplib.IMAP4_SSL` and
`smtplib.SMTP_SSL` at the module level via monkeypatch. Tests
inject fakes that record calls (`login`, `select`, `search`,
`fetch`, `store`, `logout` for IMAP; `login`, `send_message`,
`quit` for SMTP) and return canned IMAP responses shaped like
the real ones (`(b"OK", [b"1 2 3"])` for SEARCH,
`(b"OK", [(b"1 (...)", raw_message_bytes), b")"])` for FETCH).

The poll loop is exercised by calling `_poll_once()` directly
where possible, with one test driving the full `start()`
+ task + cancellation lifecycle.

### 10. Entry point

```
[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
discord = "horus_os.adapters.discord_adapter:DiscordAdapter"
slack = "horus_os.adapters.slack_adapter:SlackAdapter"
email = "horus_os.adapters.email_adapter:EmailAdapter"
```

No new extras group. Stdlib only.

### 11. Module name: email_adapter.py

We cannot name the module `email.py` because that would shadow
the stdlib `email` package on the import path. `email_adapter.py`
matches the `discord_adapter.py` and `slack_adapter.py` naming.

## Execution split

Single plan: 25-01. Adapter, entry point, tests, and setup
guide land as a coherent unit; splitting would create awkward
intermediate states.

Atomic commits:

- `docs(25)`: plan + context
- `feat(25)`: EmailAdapter module + pyproject entry point
- `test(25)`: adapter tests with mocked imaplib + smtplib
- `docs(25)`: setup guide at `docs/adapters/EMAIL.md`
- `docs(25)`: phase summary

## Deferred / not in scope

- IMAP IDLE push (no polling). `imaplib` does not expose IDLE
  cleanly; full IDLE support needs a different library. v0.3
  polls; v0.4 can swap in IDLE behind the same interface.
- OAuth 2.0 (Gmail XOAUTH2, Microsoft modern auth). v0.3
  uses app-password / password auth only. OAuth is a v0.4
  enhancement.
- HTML responses. Replies are `text/plain` only.
- Attachments inbound and outbound. The agent sees text only;
  attachments on inbound messages are ignored.
- Multi-folder polling. Only `INBOX` is polled.
- Per-sender allowlist. v0.3 processes every unread message
  from any sender (minus autoresponders and self).
- Outbound notifications without an inbound trigger (the
  adapter as a sender). v0.3 is reply-only; v0.4 can add a
  send-only tool.
