# horus-os documentation site

The official documentation site for horus-os. It is a static-exported Next.js
app styled to match the dashboard (dark, cyan-on-near-black) and deployable to
Vercel or any static host.

## Stack

- Next.js 16 with `output: "export"` (no server at runtime; pure static files).
- Tailwind v4, tokens lifted from `frontend/app/globals.css`.
- `react-markdown` + `remark-gfm` for rendering, `rehype-slug` for anchors.
- `react-syntax-highlighter` for code blocks.
- A build-time client search index (cmd-K), generated into `public/`.

## Content

All pages are markdown files under `content/docs/<section>/<page>.md`. Each file
has frontmatter:

```markdown
---
title: Page Title
description: One sentence shown as the page lede and in search.
---

## First section
Body starts at an H2. The title comes from frontmatter, so do not add an H1.
```

The sidebar, breadcrumbs, and prev/next order are defined in `lib/nav.ts`. To
add a page, create the markdown file and add its slug to `lib/nav.ts`.

Authoring rules (also enforced in CI for the repo):

- No em-dash characters anywhere.
- No personal data; use placeholders.
- Internal links are absolute and end with a slash, e.g. `/guides/cli/`.
- Code fences always carry a language tag.

## Develop

```bash
npm install
npm run dev        # regenerates the search index, then starts the dev server
```

Open http://localhost:3000 .

## Build

```bash
npm run build      # regenerates the search index, then static-exports to out/
```

The static site is written to `out/`. See `DEPLOY.md` for Vercel settings.
