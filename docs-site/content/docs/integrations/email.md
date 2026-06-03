---
title: "Email"
description: "Connect horus-os to an IMAP inbox so your agent reads new mail and replies over SMTP, with correct thread headers."
---

## Overview

The Email adapter connects horus-os to an IMAP inbox. It polls the inbox on a configurable interval, runs the configured agent on each new unread message, and replies over SMTP with proper RFC 5322 threading headers so the reply lands in the right thread in the recipient's mail client.

The adapter uses only the Python standard library (`imaplib`, `smtplib`, `email`). There is no optional pip extra to install. The adapter ships with horus-os out of the box. Whether it runs depends entirely on whether you set the environment variables below. If any required variable is missing, the adapter records a clear error in the registry and stays offline while every other adapter keeps running.

For how adapters fit together, see [Integrations overview](/integrations/overview/).

## Configuration

All configuration is supplied through environment variables. The minimum is four IMAP variables plus one SMTP variable.

| Env var | Required | Default | Purpose |
|---------|----------|---------|---------|
| `HORUS_OS_EMAIL_IMAP_HOST` | yes | none | IMAP server hostname |
| `HORUS_OS_EMAIL_IMAP_PORT` | no | `993` | IMAP SSL port |
| `HORUS_OS_EMAIL_IMAP_USER` | yes | none | IMAP login user |
| `HORUS_OS_EMAIL_IMAP_PASSWORD` | yes | none | App password (see below) |
| `HORUS_OS_EMAIL_SMTP_HOST` | yes | none | SMTP server hostname |
| `HORUS_OS_EMAIL_SMTP_PORT` | no | `465` | SMTP SSL port |
| `HORUS_OS_EMAIL_SMTP_USER` | no | IMAP user | SMTP login (if different) |
| `HORUS_OS_EMAIL_SMTP_PASSWORD` | no | IMAP password | SMTP password (if different) |
| `HORUS_OS_EMAIL_POLL_INTERVAL` | no | `60` | Seconds between inbox polls |
| `HORUS_OS_EMAIL_AGENT_PROFILE` | no | `default` | Agent profile name |

> [!IMPORTANT]
> The adapter connects to SMTP using SSL only (`SMTP_SSL`). Providers that require STARTTLS on port 587 are best-effort and may not work. See the iCloud note below.

For the full list of environment variables across horus-os, see [Environment variables](/reference/environment-variables/).

## Provider quick start

Most consumer email providers no longer accept your main account password over IMAP or SMTP. You need an application-specific password (an app password) tied to the account. The steps below cover Gmail, iCloud, and Fastmail. The pattern is the same for most other providers.

> [!WARNING]
> Use a dedicated bot inbox where possible. The adapter replies to every well-formed inbound message, so running it against your personal inbox is noisy and risky.

### Gmail

1. Sign in to your Google account and open the security page at https://myaccount.google.com/security
2. Confirm 2-Step Verification is enabled. App passwords require it.
3. Open https://myaccount.google.com/apppasswords
4. Pick "Mail" as the app and any device name, for example "horus-os".
5. Copy the 16-character password Google generates. Treat it like a password. You cannot view it again.
6. Set the environment variables:

```bash
HORUS_OS_EMAIL_IMAP_HOST=imap.gmail.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-bot-inbox@gmail.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.gmail.com
HORUS_OS_EMAIL_SMTP_PORT=465
```

7. In Gmail settings, enable IMAP under "Forwarding and POP/IMAP" so the server actually serves IMAP requests. Gmail ships with IMAP off by default on new accounts.

### iCloud

1. Sign in to https://appleid.apple.com/
2. Under "Sign-In and Security", pick "App-Specific Passwords".
3. Generate a password named "horus-os" and copy it.
4. Set the environment variables:

```bash
HORUS_OS_EMAIL_IMAP_HOST=imap.mail.me.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-handle@icloud.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.mail.me.com
HORUS_OS_EMAIL_SMTP_PORT=587
```

> [!CAUTION]
> iCloud's SMTP listener uses STARTTLS on port 587, not SSL on port 465. The adapter currently supports `SMTP_SSL` only, so iCloud support is best-effort. If your provider requires STARTTLS, open an issue at https://github.com/Ridou/horus-os/issues

### Fastmail

1. Sign in to https://app.fastmail.com/
2. Open Settings, then Password and Security, then App Passwords.
3. Click "New app password", grant it "IMAP" and "SMTP" access, and name it "horus-os".
4. Copy the password.
5. Set the environment variables:

```bash
HORUS_OS_EMAIL_IMAP_HOST=imap.fastmail.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-handle@fastmail.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.fastmail.com
HORUS_OS_EMAIL_SMTP_PORT=465
```

## Sample environment block

```bash
HORUS_OS_EMAIL_IMAP_HOST=imap.gmail.com
HORUS_OS_EMAIL_IMAP_PORT=993
HORUS_OS_EMAIL_IMAP_USER=your-bot-inbox@gmail.com
HORUS_OS_EMAIL_IMAP_PASSWORD=your-app-password
HORUS_OS_EMAIL_SMTP_HOST=smtp.gmail.com
HORUS_OS_EMAIL_SMTP_PORT=465
HORUS_OS_EMAIL_POLL_INTERVAL=60
HORUS_OS_EMAIL_AGENT_PROFILE=default
```

> [!WARNING]
> Never commit a real environment file. Add it to your `.gitignore`.

## Run and verify

Once the environment variables are set, start the server:

```bash
horus-os serve
```

Open `/api/adapters` on the local dashboard. The `email` entry should show `status: running`. Send a test message to the bot inbox from another account. Within the poll interval (60 seconds by default), the bot will reply, threaded under the original subject.

## Security

- Use a dedicated bot inbox. The adapter replies to every well-formed inbound message, so pointing it at your personal inbox is noisy and risky.
- App passwords are typically scoped to the full mailbox. A leaked Gmail app password lets an attacker read every message in the account. Rotate the password if it leaks.
- Never paste an app password into a chat, a screenshot, or a pull request. Treat it like a regular password.
- The agent runs with only the capabilities of its profile (`HORUS_OS_EMAIL_AGENT_PROFILE`, default `default`). Keep the profile narrow for an inbox that anyone can email.

For broader hardening guidance, see [Security](/operations/security/).

## Troubleshooting

- "IMAP not enabled" or login refused with no message: the provider's IMAP service is off. Enable IMAP in the provider's webmail settings. Gmail in particular ships with IMAP off by default on new accounts.
- "Less secure app" or "password rejected": you used your main account password instead of an app password. Mint an app password with the steps above.
- Auth fails immediately: double-check the host and port. Gmail IMAP is `imap.gmail.com:993` and SMTP is `smtp.gmail.com:465`. iCloud, Fastmail, and others differ.
- Reply lands in a new thread instead of the original: the inbound message did not carry a `Message-ID` header. Mainstream providers always stamp one. If you see this, the inbound likely came from a misconfigured custom server, not a bug in the adapter.
- Bot replies to its own reply (a loop): the self-filter compares the `From` address against `HORUS_OS_EMAIL_SMTP_USER`. Confirm the bot's `From` matches that variable exactly.
- Polling too aggressive (rate limits): raise `HORUS_OS_EMAIL_POLL_INTERVAL`. Gmail tolerates 60 seconds fine. Some providers prefer 300 seconds or higher.

## See also

- [Integrations overview](/integrations/overview/)
- [Environment variables](/reference/environment-variables/)
- [Security](/operations/security/)
- [Running as a service](/guides/running-as-a-service/)
