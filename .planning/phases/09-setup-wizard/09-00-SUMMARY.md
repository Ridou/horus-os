---
phase: 09-setup-wizard
plan: "00"
subsystem: cli-wizard
tags: [wizard, onboarding, api-keys, validation, env-file]

# Dependency graph
requires:
  - phase: "07-00"  # init subcommand and config file
provides:
  - "horus_os.cli.wizard.run_wizard"
  - "horus-os init --interactive flow"
  - ".env file at <data_dir>/.env with 0600 perms on POSIX"
  - ".horus-init-state.json for resumable progress"

# Tech tracking
tech-stack:
  added: []  # stdlib only; SDKs already optional from earlier phases
  patterns:
    - "Injectable validators dict. Tests pass {'anthropic': _always_ok, ...} to drive the flow without touching real SDKs. Production uses DEFAULT_VALIDATORS which make 1-token live calls."
    - "Atomic write via tempfile + os.replace, same pattern as Config.save."
    - "Resume via a step-flags state file. Each step is idempotent and writes its flag immediately so a Ctrl-C never loses progress."
    - "POSIX 0600 on the .env file because it contains secrets; on Windows the chmod call is a no-op since file ACLs work differently."

requirements-completed:
  - WIZARD-01
  - WIZARD-02
  - WIZARD-03
  - WIZARD-04

known-limitations:
  - "No env-var injection helper. The user has to source the .env in their shell or pass values explicitly. A `horus-os env` subcommand that prints `export ...` lines is a tiny follow-up."
  - "Wizard does not prompt for notes_dir or db_path overrides. The defaults from init are used."
  - "Validation makes a real API call (1 token). Users on rate-limited free tiers can hit issues. A future phase can offer a `--skip-validate` flag."

# Metrics
duration: 28m
completed: 2026-05-23
test-count: 10 (175 cumulative)
new-cli-flags: 1 (--interactive on init)
