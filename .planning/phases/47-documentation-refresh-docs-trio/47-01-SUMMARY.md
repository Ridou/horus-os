---
phase: 47-documentation-refresh-docs-trio
plan: 01
subsystem: plugins-docs
tags: [docs, plugins, v0.5, REL-12, REFERENCE-02, Pitfall-12]
requires: [Phase 46 (Pitfall 12 docs-drift test substrate), Phase 41 (MANIFEST_V1_SCHEMA), Phase 44 (installer.render_grant_prompt)]
provides:
  - docs/PLUGINS.md (plugin-author guide; 8 ordered sections)
  - docs/PLUGIN-SECURITY.md (threat model + trust contract + out-of-scope + practices; REL-12 literal sentence)
  - docs/MIGRATION-v0.4-to-v0.5.md (v0.4 → v0.5 upgrade guide; mirrors v0.3→v0.4 shape)
  - docs/manifest-v1.schema.json (JSON-Schema mirror of MANIFEST_V1_SCHEMA; Phase 49 release-gate target)
  - scripts/build_manifest_schema.py (idempotent regenerator)
  - tests/docs/ (4 docs-test files; 18 new tests)
  - Phase 46 Pitfall 12 docs-drift gate auto-activated (no test-file edit)
  - README.md "What is new in v0.5" section + 3 Documents bullets
  - CHANGELOG.md [0.5.0] - YYYY-MM-DD draft (Added / Changed / Migration)
  - installer.py render_grant_prompt links to docs/PLUGIN-SECURITY.md
affects: [src/horus_os/plugins/installer.py (one-line extension), README.md (extended), CHANGELOG.md (extended)]
tech-stack:
  added: [pydantic.BaseModel.model_json_schema() runtime export → docs/manifest-v1.schema.json]
  patterns: [docs source-of-truth fixture embedding; closed-enum mirror in markdown table; byte-stable JSON canonicalization for docs-drift CI gate]
key-files:
  created:
    - docs/PLUGINS.md
    - docs/PLUGIN-SECURITY.md
    - docs/MIGRATION-v0.4-to-v0.5.md
    - docs/manifest-v1.schema.json
    - scripts/build_manifest_schema.py
    - tests/docs/__init__.py
    - tests/docs/test_plugins_md_anatomy.py
    - tests/docs/test_plugin_security_threat_sentence.py
    - tests/docs/test_migration_v04_v05_schema_commands.py
    - tests/docs/test_manifest_schema_json_in_sync.py
  modified:
    - README.md (added "What is new in v0.5" section + 3 Documents bullets; v0.3.0 badge preserved for Phase 50)
    - CHANGELOG.md ([Unreleased] replaced by [0.5.0] - YYYY-MM-DD draft)
    - src/horus_os/plugins/installer.py (one literal-string write in render_grant_prompt referencing docs/PLUGIN-SECURITY.md)
decisions:
  - "docs/PLUGIN-SECURITY.md uses an in-prose REL-12 sentence anchored inside ## Threat model (not a code fence) so the grep gate counts prose and not comments"
  - "The build script lives at scripts/build_manifest_schema.py rather than as a pyproject.toml entry point because v0.5 has not yet defined a maintainer-CLI surface; Phase 49's release_gate.py will consume the file directly"
  - "Phase 46's Pitfall 12 test file is NOT edited — its pytest.skip branch auto-clears when the docs file lands; this preserves the Phase 46 freeze and demonstrates the conditional-skip pattern as forward-compat"
metrics:
  duration: ~25 minutes (single agent, no replans)
  completed: 2026-05-26
  tests_added: 18 (4 docs-test files, plus Phase 46 Pitfall 12 docs-drift now activating instead of skipping)
  full_suite_before: 961 collected (1 SKIPPED for docs-drift gate)
  full_suite_after: 977 passed + 2 SKIPPED (the 2 are pre-existing --run-installer-e2e tier-3 venv tests)
  deviations: 0
---

# Phase 47 Plan 01: Documentation refresh (docs trio) Summary

Ships the v0.5 documentation trio (`docs/PLUGINS.md` plugin-author guide, `docs/PLUGIN-SECURITY.md` threat model, `docs/MIGRATION-v0.4-to-v0.5.md` upgrade guide), the JSON-Schema release-gate target (`docs/manifest-v1.schema.json`), its idempotent regenerator (`scripts/build_manifest_schema.py`), and 18 new tests across 4 docs-test files. Activates the Phase 46 Pitfall 12 docs-drift gate without editing the Phase 46 test file. Closes REFERENCE-02 and REL-12.

## One-liner

Three plugin docs files + JSON-Schema mirror of MANIFEST_V1_SCHEMA + idempotent regenerator + 18 docs tests, with the Phase 46 Pitfall 12 docs-drift CI gate auto-activating without test-file edit.

## What shipped

### Documentation files

| File | Lines | Purpose |
| --- | --- | --- |
| `docs/PLUGINS.md` | 138 | Plugin-author guide: 8 ordered sections covering what-is-a-plugin, anatomy of `horus-plugin.toml` (embedded verbatim from `tests/fixtures/manifests/manifest_v1_full.toml`), capability catalog (markdown table mirroring every `Capability` enum member with its verbatim `DESCRIPTIONS` text), lifecycle hooks (`start(ctx)` + `stop()` + 2.0-second `asyncio.wait_for` bound), testing your plugin (three-tier fixtures from Phase 46), walkthrough of the reference plugin (forward-reference to Phase 48), public API surface (`horus_os.plugins.api` re-exports as a markdown table), distributing your plugin (entry points + filesystem). |
| `docs/PLUGIN-SECURITY.md` | 46 | Threat model + trust contract + out-of-scope defenses + recommended user practices. Contains the literal REL-12 sentence "plugins execute in the horus-os Python process" inside a `## Threat model` section. Under the 400-line one-sitting-read budget (ROADMAP §47 SC3). |
| `docs/MIGRATION-v0.4-to-v0.5.md` | 182 | Upgrade guide. Mirrors `docs/MIGRATION-v0.3-to-v0.4.md` shape: TL;DR, What is new, Schema migration v5→v6 (three new tables + two NULLABLE columns + one index), New base dependencies (`pydantic>=2.7,<3` + `packaging>=24.0`), How to roll back (`--disable-all-plugins`), Breaking change scan ("There are no breaking changes to v0.4 features"), Verification (`PRAGMA user_version` → `6`). |
| `docs/manifest-v1.schema.json` | 130 | JSON-Schema mirror of `MANIFEST_V1_SCHEMA.model_json_schema()`. Canonical `json.dumps(schema, indent=2, sort_keys=True) + "\n"`. The Phase 49 release-gate diff target. |

### Build script

`scripts/build_manifest_schema.py` (51 lines, executable shebang) is the idempotent regenerator. Stdlib-only after the `horus_os.plugins.manifest` import. Running the script twice in a row produces no diff (`git diff --quiet docs/manifest-v1.schema.json` succeeds). Module docstring documents the regeneration command for plugin authors editing the schema.

### Tests

| File | Tests | What it asserts |
| --- | --- | --- |
| `tests/docs/test_plugins_md_anatomy.py` | 4 | (1) PLUGINS.md exists. (2) It embeds `tests/fixtures/manifests/manifest_v1_full.toml` verbatim. (3) Every `Capability` enum member's dotted-key + verbatim `DESCRIPTIONS[cap]` text appears in PLUGINS.md. (4) The 8 canonical section headings appear as a contiguous subsequence. |
| `tests/docs/test_plugin_security_threat_sentence.py` | 5 | (1) PLUGIN-SECURITY.md exists. (2) `## Threat model` heading is present (regex). (3) The literal REL-12 sentence "plugins execute in the horus-os Python process" is present. (4) File is ≤400 lines. (5) `src/horus_os/plugins/installer.py` references `docs/PLUGIN-SECURITY.md`. |
| `tests/docs/test_migration_v04_v05_schema_commands.py` | 6 | (1) MIGRATION exists. (2) Contains `PRAGMA user_version`. (3) Contains both base-dep version pins. (4) Contains `--disable-all-plugins`. (5) Contains "no breaking changes" (case-insensitive). (6) `horus_os.storage.SCHEMA_VERSION == 6` (cross-link verifies the doc's expected output matches reality). |
| `tests/docs/test_manifest_schema_json_in_sync.py` | 3 | (1) `docs/manifest-v1.schema.json` exists. (2) Its parsed JSON equals `MANIFEST_V1_SCHEMA.model_json_schema()` semantically. (3) Its byte content equals the canonical canonicalization byte-for-byte. |

Total: 18 new tests across 4 files + 1 `__init__.py` package marker.

### Phase 46 Pitfall 12 gate auto-activation

`tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py::test_docs_drift_against_committed_schema_file` was authored in Phase 46 with a `pytest.skip` branch guarded by `if not DOCS_SCHEMA_PATH.is_file()`. When Phase 47 shipped `docs/manifest-v1.schema.json`, the file-existence check started returning True, the skip branch was no longer taken, and the assertion runs (and passes — the file is byte-identical to the runtime schema). **No edit to the Phase 46 test file is required and none was made.** This pattern preserves the Phase 46 freeze and demonstrates conditional-skip-on-missing-artifact as a forward-compat lever.

### README + CHANGELOG extensions

- `README.md` gained a new `## What is new in v0.5` section (one paragraph naming the plugin system + 3 doc-link bullets) after the existing `## What is new in v0.3` section. The `## Documents` section gained three new bullets in alphabetical order: `docs/MIGRATION-v0.4-to-v0.5.md`, `docs/PLUGIN-SECURITY.md`, `docs/PLUGINS.md`. The v0.3.0 release badge on line 6 stays unchanged (Phase 50 bumps it).
- `CHANGELOG.md` had its `[Unreleased]` section replaced by a draft `[0.5.0] - YYYY-MM-DD` heading. The `YYYY-MM-DD` placeholder is intentional — Phase 50 stamps the actual release date. Three subsections per Keep-a-Changelog 1.1.0: **Added** (11 bullets: plugin manifest contract, two-phase installer, default-deny capability grants, bounded lifecycle, `/plugins` dashboard, per-plugin observability, `horus-os plugins` CLI, `--disable-all-plugins` boot flag, three-tier test fixtures, 12-pitfall suite, reference plugin forward-reference, three new docs files, `docs/manifest-v1.schema.json`), **Changed** (one bullet: `pydantic>=2.7,<3` + `packaging>=24.0` added to `[project.dependencies]`), **Migration** (one bullet: v5→v6 schema migration shape + rollback path).

### Installer extension

`src/horus_os/plugins/installer.py::render_grant_prompt` (lines 410-423) gained a single literal-string `stdout.write` after the per-capability loop and before the final decision prompt: "See docs/PLUGIN-SECURITY.md for the trust model before granting capabilities." Existing prompt tests (7 tests in `tests/plugins/test_installer_capability_prompt.py`) still pass byte-identical because they assert substring-presence of descriptions and the "Grant all (y) / per-capability" decision line, not absence-of-additional-lines.

## Verification summary

- `pytest tests/docs/ -v` → 18 passed.
- `pytest tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py -v` → 4 passed (was 3 passed + 1 SKIPPED before Phase 47).
- `pytest -q` (full suite) → 977 passed + 2 SKIPPED (was 958 passed before Phase 46; baseline at start of Phase 47 was 961 collected with 1 SKIPPED for the Pitfall 12 gate). Delta: +16 passes = 18 new docs tests minus 2 pre-existing Pitfall 12 tests that were already counted.
- `ruff check .` → clean.
- `wc -l docs/PLUGIN-SECURITY.md` → 46 (≤400 budget).
- `grep -c "plugins execute in the horus-os Python process" docs/PLUGIN-SECURITY.md` → 1.
- `python scripts/build_manifest_schema.py && git diff --quiet docs/manifest-v1.schema.json` → empty diff (idempotent regeneration).

## Decisions

- **In-prose REL-12 sentence, not code-fenced.** The sentence "plugins execute in the horus-os Python process" lives inside a prose paragraph under the `## Threat model` section. This makes a `grep -c` over the doc count the canonical occurrence (1) and not any accidental in-comment duplicate. The test pins the substring's presence; the prose anchor pins the user-facing intent.
- **scripts/build_manifest_schema.py, not a CLI subcommand.** The regenerator lives in `scripts/` because v0.5 has not yet defined a maintainer-CLI surface. Phase 49's `release_gate.py` will consume the file directly via a JSON read; the regenerator is a one-shot dev-loop tool, not a user-facing command.
- **Phase 46 test file unedited.** The Pitfall 12 docs-drift test ships in Phase 46 with a `pytest.skip` guarded by file-absence; shipping the file in Phase 47 flips the skip without any test-file edit. This is by design — Phase 46 is frozen, the conditional-skip pattern lets the gate self-activate. Future phases can use the same pattern for forward-referenced artifacts.
- **CHANGELOG date placeholder.** `[0.5.0] - YYYY-MM-DD` keeps the placeholder so Phase 50 owns the date stamp. Keep-a-Changelog 1.1.0 conformant once stamped.

## Deviations from Plan

None. The plan executed exactly as written. The seven gates in `<verify>` (file existence, threat sentence, installer linkage, schema sync, ≤400 lines, ruff clean, idempotency) all passed on first try.

## Pointers to next phases

- **Phase 48** (`/gsd-plan-phase 48`) ships `examples/horus-os-example-plugin/` as the reference implementation of the four scenarios enumerated in `docs/PLUGINS.md` § Walkthrough. Phase 48 also lands the TEST-21 ruff custom rule that pins the reference plugin's public-API import surface to `horus_os.plugins.api` only.
- **Phase 49** (`/gsd-plan-phase 49`) extends `scripts/release_gate.py` to diff `docs/manifest-v1.schema.json` against the runtime `MANIFEST_V1_SCHEMA` at release time. The Phase 47 build script + Phase 46 docs-drift test together form the runtime substrate; Phase 49 is the CI hook.
- **Phase 50** (`/gsd-plan-phase 50`) bumps the README v0.3.0 badge and stamps `YYYY-MM-DD` → actual release date in CHANGELOG `[0.5.0]`.

## Self-Check: PASSED

- docs/PLUGINS.md: FOUND
- docs/PLUGIN-SECURITY.md: FOUND
- docs/MIGRATION-v0.4-to-v0.5.md: FOUND
- docs/manifest-v1.schema.json: FOUND
- scripts/build_manifest_schema.py: FOUND
- tests/docs/__init__.py: FOUND
- tests/docs/test_plugins_md_anatomy.py: FOUND
- tests/docs/test_plugin_security_threat_sentence.py: FOUND
- tests/docs/test_migration_v04_v05_schema_commands.py: FOUND
- tests/docs/test_manifest_schema_json_in_sync.py: FOUND
- Commit c3f399b (Task 1): FOUND
- Commit 5afc54f (Task 2): FOUND
