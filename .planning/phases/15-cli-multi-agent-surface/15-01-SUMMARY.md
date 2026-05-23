# Phase 15 Plan 01 Summary

**Status:** Shipped
**Commit:** feat(15): horus-os agents CRUD subcommand
**Date:** 2026-05-23

## What shipped

A flat `horus-os agents` subcommand group with five operations
(`list`, `show`, `create`, `edit`, `delete`) that drive the Phase 12
`AgentProfile` CRUD methods on `Database`. The surface satisfies the
requirement edge of MA-01 ("named agent profiles persist in SQLite") by
giving users a non-Python way to inspect and mutate the seeded `default`
profile and any custom profiles they want to add.

### Command shapes

```
horus-os agents list                                      # alias of bare `agents`
horus-os agents show <name>
horus-os agents create --name NAME --system-prompt P [--model M] [--allowed-tools "a,b"|all|""] [--memory-scope S]
horus-os agents edit <name> [--system-prompt P] [--model M] [--allowed-tools ...] [--memory-scope S]
horus-os agents delete <name>
```

All five accept `--data-dir` for testability and out-of-tree installs.

### Behavior locked in

- Bare `horus-os agents` defaults to `list`, matching the friendlier
  argparse pattern from research §Pattern 1.
- `create` rejects a duplicate name with exit 1 instead of silently
  overwriting; users must use `edit` to update. This protects against
  typo-driven destruction of an existing profile.
- `edit` loads the existing profile and mutates only the supplied
  fields, so `agents edit foo --model M` no longer blanks
  `system_prompt`. Pitfall 5 from the research file is mitigated.
- `--allowed-tools` accepts a comma-separated list, "all" for
  unrestricted (`None`), or an empty string for explicit deny-all
  (`[]`). The trio matches the AgentProfile semantics from Phase 12.
- All error paths (missing database, unknown name, duplicate create)
  return non-zero exit codes and write a clear message to stderr.

## Files touched

- `src/horus_os/cli/agents_cmd.py` (new): `run_agents` dispatcher plus
  `_cmd_list`, `_cmd_show`, `_cmd_create`, `_cmd_edit`, `_cmd_delete`
  helpers, `_format_profiles_table` formatter, and `_parse_allowed_tools`
  parser.
- `src/horus_os/cli/__init__.py`: exports `run_agents` alongside the
  other handlers; updates `__all__`.
- `src/horus_os/__main__.py`: nested argparse subparser block for the
  five operations, each with its own `--data-dir`.
- `tests/test_cli_agents.py` (new): 14 tests covering each operation,
  bare `agents` dispatch, missing-db path, unknown-name paths on show/
  edit/delete, duplicate-create, allowed-tools "all" reset, allowed-tools
  empty deny-all, and direct Database round-trip for create.

## Test count delta

| Surface | Before | After |
|---------|--------|-------|
| cli_agents | 0 | 14 |
| **full suite** | **224** | **238** |

All green: `python -m pytest -q` reports 238 passed in 0.81s.

## Lint status

`ruff check .` clean. `ruff format --check .` clean across 53 files
after one `ruff format` pass on the new module to satisfy the formatter.

## Notable / deferred

- The `--agent <name>` flag on `run` and the streaming output path land
  in Plan 15-02 by design. Plan 15-01 is the management surface; Plan
  15-02 is the runtime consumer.
- `agents show` deliberately prints the full `system_prompt`. This is
  the consumer's only path to read a profile before invoking it, and
  `AgentProfile` carries no secrets (`default_model` is a model name,
  not a credential).
- No JSON output flag was added. The plain-text table is already
  machine-parseable on whitespace; adding `--json` is a candidate for a
  later UX pass, not a Phase 15 must-have.
