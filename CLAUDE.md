# Claude project configuration

This file gives any Claude Code or Claude API session enough context to work productively in this repo.

## What this project is

`horus-os` is an open-source, self-hosted autonomous AI command center. The runtime is Python 3.11+, the dashboard is Next.js, persistence is SQLite. Two LLM providers are first-class for v0.1: Anthropic and Google Gemini, called via their direct SDKs.

For project intent and scope, read `PROJECT.md`. For the current phase plan, read `ROADMAP.md` and `.planning/STATE.md`. For technical shape, read `ARCHITECTURE.md`.

## Hard rules for any Claude session

1. **No personal information about any contributor or user in committed text.** Names, locations, phone numbers, IP addresses, vault paths, API keys, account-bound credentials are all forbidden in code, comments, docs, planning artifacts, or commit messages. Use placeholder values like `your-api-key`, `your-project-name`, `~/.config/horus-os/`.

2. **Apache 2.0 license applies to every contribution.** Match the license header expectations of existing files. New files do not need a per-file header for v0.1.

3. **No em-dashes in committed prose.** Use commas, periods, or hyphens. This applies to code comments, docs, commit messages, and any user-visible string.

4. **Style:** ruff is the linter and formatter. Configuration lives in `pyproject.toml`. Run `ruff check .` and `ruff format --check .` before committing.

5. **Testing:** pytest runs from the repo root. CI exercises (ubuntu-latest, macos-latest, windows-latest) by (Python 3.11, Python 3.12). Code changes ship with at least one regression test when feasible.

6. **Commits:** present tense, conventional-commit prefix (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`). Reference the phase when applicable (`feat(02): agent runtime core`).

## Workflow expectations

- The `.planning/` directory tracks phases, requirements, and project state. It is committed and public; nothing private goes there.
- New work lands in a feature branch when in doubt; `main` is the integration branch.
- `pip install -e '.[dev]'` is the canonical development install. The venv lives at `.venv/`, gitignored.
- Cross-OS path handling matters: use `pathlib`, never raw string concatenation. CI catches OS-specific regressions.

## When you start a new session

1. Read `.planning/STATE.md` to see which phase is active.
2. Read the active phase's PLAN.md if one exists under `.planning/phases/`.
3. Ask the project owner before assuming scope outside the active phase or roadmap.
4. Do not push to any remote without explicit confirmation.
