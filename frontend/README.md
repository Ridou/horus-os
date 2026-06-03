# horus-os dashboard

The web dashboard for horus-os. Next.js App Router, React, Tailwind v4,
TypeScript. It is a fully client-rendered static export: the runtime serves the
generated `out/` directory as plain files, and every page fetches its data at
runtime from the `/api/*` contract.

## Develop

```bash
npm install
npm run dev
```

The dev server runs at `http://localhost:3000`. With no backend reachable the
client falls back to bundled sample data, so the UI renders out of the box.

## Build

```bash
npm run build
```

This produces a static export in `out/`. There is no Node server in production:
the FastAPI runtime (and the marketing demo) serve `out/` at the site root.

## Demo mode

Set `NEXT_PUBLIC_HORUS_DEMO=1` to force the bundled fixtures and skip all
network requests. This powers the static marketing demo.

```bash
NEXT_PUBLIC_HORUS_DEMO=1 npm run build
# or for local preview:
NEXT_PUBLIC_HORUS_DEMO=1 npm run dev
```

Even without this flag, any failed `/api` fetch falls back to the same fixtures,
so the dashboard is never blank.

## Lint

```bash
npm run lint
```

## Layout

- `app/` - App Router pages (Home, Team, plus stub routes) and the root layout.
- `components/` - shared, framework-portable UI (status badges, metric cards,
  markdown renderer, app shell, sidebar).
- `lib/` - typed API client, React Query hooks, types, fixtures, and pure
  utilities (time, status colors).
- `public/` - static assets including the favicon and sidebar logo.

## API contract

The dashboard targets these endpoints (implemented by the runtime):

- `GET /api/team`
- `GET /api/team/{name}`
- `GET /api/memory?q=`
- `GET /api/memory/note?path=`
- `GET /api/activity?limit=`
- `GET /api/health`

Types for every shape live in `lib/types.ts`; matching sample data lives in
`lib/fixtures/`.
