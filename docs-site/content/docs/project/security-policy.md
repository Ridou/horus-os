---
title: "Security policy"
description: "How to report a horus-os vulnerability privately, which versions get security fixes, and the maintainer's response targets."
---

## Overview

This page describes how to report a security vulnerability in horus-os, which
versions receive security fixes, and what response you can expect. It mirrors
the `SECURITY.md` file in the [repository](https://github.com/Ridou/horus-os).
For hardening your own deployment, see [Security](/operations/security/).

> [!IMPORTANT]
> Do not open a public GitHub issue for a security vulnerability. Use the
> private reporting channel described below.

## Supported versions

horus-os is pre-1.0 software. The two most recent minor lines receive
security fixes, on a rolling-window policy: when a new minor ships, the
oldest still-supported line retires automatically and the supported-versions
table is updated in the same release.

| Version | Supported |
|---------|-----------|
| 0.8.x   | yes       |
| 0.7.x   | yes       |
| < 0.7   | no        |

> [!NOTE]
> Always check `SECURITY.md` in the repository for the authoritative,
> up-to-date supported-versions table.

## Reporting a vulnerability

Report security issues privately. Do not open a public GitHub issue.

The preferred channel is GitHub Security Advisories on the repository. Open a
draft advisory at
[github.com/Ridou/horus-os/security/advisories/new](https://github.com/Ridou/horus-os/security/advisories/new)
and the maintainer will respond from there.

Include in your report:

1. A description of the issue and its impact.
2. Steps to reproduce, or a minimal proof of concept.
3. The version and operating system you tested on.
4. Any mitigation or workaround you have identified.

## Response targets

These are the maintainer's response targets. The fix targets are best effort,
not contractual.

- Acknowledgement: within 7 days of the report landing in the private advisory.
- Critical (remote code execution, secret exfiltration, complete
  authentication bypass): 14 days from acknowledgement to a patched release.
- High (privilege escalation, persistent denial of service, integrity bypass
  in the audit log): 30 days.
- Medium (information disclosure with mitigation, transient denial of service,
  sandbox escape with limited scope): 90 days.
- Low (hardening opportunities, informational findings): no commitment;
  tracked in a public advisory once the maintainer has bandwidth.
- Coordinated disclosure window: 90 days by default, negotiable up or down
  based on severity and active exploitation.

### If the maintainer goes silent

horus-os is a solo-maintained project. If you receive no acknowledgement after
7 days, or no progress comment after the fix target lapses, you are invited to
file a public issue tagged `security-update-followup` with the advisory
reference. This is the explicit escalation path. The maintainer prefers public
reminders over a report being silently dropped.

## Scope

In scope:

- The `horus-os` Python package, CLI, and local web dashboard.
- Default configurations and the setup wizard.
- Persistence and audit-trail code.
- Tool execution sandboxing and path safety.
- The release-time signing and SBOM substrate: signature forgery, SBOM
  tampering, and identity-mismatch issues.

Out of scope:

- Third-party LLM providers (Anthropic, Google Gemini). Report provider issues
  to the provider.
- Bugs in user-supplied tools or adapters.
- Denial of service from misconfigured local resources.
- Issues that require physical access to the running machine, or root on the
  user's workstation.

## Disclosure

The maintainer practices coordinated disclosure. Once a fix is ready, the
advisory is published, a patched version is released, and the reporter is
credited unless they prefer to remain anonymous.

## Operational security guidance

horus-os ships with several defaults that affect security. See
[Security](/operations/security/) for full hardening guidance.

1. API keys live in environment variables, never in source control. The setup
   wizard writes a local config file with permissions tightened to the current
   user.
2. The SQLite database stores trace data, including model prompts and
   completions. Keep the data directory out of any folder you share or sync to
   a cloud service unless that is explicitly what you want.
3. The local dashboard binds to `127.0.0.1` by default. Do not expose it on a
   public interface without adding authentication.
4. The `read_file` tool supports a path sandbox. If your agent runs untrusted
   instructions, register tools with a `base_path` restriction.
5. Every memory write is logged. Audit the writes table periodically.
6. Released artifacts are sigstore-signed. Verify a downloaded wheel with the
   release verification script:

```bash
python scripts/verify_release.py \
  --version <X.Y.Z> \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --bundle <wheel.sigstore> \
  --artifact <wheel.whl>
```

## See also

- [Security](/operations/security/)
- [Contributing](/project/contributing/)
- [Code of conduct](/project/code-of-conduct/)
