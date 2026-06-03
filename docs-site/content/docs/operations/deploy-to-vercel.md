---
title: "Deploy to Vercel"
description: "Deploy your own copy of the horus-os dashboard to Vercel as a static export that reads live data from Supabase or a reachable backend."
---

This guide walks you through deploying your own copy of the horus-os dashboard to Vercel as a static site that reads live data, either from Supabase over the anon read path or from a reachable backend over `NEXT_PUBLIC_API_BASE`.

Read the warning below before any deploy step. It shapes every recommendation on this page.

## Read this first: the dashboard has no app-level auth

> [!CAUTION]
> horus-os ships no app-level authentication in this release. A Vercel deployment publishes your dashboard to the public internet. Anyone who learns the URL can open it. There is no login, no password, and no per-user access control inside horus-os itself.

The backend `/api` is wide open by design. The server sets CORS to `allow_origins=["*"]`, so a browser on any origin can call it. Combined with the fact that `/api` has no authentication layer, any reachable backend URL is usable by anyone who can reach it. If you point your Vercel build at a backend that is reachable from the public internet, you have published that backend to the public internet with no auth.

> [!WARNING]
> Do not deploy a dashboard wired to a publicly reachable backend until you have put a real authentication layer in front of that backend. See [Remote access](/guides/remote-access/) for the supported remote-access path (Tailscale, where your tailnet is the authentication boundary) and the matching no-auth rationale.

The wide-open CORS is intentional for local development and the demo, and it is not narrowed in this release. The mitigation is auth plus reachability control, which is exactly what the prerequisite below requires. For the full posture, see [Security](/operations/security/).

## Prerequisite: add a real authentication layer first

This is step zero, not an afterthought. Before you deploy anything that talks to a live backend over the public internet:

1. **Put a real authentication layer in front of your backend.** The supported answer is to keep `horus-os serve` on its loopback default and reach it only through Tailscale, where the tailnet (WireGuard plus device ACLs) is the authentication boundary. See [Remote access](/guides/remote-access/) for the full walkthrough. If you must publish the backend more broadly, put a real authenticating reverse proxy in front of it. The wide-open CORS does not authenticate anyone; it only decides which browser origins may attempt a request.
2. **Decide your live-data source.** You have two options, covered below. The recommended source is the Supabase anon read path, which is cross-origin-safe and never requires exposing your backend at all. The second option, pointing `NEXT_PUBLIC_API_BASE` at a reachable backend, is what makes the auth prerequisite above mandatory.
3. **Confirm no secret is set as a `NEXT_PUBLIC_*` variable.** Next.js inlines every `NEXT_PUBLIC_*` value into the browser bundle at build time. A secret placed there is published to the world. The env-var table below spells out which values are safe to expose and which must stay server-side only.

Only after these three steps should you continue to the deploy walkthrough.

## Vercel project configuration

Create a Vercel project from your fork or clone of the repository and set the build settings as follows. The frontend is a Next.js app configured for static export (`output: "export"` in `frontend/next.config.ts`), so the build emits a plain static site that Vercel serves directly.

| Setting | Value | Why |
|---------|-------|-----|
| Root Directory | `frontend` | The Next.js app lives in `frontend/`, not the repo root |
| Build Command | `next build` | Produces a static export (no Node server at runtime) |
| Output Directory | `out` | `next build` writes the static site to `frontend/out/` |
| Install Command | default | Vercel's default install is fine |

There is no serverless function and no Node runtime to configure. The output is static HTML, CSS, and JavaScript. All live data is fetched client-side from either Supabase or your `NEXT_PUBLIC_API_BASE` backend.

## Environment variables

Set these in the Vercel project under Settings, Environment Variables, for the build environment. Every variable below is a `NEXT_PUBLIC_*` value, which means it is inlined into the static bundle at `next build` time and is visible to anyone who loads the page. Set only values that are safe to publish.

| Env var | Safe to expose | Purpose |
|---------|----------------|---------|
| `NEXT_PUBLIC_API_BASE` | Yes (it is an origin, not a secret) | Backend origin for `/api` fetches. Leave unset for same-origin |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Your Supabase project URL for the anon read path |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes (the anon key only) | The Supabase anon key for browser reads. RLS is enforced |

### NEXT_PUBLIC_API_BASE

This is the origin the dashboard prepends to every `/api` path. When it is unset, the dashboard fetches same-origin `/api`, which is the byte-for-byte local-development behavior. When you set it, every dashboard fetch targets that origin instead.

```bash
# Point the static build at a reachable backend origin.
NEXT_PUBLIC_API_BASE=https://your-backend.example
```

Two notes that matter:

- **No trailing slash.** Set the bare origin, for example `https://your-backend.example`, not `https://your-backend.example/`. The dashboard strips a single trailing slash defensively, but the no-trailing-slash form is the documented contract and avoids any ambiguity.
- **The value bakes into the build.** Because it is a `NEXT_PUBLIC_*` variable, Vercel inlines it into the static bundle at `next build` time. Changing it later requires a rebuild and redeploy. It is not read at runtime.

### NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY

These wire the dashboard's Supabase anon read path. Set the anon key only.

> [!WARNING]
> Never set the Supabase service key (the service-role key) as a `NEXT_PUBLIC_*` variable, and never set it in any browser-facing surface. The service-role key bypasses row-level security. If it reached the browser bundle, any visitor could read and write all your data. Only the anon key, with row-level security enforced, is safe to expose. See [Supabase](/integrations/supabase/) for the two-key model.

### Tokens that must stay server-side only

Some horus-os env vars are secrets and must never be set as a `NEXT_PUBLIC_*` variable, because Next.js would inline them into the browser bundle and publish them to the world:

- `HORUS_OS_VERCEL_TOKEN` (the Vercel API token used by the server-side deploy-status surface, below)
- `GITHUB_TOKEN` (the GitHub token used by the optional GitHub tool)
- `SUPABASE_SERVICE_KEY` (the Supabase service-role key used by the sync loop)

Set these only in the server environment of the machine running `horus-os serve`, never in the Vercel build environment, and never with a `NEXT_PUBLIC_` prefix.

## Choosing a live-data source

A static Vercel build has no backend of its own. It gets live data one of two ways. Pick based on your reachability and auth posture.

### Recommended: the Supabase anon read path

The supported, cross-origin-safe live-data source is Supabase. Your backend syncs local SQLite data into Supabase server-side (see [Supabase](/integrations/supabase/)), and the dashboard reads it directly with the anon key, with row-level security enforced by Postgres. This path:

- never requires exposing your backend to the dashboard at all,
- is cross-origin-safe out of the box (Supabase serves the anon read API), and
- keeps the service-role key entirely server-side.

This is the recommended source for a Vercel-hosted dashboard. Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` and leave `NEXT_PUBLIC_API_BASE` unset (or set it only for the `/api` paths Supabase does not cover, with the prerequisite auth layer in place).

### Optional: NEXT_PUBLIC_API_BASE to a reachable backend

If you need the dashboard to call `/api` directly (for surfaces not served by the Supabase read path), point `NEXT_PUBLIC_API_BASE` at a reachable backend, for example one reachable over Tailscale. Because the backend already sets CORS to `allow_origins=["*"]`, the cross-origin `/api` fetch works out of the box with no extra CORS configuration.

That same wide-open CORS plus the no-auth `/api` is precisely why the auth prerequisite is mandatory. Any backend you make reachable to your Vercel dashboard is reachable, with no authentication, by anyone who can reach the same URL. Keep the backend on its loopback default behind Tailscale, or behind a real authenticating proxy, before you point a public dashboard at it.

## Observing Vercel deploy status from horus-os

horus-os exposes an observe-only deploy-status surface at `GET /api/integrations/vercel/status`. It reads the server-side `HORUS_OS_VERCEL_TOKEN` (set it under Vercel Dashboard, Account Settings, Tokens) and returns only a derived status (state, url, created_at). The token itself is never included in the response body and never reaches the browser.

This surface is optional. When `HORUS_OS_VERCEL_TOKEN` is unset, the endpoint returns a clear not-configured status with no error, and the local runtime starts and runs fully without it. If you set the optional `HORUS_OS_VERCEL_PROJECT_ID`, the status filters to that project.

> [!IMPORTANT]
> `HORUS_OS_VERCEL_TOKEN` is a server-side secret. Never set it as a `NEXT_PUBLIC_*` variable. Set it only in the environment of the machine running `horus-os serve`.

## Summary

- The dashboard has no app-level auth. A Vercel deploy is public; wide-open CORS plus no-auth `/api` means any reachable backend URL is usable by anyone who can reach it.
- Add a real authentication layer in front of your backend first. This is a prerequisite, not an afterthought. See [Remote access](/guides/remote-access/).
- Configure Vercel with Root Directory `frontend`, Build Command `next build`, and Output Directory `out` for the static export.
- Set only `NEXT_PUBLIC_*` values that are safe to publish: `NEXT_PUBLIC_API_BASE` (no trailing slash, bakes in at build time), `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (the anon key only, never the service key).
- Never set `HORUS_OS_VERCEL_TOKEN`, `GITHUB_TOKEN`, or `SUPABASE_SERVICE_KEY` as a `NEXT_PUBLIC_*` variable.
- Prefer the Supabase anon read path as your live-data source. Reserve `NEXT_PUBLIC_API_BASE` to a reachable backend for the `/api` paths, with the auth prerequisite satisfied.

## See also

- [Remote access](/guides/remote-access/)
- [Supabase](/integrations/supabase/)
- [Security](/operations/security/)
