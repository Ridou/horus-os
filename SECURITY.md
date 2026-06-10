# Security Policy

## Supported versions

`horus-os` is pre-1.0 software. The two most recent minor lines receive security fixes. As of v0.8, the supported lines are v0.8.x and v0.7.x; earlier lines are retired and will not receive backported fixes.

| Version | Supported |
|---------|-----------|
| 0.8.x   | yes       |
| 0.7.x   | yes       |
| < 0.7   | no        |

When the next minor ships, the oldest supported line retires automatically (a two-line rolling window). The supported-versions table is updated in the same commit as each release.

## Reporting a vulnerability

Please report security issues privately. **Do not open a public GitHub issue for a security vulnerability.**

Preferred channel: **GitHub Security Advisories** on this repository. Open a draft advisory at https://github.com/Ridou/horus-os/security/advisories/new and the maintainer will respond from there.

Include in the report:

1. A description of the issue and the impact.
2. Steps to reproduce, or a minimal proof of concept.
3. The version and operating system you tested on.
4. Any mitigation or workaround you have identified.

## Severity-tier SLOs

The maintainer's response targets:

- **Acknowledgement:** within 7 days of the report landing in the private advisory.
- **Fix targets (best effort, not contractual):**
  - **Critical** (RCE, secret exfiltration, complete authn bypass): 14 days from acknowledgement to a patched release.
  - **High** (privilege escalation, persistent denial-of-service, integrity bypass in the audit log): 30 days.
  - **Medium** (information disclosure with mitigation, transient DoS, sandbox escape with limited scope): 90 days.
  - **Low** (hardening opportunities, informational findings): no commitment; tracked in a public advisory once the maintainer has bandwidth.
- **Coordinated disclosure window:** 90 days default. Negotiable up or down based on severity and active exploitation.

## Over-capacity language

horus-os is a solo-maintained project. If the maintainer goes silent on a report (no acknowledgement after 7 days, no progress comment after the fix target lapses), the reporter is invited to file a public issue tagged `security-update` with the advisory reference. This is the explicit escalation path; the maintainer prefers public reminders over the report being silently dropped.

## Test-advisory ritual

Before any real CVE lands, the maintainer publishes at least one rehearsal GitHub Security Advisory (test record, no actual vulnerability) to verify the disclosure flow works end-to-end. This is standing policy, established during the contribution-gate hardening work.

## Scope

In scope:

- The `horus-os` Python package, CLI, and local web dashboard.
- Default configurations and the setup wizard.
- Persistence and audit-trail code.
- Tool execution sandboxing and path safety.
- The release-time signing + SBOM substrate (Phase 52 + 53): signature forgery, SBOM tampering, identity-mismatch issues.

Out of scope:

- Third-party LLM providers (Anthropic, Google Gemini). Report provider issues to the provider.
- Bugs in user-supplied tools or adapters.
- Denial of service from misconfigured local resources.
- Issues that require physical access to the running machine or root on the user's workstation.

## Disclosure

The maintainer practices coordinated disclosure. Once a fix is ready, we will publish the advisory, release a patched version, and credit the reporter unless the reporter prefers to remain anonymous.

## Contributor-pipeline security

`horus-os` accepts outside pull requests (see `CONTRIBUTING.md` for the flow). Every incoming PR runs the full public CI and supply-chain checks (lint, the three-OS test matrix, install-smoke, pip-audit, dependency review) before any human review. Forked-PR builds run with restricted tokens that never see repository secrets. Workflow changes, release scripts, and this policy file require maintainer review per `.github/CODEOWNERS`.

## Operational security guidance for users

The project ships with the following defaults that affect security:

1. **API keys live in environment variables**, never in source control. The setup wizard writes a local config file with file permissions tightened to the current user.
2. **SQLite database** stores trace data including model prompts and completions. Keep the data directory out of any folder you share or sync to a cloud service unless that is explicitly what you want.
3. **The local dashboard binds to 127.0.0.1 by default.** Do not expose it on a public interface without adding authentication.
4. **The `read_file` tool supports a path sandbox.** If your agent has untrusted instructions, register tools with a `base_path` restriction.
5. **Every memory write is logged.** Audit the writes table periodically.
6. **Released artifacts are sigstore-signed.** Verify a downloaded wheel via `python scripts/verify_release.py --version <X.Y.Z> --cert-oidc-issuer https://token.actions.githubusercontent.com --bundle <wheel.sigstore> --artifact <wheel.whl>`.
