# Security Policy

## Supported versions

`horus-os` is pre-1.0 software. Only the latest minor release receives
security fixes. As of this writing that is `v0.3.x`.

| Version | Supported |
|---------|-----------|
| 0.3.x   | yes       |
| < 0.3   | no        |

## Reporting a vulnerability

Please report security issues privately. **Do not open a public GitHub
issue for a security vulnerability.**

Preferred channel: **GitHub Security Advisories** on this repository.
Open a draft advisory at
https://github.com/Ridou/horus-os/security/advisories/new and the
maintainers will respond from there.

Include in the report:

1. A description of the issue and the impact.
2. Steps to reproduce, or a minimal proof of concept.
3. The version and operating system you tested on.
4. Any mitigation or workaround you have identified.

You will receive an acknowledgement within 7 days. A fix timeline
depends on severity; expect a response in the advisory thread within
14 days.

## Scope

In scope:

- The `horus-os` Python package, CLI, and local web dashboard.
- Default configurations and the setup wizard.
- Persistence and audit-trail code.
- Tool execution sandboxing and path safety.

Out of scope:

- Third-party LLM providers (Anthropic, Google Gemini). Report
  provider issues to the provider.
- Bugs in user-supplied tools or adapters.
- Denial of service from misconfigured local resources.
- Issues that require physical access to the running machine or root
  on the user's workstation.

## Disclosure

The maintainers practice coordinated disclosure. Once a fix is ready,
we will publish the advisory, release a patched version, and credit
the reporter unless the reporter prefers to remain anonymous.

## Contributor-pipeline security (not active yet)

`horus-os` is in a solo development phase and **does not currently
accept outside pull requests** (see `CONTRIBUTING.md` for the full
notice). When the project opens for contributions, every incoming
PR will pass through a private pre-review process before any human
review. Until then, treat the existing surface area as
single-maintainer code with no third-party PR exposure.

## Operational security guidance for users

The project ships with the following defaults that affect security:

1. **API keys live in environment variables**, never in source
   control. The setup wizard writes a local config file with file
   permissions tightened to the current user.
2. **SQLite database** stores trace data including model prompts and
   completions. Keep the data directory out of any folder you share
   or sync to a cloud service unless that is explicitly what you
   want.
3. **The local dashboard binds to 127.0.0.1 by default.** Do not
   expose it on a public interface without adding authentication.
4. **The `read_file` tool supports a path sandbox.** If your agent
   has untrusted instructions, register tools with a `base_path`
   restriction.
5. **Every memory write is logged.** Audit the writes table
   periodically.
