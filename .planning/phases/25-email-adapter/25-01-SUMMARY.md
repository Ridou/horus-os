---
phase: 25-email-adapter
plan: "01"
subsystem: adapters
tags: [adapter, email, imap, smtp, lifecycle, stdlib-only]

requires:
  - phase: "22-01"
provides:
  - "EmailAdapter with IMAP poll loop, SMTP reply, RFC 5322 threading headers"
  - "stdlib-only implementation; no new pip dependencies"
  - "horus_os.adapters entry-point declaration for email"
  - "docs/adapters/EMAIL.md setup guide"

requirements-completed:
  - MAIL-01  # IMAP poll, mark seen after processing, run agent on body
  - MAIL-02  # In-Reply-To and References headers preserved on replies
  - MAIL-03  # Configurable poll interval, clean idle sleep

duration: ~50m
completed: 2026-05-24
total-tests: 406
delta-tests: +26
v0.3-progress: Phase 25 of 31 complete (third v0.3 adapter shipped)
---

# Phase 25 Plan 01 Summary: Email adapter

## What shipped

EmailAdapter polls an IMAP inbox on a configurable interval,
runs the configured agent on each new unread message, and
replies via SMTP with proper RFC 5322 threading headers so the
reply lands in the right thread. Stdlib only: `imaplib`,
`smtplib`, `email.message`, `email.parser`, `email.utils`. No
new pip extras.

### New module

`src/horus_os/adapters/email_adapter.py` defines `EmailAdapter`.
The class satisfies both the `Adapter` Protocol (name, no-op
`bind`) and the `LifecycleAdapter` Protocol (async `start`,
async `stop`).

| Surface | Behavior |
|---------|----------|
| `bind(app, context)` | No-op; email uses IMAP / SMTP, not HTTP routes |
| `start(context)` | Reads env vars via `_load_email_config_from_env()`. Missing required var flips registry to `error` and returns. Otherwise schedules `asyncio.create_task(self._poll_loop())` and marks registry `running` |
| `stop()` | Cancels the poll task. No-op when start never ran |
| `_poll_loop()` | Runs `_poll_once` in `asyncio.to_thread` every `poll_interval` seconds. Exponential backoff on failure, capped at 300s; resets on recovery |
| `_poll_once()` | Connects via `IMAP4_SSL`, logs in, selects `INBOX`, searches `UNSEEN`, fetches each with `BODY.PEEK[]` so the server does not auto-flip `\Seen`, parses, dispatches to `run_agent`, sends SMTP reply, then marks `\Seen` |
| `_should_process(msg, smtp_user)` | Filters out self-messages (From == SMTP user), autoresponders (`Auto-Submitted` not `no`), and bulk mail (`Precedence` in {bulk, list, junk}) |
| `_extract_plain_text(msg)` | Prefers `text/plain` parts, falls back to any `text/*` part; skips attachment-dispositioned parts |
| `_strip_quoted_reply(text)` | Truncates at the earliest of three quote markers (`On ... wrote:`, French `Le ... a ecrit:`, Outlook `From:` citation) and drops trailing `>`-prefixed lines |
| `_build_reply(original, response, from_addr)` | Builds an `EmailMessage` with `In-Reply-To: <original-message-id>`, `References` appending original Message-ID to any prior, `Subject: Re: <subject>` de-duplicated, fresh `Message-ID` via `make_msgid()`, `Date` via `formatdate(usegmt=True)`. `To` prefers `Reply-To` over `From` |
| `_dispatch(prompt)` | Loads `AgentProfile` by `HORUS_OS_EMAIL_AGENT_PROFILE` (defaults `default`); missing profile is non-fatal |

Errors during `run_agent` are caught: the message is marked
seen anyway so a single poison message does not loop forever,
the error is logged via `registry.mark_error`, and the poll
loop continues. SMTP send failures bubble up to the poll
loop's exception handler and the message stays unread for
retry.

### Entry point

`pyproject.toml` gains one line:

```
[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
discord = "horus_os.adapters.discord_adapter:DiscordAdapter"
slack = "horus_os.adapters.slack_adapter:SlackAdapter"
email = "horus_os.adapters.email_adapter:EmailAdapter"
```

No new optional-dependencies group, no change to the `all`
extras list.

### Setup guide

`docs/adapters/EMAIL.md` (173 lines) walks operators through:
required env vars, app-password creation on Gmail, iCloud, and
Fastmail (the three most common consumer providers), sample
`.env` block, security caveats (dedicated bot inbox, app-password
scope), verification steps, and a troubleshooting section
covering IMAP-disabled providers, less-secure-app errors, auth
failures, threading misses, self-loop edge cases, and rate
limits.

## Files touched

- `src/horus_os/adapters/email_adapter.py` (new, ~290 lines)
- `src/horus_os/adapters/__init__.py`: re-export `EmailAdapter`
- `pyproject.toml`: one new entry-point line
- `tests/test_adapters_email.py` (new, 26 tests)
- `docs/adapters/EMAIL.md` (new, 173 lines)

## Test surface

26 net new tests. All run with `imaplib.IMAP4_SSL` and
`smtplib.SMTP_SSL` replaced by fakes via
`monkeypatch.setattr(email_adapter_module.imaplib, ...)`.
`run_agent` is monkeypatched at the adapter module level so
no provider SDK is needed and no network call happens.

| Group | Tests |
|-------|-------|
| Construction | clean construct, no-op bind |
| Start errors | missing IMAP host, missing IMAP user, missing IMAP password, missing SMTP host |
| Start happy path | task scheduled and registry running, poll-interval env var honored |
| Poll happy path | fetches one UNSEEN message, run_agent called with stripped body, SMTP reply sent, `\Seen` flag stored, logout clean |
| Reply headers (MAIL-02) | In-Reply-To set, References appended, no double Re:, Reply-To preferred over From |
| Body parsing | quote stripping before run_agent, text/plain preferred over text/html |
| Filters | self-message skipped + marked seen, Auto-Submitted skipped + marked seen, Precedence: bulk skipped |
| Profile routing | env var picks seeded profile and forwards system_prompt + model |
| Idle sleep (MAIL-03) | empty UNSEEN search returns cleanly, loop sleeps configured interval |
| Poison message | run_agent exception caught, message marked seen anyway, mark_error recorded |
| Connection backoff | first IMAP connect raises, second succeeds, mark_error captures failure |
| Stop | task cancelled, no-op when start never ran |
| Helpers | _strip_quoted_reply patterns, _should_process filter matrix |

Full suite: 406 passed in 5.12s (380 baseline + 26 new). All
v0.2, Phase 22, Phase 23, and Phase 24 tests pass byte-identical.

## Lint status

`ruff check .` clean. `ruff format --check .` clean. Initial run
caught two RUF012 (mutable class default) and two UP041 (aliased
TimeoutError); fixed by switching to `ClassVar[list[...]]` for
the per-test instance trackers and replacing
`asyncio.TimeoutError` with builtin `TimeoutError`.

## Notable / deferred

- IMAP IDLE push is out of scope. stdlib `imaplib` does not
  expose IDLE cleanly; full IDLE support would need a different
  library. v0.3 polls; v0.4 can swap in IDLE behind the same
  interface
- OAuth 2.0 (Gmail XOAUTH2, Microsoft modern auth) is deferred.
  v0.3 uses app-password / password auth only. The setup guide
  walks operators through minting an app password on the three
  most common consumer providers
- STARTTLS (port 587) is not yet supported. Only SMTP_SSL on
  port 465. iCloud and some self-hosted servers need STARTTLS,
  which means the adapter is best-effort for those. v0.4 can
  add a SMTP_SSL / SMTP+STARTTLS switch via a config knob
- HTML responses are deferred. Replies are `text/plain` only.
  The adapter does extract `text/html` as a fallback if no
  `text/plain` part exists on the inbound, but it never produces
  HTML output
- Attachments inbound and outbound are out of scope. The agent
  sees text only; attachment parts on inbound messages are
  ignored. No attachment support on replies
- Multi-folder polling is out of scope. Only `INBOX` is polled
- Per-sender allowlist is out of scope. v0.3 processes every
  unread well-formed message (minus autoresponders, bulk mail,
  and self). A per-sender allowlist or denylist is a v0.4
  backlog item
- Outbound notifications without an inbound trigger (adapter as
  sender) are deferred. v0.3 is reply-only; v0.4 can add a
  send-only tool that exposes the SMTP path to agents
- Phase 26 (Calendar) can ship in parallel. It is the last v0.3
  adapter
