# Email adapter

The Email adapter connects horus-os to an IMAP inbox. It polls
the inbox on a configurable interval, runs the configured agent
on each new unread message, and replies via SMTP with proper
RFC 5322 threading headers so the reply lands in the right
thread in the recipient's mail client.

The adapter uses only Python stdlib (`imaplib`, `smtplib`,
`email.*`). There is no optional extra to install; the
adapter ships with horus-os out of the box. Whether it runs
depends entirely on whether you set the env vars below.

## 1. Required environment variables

The minimum configuration is four IMAP variables plus one SMTP
variable:

| Env var | Required | Default | Purpose |
|---------|----------|---------|---------|
| `HORUS_OS_EMAIL_IMAP_HOST` | yes | -- | IMAP server hostname |
| `HORUS_OS_EMAIL_IMAP_PORT` | no | `993` | IMAP SSL port |
| `HORUS_OS_EMAIL_IMAP_USER` | yes | -- | IMAP login user |
| `HORUS_OS_EMAIL_IMAP_PASSWORD` | yes | -- | App password (see below) |
| `HORUS_OS_EMAIL_SMTP_HOST` | yes | -- | SMTP server hostname |
| `HORUS_OS_EMAIL_SMTP_PORT` | no | `465` | SMTP SSL port |
| `HORUS_OS_EMAIL_SMTP_USER` | no | IMAP user | SMTP login (if different) |
| `HORUS_OS_EMAIL_SMTP_PASSWORD` | no | IMAP password | SMTP password (if different) |
| `HORUS_OS_EMAIL_POLL_INTERVAL` | no | `60` | Seconds between polls |
| `HORUS_OS_EMAIL_AGENT_PROFILE` | no | `default` | Agent profile name |

If any required variable is missing the adapter records a clear
error in the registry and stays offline. Other adapters keep
running.

## 2. Provider quick-start

Most consumer email providers no longer accept your main
account password over IMAP / SMTP. You need an
application-specific password (app password) tied to the
account. The steps below cover Gmail, iCloud, and Fastmail; the
pattern is the same for most others.

### Gmail

1. Sign in to your Google account and open
   https://myaccount.google.com/security
2. Confirm 2-Step Verification is enabled (app passwords
   require it)
3. Open https://myaccount.google.com/apppasswords
4. Pick "Mail" as the app and any device name (for example,
   "horus-os")
5. Copy the 16-character password Google generates. Treat it
   like a password; you cannot view it again
6. Set the env vars:

```
HORUS_OS_EMAIL_IMAP_HOST=imap.gmail.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-bot-inbox@gmail.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.gmail.com
HORUS_OS_EMAIL_SMTP_PORT=465
```

7. In Gmail settings, enable IMAP under "Forwarding and POP/IMAP"
   so the server actually serves IMAP requests

### iCloud

1. Sign in to https://appleid.apple.com/
2. Under "Sign-In and Security" pick "App-Specific Passwords"
3. Generate a password named "horus-os" and copy it
4. Set the env vars:

```
HORUS_OS_EMAIL_IMAP_HOST=imap.mail.me.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-handle@icloud.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.mail.me.com
HORUS_OS_EMAIL_SMTP_PORT=587
```

iCloud's SMTP listener uses STARTTLS on port 587, not SSL on
465. The adapter currently supports SMTP_SSL only; iCloud
support is therefore best-effort. If your provider requires
STARTTLS, file an issue.

### Fastmail

1. Sign in to https://app.fastmail.com/
2. Open Settings then Password & Security then App Passwords
3. Click "New app password", grant it "IMAP" and "SMTP" access,
   and name it "horus-os"
4. Copy the password
5. Set the env vars:

```
HORUS_OS_EMAIL_IMAP_HOST=imap.fastmail.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-handle@fastmail.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.fastmail.com
HORUS_OS_EMAIL_SMTP_PORT=465
```

## 3. Sample .env block

```
HORUS_OS_EMAIL_IMAP_HOST=imap.gmail.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-bot-inbox@gmail.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.gmail.com
HORUS_OS_EMAIL_SMTP_PORT=465
HORUS_OS_EMAIL_POLL_INTERVAL=60
HORUS_OS_EMAIL_AGENT_PROFILE=default
```

Never commit a real `.env`. Add it to `.gitignore`.

## 4. Security caveats

- Use a dedicated bot inbox where possible. The adapter replies
  to every well-formed inbound message; running it against your
  personal inbox is noisy and risky
- App passwords are typically full-mailbox-scoped. A leaked Gmail
  app password lets an attacker read every message in the
  account. Rotate on leak
- Never paste an app password into a chat, a screenshot, or a
  pull request. Treat it like a regular password
- The adapter calls `run_agent(..., tools=None)`; the agent runs
  with only the capabilities of its profile. Per-channel tool
  gating is not currently supported

## 5. Run and verify

Once the env vars are set, start the server:

```
horus-os serve
```

Visit `/api/adapters` on the local dashboard. The `email`
entry should show `status: running`. Send a test message to
the bot inbox from another account. Within `poll_interval`
seconds the bot will reply, threaded under the original
subject.

## 6. Troubleshooting

- "IMAP not enabled" or login refused with no message: the
  provider's IMAP service is off. Enable IMAP in the provider's
  webmail settings (Gmail in particular ships with IMAP off by
  default on new accounts)
- "Less secure app" or "password rejected": you used your main
  account password instead of an app password. Mint an app
  password per the steps above
- Auth fails immediately: double-check `HOST` and `PORT`. Gmail
  IMAP is `imap.gmail.com:993`, SMTP is `smtp.gmail.com:465`.
  iCloud, Fastmail, and others differ
- Reply lands in a new thread instead of the original: the
  inbound message did not carry a `Message-ID` header. Mainstream
  providers always stamp one; if you are seeing this, the
  inbound likely came from a misconfigured custom server. Not a
  bug in the adapter
- Bot replies to its own reply (loop): the self-filter
  compares `From` against `HORUS_OS_EMAIL_SMTP_USER`. Confirm
  the bot's `From` matches that env var exactly
- Polling too aggressive (rate limits): raise
  `HORUS_OS_EMAIL_POLL_INTERVAL`. Gmail tolerates 60 seconds
  fine; some providers prefer 300 seconds or higher
