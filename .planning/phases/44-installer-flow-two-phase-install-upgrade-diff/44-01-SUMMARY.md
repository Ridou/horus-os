---
phase: 44-installer-flow-two-phase-install-upgrade-diff
plan: 01
subsystem: plugins
tags:
  - installer
  - cli
  - pip
  - capability-grant
  - upgrade-diff
  - rollback
  - v0.5
dependency_graph:
  requires:
    - phase-41 (manifest + validate_manifest + compute_manifest_hash)
    - phase-42 (discover_plugins + PluginRegistry)
    - phase-43 (PermissionService.grant/revoke/pending_on_upgrade)
  provides:
    - horus-os plugins CLI surface (9 subcommands)
    - installer module (5-phase pipeline with rollback)
    - upgrade-diff classifier (unchanged/reduced/expanded)
  affects:
    - phase-45 (dashboard /plugins tab consumes the plugins + plugin_capabilities + plugin_status rows the installer writes)
    - phase-46 (pitfall-regression tests consume the .pth + sdist + downgrade refusal helpers)
    - phase-49 (3-OS install-smoke runs TEST-20 against the real installer chokepoint)
tech_stack:
  added:
    - packaging.requirements.Requirement (parses Requires-Dist for downgrade gate)
    - email.parser.BytesParser (parses *.dist-info/METADATA)
  patterns:
    - single subprocess chokepoint (run_pip helper) → grep -c "subprocess.run" returns 1
    - structured PluginInstallError(phase, reason, message) with stable _REASON_* tokens
    - argparse subparser pattern mirrored from agents_cmd
key_files:
  created:
    - src/horus_os/plugins/installer.py
    - src/horus_os/cli/plugins_cmd.py
    - tests/fixtures/installer/__init__.py
    - tests/fixtures/installer/build_fixture_wheels.py
    - tests/fixtures/installer/wheel_clean/{horus-plugin.toml,RECORD,METADATA}
    - tests/fixtures/installer/wheel_with_pth/{horus-plugin.toml,RECORD,METADATA}
    - tests/fixtures/installer/wheel_downgrades_pydantic/{horus-plugin.toml,RECORD,METADATA}
    - tests/fixtures/installer/sdist_only/horus-plugin.toml
    - tests/plugins/test_installer_venv_refusal.py
    - tests/plugins/test_installer_sdist_refusal.py
    - tests/plugins/test_installer_pth_refusal.py
    - tests/plugins/test_installer_downgrade_refusal.py
    - tests/plugins/test_installer_capability_prompt.py
    - tests/plugins/test_installer_rollback.py
    - tests/plugins/test_installer_upgrade_diff.py
    - tests/plugins/test_plugin_freeze_roundtrip.py
    - tests/plugins/test_cli_plugins_subcommands.py
    - tests/plugins/test_horus_os_plugins_list.py
  modified:
    - src/horus_os/__main__.py (added plugins subparser + 9 sub-subparsers)
    - src/horus_os/cli/__init__.py (re-exports run_plugins)
    - tests/plugins/conftest.py (added installer_fixture_wheels session fixture)
decisions:
  - chokepoint-helper: single run_pip() wrapper around subprocess.run. Forecloses Pitfall 4 modes 1-6 by construction; grep -c "subprocess.run\b" returns 1.
  - structured-error-class: PluginInstallError carries phase + reason + message. Reason tokens are lowercase-snake constants the CLI layer branches on without parsing the message.
  - set-equality-on-names: update_plugin classifies by set comparison on capability NAMES (not manifest hash equality) because hashes can drift for orthogonal reasons. Pitfall 5 mitigation.
  - synthetic-wheel-fixtures: 4 template directories under tests/fixtures/installer/ get zipped into real .whl files by build_fixture_wheels() at session start. Avoids a build/setuptools test dependency.
metrics:
  duration: ~25 min
  completed_date: 2026-05-26
  new_tests: 47 (25 Task 1 + 22 Task 2)
  total_tests: 888 (was 841 baseline)
  installer_test_runtime_sec: 0.13 (mock-only, no real pip)
  subprocess_run_count: 1
---

# Phase 44 Plan 01: Installer flow (two-phase install + upgrade diff) Summary

Two-phase plugin installer + `horus-os plugins` CLI subcommand surface land in a single plan. INSTALL-01 through INSTALL-06 close out. 47 new tests, 888 total in the suite (was 841), 0.13 s installer runtime (all mocked), 0 real pip invocations in CI, ruff clean, single `subprocess.run` chokepoint inside `run_pip`.

## Final shape of installer.py (function-by-function tour)

The five-phase pipeline lives in one orchestrator `install_plugin(spec_str, *, db, ...)` plus a small toolbelt of pure helpers:

| Function | Role |
|----------|------|
| `is_venv()` | `sys.prefix != sys.base_prefix` — Phase 0 gate predicate |
| `run_pip(*args, check=True)` | The **single chokepoint** for every pip invocation. `[sys.executable, "-m", "pip", *args]` with `capture_output=True, text=True`. Every test patches this function instead of `subprocess.run` directly. |
| `pip_freeze_sha256()` | sha256 of `pip freeze` stdout — used pre/post install for the round-trip check |
| `parse_freeze(text)` | `{package_lower: version}` parsed from freeze output. Handles `name==version` AND `name @ url` (editable) lines. |
| `extract_horus_plugin_toml(wheel_path)` | Pulls `horus-plugin.toml` bytes out of the wheel zip. Two search locations: wheel root OR `<dist-name>/horus-plugin.toml`. |
| `read_wheel_record(wheel_path)` | Parses `*.dist-info/RECORD` into `[(filename, hash, size), ...]` triples. |
| `read_wheel_metadata(wheel_path)` | Parses `*.dist-info/METADATA` via `email.parser.BytesParser` → callers iterate `Requires-Dist`. |
| `check_no_pth(wheel_path)` | Refuses any wheel whose RECORD contains a `.pth` entry. Pitfall 4 mode 6. |
| `check_no_downgrade(wheel_path, current_freeze)` | For each `Requires-Dist` in METADATA that targets a HORUS_OS_RUNTIME_DEPS entry, refuses if the specifier excludes the currently-installed version. |
| `detect_sdist(download_dir)` | True iff the dir holds an sdist with no wheel sibling. |
| `render_grant_prompt(spec, stdout)` | Prints the literal prompt scheme: `Grant all (y) / per-capability (a/b/c/...) / refuse (n)?` with DESCRIPTIONS per capability. |
| `prompt_for_grants(spec, *, stdin, stdout, assume_yes)` | Reads the user's decision. `y` → full set. `n` → raises `user_refused_grant`. Partial-letter input that does not cover every requested cap → raises `partial_grant_refused` (INSTALL-05 forbids half-grant state). |
| `install_plugin(spec_str, ...)` | The orchestrator. Walks Phase 0 → Phase A → Phase A.5 → Phase B → Phase C → Phase D → Phase E. Any post-Phase-D failure triggers automatic rollback. |
| `uninstall_plugin(name, *, db)` | `pip uninstall -y` + `DELETE FROM plugins WHERE name=?`. CASCADE removes plugin_capabilities + plugin_status. |
| `update_plugin(name, spec_str, ...)` | Upgrade-diff classifier: classifies unchanged/reduced/expanded by set-equality on capability names. Expanded → `PermissionService.pending_on_upgrade` + re-prompt for ONLY the new caps; refused expansion leaves the old version installed. |
| `grant_capability(name, capability, *, db)` | Wraps `PermissionService.grant(actor='cli', manifest_hash=existing)`. |
| `revoke_capability(name, capability, *, db)` | Symmetric. |

## The four fixture wheels and what each one tests

Under `tests/fixtures/installer/`:

| Template dir | Contains | Tests |
|--------------|----------|-------|
| `wheel_clean/` | manifest with all 4 capabilities, RECORD without `.pth`, METADATA with `Requires-Dist: pydantic>=2.7,<3` | Happy path for capability prompt, freeze round-trip, rollback |
| `wheel_with_pth/` | RECORD containing `horus_example_pth/__path_hack__.pth` | `.pth` refusal |
| `wheel_downgrades_pydantic/` | METADATA with `Requires-Dist: pydantic<2.0` | Runtime-dep downgrade refusal |
| `sdist_only/` | Just `horus-plugin.toml` (packaged as `.tar.gz` not `.whl`) | sdist gate refusal |

`build_fixture_wheels.py` reads the templates and emits real `.whl` / `.tar.gz` files into a session-scoped tmp dir. The `installer_fixture_wheels` fixture in `tests/plugins/conftest.py` builds them lazily on first use and returns the path map.

## subprocess.run chokepoint count

```
$ grep -c "subprocess.run\b" src/horus_os/plugins/installer.py
1
```

The single hit is line 196 inside `run_pip`. Pitfall 4 modes 1-6 (calling bare `pip`, shelling out via `shell=True`, allowing argv string injection, mixing pip configs, missing `--no-build-isolation`, importing the `pip` module) are foreclosed by construction.

## pip freeze sha256 round-trip behavior

Phase B captures `pre_freeze_hash = sha256(run_pip("freeze").stdout)` + a parsed `{package_lower: version}` map. Phase E re-captures `post_freeze_hash` and routes through three branches:

1. **Branch A (success):** `post_hash != pre_hash` AND HORUS_OS_RUNTIME_DEPS rows unchanged → install succeeds, plugins row INSERTed with `status='pending'`, plugin_status row INSERTed.
2. **Branch B (silent rollback):** `post_hash == pre_hash` → `PluginInstallError(reason='silent_rollback')`. pip reported success but nothing landed. Rollback called.
3. **Branch C (runtime dep changed):** post-freeze shows a HORUS_OS_RUNTIME_DEPS entry moved → `PluginInstallError(reason='runtime_dep_changed')`. Rollback called. Test seeds `post=pydantic==2.6.0` vs `pre=pydantic==2.7.0` to exercise this path.

`test_plugin_freeze_roundtrip.py` covers all three branches via scripted-stdout fake `run_pip`.

## Upgrade-diff classifier: which set operation drives the unchanged/reduced/expanded decision

```python
old_caps = {row["capability"] for row in plugin_capabilities WHERE plugin_name AND plugin_version AND state='granted'}
new_caps = {cap.name for cap in new_spec.capabilities}

added   = new_caps - old_caps
removed = old_caps - new_caps

if not added and not removed: outcome = "unchanged"
elif not added and removed:   outcome = "reduced"
else:                         outcome = "expanded"
```

The classifier compares **capability name sets** (not manifest hashes). Hash equality can drift for orthogonal reasons (Pitfall 5: a future extension of `compute_manifest_hash` might fold the version into the hash); set-equality on capability names is the canonical "do we need to re-prompt?" signal.

| Outcome | Behavior |
|---------|----------|
| Unchanged | Re-grant every cap under the new version. No prompt. |
| Reduced | Revoke audit row per surplus old cap under the OLD version. Re-grant survivors under the new version. |
| Expanded | `PermissionService.pending_on_upgrade` stages the expanded diff. Re-prompt for ONLY the new caps. On `y` → grant the new caps + re-grant the unchanged ones. On `n` → `PluginInstallError(reason='user_refused_grant')`, old version stays installed, old grants stay granted (no mutation). |

## All requirements (INSTALL-01..06) mapped to test files

| Req | What it asserts | Test files |
|-----|-----------------|------------|
| INSTALL-01 | `subprocess.run([sys.executable, "-m", "pip", ...])` via single chokepoint + `--require-virtualenv` gate + `--allow-system-python` escape hatch | `test_installer_venv_refusal.py` (3 tests) |
| INSTALL-02 | Phase A `pip download --no-deps` → Phase B validate + capability prompt → Phase D `pip install` only on grant; refusal aborts cleanly | `test_installer_capability_prompt.py` (8 tests incl. `test_refuse_at_prompt_blocks_phase_d`) |
| INSTALL-03 | sdist default refusal + `--allow-sdist` escape; `.pth` in RECORD refusal | `test_installer_sdist_refusal.py` (2 tests), `test_installer_pth_refusal.py` (3 tests) |
| INSTALL-04 | `pip freeze` sha256 captured pre/post; runtime-dep downgrade refused; silent-rollback + runtime-dep-changed branches | `test_installer_downgrade_refusal.py` (4 tests), `test_plugin_freeze_roundtrip.py` (5 tests), `test_installer_rollback.py` (1 test) |
| INSTALL-05 | Grant prompt with plain-English descriptions; refuse → abort with no half-grant state | `test_installer_capability_prompt.py` (`test_prompt_*` series) |
| INSTALL-06 | All 9 subcommands (install/uninstall/list/info/enable/disable/update/grant/revoke); update runs upgrade-diff | `test_cli_plugins_subcommands.py` (14 tests), `test_horus_os_plugins_list.py` (4 tests), `test_installer_upgrade_diff.py` (4 tests) |

## Threat-model items mitigated

| Threat ID | What enforces it |
|-----------|-------------------|
| T-44-01 (Tampering: subprocess.run) | `run_pip` helper in `installer.py:196` is the single chokepoint. `grep -c "subprocess.run\b"` returns 1. |
| T-44-02 (EoP: venv check) | `is_venv()` predicate + `install_plugin` Phase 0 gate. Test: `test_installer_venv_refusal.py::test_venv_refused_outside_venv`. |
| T-44-03 (EoP: sdist refusal) | `detect_sdist(download_dir)` + Phase A.5 gate. Test: `test_installer_sdist_refusal.py::test_sdist_only_refused_by_default`. |
| T-44-04 (EoP: .pth refusal) | `check_no_pth(wheel_path)` + RECORD parser. Test: `test_installer_pth_refusal.py::test_install_refuses_wheel_with_pth`. |
| T-44-05 (Tampering: runtime-dep downgrade) | `check_no_downgrade(wheel_path, current_freeze)` + `packaging.requirements.Requirement.specifier.contains()`. Test: `test_installer_downgrade_refusal.py::test_install_refuses_downgrade_wheel`. |
| T-44-06 (EoP: silent capability expansion on upgrade) | `update_plugin` classifier + `PermissionService.pending_on_upgrade`. Test: `test_installer_upgrade_diff.py::test_update_expanded_prompts_and_grants_on_accept`. |
| T-44-08 (DoS: partial-failure rollback) | `_rollback(db, name)` called from any Phase D+ exception path. Test: `test_installer_rollback.py::test_phase_e_failure_triggers_rollback` (asserts pre-install freeze sha256 equals post-rollback sha256). |
| T-44-09 (Repudiation: grant audit log) | Every `PermissionService.grant/revoke/pending_on_upgrade` call from installer writes a row to `plugin_capability_grants_log` with `actor='cli'`. Test: `test_installer_capability_prompt.py::test_grant_all_inserts_audit_rows`. |
| T-44-10 (Spoofing: actor field) | CHECK constraint on `plugin_capability_grants_log.actor IN ('cli','dashboard','system')`. Phase 43's `test_permission_service.py::test_log_actor_check_constraint` already covers it; Phase 44's installer is hard-coded to pass `actor='cli'`. |
| T-44-07, T-44-11 (Information Disclosure) | Accepted in threat register; the prompt + error messages render closed-catalog content only. |
| T-44-12 (Spoofing: typosquatted PyPI spec) | Accepted; capability grant prompt is the last line of defense. Documented for Phase 47 `docs/PLUGIN-SECURITY.md`. |

## Test count delta vs Phase 43 baseline

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| `tests/plugins/` | 120 | 167 | +47 |
| Full repo | 841 | 888 | +47 |
| Installer subset runtime | n/a | 0.13 s | (no real pip in CI) |

The 47 new tests break down as:
- 25 Task 1 tests across 7 files (installer behavior + helpers + rollback + freeze round-trip)
- 22 Task 2 tests across 3 files (CLI parse routing + list output shape + upgrade-diff classifier)

## Deferred items

**Real `pip install` in CI** — deliberate per the plan's "real install lands in Phase 49 via TEST-20" note. Every installer test path mocks `run_pip`, so the suite stays sub-second on a developer laptop. The 3-OS install-smoke gate in Phase 49 will exercise the actual `pip download` + `pip install` path against a published wheel (likely the Phase 48 `horus-os-example-plugin`).

**`pip install --dry-run --report -` JSON output** — the Plan 44 ROADMAP entry mentions parsing pip's JSON report for downgrade detection. Implementation in this commit uses a simpler path: parse the wheel's own `Requires-Dist` lines via `packaging.requirements.Requirement` and compare against the current `pip freeze`. This is more deterministic (doesn't depend on which pip version is installed) and gives the same coverage for HORUS_OS_RUNTIME_DEPS. The `--dry-run --report` path can be revisited in Phase 49 if integration testing surfaces missed downgrade vectors.

**`fastapi` / `anthropic` / `google-genai` downgrade gates** — out of scope for HORUS_OS_RUNTIME_DEPS in v0.5 because those packages are optional extras (`[dashboard]` / `[anthropic]` / `[gemini]`). A user without `[dashboard]` installed has no fastapi at all; a plugin that requires fastapi<0.100 would just install fastapi at its preferred version. When the v0.6 milestone considers moving them to base deps, add them to `HORUS_OS_RUNTIME_DEPS` in `installer.py`.

## Phase 45 handoff notes

Phase 44 writes the following rows on a successful install — Phase 45's `/api/plugins` and `/plugins` dashboard tab can consume them directly with no schema additions:

| Table | When written |
|-------|--------------|
| `plugins` | INSERTed after Phase C grant + before Phase D install (so a Phase D failure can DELETE-on-rollback) |
| `plugin_capabilities` | One row per granted capability, via `PermissionService.grant(actor='cli')` |
| `plugin_capability_grants_log` | One audit row per grant + one per revoke + one per pending_on_upgrade transition |
| `plugin_status` | INSERTed after Phase E success with `status='pending'`; the FastAPI lifespan flips to `loaded` or `error` on next boot |

Phase 45's `_cmd_info` example in this plan's `plugins_cmd.py` already shows the JOIN shape for `info <name>` (plugins + plugin_capabilities + plugin_capability_grants_log).

## Phase 49 handoff notes

The TEST-20 three-OS install-smoke gate in Phase 49 should exercise:
1. `horus-os plugins install <example-plugin-spec>` against the Phase 48 `horus-os-example-plugin` package published to TestPyPI
2. Verify the plugin's tool shows up via `horus-os run <prompt>` after restart
3. `horus-os plugins update <name> <new-version-spec>` against a v0.2 of the example plugin that ADDS a capability — assert the re-prompt fires
4. `horus-os plugins uninstall <name>` returns the venv to a clean state

The fake-pip suite in Phase 44 covers the unit-level correctness of every gate; Phase 49 exercises the actual subprocess + pip + entry-point integration.

## Self-Check: PASSED

- [x] `src/horus_os/plugins/installer.py` exists (verified via Read)
- [x] `src/horus_os/cli/plugins_cmd.py` exists (verified via Read)
- [x] All 4 fixture wheel directories exist
- [x] All 10 new test files in `tests/plugins/` exist
- [x] Commit `f31c627` (Task 1) present in git log
- [x] Commit `4cb186d` (Task 2) present in git log
- [x] `grep -c "subprocess.run\b" src/horus_os/plugins/installer.py` = 1
- [x] `python -m pytest -q` = 888 passed
- [x] `python -m ruff check .` = clean
- [x] `python -m horus_os plugins --help` lists all 9 subcommands
