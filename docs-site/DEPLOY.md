# Deploying the docs site to Vercel

The documentation site is a static export, so Vercel builds it and serves the
contents of `out/` directly. There is no server, no serverless function, and no
runtime configuration.

This is a separate Vercel project from the dashboard demo
(`horus-os-demo.vercel.app`). Create a new project for the docs.

## Vercel project settings

Create a Vercel project from this repository and set:

| Setting | Value | Why |
|---------|-------|-----|
| Root Directory | `docs-site` | The docs app lives in `docs-site/`, not the repo root |
| Framework Preset | Next.js | Detected automatically |
| Build Command | `next build` | Runs the `prebuild` search-index step, then the static export |
| Output Directory | `out` | `next build` writes the static site to `docs-site/out/` |
| Install Command | default | Vercel's default install is fine |

The committed `docs-site/vercel.json` already pins the build command, output
directory, and framework, so most of this is set for you once Root Directory is
`docs-site`.

## Environment variables

None are required. The docs site reads no secrets and calls no backend. Every
page and the search index are baked in at build time.

> [!NOTE]
> Unlike the dashboard, the docs site publishes nothing sensitive. It is safe to
> deploy publicly with no auth.

## Custom domain

Point a domain or subdomain (for example `docs.your-domain` or a
`horus-os-docs.vercel.app` Vercel subdomain) at the project in Vercel under
Settings, Domains. If you change the canonical URL, update `metadataBase` in
`app/layout.tsx` so Open Graph and canonical tags match.

## Local production check

To reproduce the Vercel build locally before deploying:

```bash
cd docs-site
npm install
npm run build
npx serve out      # or any static file server
```
