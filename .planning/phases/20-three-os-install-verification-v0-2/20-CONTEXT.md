# Phase 20 Context: Three-OS install verification (v0.2)

**Date:** 2026-05-23
**Phase:** 20
**Status:** Plan staged; install-smoke needs v0.2 surface

## Domain

Phase 10 stood up the `install-smoke` GitHub Actions job that runs
`pip install '.[all]'` and exercises the v0.1 CLI surface on Ubuntu,
macOS, and Windows by Python 3.11 and 3.12. Phases 12-19 added the v0.2
surface (agent profiles, multi-agent runtime, streaming-by-default,
adapter plugin contract). The smoke script has not been updated, so a
fresh install only confirms that v0.1 still works.

Phase 20 closes the gap: the same job, same matrix, but the script
exercises the v0.2 surface so a regression on any of three OSes shows up
in CI before release.

## What install_smoke.py already exercises (v0.1)

1. `horus-os --version` prints the package version
2. `horus-os --help` lists every subcommand (init, traces, serve, run)
3. `horus-os init --data-dir <tmp>` creates `config.toml`, `horus.sqlite`, and `notes/`
4. `init` is idempotent without `--force` (exit 1 + already-initialized message)
5. `init --force` reinitializes cleanly
6. `traces --data-dir <tmp>` on an empty DB prints the empty marker
7. `run "hello" --data-dir <tmp>` with no API keys exits 2 with a clear error
8. `serve --help` prints `--host` and `--port`

## What v0.2 adds and what install-smoke must now verify

The v0.2 surface adds:

- `horus-os agents` subcommand with `list`, `show`, `create`, `edit`, `delete`
- The default agent profile is bootstrapped on init (one row in `agent_profiles` table)
- SQLite schema is on `user_version=4` on disk (Phase 12 migration)
- `traces` table carries `parent_trace_id` and `agent_profile_name` columns
- Streaming-by-default for `horus-os run`, with `--no-stream` fallback
- `horus_os` package exports: `Adapter`, `AdapterContext`, `discover_adapters`, `ToolCallEvent`, `run_agent_stream`
- The reference webhook adapter registers via the `horus_os.adapters` entry point

The smoke script must add coverage for each of those, exercise the
agents CRUD round-trip end to end against a temp data dir, open the
SQLite file directly to confirm schema version + columns, and assert
that `discover_adapters()` runs without crashing on a fresh install.

Constraint: the script runs offline. GitHub-hosted runners have no
API keys, so neither the streaming nor the buffered run path can call
a real provider. The script exercises the CLI surface only (parser,
data-dir wiring, error messages, no-keys path). The
`horus-os run --agent default "hello"` ROADMAP criterion that requires
keys is documented as a manual verification step, not a CI check.

## Out of scope for Phase 20

- Live API calls or provider mocks. CI never has keys.
- Truly fresh-VM images. The matrix uses GitHub-hosted runners.
- Bumping the package version or tagging a release (Phase 21).
- Changing the matrix (Ubuntu, macOS, Windows by Python 3.11, 3.12 stays).
- New dependencies. Stdlib `sqlite3` reads the schema; nothing else.

## Expected delta

`scripts/install_smoke.py` grows from 8 checks to roughly 16 checks.
A new `tests/test_install_smoke.py` runs the same script under pytest
against `tmp_path` so the smoke logic also rides the regular pytest
matrix, not only the dedicated `install-smoke` job. CI workflow either
unchanged or only path-tweaked. Suite target: 318 + 1 to 3 = 319 or
more. Lint clean. Three-OS matrix green on push.
