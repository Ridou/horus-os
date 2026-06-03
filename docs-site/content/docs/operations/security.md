---
title: "Security model"
description: "How horus-os stays safe by being local-first, why the dashboard ships no auth, and how to expose it safely with Tailscale or a real auth proxy."
---

## The model in one sentence

horus-os is local-first. The dashboard and the `/api` backend ship **no app-level authentication** in this release, so the security boundary is the **network**: by default the server binds to loopback (`127.0.0.1:8765`), reachable only from the machine it runs on. Everything below follows from that one fact.

> [!IMPORTANT]
> There is no login, no password, and no per-user access control inside horus-os. Anyone who can reach the dashboard URL on the network can read your traces, agent prompts, and tasks, and can drive the dashboard. Do not put a routable address in front of it without a real authentication layer.

## What "local-first by default" buys you

When you run `horus-os serve` with no flags, the server listens on `127.0.0.1:8765`. That address is reachable only from the same machine. Nothing on your LAN, your Wi-Fi, or the internet can connect to it. For a single-user workstation this is the whole story: the operating system account already gates access, and the absence of network reachability is the absence of attack surface.

Your data stays local too. Traces, prompts, completions, tasks, and the vault all live in the data directory on disk (`config.toml`, `horus.sqlite`, `notes/`, and friends). See [The vault](/concepts/the-vault/) and [Configuration](/getting-started/configuration/) for where that lives and how to point it elsewhere.

> [!WARNING]
> The SQLite database stores model prompts and completions in plain trace records. Keep the data directory out of any folder you sync to a cloud service unless that is explicitly what you want.

## No app-level auth: why, and what protects you instead

The dashboard and `/api` have no authentication layer, and the CORS policy is wide open. In `src/horus_os/server/api.py` the server sets:

```python
allow_origins=["*"]
```

This is intentional for local development and the demo. CORS only decides which **browser origins** may attempt a request; it authenticates nobody. Combined with the no-auth `/api`, the practical meaning is:

- **On loopback (the default):** safe. The only origin that can reach the backend is something already running on your machine.
- **On any routable address:** anyone who can reach that address can use the backend with no login.

So the mitigation is never "lock down CORS." The mitigation is **reachability control plus a real authentication layer in front of the backend**. The supported way to add that layer is described under [Exposing the dashboard safely](#exposing-the-dashboard-safely) below.

### The loopback key-write guard

One endpoint is hardened beyond the loopback default: the credential-write endpoint rejects any request whose TCP peer is not loopback, so secrets cannot be written from a remote address. That guard protects key writes specifically. It does **not** authenticate the dashboard as a whole and is not a substitute for a network auth layer.

## Secrets stay server-side

Provider keys and integration tokens are environment variables, never source-controlled, never browser-facing.

- Provider keys: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.
- Integration secrets that must stay server-side only: `GITHUB_TOKEN`, `SUPABASE_SERVICE_KEY` (the Supabase service-role key, which bypasses row-level security), and `HORUS_OS_VERCEL_TOKEN`.

When you deploy the Next.js dashboard, the rule is absolute: **never set a secret as a `NEXT_PUBLIC_*` variable.** Next.js inlines every `NEXT_PUBLIC_*` value into the browser bundle at build time, which publishes it to anyone who loads the page. Only values that are safe to expose belong there, such as `NEXT_PUBLIC_API_BASE` (an origin, not a secret), `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (the anon key only, with row-level security enforced).

The setup wizard writes the local config file with permissions tightened to the current user. See [Deploy to Vercel](/operations/deploy-to-vercel/) for the full env-var safety table and [Environment variables](/reference/environment-variables/) for the canonical list.

> [!CAUTION]
> The Supabase service-role key bypasses row-level security. If it reached the browser bundle, any visitor could read and write all your data. Only the anon key, with row-level security enforced, is safe to put in a `NEXT_PUBLIC_*` variable.

## Tool and plugin capabilities are gated

horus-os limits what agent tools and plugins can do, default-deny.

- **Path sandbox.** The file-reading tool supports a `base_path` restriction. If an agent might receive untrusted instructions, register tools with a `base_path` so reads cannot escape a chosen directory.
- **Capability grants for plugins.** Plugins declare the capabilities they need in their manifest, and capabilities are granted explicitly. Sensitive abilities are gated behind a grant prompt and are default-deny: for example, a skill marked `kind=code` cannot run code, and the `shell_exec` tool never reaches an agent, without the matching capability grant. Without the grant, the capability simply does not exist for that agent.

See [Plugin security](/extending/plugin-security/) and the [Manifest reference](/extending/manifest-reference/) for how capabilities are declared and granted.

## Audit trail

Every memory write is logged. Audit the writes table periodically to confirm that what your agents persisted matches what you expected. See [Traces and observability](/concepts/traces-and-observability/) for how trace and write data is recorded.

## Exposing the dashboard safely

If you need to reach the dashboard from another device, do not bind it to a routable address and hope. Use one of the supported patterns.

### Recommended: Tailscale serve

Keep `horus-os serve` on its loopback default and reach it over your tailnet. With Tailscale, the tailnet (WireGuard plus device ACLs) **is** the authentication boundary: only devices you have added to your tailnet, and that pass your ACLs, can connect.

```bash
# 1. Join the host to your tailnet (authenticates once in a browser).
tailscale up

# 2. Start horus-os on loopback. --host 0.0.0.0 is NOT needed.
horus-os serve

# 3. Expose port 8765 to your tailnet over HTTPS (tailnet-only, not public).
tailscale serve 8765
```

Then open the host's MagicDNS name from another tailnet device at `https://your-machine.your-tailnet.ts.net`. The full walkthrough, including remote host management, is in [Remote access](/guides/remote-access/).

> [!WARNING]
> Never use `tailscale funnel` for the dashboard. Funnel publishes to the public internet, does not restrict access to your tailnet, and injects no identity. It would expose an unauthenticated dashboard to the world. Use `tailscale serve`, not `funnel`.

### Alternative: a real authenticating reverse proxy

If you genuinely need to publish the backend more broadly, put a real authenticating reverse proxy in front of it first, then point clients at the proxy. Only in that case should you consider `horus-os serve --host 0.0.0.0`, which binds every interface and is unsafe on its own.

```bash
horus-os serve --host 0.0.0.0   # binds EVERY interface, no app auth, use only behind a real auth proxy
```

### Deploying the static dashboard to Vercel

A Vercel deploy is public to anyone with the URL. Add a real authentication layer in front of your backend **before** you point a public dashboard at it, and prefer the Supabase anon read path as your live-data source so you never have to expose the backend at all. The complete prerequisites and env-var rules are in [Deploy to Vercel](/operations/deploy-to-vercel/).

## Scope and out of scope

The security scope covers the `horus-os` Python package, CLI, and local web dashboard; default configurations and the setup wizard; persistence and audit-trail code; tool execution sandboxing and path safety; and release-time signing and SBOM integrity.

Out of scope: third-party LLM providers (report provider issues to the provider), bugs in user-supplied tools or adapters, denial of service from misconfigured local resources, and anything requiring physical access or root on the workstation.

## Reporting a vulnerability

Report security issues privately. **Do not open a public GitHub issue for a vulnerability.** Open a draft GitHub Security Advisory at `https://github.com/Ridou/horus-os/security/advisories/new` and the maintainer responds from there. Full reporting expectations, severity SLOs, and the disclosure process are in the [Security policy](/project/security-policy/).

## See also

- [Security policy](/project/security-policy/) for reporting, SLOs, and supported versions.
- [Remote access](/guides/remote-access/) for the Tailscale walkthrough and always-on service.
- [Deploy to Vercel](/operations/deploy-to-vercel/) for the public-deploy prerequisites and safe env vars.
- [Plugin security](/extending/plugin-security/) for the capability-grant model.
