---
phase: 07-cli-surface
plan: "00"
subsystem: cli
tags: [cli, argparse, config, toml, init, traces]

# Dependency graph
requires:
  - phase: "03-persistence-layer"
    provides: "Database class used by init and traces"
  - phase: "06-memory-layer-write-path"
    provides: "Schema v2; init runs Database.init which establishes both tables"
provides:
  - "Config dataclass + load + save + default_data_dir"
  - "horus-os init / traces / serve subcommands via argparse subparsers"
  - "Testable main(argv, stdout=, stderr=) entry point"
  - "TOML config file format at data_dir/config.toml"
affects:
  - "07-01 (multi-turn loop + run subcommand) reuses Config for default models"
  - "08 (web chat + dashboard) reads from the same Config + data_dir"
  - "09 (setup wizard) extends init with interactive API key onboarding"

# Tech tracking
tech-stack:
  added: []  # tomllib is stdlib in 3.11+
  patterns:
    - "argparse subparsers, no new CLI framework dep. Subcommands live in `cli/<name>_cmd.py` and expose `run_<name>(args, *, stdout, stderr)` so tests can capture output without subprocess."
    - "TOML for config; tomllib for read; hand-formatted write. Keeps dependencies at zero for the core."
    - "Atomic write via tempfile.mkstemp in the same directory plus os.replace. Survives kill mid-write."
    - "Platform-aware default data dir: macOS Library, Linux XDG, Windows APPDATA. HORUS_OS_DATA_DIR overrides."

key-files:
  created:
    - "src/horus_os/config.py, 130 lines, Config + load/save + default_data_dir + TOML helpers"
    - "src/horus_os/cli/__init__.py, 17 lines, re-exports"
    - "src/horus_os/cli/init_cmd.py, 45 lines, run_init"
    - "src/horus_os/cli/traces_cmd.py, 48 lines, run_traces + table + JSON formatters"
    - "src/horus_os/cli/serve_cmd.py, 19 lines, stub"
    - "tests/test_config.py, 118 lines, 11 tests"
    - "tests/test_cli_init.py, 56 lines, 4 tests"
    - "tests/test_cli_traces.py, 84 lines, 5 tests"
    - "tests/test_cli_serve.py, 28 lines, 2 tests"
  modified:
    - "src/horus_os/__main__.py, upgraded to argparse subparsers + main(argv, stdout=, stderr=) signature"
    - "src/horus_os/__init__.py, re-exports Config"

key-decisions:
  - "argparse over Click/Typer. Zero new dependencies, the subcommand set is small enough that argparse stays readable, and it matches the existing __main__.py pattern from Phase 01."
  - "Config is data-only. No subcommand mutates the loaded Config; subcommands always reload from disk to keep concurrent CLIs consistent."
  - "init is idempotent without --force. The user can re-run init safely to inspect status; --force is required to overwrite the config file."
  - "traces falls back to a hint when the database is missing. Better UX than a stack trace; matches the same pattern future subcommands will use."
  - "serve ships as a stub now so the surface is forward-stable. A user who scripts around `horus-os serve` today gets an exit 0 with a clear message rather than a missing-command error when 07-01 / Phase 08 lands the real implementation."
  - "main(argv, stdout=, stderr=) accepts streams. Tests pass StringIO buffers and assert on captured text without spawning subprocesses. The default behavior (sys.stdout / sys.stderr) is unchanged for real CLI users."

patterns-established:
  - "Subcommand handlers live in `cli/<name>_cmd.py` with `run_<name>(args, *, stdout, stderr) -> int` signature. Adding a new subcommand is a new file plus three lines in __main__.py."
  - "Tests invoke main() directly, not subprocess. Two reasons: speed (in-process is ~100x faster) and isolation (no inherited env or working directory surprises)."
  - "All write paths in this CLI are atomic. The save() helper in Config sets the precedent; future settings writers reuse it."

requirements-completed:
  - CORE-02 (partial)  # CLI surface accepting commands; full prompt-run lands in 07-01
  - CORE-04           # Configure via a single config file (TOML format under data_dir)

known-limitations:
  - "No `horus-os run <prompt>` yet. That subcommand needs the multi-turn agent loop, which is 07-01."
  - "No interactive setup wizard. The init subcommand creates the files but does not validate API keys. Wizard lands in Phase 09."
  - "No watch mode for traces. The user runs the command again to refresh. The dashboard (Phase 08) will offer live tail."
  - "Config has no schema validation beyond TOML parsing. Future phases can add a Pydantic or attrs validator if the config grows."

# Metrics
duration: 32m
completed: 2026-05-23
commit-count: 1
test-count: 22 (120 total cumulative, one diff from my count was a test renamed during ruff fix)
lint-issues: 0
new-public-api-symbols: 1 (Config)
new-cli-subcommands: 3 (init, traces, serve)
