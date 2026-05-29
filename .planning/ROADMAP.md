# Roadmap: horus-os

## Milestones

- [x] **v0.1 Foundation** (Phases 01-11), shipped 2026-05-23 as v0.1.0. CLI + web chat, Anthropic + Gemini, one agent, six tools, full memory layer, 3-OS install gate, first public release.
- [x] **v0.2 Multi-Agent + Streaming** (Phases 12-21), shipped 2026-05-23 as v0.2.0. Named agent profiles, coordinator-to-sub-agent delegation, provider streaming on both CLI and dashboard, adapter plugin interface.
- [x] **v0.3 Adapter Ecosystem** (Phases 22-31), shipped 2026-05-24 as v0.3.0. Discord, Slack, email, and calendar adapters on top of the v0.2 plugin contract, plus adapter lifecycle hooks and dashboard adapter management.
- [x] **v0.4 Observability** (Phases 32-39), shipped 2026-05-26 as v0.4.0. Local-first cost, latency, and tool-reliability instrumentation. New `llm_calls` + `tool_invocations` child tables, bundled `pricing.json`, `/observability` dashboard tab, `horus-os usage` CLI subcommand, opt-in OpenTelemetry exporter behind a `[otel]` extra.
- [x] **v0.5 Plugin System** (Phases 40-50), shipped 2026-05-27 as v0.5.0. Third-party plugin runtime: TOML manifest contract, entry-point + filesystem discovery, default-deny capability grants, two-phase `pip install` flow, in-process loader with bounded lifecycle and failure isolation, `/plugins` dashboard tab, per-plugin observability, reference plugin, additive v5→v6 schema migration.
- [ ] **v0.6 Contribution Gate** (Phases 51-59), in planning. Trust + supply-chain + contributor-experience substrate that makes "outside PRs welcome" safe: keyless sigstore signing on wheels + sdists + SBOMs + tags, CycloneDX 1.6 SBOMs against installed-from-wheel venvs, pip-audit dual-mode on every PR, Dependabot for pip + github-actions with security-updates explicitly un-grouped, every action `uses:` SHA-pinned, `pull_request_target` forbidden by default, contributor docs and SECURITY.md disclosure-flow refreshed, release-gate extended from 8 to 13 checks, soft launch with invited contributors before the atomic gate flip at v0.6.0 ship.

## Phases

<details>
<summary>v0.1 Foundation (Phases 01-11) - SHIPPED 2026-05-23</summary>

- [x] **Phase 01: Repo scaffold and CI** (completed 2026-05-23)
- [x] **Phase 02: Agent runtime core** (completed 2026-05-23)
- [x] **Phase 03: Persistence layer** (completed 2026-05-23)
- [x] **Phase 04: Tool registry** (completed 2026-05-23)
- [x] **Phase 05: Memory layer, read path** (completed 2026-05-23)
- [x] **Phase 06: Memory layer, write path** (completed 2026-05-23)
- [x] **Phase 07: CLI surface** (completed 2026-05-23)
- [x] **Phase 08: Web chat and dashboard** (completed 2026-05-23)
- [x] **Phase 09: Setup wizard with API key onboarding** (completed 2026-05-23)
- [x] **Phase 10: Three-OS install verification** (completed 2026-05-23)
- [x] **Phase 11: First public release** (completed 2026-05-23)

</details>

<details>
<summary>v0.2 Multi-Agent + Streaming (Phases 12-21) - SHIPPED 2026-05-23</summary>

- [x] **Phase 12: Agent profile model and schema migration** (completed 2026-05-23)
- [x] **Phase 13: Multi-agent orchestration runtime** (completed 2026-05-23)
- [x] **Phase 14: Streaming response support** (completed 2026-05-23)
- [x] **Phase 15: CLI multi-agent surface** (completed 2026-05-23)
- [x] **Phase 16: Dashboard multi-agent view and streaming chat** (completed 2026-05-23)
- [x] **Phase 17: Adapter plugin interface** (completed 2026-05-23)
- [x] **Phase 18: Documentation and examples refresh** (completed 2026-05-23)
- [x] **Phase 19: Test surface expansion** (completed 2026-05-23)
- [x] **Phase 20: Three-OS install verification (v0.2)** (completed 2026-05-23)
- [x] **Phase 21: v0.2.0 release** (completed 2026-05-23)

</details>

<details>
<summary>v0.3 Adapter Ecosystem (Phases 22-31) - SHIPPED 2026-05-24</summary>

- [x] **Phase 22: Adapter lifecycle hooks** (completed 2026-05-23)
- [x] **Phase 23: Discord adapter** (completed 2026-05-24)
- [x] **Phase 24: Slack adapter** (completed 2026-05-24)
- [x] **Phase 25: Email adapter** (completed 2026-05-24)
- [x] **Phase 26: Calendar adapter** (completed 2026-05-24)
- [x] **Phase 27: Dashboard adapter management** (completed 2026-05-24)
- [x] **Phase 28: Documentation and examples refresh** (completed 2026-05-24)
- [x] **Phase 29: Test surface expansion** (completed 2026-05-24)
- [x] **Phase 30: Three-OS install verification (v0.3)** (completed 2026-05-24)
- [x] **Phase 31: v0.3.0 release** (completed 2026-05-24)

</details>

<details>
<summary>v0.4 Observability (Phases 32-39) - SHIPPED 2026-05-26</summary>

- [x] **Phase 32: Schema migration, persistence skeleton, v0.3 baseline** (completed 2026-05-26)
- [x] **Phase 33: Capture at the runner + SSE branch** (completed 2026-05-26)
- [x] **Phase 34: Pricing table and cost annotation** (completed 2026-05-26)
- [x] **Phase 35: Query module and read APIs** (completed 2026-05-26)
- [x] **Phase 36: Observability dashboard tab** (completed 2026-05-26)
- [x] **Phase 37: `horus-os usage` CLI subcommand** (completed 2026-05-26)
- [x] **Phase 38: OpenTelemetry adapter** (completed 2026-05-26)
- [x] **Phase 39: Three-OS gate, release, migration doc** (completed 2026-05-26)

</details>

### v0.5 Plugin System (Phases 40-50)

**Milestone Goal:** Turn horus-os from "built-in tools and adapters only" into "anyone can ship a horus-os plugin." A TOML manifest contract, entry-point + filesystem discovery, default-deny capability grants persisted in SQLite, a `pip`-wrapped two-phase installer, an in-process loader with bounded lifecycle and failure isolation, a `/plugins` dashboard tab, per-plugin observability rolling up on the v0.4 ObservationBus, one reference plugin, and an additive v5→v6 schema migration. Anti-pattern explicitly rejected: OS sandboxing, hosted catalog, hot-reload, default-allow grants. Trust model: "you `pip install`-ed it; the manifest declares what it touches; you grant before it runs."

**Execution Order:** 40 → 41 → 42 → 43 → (44 ∥ 45) → 46 → 47 → 48 → 49 → 50. Mostly sequential because each phase consumes prior phase's substrate. The only legitimate parallel opportunity is Phase 44 (installer CLI) and Phase 45 (dashboard tab + observability extension): both consume the grant table + registry shipped in Phase 43 without depending on each other (mirrors v0.4's Phase 36 ∥ 37).

**Six constraints carried from research that ride across phases:**
1. **`plugins/api.py` is the SINGLE public API surface** (Pitfall 8). Defined in Phase 41, enforced by a ruff custom rule in Phase 48 against the reference plugin (`from horus_os` imports outside `horus_os.plugins.api` fail CI).
2. **Manifest hash drives re-prompt** (PERMISSION-02). `grant_hash = sha256(capabilities_set)`; manifest-hash diff on upgrade flips previously-granted `plugin_capabilities` rows to `state="pending"`. Lands in Phase 43.
3. **Bounded `asyncio.wait_for(start, timeout=2.0)`** matches v0.4 Phase 38 OtelAdapter shape (`force_flush(timeout_millis=2000)` precedent). Literal `timeout=2.0` appears in Phase 43's success criteria as a verifiable artifact.
4. **Two-phase install** for INSTALL-02: phase A `pip download --no-deps` → phase B validate manifest + capability prompt → phase C `pip install --no-deps --no-build-isolation <wheel>`. The literal three-step sequence is a Phase 44 success criterion.
5. **v5→v6 migration is additive only** (MIG-05). Three new tables (`plugins`, `plugin_capabilities`, `plugin_status`) + two NULLABLE columns (`llm_calls.plugin_name`, `tool_invocations.plugin_name`) + one index (`idx_tool_invocations_plugin`). Lands in Phase 41. v0.4 fixture round-trip is mandatory in Phase 41 and re-asserted in Phase 49's release gate.
6. **Two new direct deps** in `pyproject.toml` base `[project.dependencies]` (not an optional extra): `pydantic>=2.7,<3` and `packaging>=24.0`. Lands in Phase 41. v0.4 shipped with `dependencies = []`; this is the deliberate first runtime-dep addition called out in REL-10.

- [x] **Phase 40: v0.5 baseline artifact** - Mirror of v0.4 Phase 32. Commit `tests/perf/v0_4_baseline.json` snapshotting v0.4 cold-start + zero-plugin discovery overhead on the 3-OS matrix so Phase 42's <100ms cold-start benchmark has a pinned reference. Pure infrastructure; no behavior change for users. (completed 2026-05-26)
- [x] **Phase 41: Manifest schema, public API, persistence migration** - Define `PluginSpec`, `MANIFEST_V1_SCHEMA` (pydantic v2), `plugins/api.py` single-public-surface module, `capability_catalog.py` closed enum. Land v5→v6 additive SQLite migration (three new tables + two NULLABLE plugin_name columns + one index). Add `pydantic>=2.7,<3` and `packaging>=24.0` to base `[project.dependencies]`. v0.4 fixture round-trip green. (completed 2026-05-26)
- [x] **Phase 42: Discovery + loading + failure isolation** - `plugins/discovery.py` (entry-points + filesystem walk with DiscoveryError side-channel), `plugins/loader.py` (CapabilityGuard pass-through stub + rollback-on-error), `plugins/registry.py` (mirrors AdapterRegistry shape, persists to plugins + plugin_status tables). `pkg_resources` banned via ruff banned-api rule + source-tree grep test (two-layer guard). Cold-start median 0.056ms (darwin/3.12) vs 100ms threshold. Five broken-plugin fixtures (bad_toml → discover, schema_fail → validate, import_raises → load, tool_raises_registration → load with rollback, healthy → loaded) prove the isolation guarantee. FastAPI lifespan sets `app.state.plugin_registry`. (completed 2026-05-26)
- [x] **Phase 43: Permission model + bounded lifecycle** - `plugins/permissions.py` with `PermissionGate` + `CapabilityGuard` + `PermissionService`; helper shims (`ctx.filesystem`, `ctx.secrets`, `ctx.net`) with path-escape defense; per-version grants keyed on `(plugin_name, plugin_version, capability)` AND tied to `manifest_hash`; `DEFAULT_GRANT_POLICY = "deny"` constant; bounded `asyncio.wait_for(start, timeout=2.0)` / `asyncio.wait_for(stop, timeout=2.0)` lifecycle wrappers in FastAPI lifespan (5s-sleep adapter cut in 2.21s wall clock); `--disable-all-plugins` CLI escape hatch + `HORUS_OS_DISABLE_PLUGINS` env var + `PluginRegistry.enable/disable/is_enabled`. `plugin_capability_grants_log` audit table (additive within v6). 120 plugin tests green. (completed 2026-05-26)
- [x] **Phase 44: Installer flow (two-phase install + upgrade diff)** - `cli/plugins_cmd.py` with `install/uninstall/list/info/enable/disable/update/grant/revoke`. Two-phase install via `subprocess.run([sys.executable, "-m", "pip", ...])` chokepoint (`grep -c subprocess.run` returns 1). Refuse install outside venv (`--allow-system-python` escape hatch), refuse sdists by default (`--allow-sdist`), refuse wheels with `.pth` in RECORD, refuse runtime-dep downgrade. First-install grant prompt with plain-English capability descriptions. Upgrade-diff classifier (unchanged/reduced/expanded by set-equality on capability names) routes through PermissionService.pending_on_upgrade on expansion. 47 new tests (25 installer + 22 CLI/upgrade). Suite: 888 passing. (completed 2026-05-26)
- [x] **Phase 45: REST API + `/plugins` dashboard tab + per-plugin observability** - Six `/api/plugins` routes (list/get/enable/disable/grant/revoke) via dedicated APIRouter; per-request `Database(cfg.db_path)` pattern; T-45-01 mitigation hard-codes `actor='dashboard'` on grant/revoke. `/api/observability/plugins?since=7d|30d` returns per-plugin rollup with NULL plugin_name bucketed under literal `'horus-os core'`; Pitfall 10 (n<10 → null) + Pitfall 11 (NULL cost stays null, never 0) honored. `/plugins` dashboard tab with card-style tiles (status badge, declared tool/adapter chips, granted/pending capability chips with inline grant/revoke buttons, author + safeUrl-gated homepage/issue_tracker links). Fourth `obs-panel` "by plugin" in `/observability`. DASH-5-03 sanitation: every manifest-sourced string flows through `escapeHtml` / `textContent`; `safeUrl` helper gates URLs on `startsWith('http://')`/`startsWith('https://')`. 28 new tests (6 observability + 17 routes + 5 dashboard/sanitation). Suite: 916 passing. v0.4 byte-identity contract preserved. (completed 2026-05-26)
- [x] **Phase 46: Test surface (three-tier fixtures + pitfall regression suite)** - Tier 1: `make_synthetic_plugin` + `make_fake_entry_point` helpers in `tests/plugins/conftest.py`. Tier 2: existing Phase 42 `fake_plugin_entry_points` monkeypatch fixture (byte-identical). Tier 3: session-scoped `clean_venv` fixture in new top-level `tests/conftest.py`; opt-in via `--run-installer-e2e` flag + `@pytest.mark.installer_e2e` marker registered in `pyproject.toml`. `tests/test_plugin_pitfalls/` directory with 12 pitfall regression test files mapping 1:1 to PITFALLS.md by number (42 new tests, 3 tier-3 skipped on default invocation). Full suite 958 passing in 27s wall clock; pitfalls + plugins suite in 7.6s — well under the 90s budget Phase 49 will gate against. (completed 2026-05-26)
- [x] **Phase 47: Documentation refresh (docs trio)** - `docs/PLUGINS.md` (plugin-author guide: manifest + capabilities + lifecycle + testing + walkthrough of the four reference-plugin scenarios). `docs/PLUGIN-SECURITY.md` with explicit "Threat model" section containing the literal sentence "plugins execute in the horus-os Python process" and enumerating the capability-grant trust contract. `docs/MIGRATION-v0.4-to-v0.5.md` covering v5→v6 schema + the two new direct deps. Plus `docs/manifest-v1.schema.json` (Phase 49 release-gate target), `scripts/build_manifest_schema.py` (idempotent regenerator), 4 docs-test files (18 new tests). The previously-skipped Phase 46 Pitfall 12 docs-drift test auto-activates. README + CHANGELOG extended. Installer grant prompt links to PLUGIN-SECURITY.md. (completed 2026-05-26)
- [x] **Phase 48: Reference plugin (`horus-os-example-plugin`)** (completed 2026-05-26) - `examples/horus-os-example-plugin/` shipped as a separate package with its own `pyproject.toml` and `horus-plugin.toml`. Demonstrates four scenarios: simple tool + capability check, config-reading tool, lifecycle adapter with start/stop, plugin registering both tool + adapter. CI lint rejects any `from horus_os` import that doesn't come from `horus_os.plugins.api` (TEST-21, ruff `flake8-tidy-imports.banned-api` + pytest source-tree backstop).
- [x] **Phase 49: Three-OS install gate + release-gate extension** (completed 2026-05-26) - `.github/workflows/ci.yml` gained the `install-smoke-plugin` job (3-OS x 2-Python = 6 matrix entries; 20 OS-fanned steps; `pip install -e ./examples/horus-os-example-plugin` -> boot serve -> assert `/api/plugins` pending -> `horus-os plugins grant horus-os-example-plugin --all` -> restart -> assert loaded). `scripts/release_gate.py` extended from 4 to 8 checks (docs-drift, plugin-install-smoke-ci, reference-plugin-manifest-valid, v0-4-fixture-roundtrip). New `horus-os plugins grant --all` ergonomics flag wires a mutex argparse group + `installer.grant_all_capabilities` helper. `docs/RELEASE.md` documents the expanded gate + schema-regen step. 25 new tests (18 + 7). Suite: 1011 passing. TEST-20 + REL-11 complete.
- [x] **Phase 50: v0.5.0 release** (completed 2026-05-27, tag v0.5.0 published) - Version bumped to `0.5.0` in `pyproject.toml` + `src/horus_os/__init__.py`. CHANGELOG `[0.5.0] - YYYY-MM-DD` draft promoted to `[0.5.0] - 2026-05-26` with fresh `[Unreleased]` stub above; v0.5 body content preserved byte-identical from the Phases 47-49 draft. Phase 50 SUMMARY carries the STOP-BEFORE-TAG block reproducing `git tag -a v0.5.0`, `git push origin v0.5.0`, `gh release create v0.5.0`, and STATE.md milestone roll-forward verbatim from docs/RELEASE.md `## Release procedure`. Release-gate active checks (pricing-freshness, ci-two-variant-smoke, docs-drift, plugin-install-smoke-ci, reference-plugin-manifest-valid, v0-4-fixture-roundtrip) all OK; wheel-pricing-bundle + pytest SKIPped under executor env overrides for the maintainer to re-run at full strength as STOP-BEFORE-TAG step 1. Full pytest suite 1011 passed, 3 skipped. REL-10 complete.

### v0.6 Contribution Gate (Phases 51-59)

**Milestone Goal:** Flip horus-os from solo-development mode to "outside contributions welcome" by landing the trust, supply-chain, and contributor-experience infrastructure required to safely accept fork PRs, then flipping the public gate at v0.6.0 ship. v0.6 is NOT a feature milestone; it is a trust-substrate milestone. One external bit flips at v0.6.0 ship (STATUS.md TL;DR rewritten to "contributions OPEN") and the infrastructure underneath makes that flip safe: keyless artifact + tag signing, SLSA L2 provenance, CycloneDX SBOMs, supply-chain scanning, fork-PR CI hardening, contributor + SECURITY doc refresh, release-gate extension from 8 to 13 checks, atomic single-commit gate flip.

**Execution Order:** 51 → (52 ∥ 53) → 54 → (55 ∥ 56) → 57 → 58 → 59. Phase 51 lands first because PITFALL 1 + 2 (`pull_request_target` misuse, mutable action tag pins) are highest blast radius and their fixes are precondition for everything downstream. Phases 52 and 53 run parallel: signing substrate (`release.yml` NEW) and SBOM + supply-chain scan substrate (`audit.yml` NEW) both consume Phase 51's SHA-pin + `permissions:` baseline without depending on each other (mirrors v0.5 Phase 44 ∥ 45). Phase 54 (Dependabot + zizmor) lands after 51 because Dependabot's github-actions ecosystem only meaningfully bumps SHA-pinned references. Phases 55 (contributor docs + templates) and 56 (SECURITY refresh + Runbook + Discussions) run parallel; different files, no overlap. Phase 57 (release-gate extension 8 → 13) lands after 52-54 because the new checks grep files those phases create. Phase 58 (soft launch + release rehearsal) is the dress rehearsal that absorbs friction before the public flip; PITFALL 10 mitigation. Phase 59 (gate flip + v0.6.0 release) lands as a SINGLE ATOMIC COMMIT so contributors never see contradictory signals (STATUS.md "OPEN" + CONTRIBUTING.md "NOT accepting PRs" cannot coexist).

**Phase 52 / Fork-PR CI split (consolidated):** The research SUMMARY flagged Phase 52 (fork-PR label-gate scaffolding) as optional and recommended SKIP / MERGE since v0.5 tests use recorded provider responses and require no live secrets in fork CI. Adopted: the `pull_request_target` lint and fork-safe interpolation discipline (CIHARD-01..03) land inside Phase 51 instead of a stand-alone phase. v0.6 ships with ZERO `pull_request_target` triggers. If v0.7+ ever needs live secrets in fork CI, the `safe-to-test` label-gate pattern can be reintroduced as its own phase then. Result: a 9-phase shape (51-59) instead of 10.

**Seven constraints carried from research that ride across phases:**
1. **`pyproject.toml` base `[project.dependencies]` adds NOTHING** in v0.6. Signing, SBOM, and audit tooling are CI-time only. `[dev]` extras gets exactly ONE addition: `pip-audit>=2.10,<3` (Phase 53). REL-13 documents this is the one delta.
2. **`ci.yml` job names are byte-identity contracts.** `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` are grep'd by `scripts/release_gate.py`. v0.6 adds `permissions: read-all` + SHA-pins every existing `uses:` in `ci.yml` (Phase 51) but does NOT rename or remove jobs. Same lock as v0.5's "TEST-25 install-smoke + install-smoke-plugin byte-identical."
3. **`release_gate.py`'s 8 existing `--check` enum values are APPENDED to, never renamed** (Phase 57). The v0.5 Phase 49 idiom continues: the new 5 checks (`release-workflow-signing-present`, `release-workflow-sbom-present`, `audit-workflow-present`, `local-pip-audit-clean`, `actions-pinned-by-sha`) append to the existing 8 (`pricing-freshness`, `ci-two-variant-smoke`, `wheel-pricing-bundle`, `pytest-suite`, `docs-drift`, `plugin-install-smoke-ci`, `reference-plugin-manifest-valid`, `v0-4-fixture-roundtrip`). Total: 13.
4. **Every third-party `uses:` is pinned to a 40-character commit SHA** (CIHARD-04, Phase 51). `pinact` documented as the local maintainer refresh tool. tj-actions/changed-files CVE-2025-30066 (~23k repos compromised, 350+ tags retargeted) is the cited incident.
5. **Sigstore verification uses workflow-scoped EXACT-match identity** (SIGN-04, Phase 52). `EXPECTED_IDENTITY = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"` — no wildcards, no regex, mandatory `--cert-oidc-issuer`. Negative test (Phase 58 TEST-24) rejects a wrong-identity fixture.
6. **SBOM generated against a FRESH `pip install <wheel>` venv** (SBOM-01, Phase 53), NEVER `pip freeze` of the dev venv. CycloneDX 1.6 JSON locked. Two SBOMs per release: clean install AND `[dev,otel]` install (matches existing two-variant install-smoke convention).
7. **The gate flip is ONE ATOMIC COMMIT** (FLIP-01, Phase 59). STATUS.md TL;DR + milestone row, README CTAs + badge, CONTRIBUTING.md NOTICE deletion, PR template NOTICE deletion, SECURITY.md "(not active yet)" deletion, `issue-claim-watcher.yml` deletion, saved replies, CHANGELOG promotion all land together. Contributors never see contradictory signals.

- [x] **Phase 51: CI hardening substrate** — Workflow YAML lint (`pull_request_target` audit, `actions/checkout` ref audit, no-shell-interpolation via actionlint); `permissions: read-all` top-level on `ci.yml` + new `audit.yml` + new `release.yml`; every existing `uses:` SHA-pinned via `pinact run`; SHA-pin lint added as a release-gate precondition; TEST-23 workflow-lint regression test enforces CIHARD-01..05. Anti-pattern: `pull_request_target` ABSENT (v0.5 tests use recorded responses; no live-secret fork-CI in v0.6). (completed 2026-05-29)
- [x] **Phase 52: Signing substrate (`release.yml` NEW)** — `.github/workflows/release.yml` triggered by `on: release: types: [published]`. Sigstore-python (>=4.2,<5) via `sigstore/gh-action-sigstore-python@<sha>` signs wheel + sdist + SBOM JSON; produces `.sigstore` bundles (NOT detached `.sig`); sign step within 5 minutes of `id-token: write` OIDC mint. `actions/attest-build-provenance@<sha>` generates SLSA Build L2 attestations. Tag signing via `gitsign` keyless (no long-lived GPG keypair). `scripts/verify_release.py` NEW is the 5-check user-facing trust-chain verifier with workflow-scoped EXACT-match identity. PyPI Trusted Publishing OUT OF SCOPE; deferral documented in `.planning/decisions/no-pypi-in-v0.6.md`. (completed 2026-05-29)
- [ ] **Phase 53: SBOM + supply-chain scan substrate (`audit.yml` NEW)** — `cyclonedx-bom` (>=7.3,<8) generates CycloneDX 1.6 JSON SBOMs against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of dev venv); two SBOMs per release (clean + `[dev,otel]`); `actions/attest-sbom@<sha>` binds SBOM attestations to artifacts. `audit.yml` runs `pypa/gh-action-pip-audit@<sha>` (>=2.10,<3) dual-mode (`-s osv` AND `-s pypi`) on every PR + `actions/dependency-review-action@<sha>` with explicit license allowlist (Apache-2.0, MIT, BSD-2/3, ISC, PSF-2.0). `.github/pip-audit-ignore.txt` with mandatory dated-comment discipline. `pip-audit` added to `[dev]` extras (the ONE base-dep-extras change in v0.6).
- [ ] **Phase 54: Dependabot tuning + zizmor** — `.github/dependabot.yml` v2 with `package-ecosystem: pip` (groups: `ai-sdks` for anthropic + google-genai, `otel`, `web-stack`, `dev-tools`; cooldown 3 days default, 14 days majors; `applies-to: version-updates`) AND `package-ecosystem: github-actions` (SHA-pin refresh, weekly cadence). Security updates explicitly UN-grouped — one PR per CVE with a distinct `security-update` label; CVE PRs never hide inside a weekly grouped bump. `zizmor` workflow runs on every PR + on `.github/workflows/**` edits; static-analysis findings block merge; complements actionlint by covering known-bad expression interpolation patterns.
- [ ] **Phase 55: Contributor docs + templates** — `CONTRIBUTING.md` rewritten with honest solo-maintainer language: claim flow ("comment to claim, maintainer assigns"), branch policy, commit format (conventional commits, present tense, no em-dashes per CLAUDE.md), test/doc/changelog expectations, "aim to acknowledge within 7 days." NO 24-hour SLA, NO CLA, Discord optional. PR template gains a checklist (tests, docs, CHANGELOG, license header); NOTICE block STAGED for deletion at gate-flip. Three issue templates (`bug.yml`, `feature.yml`, `security.yml`); banners STAGED for flip. `.github/CODEOWNERS` NEW with PATH-SCOPED ownership (workflows, scripts/release_gate.py, scripts/verify_release.py, SECURITY.md, .planning/), NOT `* @Ridou` blanket. `docs/TRIAGE.md` NEW (label taxonomy ≤15 hard cap, `good-first-issue` rubric, weekly Sunday cadence, "may go silent up to 2 weeks", NO `actions/stale`). `docs/LABEL-TAXONOMY.md` NEW. Five rationale files in `.planning/decisions/` (`no-cla.md`, `no-stale-bot.md`, `sigstore-keyless.md`, `sbom-cyclonedx.md`, `no-pypi-in-v0.6.md`).
- [ ] **Phase 56: SECURITY refresh + Runbook + Discussions** — `SECURITY.md` "(not active yet)" / staged-pipeline section STAGED for deletion at gate-flip; replaced with active vulnerability-disclosure flow pointing at GitHub Security Advisories private reporting. Severity-tier SLOs (critical 14d / high 30d / medium 90d / low no commitment); coordinated disclosure 90-day default; over-capacity acknowledgement language ("if we go silent, file a public issue tagged `security-update-followup`"). Supported-versions table refreshed to cover v0.5.x and v0.6.x; clear retirement policy. `docs/MAINTAINER-RUNBOOK.md` NEW — single doc covering BOTH v0.6.0 release procedure AND post-flip operational playbook (freeze/throttle/burnout triggers, decision matrix). One-time GitHub repo settings checklist appended to `docs/RELEASE.md` (private vulnerability reporting, Dependabot alerts + security updates, secret scanning + push protection, Discussions). `.planning/rollback/flip-gate-revert.md` ships the one-commit revert template tested via `git apply` rehearsal in Phase 58. GitHub Discussions enabled (one-time settings step documented).
- [ ] **Phase 57: Release-gate extension (8 → 13 checks)** — Phase 49 idiom continues. `scripts/release_gate.py` `--check` enum APPENDED with 5 new values (existing 8 byte-identical): `release-workflow-signing-present` (grep for sigstore-python + attest-build-provenance literals), `release-workflow-sbom-present` (grep for cyclonedx-py + attest-sbom), `audit-workflow-present` (grep for pip-audit + dependency-review-action), `local-pip-audit-clean` (`pip-audit -s osv` exits 0), `actions-pinned-by-sha` (regex asserts every `uses:` is `@<40-hex>`). Two-tier execution: tier 1 (pre-merge, local, <10s) covers grep-only checks + lint; tier 2 (pre-release, network, ~60s) adds pip-audit network call + sigstore-verify on the built wheel. `--tier {local,release}` CLI flag (default `release`); `--allow-offline` flag short-circuits tier-2 with warning.
- [ ] **Phase 58: Soft launch + release rehearsal** — Pre-flip dress rehearsal. 3-5 invited contributors land sample PRs end-to-end through the new `audit.yml` + `release.yml` + `verify_release.py` pipeline; friction tracked in `.planning/phases/58-*/REHEARSAL.md`; rehearsal PRs credited in CHANGELOG (TEST-26). `tests/test_contribution_gate_pitfalls/` directory shipped with one regression test per pitfall in `.planning/research/PITFALLS.md` (minimum 12 tests, names map 1:1 to pitfall numbers — mirrors v0.5 TEST-17). Sigstore identity negative-test fixtures committed under `tests/fixtures/sigstore/` (wrong-identity MUST fail, canonical MUST pass — TEST-24). Three-OS install-smoke matrix remains green; `verify_release.py` test runs on every OS; existing install-smoke + install-smoke-plugin jobs byte-identical (TEST-25). First-time-contributor approval gate enabled in branch protection settings — every fork-PR from a user without prior merged PRs requires explicit "Approve and run" before CI runs (FLIP-02). `.planning/rollback/flip-gate-revert.md` revert template `git apply`-tested against a stale working tree.
- [ ] **Phase 59: Gate flip + v0.6.0 release** — SINGLE ATOMIC COMMIT lands all external-bit-flip prose changes (FLIP-01): STATUS.md TL;DR rewritten to "contributions OPEN" + milestone row marked SHIPPED; README "Project status" + CTAs updated + badge bumped to v0.6.0; CONTRIBUTING.md NOTICE blocks deleted; PR template NOTICE block deleted; SECURITY.md "(not active yet)" section deleted; `.github/workflows/issue-claim-watcher.yml` deleted; saved replies updated; CHANGELOG `[0.6.0]` promoted. `accepted-for-review` throttle active for first 30 days (FLIP-03) — PRs without that label do not block the queue; documented in `docs/MAINTAINER-RUNBOOK.md` as the burnout-prevention valve; removed after first 30 days unless retained based on volume. Tag `v0.6.0` (gitsign-signed) pushed; `release.yml` runs; GitHub Release published atomically with wheel + sdist + two SBOMs + four `.sigstore` bundles + SLSA attestations + SBOM attestations all attached. `docs/MIGRATION-v0.5-to-v0.6.md` documents: no schema migration, no new base dependencies, one new `[dev]` addition (`pip-audit`), the gate flip's external-facing changes (REL-13). Release-gate green on all 13 checks (8 carried from v0.5 + 5 new from Phase 57). Pinned "Project Status" Discussion post created (DISCGH-02).


## Phase Details

### Phase 22: Adapter lifecycle hooks
**Goal**: Give the Adapter Protocol optional lifecycle hooks (`start`, `stop`) so long-running adapters can manage their own connections, and expose adapter status via `/api/adapters`.
**Depends on**: Phase 17 (Adapter Protocol shipped in v0.2)
**Requirements**: ART-01, ART-02, ART-03
**Success Criteria** (what must be TRUE):
  1. `Adapter` Protocol gains optional `start(ctx) -> awaitable` and `stop() -> awaitable` methods that adapters can implement; existing webhook adapter continues to work without implementing them
  2. FastAPI app lifespan hooks call `start` on each discovered adapter at startup and `stop` at shutdown
  3. `GET /api/adapters` returns a list of adapters with `name`, `status` (running/stopped/error), `last_activity_at`, `error_count`
  4. `WebhookAdapter` (the v0.2 reference) registers as `status: running` (bound but no background task)
**Plans**: TBD

Plans:
- [ ] 22-01: Lifecycle Protocol additions, FastAPI lifespan integration, status API

### Phase 23: Discord adapter
**Goal**: Ship a Discord adapter that listens for mentions and direct messages, routes them to a configured agent profile, and replies in-channel.
**Depends on**: Phase 22
**Requirements**: DISC-01, DISC-02, DISC-03
**Success Criteria** (what must be TRUE):
  1. `DiscordAdapter` connects on `start`, listens for `app_mention` and DMs, runs the configured agent profile, posts the response back to the source channel/DM
  2. Disconnects trigger an exponential-backoff reconnect (configurable cap)
  3. Setup guide documents bot creation, required intents, and `HORUS_OS_DISCORD_TOKEN` env var
  4. Tests mock the Discord SDK and cover: message routing, reconnect, intent validation
**Plans**: TBD

Plans:
- [ ] 23-01: Discord adapter implementation with mocked-SDK tests

### Phase 24: Slack adapter
**Goal**: Ship a Slack adapter that handles `app_mention`, DMs, and slash commands via the Events API, with HMAC signature verification.
**Depends on**: Phase 22
**Requirements**: SLAK-01, SLAK-02, SLAK-03
**Success Criteria** (what must be TRUE):
  1. `SlackAdapter` binds an Events API webhook endpoint that handles `app_mention` and DM events
  2. Signature verification uses Slack's signing secret (HMAC-SHA256 over body + timestamp)
  3. Slash commands route to an agent profile and respond inline
  4. Tests mock the Slack SDK and cover: signature pass/fail, event routing, slash command handling
**Plans**: TBD

Plans:
- [ ] 24-01: Slack adapter implementation with mocked-SDK tests

### Phase 25: Email adapter
**Goal**: Ship an email adapter that polls IMAP for new messages, runs an agent, and replies via SMTP. No new heavy dependencies.
**Depends on**: Phase 22
**Requirements**: MAIL-01, MAIL-02, MAIL-03
**Success Criteria** (what must be TRUE):
  1. `EmailAdapter` connects to IMAP, marks messages seen as it processes them, runs the configured agent on the message body
  2. Replies sent via SMTP preserve `In-Reply-To` and `References` headers so they thread correctly
  3. Configurable poll interval; sleeps cleanly when no messages
  4. Tests use stdlib `imaplib` + `smtplib` mocks and cover: poll, send, thread headers, idle sleep
**Plans**: TBD

Plans:
- [ ] 25-01: Email adapter implementation with mocked tests

### Phase 26: Calendar adapter
**Goal**: Google Calendar adapter exposes a "list today's events" tool agents can call; optional event creation gated behind a permission flag.
**Depends on**: Phase 22
**Requirements**: CAL-01, CAL-02
**Success Criteria** (what must be TRUE):
  1. `CalendarAdapter` exposes a `list_calendar_events_today` tool that agents can invoke; returns events in a structured format
  2. Optional `create_calendar_event` tool, gated behind `HORUS_OS_CALENDAR_WRITE_ALLOWED=true`
  3. OAuth flow documented (Google Cloud project setup, OAuth client, token storage in the data dir)
  4. Tests mock `google-api-python-client` calls and cover: list events, create event (allowed/denied), token refresh path
**Plans**: TBD

Plans:
- [ ] 26-01: Calendar adapter implementation with mocked SDK tests

### Phase 27: Dashboard adapter management
**Goal**: Dashboard `/adapters` view shows configured adapters with health, allows enable/disable, and surfaces per-adapter activity.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26
**Requirements**: DASH-3-01, DASH-3-02
**Success Criteria** (what must be TRUE):
  1. `/adapters` page lists configured adapters with status, last activity timestamp, and error count
  2. Each adapter has an enable/disable toggle that calls `POST /api/adapters/{name}/disable` and `/enable`
  3. Health indicator reflects status (running, stopped, error)
  4. v0.2 dashboard surfaces (agents view, trace explorer, SSE chat) continue to work unchanged
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 27-01: Adapter management UI, enable/disable endpoints, health indicator

### Phase 28: Documentation and examples refresh
**Goal**: Refresh ARCHITECTURE.md for v0.3, add four adapter example scripts, write the v0.2 to v0.3 migration guide.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26, Phase 27
**Requirements**: REL-06
**Success Criteria** (what must be TRUE):
  1. ARCHITECTURE.md documents the lifecycle hooks, adapter status, and dashboard adapter management
  2. `examples/discord_adapter.py`, `slack_adapter.py`, `email_adapter.py`, `calendar_adapter.py` exist and run offline (stub SDKs)
  3. `docs/MIGRATION-v0.2-to-v0.3.md` covers the additive Protocol changes and any user-visible behavior
  4. README links to the new examples and migration guide
**Plans**: TBD

Plans:
- [ ] 28-01: ARCHITECTURE refresh, four examples, migration guide

### Phase 29: Test surface expansion
**Goal**: Cross-adapter E2E flows, lifecycle tests, and shared mocked-SDK fixtures.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26, Phase 27
**Requirements**: TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
  1. Lifecycle tests cover start/stop/error transitions for an adapter with all three states
  2. Each of the four new adapters has E2E mocked-SDK tests
  3. Cross-adapter routing test: one trigger reaches multiple adapter channels without race conditions
  4. Overall test count maintains or exceeds the v0.2 baseline (319) plus the new tests
**Plans**: TBD

Plans:
- [ ] 29-01: Lifecycle E2E + cross-adapter routing + mock fixture consolidation

### Phase 30: Three-OS install verification (v0.3)
**Goal**: `install-smoke` job re-runs against the v0.3 feature set and stays green on Ubuntu, macOS, Windows.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26, Phase 27, Phase 28, Phase 29
**Requirements**: TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
  1. The `install-smoke` CI job passes on Ubuntu, macOS, and Windows for Python 3.11 and 3.12
  2. Each of the four new adapter modules imports cleanly on each OS
  3. Adapter discovery via entry points works on each OS
  4. Streaming and multi-agent surfaces from v0.2 continue to pass install-smoke
**Plans**: TBD

Plans:
- [ ] 30-01: Update install-smoke for v0.3 surface, verify three-OS green

### Phase 31: v0.3.0 release
**Goal**: Tag v0.3.0, update CHANGELOG with the milestone diff, publish GitHub Release with migration notes.
**Depends on**: Phase 30
**Requirements**: REL-05, REL-06
**Success Criteria** (what must be TRUE):
  1. The `v0.3.0` tag exists on origin
  2. CHANGELOG.md has a complete `[0.3.0]` section describing the four new adapters, lifecycle hooks, and dashboard updates
  3. A GitHub Release at the v0.3.0 tag is published with the CHANGELOG body and a link to the migration guide
  4. Version bumped to `0.3.0` in `pyproject.toml` and `src/horus_os/__init__.py`
**Plans**: TBD

Plans:
- [ ] 31-01: Version bump, CHANGELOG, tag, GitHub Release

### Phase 32: Schema migration, persistence skeleton, v0.3 baseline
**Goal**: Land the v4-to-v5 additive SQLite migration, the `ObservationBus` plus `SQLitePersister` infrastructure (not yet wired into the runner), and commit a `tests/perf/v0_3_baseline.json` artifact so the Phase 33 capture-overhead benchmark has a pinned reference. Pure infrastructure phase, no behavior change for users.
**Depends on**: Phase 31 (v0.3.0 shipped; v0.3 schema and lifecycle hooks in place)
**Requirements**: STORE-01, STORE-02, STORE-03, STORE-04, STORE-05, BASELINE-01, TEST-11, MIG-04
**Success Criteria** (what must be TRUE):
  1. `Database.init()` against a fresh database creates `llm_calls` and `tool_invocations` tables plus the four nullable rollup columns on `traces`; running it twice on a v5 schema is a no-op (idempotent)
  2. `Database.init()` against the checked-in `tests/fixtures/v0_3_database.sqlite3` upgrades cleanly: new columns and tables exist, old `traces.usage` JSON blob still reads, pre-v0.4 rows have NULL on new columns (Pitfall 11 guard)
  3. SQLite pragmas read back as `journal_mode=wal` and `synchronous=NORMAL` after init; never `synchronous=FULL` (Pitfall 8 guard)
  4. `tests/perf/v0_3_baseline.json` artifact committed before Phase 33 starts; captures wall-clock latency for the same fixture 3-iteration agent loop on Ubuntu, macOS, Windows under Python 3.11 + 3.12
  5. Unit tests publish synthetic `ObservationEvent`s directly to `ObservationBus`; `SQLitePersister` inserts one row per event into the right table; no runner code touched yet
**Plans**: 1 plan

Plans:
- [x] 32-01-PLAN.md: v4-to-v5 migration, ObservationBus + SQLitePersister, v0.3 baseline artifact, lint guard

### Phase 33: Capture at the runner + SSE branch
**Goal**: Wire the bus into the runner so real agent runs publish `LLM_CALL` and `TOOL_CALL` events that the SQLitePersister writes. Fix two confirmed v0.3 correctness bugs: per-iteration token undercount (Pitfall 1) and the streaming path silently recording $0 (Pitfall 2). Cost still NULL at this point; pricing lands in Phase 34.
**Depends on**: Phase 32
**Requirements**: METRIC-01, METRIC-02, METRIC-03, METRIC-04, METRIC-05, TEST-12
**Success Criteria** (what must be TRUE):
  1. A 3-iteration agent run with stubbed `usage={input:100,output:50}` per turn results in `traces.total_input_tokens == 300` and three rows in `llm_calls`; the v0.3 "last iteration overwrites" bug is structurally fixed (Pitfall 1)
  2. A streaming run via `/api/chat/stream` produces an `llm_calls` row with non-zero `input_tokens` and `output_tokens` read from `stream.get_final_message().usage` (Anthropic) or `response.usage_metadata` (Gemini); the SSE path never silently lands at $0 (Pitfall 2)
  3. Every `llm_calls` and `tool_invocations` row uses `time.perf_counter()` for `latency_ms`; a ruff/grep CI rule fails the build if `time.time()` appears inside `horus_os/observability/`, `agent.py`, or `tools/loop.py`; `SQLitePersister` asserts `latency_ms >= 0` and refuses to insert negatives (Pitfall 3)
  4. Tool invocations persist `status` (success / error), `retry_count` (best-effort, NULL allowed if SDK does not surface it), and `last_error_text` (exception class name only, never user-supplied content) (Pitfall 9 substrate)
  5. Capture-overhead benchmark in CI runs the fixture 5-iteration / 3-tool-call loop on the 3-OS matrix and asserts total wall-clock is within 50ms of the Phase 32 baseline (METRIC-05, Pitfall 8 guard)
**Plans**: 1 plan

Plans:
- [x] 33-01-PLAN.md: Runner + SSE capture sites with trace_id threading, Pitfall 1/2/3/9 regression tests, lint guard extension, 3-OS capture-overhead benchmark

### Phase 34: Pricing table and cost annotation
**Goal**: Ship `pricing.json` as package data plus the `PricingTable` and `CostAnnotator` that turn token counts into USD costs. Cost annotation subscribes BEFORE the persister so each `LLM_CALL` event is mutated in place. Unknown models persist with `pricing_missing=1, cost_usd=NULL` (NULL is honest, zero is a lie).
**Depends on**: Phase 33
**Requirements**: PRICE-01, PRICE-02, PRICE-03, PRICE-04, PRICE-05
**Success Criteria** (what must be TRUE):
  1. Bundled `src/horus_os/observability/pricing.json` ships current Anthropic + Gemini rates including separate `input_per_million`, `output_per_million`, `cache_write_per_million`, `cache_read_per_million` columns; schema mirrors LiteLLM's `model_prices_and_context_window.json` shape (PRICE-01, PRICE-02)
  2. A known-model `LLM_CALL` event with `input_tokens=1000, output_tokens=200, cache_read_input_tokens=500` lands in `llm_calls` with `cost_usd` equal to the hand-computed cache-aware sum, rounded to 6 decimal places (PRICE-02)
  3. An unknown-model event lands with `pricing_missing=1` and `cost_usd=NULL`; never `cost_usd=0` for an uncovered model (PRICE-03, Pitfall 5)
  4. `HORUS_OS_PRICING_PATH` env var (and `cfg.pricing_path` config field) override the bundled file; a fixture test confirms the override path takes precedence (PRICE-04)
  5. `pricing.json` carries `version`, `updated_at`, and `release_version` top-level fields; `PricingTable.is_stale(now, threshold_days=30)` returns True past 30 days for the dashboard banner Phase 36 will render (PRICE-05)
**Plans**: 1 plan

Plans:
- [x] 34-01-PLAN.md: PricingTable, bundled pricing.json + package-data wiring, CostAnnotator subscriber with cache-aware math, user override, Pitfall 5 defence-in-depth

### Phase 35: Query module and read APIs
**Goal**: Build `observability/queries.py` once so the dashboard (Phase 36) and CLI (Phase 37) cannot drift. All percentiles via SQLite-side `NTILE(100) OVER (...)`, never aggregate-of-aggregates. Ship the four new `/api/observability/*` GET routes and the `/api/agents` extension that adds rollup columns to the existing v0.3 surface.
**Depends on**: Phase 34
**Requirements**: DASH-4-04
**Success Criteria** (what must be TRUE):
  1. `observability/queries.py` exposes `agent_totals(window)`, `cost_by_agent(window)`, `latency_p50_p95(window)`, `tool_reliability(window)` as pure functions returning JSON-serializable dicts; all aggregation in SQL, no Python percentile math (Pitfall 10 anti-pattern guard)
  2. Four new GET routes (`/api/observability/cost`, `/latency`, `/tools`, `/llm-calls`) accept `?since=24h|7d|30d` and return the query-module output as JSON; default window is `7d`
  3. Existing `/api/agents` route gains `total_runs`, `total_cost_usd`, `latency_p50`, `latency_p95` fields per agent, sourced from the v0.4 rollup columns; pre-v0.4 rows contribute NULL and are excluded from cost sums via `COALESCE` (DASH-4-04 backend half, Pitfall 11 NULL handling)
  4. Percentile queries return NULL (not 0) for windows with no data; queries return raw `sample_count` alongside `p50`/`p95` so callers can apply the n-threshold rule (Pitfall 10)
  5. Reliability query honors the `status` enum so `retry_then_success` rows do not count toward `error_count`; query never reads `error_message` content (Pitfall 9)
**Plans**: 1 plan

Plans:
- [x] 35-01-PLAN.md: queries.py (parse_window + agent_totals + cost_by_agent + latency_p50_p95 + tool_reliability), four new /api/observability routes, /api/agents extension with rollup columns (DASH-4-04 backend half)

### Phase 36: Observability dashboard tab
**Goal**: New `/observability` tab with three panels (cost-by-agent, latency p50/p95, tool reliability) plus the small UI tweak that extends the existing `/agents` tab with the cost and latency columns sourced from Phase 35's `/api/agents` extension. Same vanilla-JS pattern as the v0.3 Adapters tab. Render NULLs honestly so pre-v0.4 runs never look like $0.
**Depends on**: Phase 35
**Requirements**: DASH-4-01, DASH-4-02, DASH-4-03, DASH-4-05
**Success Criteria** (what must be TRUE):
  1. `/observability` tab renders three panels (cost-by-agent bar chart, latency p50/p95 table, tool reliability list) with a window selector (24h / 7d / 30d, default 7d) that drives all three (DASH-4-01, DASH-4-02)
  2. Percentile cells with `sample_count < 10` render as "—" with hover text "need at least 10 runs for percentile"; never as a number, never as `0ms` (DASH-4-03, Pitfall 10)
  3. Pre-v0.4 trace rows in the agents table render "—" for new cost and latency columns with hover text "no cost data captured before v0.4"; a separate small tile shows "N runs from before v0.4 with no cost data" so the missing dollars are explained, not hidden (DASH-4-05, Pitfall 11)
  4. Pricing-staleness banner renders when `pricing.json.updated_at` is more than 30 days old; yellow at 30-60 days, red at 90+; copy includes the user override path (Pitfall 5)
  5. Existing `/agents` tab shows the new `total_cost_usd`, `latency_p50`, `latency_p95` columns sourced from the Phase 35 `/api/agents` extension; v0.3 surfaces (trace explorer, SSE chat, Adapters tab) keep working unchanged
**Plans**: 1 plan
**UI hint**: yes

Plans:
- [x] 36-01-PLAN.md: /observability tab + /agents extension + pricing-staleness banner + small-sample + NULL render contracts

### Phase 37: `horus-os usage` CLI subcommand
**Goal**: Ship `horus-os usage --since 7d --format json|csv|table --by model|tool|agent` as an argparse subparser. Reuses `observability/queries.py` from Phase 35 so the CLI and dashboard cannot disagree. Stdlib `json` and `csv`; no new dependencies.
**Depends on**: Phase 35
**Requirements**: USAGE-01, USAGE-02, USAGE-03, USAGE-04
**Success Criteria** (what must be TRUE):
  1. `horus-os usage --since 7d` returns a usage report over a configurable window; `--since` accepts `24h`, `7d`, `30d`, or any `Nh`/`Nd` form (USAGE-01)
  2. `--format json|csv|table` controls output shape; the JSON output schema is documented in `docs/CLI.md` and pinned by a test that diffs the output against a fixture (USAGE-02)
  3. `--by model|tool|agent` slices the report into per-model, per-tool, or per-agent views; output for each shape matches the corresponding `/api/observability/*` route byte-for-byte where the data overlaps (USAGE-03)
  4. Costs render rounded to 6 decimal places, durations to integer ms, consistent units across all three formats; a `jq` pipe on the JSON output never trips on float-precision noise like `0.04200000000000001` (USAGE-04, Pitfall float-precision UX trap)
**Plans**: 1 plan

Plans:
- [x] 37-01-PLAN.md: usage subparser, three formatters (JSON/CSV/table) with float-precision rounding, additive cost_by_model query + matching /api/observability/cost-by-model route for --by model byte-for-byte parity, JSON schema pin, docs/CLI.md entry

### Phase 38: OpenTelemetry adapter
**Goal**: Highest-risk phase, lands LAST among the feature phases. Ship `OtelAdapter` as a v0.3-style `LifecycleAdapter` behind a `[otel]` extra. Lazy imports so a bare `pip install horus-os` never sees `opentelemetry-*`. Default-deny content capture: prompt and completion bodies are NEVER attached to spans by default; opt-in via `HORUS_OS_OTEL_CAPTURE_CONTENT=true` plus a redactor allowlist. `BatchSpanProcessor` always, never `SimpleSpanProcessor` in production. Bounded `force_flush(2000)` then `shutdown()` so Ctrl-C never blocks for 60 seconds (Pitfalls 6, 7, 12).
**Depends on**: Phase 37 (and the ObservationBus has now had five commits of stability across Phases 32-37)
**Requirements**: OTEL-01, OTEL-02, OTEL-03, OTEL-04, OTEL-05, OTEL-06, OTEL-07, TEST-13, TEST-14, TEST-15
**Success Criteria** (what must be TRUE):
  1. `pip install horus-os` (no extra) installs zero `opentelemetry-*` packages; `from horus_os.adapters.otel_adapter import OtelAdapter` succeeds; `OtelAdapter().start(ctx)` raises a clean `RuntimeError("OTel adapter requires 'pip install horus-os[otel]'")`, never `ModuleNotFoundError` (OTEL-01, OTEL-07, Pitfall 12)
  2. **TEST-13 PII-not-leaked:** an `InMemorySpanExporter` fixture receives an `LLM_CALL` event whose prompt contains the literal `AKIAIOSFODNN7EXAMPLE`; the exported span contains `gen_ai.usage.input_tokens` and `horus_os.cost_usd` but DOES NOT contain the literal string `AKIAIOSFODNN7EXAMPLE` anywhere in its attributes (OTEL-03, OTEL-04, Pitfall 7)
  3. **TEST-14 bounded-shutdown:** `OtelAdapter` pointed at `http://127.0.0.1:1` (closed port), one event published, `await adapter.stop()` completes in less than 3 seconds wall clock; `BatchSpanProcessor` (never `SimpleSpanProcessor`) is used; `force_flush(timeout_millis=2000)` precedes `shutdown()` (OTEL-02, OTEL-06, Pitfall 6)
  4. **TEST-15 two-variant install-smoke:** parallel CI jobs run on the 3-OS matrix; the `[dev]` job (no otel) asserts the import-plus-clean-RuntimeError contract from criterion 1; the `[dev,otel]` job asserts `start(ctx)` succeeds when `OTEL_EXPORTER_OTLP_ENDPOINT` is set and spans appear in a local `InMemorySpanExporter` (OTEL-07, Pitfall 12)
  5. Span attribute names come from `horus_os/_observability/semconv.py` constants; emitted attributes are exactly `gen_ai.system`, `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens`, `horus_os.cost_usd`, `error.type`; never the deprecated `gen_ai.prompt` / `gen_ai.completion`; never `gen_ai.input.messages` / `gen_ai.output.messages` in default mode (OTEL-05)
**Plans**: 1 plan

Plans:
- [x] 38-01-PLAN.md: OtelAdapter (lazy import + RuntimeError contract), BatchSpanProcessor + bounded shutdown, 8 canonical GenAI attrs from semconv module, redactor allowlist + default-deny content capture, three non-negotiable tests (TEST-13 PII / TEST-14 bounded-shutdown / TEST-15 two-variant install-smoke), docs/OTEL.md with Threat model section

### Phase 39: Three-OS gate, release, migration doc
**Goal**: The release-quality gate. Document the v0.3-to-v0.4 migration, the observability surface, and the OTel threat model. Ship `scripts/release_gate.py` carrying both the pricing freshness check and the two-variant install-smoke matrix as a release-blocking gate. Three-OS CI green on the full test suite plus all v0.4 tests. Tag v0.4.0 and publish the GitHub Release.
**Depends on**: Phase 38
**Requirements**: REL-07, REL-08, REL-09
**Success Criteria** (what must be TRUE):
  1. `docs/MIGRATION-v0.3-to-v0.4.md`, `docs/OBSERVABILITY.md`, and `docs/OTEL.md` exist; `docs/OTEL.md` contains an explicit "Threat model" section covering what an OTel collector receives in default mode versus content-capture-enabled mode (REL-09, Pitfall 7)
  2. `scripts/release_gate.py` enforces both (a) `pricing.json.updated_at` within 14 days of the tag date and (b) the two-variant install-smoke matrix from Phase 38 is green; release workflow refuses to tag when either fails (REL-08, Pitfalls 5 and 12)
  3. Three-OS CI matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) green on the full test suite plus the new v0.4 tests including the capture-overhead benchmark from Phase 33 and the three non-negotiable OTel tests from Phase 38
  4. `v0.4.0` tag exists on origin; CHANGELOG has a complete `[0.4.0]` section describing the new cost / latency / reliability surface, the OTel opt-in adapter, the two v0.3 correctness fixes, and the v0.3-to-v0.4 migration; GitHub Release at the tag is published with the CHANGELOG body and a link to the migration guide; version bumped to `0.4.0` in `pyproject.toml` and `src/horus_os/__init__.py` (REL-07)
**Plans**: 1 plan

Plans:
- [x] 39-01-PLAN.md: Docs trio (MIGRATION + OBSERVABILITY + OTEL polish + RELEASE), scripts/release_gate.py + tests, version bump to 0.4.0, CHANGELOG promotion (STOP-BEFORE-TAG; maintainer runs git tag + gh release after approval)

### Phase 40: v0.5 baseline artifact
**Goal**: Mirror of v0.4 Phase 32's structure. Commit a `tests/perf/v0_4_baseline.json` artifact that snapshots v0.4 cold-start time and discovery overhead with zero installed plugins on the 3-OS matrix, so Phase 42's cold-start <100ms benchmark has a pinned reference. Pure infrastructure phase; no behavior change for users, no v0.5 runtime code yet.
**Depends on**: Phase 39 (v0.4.0 shipped; v0.4 schema and observability surface in place)
**Requirements**: BASELINE-02
**Success Criteria** (what must be TRUE):
  1. `tests/perf/v0_4_baseline.json` artifact committed before any Phase 42 discovery work lands; captures wall-clock cold-start time for `from horus_os.server.api import create_app; create_app()` on Ubuntu, macOS, Windows under Python 3.11 + 3.12 (BASELINE-02)
  2. Baseline artifact captures discovery overhead with zero installed plugins (no entry points in `horus_os.plugins` group; empty `~/.horus-os/plugins/` directory); v4 baseline carries `version`, `captured_at`, `platform`, `python_version`, `cold_start_ms`, `discovery_ms` fields per OS/Python combination
  3. A 3-OS CI workflow step captures the baseline numbers in a reproducible manner (same fixture as v0.3 baseline pattern); committed values match the workflow output within float tolerance so a future re-capture diffs cleanly
  4. No runtime code touched in this phase; pure `tests/perf/` artifact + the `scripts/capture_v0_4_baseline.py` capture script if one is needed for reproducibility; `pip install -e .` continues to work unchanged
**Plans**: 1 plan

Plans:
- [x] 40-01-PLAN.md — Capture script + seeded v0_4_baseline.json (maintainer row + linux/win32 placeholders) + schema-shape pytest

### Phase 41: Manifest schema, public API, persistence migration
**Goal**: Pure infrastructure phase landing the entire schema substrate that every later v0.5 phase consumes. Ship `PluginSpec` (frozen dataclass), `MANIFEST_V1_SCHEMA` (pydantic v2 model with `manifest_version: int` required from day one), `plugins/api.py` as the single public re-export surface, `capability_catalog.py` closed enum with plain-English descriptions. Land the v5→v6 additive SQLite migration: three new tables (`plugins`, `plugin_capabilities`, `plugin_status`) + two NULLABLE columns (`llm_calls.plugin_name`, `tool_invocations.plugin_name`) + one index (`idx_tool_invocations_plugin`). Add the two new base direct deps (`pydantic>=2.7,<3` and `packaging>=24.0`) to `[project.dependencies]`. No discovery, no loader, no behavior change yet.
**Depends on**: Phase 40 (baseline artifact pinned)
**Requirements**: MANIFEST-01, MANIFEST-02, MANIFEST-03, MANIFEST-04, MANIFEST-05, OBSERVE-01, MIG-05
**Success Criteria** (what must be TRUE):
  1. `Database.init()` against a fresh database creates `plugins`, `plugin_capabilities`, `plugin_status` tables and adds `plugin_name TEXT` NULLABLE columns to `llm_calls` and `tool_invocations` plus `idx_tool_invocations_plugin(plugin_name, created_at)`; running `init()` twice on a v6 schema is a no-op (idempotent); `Database.init()` against the checked-in `tests/fixtures/v0_4_database.sqlite3` upgrades cleanly and pre-v0.5 rows have NULL `plugin_name` (MIG-05, OBSERVE-01, Pitfall 9)
  2. `MANIFEST_V1_SCHEMA` (pydantic v2 `BaseModel`) accepts a valid `horus-plugin.toml` parsed via `tomllib.loads`; requires `manifest_version: int` and rejects manifests without it; declares `name`, `version`, `description`, `author`, `license`, `homepage`, `issue_tracker`, `horus_os_compat`, `[contributions]` tool + adapter dotted-path entries, `[capabilities]` list (MANIFEST-01, MANIFEST-02, MANIFEST-03, MANIFEST-04)
  3. `validate_manifest()` parses `horus_os_compat` as a `packaging.SpecifierSet` and rejects mismatches against `horus_os.__version__` before load; `format_validation_error()` turns pydantic `ValidationError.errors()` into a plain-English line-numbered string the installer (Phase 44) renders verbatim; one fixture test asserts a bad manifest yields a human-readable error mentioning the offending key (MANIFEST-02, MANIFEST-05)
  4. `capability_catalog.py` exports a closed enum (`Capability` or equivalent typed-string set) containing at minimum `filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`; every entry carries a plain-English `description` attribute; `MANIFEST_V1_SCHEMA` validation refuses any `[capabilities]` entry whose `name` is not a member of the catalog (MANIFEST-04, PERMISSION-04 substrate, Pitfall 1 closed-enum guard)
  5. `src/horus_os/plugins/api.py` re-exports the entire v0.5 public surface (`PluginSpec`, `Capability`, `validate_manifest`, `format_validation_error`, the future `PluginContext`/`AdapterContext` shims); `pyproject.toml` `[project.dependencies]` lists exactly `pydantic>=2.7,<3` and `packaging>=24.0` as new base deps (no optional extra); pytest 525+ green, ruff clean (Pitfall 8, REL-10 substrate)
**Plans**: 1 plan

Plans:
- [ ] 41-01-PLAN.md — Plugin manifest schema (PluginSpec + MANIFEST_V1_SCHEMA + capability_catalog), single-public-surface plugins/api.py, v5→v6 additive SQLite migration (3 tables + 2 NULLABLE columns + 1 index) + v0.4 fixture, pyproject.toml base deps (pydantic + packaging)

### Phase 42: Discovery + loading + failure isolation
**Goal**: Wire the schema substrate from Phase 41 into a real `discover_plugins()` pass that walks `importlib.metadata.entry_points(group="horus_os.plugins")` AND the filesystem walk of `~/.horus-os/plugins/`. Ship `plugins/registry.py` (mirror of v0.3 `AdapterRegistry`), `plugins/loader.py` with the CapabilityGuard hook stubbed as pass-through (real enforcement lands Phase 43). Wire the six-phase pipeline into FastAPI lifespan, but with permission gate (Phase C) stubbed to "always grant" and `start()` lifecycle wrapper unbounded — Phase 43 tightens both. Ban `pkg_resources` via ruff custom rule. Land the <100ms cold-start benchmark vs Phase 40 baseline. Surface plugin import failures, manifest validation failures as `status="error"` with structured `error_phase` (discover/validate/load) without crashing host.
**Depends on**: Phase 41 (PluginSpec, MANIFEST_V1_SCHEMA, schema migration)
**Requirements**: DISCOVERY-01, DISCOVERY-02, ISOLATE-04, TEST-18, TEST-19
**Success Criteria** (what must be TRUE):
  1. `discover_plugins(extra_paths=[...])` returns a `list[PluginSpec]` from `importlib.metadata.entry_points(group="horus_os.plugins")` plus a filesystem walk of `~/.horus-os/plugins/<name>/horus-plugin.toml`; filesystem-discovered plugins load via `importlib.util.spec_from_file_location` (no `sys.path` mutation); ruff custom rule fails CI if `pkg_resources` appears anywhere under `src/horus_os/` (DISCOVERY-01, DISCOVERY-02, Pitfall 3)
  2. **TEST-18 cold-start benchmark:** full `discover_plugins()` + validate + load pass with zero installed plugins completes in <100ms wall clock on the Ubuntu CI runner under Python 3.11 + 3.12; CI fails the build on regression vs Phase 40's `v0_4_baseline.json` cold-start number (TEST-18, Pitfall 3)
  3. **TEST-19 broken-plugin fixtures:** synthetic plugins with (a) invalid TOML (parse failure), (b) schema-failing manifest (missing `manifest_version`), (c) import-raising module (`raise RuntimeError` at module top-level), (d) duplicate tool name colliding with a built-in — each appears in `/api/plugins` with `status="error"` and structured `error_phase` (`discover`/`validate`/`load`); FastAPI lifespan completes; built-in tools and adapters keep working byte-identically (TEST-19, ISOLATE-04, Pitfall 6 discover+load half)
  4. Per-plugin error surfacing rides on `ObservationBus.publish` exception-swallow (`observability/bus.py:174-181`); a plugin tool that raises mid-invocation lands in `tool_invocations` with `status="error"`, `plugin_name="<plugin>"`, but does not crash the agent loop or other tools; `PluginHealthSubscriber` increments per-plugin `error_count` and surfaces it via `/api/plugins/{name}.health.error_rate_1h` (ISOLATE-04)
  5. `app.state.plugin_registry` exists after lifespan startup; `PluginRegistry.register(name, spec=spec)` is idempotent; pre-v0.5 surfaces (`/api/adapters`, `/api/observability/*`, `/api/agents`, SSE chat, trace explorer) keep working byte-identically; v0.4 fixture upgrades through Phase 41's migration still pass (carried-forward regression guard)
**Plans**: 1 plan

Plans:
- [ ] 42-01-PLAN.md — discovery (entry_points + filesystem walk) + PluginLoader with rollback (CapabilityGuard pass-through stub) + PluginRegistry mirroring AdapterRegistry + FastAPI lifespan integration + ruff ban on pkg_resources + cold-start <100ms benchmark + four broken-plugin fixtures (bad_toml/schema_fail/import_raises/tool_raises_registration) + healthy control

### Phase 43: Permission model + bounded lifecycle
**Goal**: Turn Phase 42's stubbed pass-through guards into real default-deny enforcement. Ship `plugins/permissions.py` with `PermissionGate` + `CapabilityGuard`; the four helper shims (`ctx.filesystem`, `ctx.secrets`, `ctx.net`, `ctx.process`) that raise `PermissionDenied` when the grant row is missing; per-version grants keyed on `(plugin_name, plugin_version, capability)` AND tied to `manifest_hash = sha256(capabilities_set)`. Manifest-hash diff on upgrade flips previously-granted rows to `state="pending"` and triggers re-prompt. Wrap plugin `start()` and `stop()` in `asyncio.wait_for(..., timeout=2.0)` matching the v0.4 Phase 38 OtelAdapter `force_flush(timeout_millis=2000)` precedent. Add `--disable-all-plugins` CLI escape hatch + per-plugin `plugins.enabled` column gate at discovery time. ISOLATE-01's lifespan-continues guarantee fully cemented here (status surfacing + bounded lifecycle).
**Depends on**: Phase 42 (loader + registry shipped with stubbed guards)
**Requirements**: PERMISSION-01, PERMISSION-02, PERMISSION-03, PERMISSION-04, ISOLATE-01, ISOLATE-02, ISOLATE-03
**Success Criteria** (what must be TRUE):
  1. `DEFAULT_GRANT_POLICY = "deny"` is a module-level constant in `plugins/permissions.py`; helper shims (`ctx.filesystem.read`, `ctx.filesystem.write`, `ctx.secrets.read`, `ctx.net.outbound`) raise `PermissionDenied` if the corresponding grant row is missing OR in `state="pending"` OR `state="revoked"`; a fixture plugin with no granted capabilities cannot read a file via `ctx.filesystem` (PERMISSION-01, PERMISSION-04, Pitfall 1)
  2. Grants persist in `plugin_capabilities` keyed on `(plugin_name, plugin_version, capability)` UNIQUE; `manifest_hash` column stored alongside; on plugin upgrade where `sha256(new_capabilities_set) != old.manifest_hash`, the loader flips previously-granted rows to `state="pending"` and the dashboard re-prompts before next run; upgrade-with-shrunk-capabilities path auto-grants the subset (PERMISSION-02, Pitfall 5)
  3. Grants revocable via `horus-os plugins revoke <name> <capability>` AND via `DELETE /api/plugins/{name}/grant/{capability}`; revocation flips `state="revoked"` + `revoked_at=<ts>`; takes effect on next plugin run; no in-flight cancellation required for v0.5 (PERMISSION-03)
  4. **Bounded lifecycle:** plugin `start(ctx)` and `stop()` wrapped in `asyncio.wait_for(start(ctx), timeout=2.0)` and `asyncio.wait_for(stop(), timeout=2.0)` respectively (literal `timeout=2.0`, matching v0.4 Phase 38 `force_flush(timeout_millis=2000)` shape); timeout or exception → `plugin_status.status="error"`, `error_phase="start"` or `"stop"`, host lifespan continues; a fixture plugin whose `start()` sleeps 30s flips to error within 3 seconds wall clock (ISOLATE-02, Pitfall 6)
  5. ISOLATE-01 cemented: import failure, manifest validation failure, permission denied, `start()` exception/timeout NEVER crash horus-os; `plugin_status` table carries `status` in `{"loaded", "pending", "error", "disabled"}` and structured `error_phase` in `{"discover", "validate", "permission", "load", "start", "stop", NULL}`; `plugins.enabled=0` skips discovery cleanly (no half-loaded state); `horus-os --disable-all-plugins` boot flag loads with empty plugin list (ISOLATE-01, ISOLATE-03)
**Plans**: TBD

Plans:
- [ ] 43-01: PermissionGate + CapabilityGuard + helper shims + per-version+hash grants + bounded asyncio.wait_for(timeout=2.0) + --disable-all-plugins flag + ISOLATE-01 status surfacing

### Phase 44: Installer flow (two-phase install + upgrade diff)
**Goal**: Ship `horus-os plugins {install, uninstall, list, info, enable, disable, update, grant, revoke}` as a new argparse subparser. The `install` subcommand is the highest-stakes path: wraps `pip` via `subprocess.check_call([sys.executable, "-m", "pip", ...])` with `--require-virtualenv`; refuses outside a venv (`sys.prefix == sys.base_prefix` check) with `--allow-system-python` escape hatch. Implements the literal three-phase install sequence (phase A `pip download --no-deps` → phase B validate manifest + show capability prompt → phase C `pip install --no-deps --no-build-isolation <wheel>`). Refuses sdists by default (`*.tar.gz`) with `--allow-sdist` escape hatch. Refuses wheels containing `.pth` files in RECORD. Captures `pip freeze` hash pre/post install and refuses any spec that downgrades horus-os runtime deps. `update` runs the upgrade-with-diff that consumes Phase 43's manifest-hash logic. Can run in parallel with Phase 45.
**Depends on**: Phase 43 (PermissionGate + grant table)
**Requirements**: INSTALL-01, INSTALL-02, INSTALL-03, INSTALL-04, INSTALL-05, INSTALL-06
**Success Criteria** (what must be TRUE):
  1. `horus-os plugins install <pip-spec>` wraps `subprocess.check_call([sys.executable, "-m", "pip", "install", "--require-virtualenv", "--no-deps", "--no-build-isolation", "<wheel>"])`; refuses to run when `sys.prefix == sys.base_prefix` with a clean error message and `--allow-system-python` escape hatch; a fixture test outside a venv asserts the refusal (INSTALL-01, Pitfall 4)
  2. **Two-phase install (the literal three-step sequence):** phase A runs `pip download --no-deps <spec>` into a temp directory; phase B parses the downloaded wheel's embedded `horus-plugin.toml`, validates via `MANIFEST_V1_SCHEMA`, and prints the requested capabilities with plain-English descriptions from `capability_catalog.py`, then prompts `Grant all (y) / per-capability (a/b/c/...) / refuse (n)?`; phase C runs `pip install --no-deps --no-build-isolation <local-wheel-path>` ONLY if the user grants; refusal aborts cleanly with no venv mutation (INSTALL-02, INSTALL-05, Pitfalls 4 and 1)
  3. Sdists (`*.tar.gz`) refused by default; `--allow-sdist` flag required to bypass; wheels containing `.pth` files in RECORD also refused (parsed by reading `<wheel>.dist-info/RECORD` and grepping `\.pth\b`); a fixture sdist and a fixture `.pth`-wheel both rejected with structured error messages (INSTALL-03, Pitfall 4)
  4. Pre-install `pip freeze` hash captured; post-install `pip freeze` hash captured; installer refuses any spec that would downgrade `pydantic`, `packaging`, `fastapi`, or any other horus-os runtime dep (check against the resolver's planned changes via `pip install --dry-run --report -` JSON output); on downgrade-attempt detected, install aborts BEFORE phase C runs (INSTALL-04, Pitfall 4)
  5. Subcommand suite complete: `uninstall <name>` runs `pip uninstall -y <pkg>` then `discover_plugins()` refresh; `list` prints discovered plugins with status; `info <name>` prints manifest + grants + health; `enable <name>` / `disable <name>` flip `plugins.enabled`; `update <name>` runs Phase 43's upgrade-with-diff (unchanged auto / reduced auto / expanded re-prompt); `grant <name> --capability <cap>` flips `state="granted"`; `revoke <name> --capability <cap>` flips `state="revoked"` (INSTALL-06, PERMISSION-02 consumer)
**Plans**: TBD

Plans:
- [x] 44-01: cli/plugins_cmd.py with all subcommands + two-phase install + venv/sdist/.pth/downgrade refusals + upgrade-with-diff (completed 2026-05-26)

### Phase 45: REST API + `/plugins` dashboard tab + per-plugin observability
**Goal**: Land the read/write API and dashboard surface. Six `/api/plugins` routes (list/get/enable/disable/grant/revoke). `/plugins` dashboard tab (vanilla JS, mirrors v0.3 `/adapters` tab and v0.4 `/observability` tab patterns) with plugin tiles showing version, declared contributions (tools + adapters), capability chips (granted/pending/revoked with revoke buttons), lifecycle status, last error preview, error rate over selected window. Author / homepage / issue_tracker hyperlinks rendered from validated manifest fields only (no inline rendering of arbitrary URLs from plugin code). `/api/observability/plugins` route + dashboard rollup tile on `/observability` ("by plugin" alongside existing "by agent" and "by tool"). OBSERVE-02 per-plugin LLM cost attribution if the column-add is cheap (already in place via Phase 41's `llm_calls.plugin_name` column). Can run in parallel with Phase 44.
**Depends on**: Phase 43 (grant table + status; both run in parallel after Phase 43)
**Requirements**: DASH-5-01, DASH-5-02, DASH-5-03, OBSERVE-02
**Success Criteria** (what must be TRUE):
  1. Six `/api/plugins` routes wired and tested: `GET /api/plugins` (list all with health), `GET /api/plugins/{name}` (full detail), `POST /api/plugins/{name}/enable`, `POST /api/plugins/{name}/disable`, `POST /api/plugins/{name}/grant` (body `{"capability": "filesystem.read"}`), `DELETE /api/plugins/{name}/grant/{capability}`; all return the `PluginRow` shape; enable/disable/grant return `needs_restart=true` (DASH-5-02 consumer)
  2. `/plugins` dashboard tab renders one tile per discovered plugin showing: `name` + `version` + status badge (`loaded`/`pending`/`error`/`disabled`); declared tools and adapters as labeled chips; capability chips (granted=green, pending=yellow, revoked=gray) with revoke buttons; last error preview (first 200 chars) on hover for `status="error"`; error rate + p50/p95 latency over selected window from `PluginHealthSubscriber` rollup (DASH-5-01)
  3. Plugin tile renders hyperlinks from manifest `author`, `homepage`, `issue_tracker` fields ONLY (rendered via `<a href="{validated_url}" rel="noopener noreferrer">` after URL validation); no inline rendering of arbitrary URLs from plugin code, no markdown rendering of plugin-provided text (XSS guard) (DASH-5-03)
  4. `/api/observability/plugins?since=7d|30d` returns per-plugin `error_rate`, `latency_p50_ms`, `latency_p95_ms`, `total_invocations`, `total_cost_usd` from a SQL query joining `tool_invocations` + `llm_calls` on `plugin_name`; pre-v0.5 rows (NULL `plugin_name`) roll up under `"horus-os core"`; `/observability` dashboard gains a "by plugin" tile alongside "by agent" and "by tool" (OBSERVE-02, Pitfall 7)
  5. OBSERVE-02 LLM cost attribution: a plugin tool that triggers an LLM call lands in `llm_calls` with `plugin_name="<plugin>"` set; cost rolls up correctly per plugin; an integration test asserts a fixture plugin call increments only its own row, never another plugin's; v0.4 `/api/observability/*` routes keep working byte-identically (OBSERVE-02, Pitfall 7)
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 45-01: /api/plugins routes + /plugins dashboard tab + /api/observability/plugins + dashboard rollup tile

### Phase 46: Test surface (three-tier fixtures + pitfall regression suite)
**Goal**: Land the three-tier test fixture strategy that makes plugin testing tractable without polluting the test-runner venv. Tier 1: in-process unit tests against synthetic `PluginSpec` objects (no entry points, no filesystem). Tier 2: `fake_plugin_entry_points` pytest fixture that monkeypatches `importlib.metadata.entry_points` for a single test. Tier 3: `clean_venv` pytest fixture opt-in via `@pytest.mark.installer_e2e` that spawns a real `venv` and runs `pip install` against the test plugin (slow, real E2E, marked off-by-default). Ship `tests/test_plugin_pitfalls/` with one regression test per pitfall in `.planning/research/PITFALLS.md` — minimum 12 tests, names map 1:1 to pitfall numbers (e.g. `test_pitfall_1_default_allow_normalizes_compromise.py`).
**Depends on**: Phase 45 (full v0.5 runtime surface available for tier 3 e2e)
**Requirements**: TEST-16, TEST-17
**Success Criteria** (what must be TRUE):
  1. Tier 1 fixture: synthetic `PluginSpec` objects constructable via a `make_plugin_spec(**overrides)` factory; one example unit test in `tests/plugins/test_registry.py` uses ONLY this tier and runs in <50ms; ruff clean, pytest clean (TEST-16 tier 1)
  2. Tier 2 fixture: `fake_plugin_entry_points` pytest fixture that monkeypatches `importlib.metadata.entry_points(group="horus_os.plugins")` to return a configurable list; one example test in `tests/plugins/test_discovery.py` uses ONLY this tier, no real entry points touched in the runner venv; tier 2 tests run in <500ms total (TEST-16 tier 2)
  3. Tier 3 fixture: `clean_venv` pytest fixture opt-in via `@pytest.mark.installer_e2e`; creates a fresh `venv` via `python -m venv`, runs `pip install -e .` for horus-os plus the test plugin path, asserts plugin appears in `/api/plugins`; marked off in the default `pytest` invocation; the default `pytest -m "not installer_e2e"` invocation never installs anything into the runner venv (TEST-16 tier 3, Pitfall 11)
  4. `tests/test_plugin_pitfalls/` directory contains at minimum 12 regression test files, one per pitfall in `.planning/research/PITFALLS.md`; filenames match `test_pitfall_<N>_<slug>.py` 1:1 to pitfall numbers (`test_pitfall_1_default_allow.py`, `test_pitfall_2_manifest_schema_drift.py`, ... `test_pitfall_12_docs_drift.py`); each test cites the pitfall number in its docstring (TEST-17)
  5. Default pytest run (excluding tier 3) maintains or exceeds the v0.4 baseline test count (520+) and stays under 90s wall clock on the Ubuntu CI runner; ruff clean across the new `tests/test_plugin_pitfalls/` directory
**Plans**: 1 plan

Plans:
- [ ] 46-01-PLAN.md — three-tier fixtures (tier-1 in-process unit helper, tier-2 monkeypatched entry_points, tier-3 opt-in clean_venv via @pytest.mark.installer_e2e) + 12 pitfall regression tests in tests/test_plugin_pitfalls/ mapping 1:1 to PITFALLS.md

### Phase 47: Documentation refresh (docs trio)
**Goal**: Ship the three documentation files that v0.5 needs for plugin authors and existing v0.4 users. `docs/PLUGINS.md` is the plugin-author guide: manifest schema, capability catalog, lifecycle hooks, testing harness, walkthrough of each reference-plugin scenario in order. `docs/PLUGIN-SECURITY.md` carries an explicit "Threat model" section with the literal sentence `plugins execute in the horus-os Python process` and enumerates the capability-grant trust contract; linked from the install-prompt screen. `docs/MIGRATION-v0.4-to-v0.5.md` documents the v5→v6 schema migration plus the two new direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`). Embedded `horus-plugin.toml` snippet in `docs/PLUGINS.md` diffs against the reference plugin in CI (docs-drift trip wire for Phase 49's gate).
**Depends on**: Phase 46 (full test surface available so docs examples can reference real test patterns)
**Requirements**: REFERENCE-02, REL-12
**Success Criteria** (what must be TRUE):
  1. `docs/PLUGINS.md` exists and covers in order: `horus-plugin.toml` schema with annotated example, capability catalog (`filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`) with plain-English descriptions, lifecycle hooks (`start(ctx)` / `stop()` contract + bounded `asyncio.wait_for(timeout=2.0)`), testing harness using the three-tier fixtures from Phase 46, walkthrough of each of the four reference-plugin scenarios from Phase 48 (REFERENCE-02)
  2. The `horus-plugin.toml` snippet embedded in `docs/PLUGINS.md` is byte-identical to `examples/horus-os-example-plugin/horus-plugin.toml`; a CI docs-drift check (extended in Phase 49's release gate) fails the build on divergence (REFERENCE-02, Pitfall 12)
  3. `docs/PLUGIN-SECURITY.md` exists with a section titled "Threat model" containing the literal sentence `plugins execute in the horus-os Python process` and enumerating the capability-grant trust contract; the install-prompt screen (from Phase 44) links to this doc by URL; the doc is short enough (<400 lines) to read in one sitting (REL-12, Pitfall 1)
  4. `docs/MIGRATION-v0.4-to-v0.5.md` documents: the v5→v6 schema migration (three new tables + two NULLABLE columns + one index, all additive); the two new base direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`) and why they were added; how to roll back (`horus-os --disable-all-plugins` boot flag); the breaking-change-free upgrade path for existing v0.4 users (REL-12 consumer, MIG-05 consumer)
  5. README.md updated with v0.5 capability call-outs and a link to `docs/PLUGINS.md`; CHANGELOG `[0.5.0]` section drafted (final tag lands in Phase 50)
**Plans**: 1 plan

Plans:
- [ ] 47-01: docs/PLUGINS.md + docs/PLUGIN-SECURITY.md (Threat model) + docs/MIGRATION-v0.4-to-v0.5.md + README + CHANGELOG draft

### Phase 48: Reference plugin (`horus-os-example-plugin`)
**Goal**: Ship `examples/horus-os-example-plugin/` as a separate installable package living in the same monorepo with its own `pyproject.toml`, `horus-plugin.toml`, and `src/` tree. Demonstrates four scenarios in `src/horus_os_example_plugin/`: (a) simple tool that requires a capability and uses `ctx.filesystem`, (b) config-reading tool that respects `secrets.read`, (c) lifecycle adapter with `start()` + `stop()` that respects the bounded `asyncio.wait_for(timeout=2.0)` contract, (d) plugin registering both a tool AND an adapter in the same package. Enforces the public-API contract via a ruff custom rule that fails CI on any `from horus_os` import outside `horus_os.plugins.api` — this is the byte-level enforcement of Pitfall 8.
**Depends on**: Phase 47 (docs reference this plugin in the walkthrough)
**Requirements**: REFERENCE-01, TEST-21
**Success Criteria** (what must be TRUE):
  1. `examples/horus-os-example-plugin/` exists as a self-contained package: `pyproject.toml` declaring `[project.entry-points."horus_os.plugins"]`, `horus-plugin.toml` with `manifest_version=1` plus all required fields, `README.md`, `src/horus_os_example_plugin/{__init__,tools,adapter}.py`; `pip install -e ./examples/horus-os-example-plugin` from the host repo succeeds in a clean venv (REFERENCE-01)
  2. Four reference scenarios demonstrated: (a) `tools.py::echo_text_tool` requires `filesystem.read` and reads a file via `ctx.filesystem.read(path)`; (b) `tools.py::lookup_secret_tool` requires `secrets.read` and reads via `ctx.secrets.read(key)`; (c) `adapter.py::ExampleAdapter` implements `start(ctx)` + `stop()` and respects the bounded lifecycle (sleeps no more than 1 second in `start`); (d) the single package registers BOTH `tools.py` tools AND `adapter.py::ExampleAdapter` via its manifest (REFERENCE-01)
  3. **TEST-21 single-public-API-surface lint:** a ruff custom rule fails CI on any `from horus_os ...` or `import horus_os...` line in the reference plugin source EXCEPT `from horus_os.plugins.api import ...`; the rule is documented in `docs/PLUGINS.md` and tested with a synthetic bad-import fixture that MUST fail CI (TEST-21, Pitfall 8)
  4. CI runs `pip install -e ./examples/horus-os-example-plugin` in a clean venv, boots horus-os, calls `GET /api/plugins`, asserts the example plugin appears with `status="pending"` (no grants yet); after `horus-os plugins grant horus-os-example-plugin --all`, restart asserts `status="loaded"`; tools and adapter both registered (REFERENCE-01)
  5. CHANGELOG `[0.5.0]` section updated with a link to the example plugin and a callout that the reference is the contract for third-party authors
**Plans**: 1 plan

Plans:
- [ ] 48-01: examples/horus-os-example-plugin/ package + four scenarios + ruff single-API-surface custom rule (TEST-21) + CI install-smoke

### Phase 49: Three-OS install gate + release-gate extension
**Goal**: The v0.5 release-quality gate. Three-OS install-smoke job (macOS + Ubuntu + Windows × Python 3.11 + 3.12) installs the reference plugin via `pip install -e ./examples/horus-os-example-plugin` and asserts the plugin appears in `/api/plugins` with `status="running"` after grant. Extends `scripts/release_gate.py` (shipped in v0.4 Phase 39) with four new v0.5 checks: (a) docs-drift check between `MANIFEST_V1_SCHEMA` runtime constant and `docs/manifest-v1.schema.json`; (b) plugin install-smoke on each OS from TEST-20; (c) reference plugin manifest validates against the runtime schema; (d) v0.4 fixture round-trips the v5→v6 migration. Three-OS CI green on the full test suite plus the new v0.5 tests including TEST-18 cold-start benchmark + TEST-19 broken-plugin fixtures + TEST-20 install-smoke.
**Depends on**: Phase 48 (reference plugin installable for the smoke test)
**Requirements**: TEST-20, REL-11
**Success Criteria** (what must be TRUE):
  1. **TEST-20 three-OS plugin install-smoke:** parallel CI jobs on macOS + Ubuntu + Windows × Python 3.11 + 3.12 (six total combinations) each: (a) run `pip install -e ./examples/horus-os-example-plugin` in the host venv, (b) boot horus-os via `horus-os serve` in the background, (c) `curl -s http://localhost:8000/api/plugins | jq` asserts `horus-os-example-plugin` appears with `status="pending"`, (d) `horus-os plugins grant horus-os-example-plugin --all && horus-os serve restart`, then re-curl asserts `status="running"`; all six combinations green (TEST-20)
  2. `scripts/release_gate.py` carries the four new v0.5 checks alongside the existing v0.4 pricing-freshness + two-variant install-smoke checks: (a) `MANIFEST_V1_SCHEMA.model_json_schema()` diffs against committed `docs/manifest-v1.schema.json`; (b) the TEST-20 install-smoke matrix is green; (c) parsing `examples/horus-os-example-plugin/horus-plugin.toml` via the runtime `validate_manifest()` succeeds with zero errors; (d) `tests/fixtures/v0_4_database.sqlite3` upgrades cleanly through Phase 41's v5→v6 migration with all three new tables and both new columns present (REL-11)
  3. Release workflow refuses to allow the v0.5.0 tag when ANY of the eight gate checks fails (four new + four carried from v0.4); a fixture test asserts each of the four new checks individually fails the gate when its precondition is broken (e.g. mutating the docs schema file diverges from the runtime constant) (REL-11)
  4. Three-OS CI matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) green on the full test suite including: v0.4 capture-overhead benchmark, v0.4 OTel three non-negotiable tests (PII-not-leaked, bounded-shutdown, two-variant install-smoke), v0.5 cold-start <100ms benchmark (TEST-18), v0.5 broken-plugin fixtures (TEST-19), v0.5 plugin install-smoke (TEST-20), the 12+ pitfall regression tests from Phase 46
  5. `docs/manifest-v1.schema.json` committed alongside `MANIFEST_V1_SCHEMA` runtime constant; both stay in sync via the docs-drift gate; any future schema change must update both atomically or the gate refuses the tag
**Plans:** 1 plan

Plans:
- [ ] 49-01: TEST-20 three-OS plugin install-smoke + scripts/release_gate.py extension (4 new checks) + docs/manifest-v1.schema.json + v0.4-fixture v5→v6 round-trip test

### Phase 50: v0.5.0 release
**Goal**: Tag `v0.5.0`, finalize CHANGELOG `[0.5.0]` section, publish GitHub Release with migration-notes link. Version bumped to `0.5.0` in `pyproject.toml` and `src/horus_os/__init__.py`. Release-gate green on all 8 checks (4 new v0.5 + 4 carried from v0.4). STOP-BEFORE-TAG block: maintainer runs `git tag` + `gh release create` after final approval, mirroring v0.4 Phase 39's release pattern.
**Depends on**: Phase 49 (release gate green)
**Requirements**: REL-10
**Success Criteria** (what must be TRUE):
  1. `v0.5.0` tag exists on origin; CHANGELOG has a complete `[0.5.0]` section describing the plugin manifest contract, two-phase installer, default-deny capability grants with manifest-hash re-prompt, bounded lifecycle, `/plugins` dashboard tab, per-plugin observability, reference plugin, v5→v6 migration, and the two new direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`) (REL-10)
  2. GitHub Release at the `v0.5.0` tag is published with the CHANGELOG body and a link to `docs/MIGRATION-v0.4-to-v0.5.md`; release notes call out the deliberate addition of two new base runtime deps and the trust model summary (`plugins execute in the horus-os Python process`, default-deny grants, manifest-hash drives re-prompt) (REL-10)
  3. Version bumped to `0.5.0` in `pyproject.toml` and `src/horus_os/__init__.py`; `horus-os --version` returns `0.5.0`; `pip show horus-os` returns version `0.5.0` after install
  4. All 8 release-gate checks green at tag time: (v0.4 carried) pricing freshness within 14 days, two-variant `[dev]`/`[dev,otel]` install-smoke, full 3-OS test suite green, pricing.json metadata schema; (v0.5 new) docs-drift check, plugin install-smoke 3-OS matrix, reference plugin manifest validates, v0.4 fixture v5→v6 round-trip
**Plans**: TBD

Plans:
- [ ] 50-01: Version bump to 0.5.0 + CHANGELOG promotion + STOP-BEFORE-TAG block (maintainer runs git tag + gh release after approval)

### Phase 51: CI hardening substrate
**Goal**: Make every workflow in `.github/workflows/` fork-safe and supply-chain-resistant before any other v0.6 phase ships. PITFALL 1 (`pull_request_target` + checkout-PR-head leaks every secret on the first malicious fork PR — Ultralytics 8.3.41/42 Dec 2024, Spotipy GHSA, "testedbefore" March 2026) and PITFALL 2 (mutable action tag pin same as not pinning — tj-actions/changed-files CVE-2025-30066, ~23k repos compromised) are both addressed in this phase. The fix is pure infrastructure and must land BEFORE STATUS.md ever says "open."
**Depends on**: Phase 50 (v0.5.0 shipped — current `ci.yml` shape is the byte-identity baseline this phase preserves)
**Requirements**: CIHARD-01, CIHARD-02, CIHARD-03, CIHARD-04, CIHARD-05, TEST-23
**Success Criteria** (what must be TRUE):
  1. ZERO `pull_request_target` triggers across `.github/workflows/*.yml`; release-gate lint rejects any new occurrence unless guarded by a `# SECURITY:` comment AND a `safe-to-test` label gate; v0.6 ships with no live-secret fork-CI path (CIHARD-01)
  2. Top-level `permissions: read-all` set on every workflow (`ci.yml`, `audit.yml` NEW in Phase 53, `release.yml` NEW in Phase 52); per-job opt-in for any write scope; workflow-lint test asserts no workflow inherits the legacy GITHUB_TOKEN default scope (CIHARD-02)
  3. Every `actions/checkout` step sets `persist-credentials: false` unless explicitly required for push; no `${{ github.event.pull_request.* }}` interpolation appears in any `run:` shell line; workflow-lint test enforces both (CIHARD-03)
  4. Every third-party `uses:` line in every workflow is pinned to a 40-character commit SHA (`@<sha>` exact match); release-gate `actions-pinned-by-sha` check rejects any `@v<N>`, `@main`, `@master`, or short-SHA pin; `pinact` documented in `docs/MAINTAINER-RUNBOOK.md` as the local maintainer refresh tool (CIHARD-04)
  5. `actionlint` runs as a new workflow lint job on every PR; failures block merge; covers untrusted-input interpolation, expired action references, missing `permissions:` (CIHARD-05). `ci.yml` job names `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` remain byte-identical (grep'd by `scripts/release_gate.py`); no job renamed or removed
  6. TEST-23 regression test in `tests/test_workflow_lint/` scans every `.github/workflows/*.yml` for forbidden patterns (`pull_request_target` unguarded, missing top-level `permissions:`, non-SHA action pin, `${{ github.event.* }}` in shell, missing `persist-credentials: false`); test names map 1:1 to CIHARD-01..05; CI fails on any violation
**Plans**: 2 plans

Plans:
**Wave 1**
- [x] 51-01-PLAN.md: Wave 0 test scaffolding, tests/test_contribution_gate_pitfalls/ package marker + three TEST-23 regression files (test_pitfall_01_pull_request_target, test_pitfall_02_action_sha_pinning, test_ci_hardening_workflow_structure) with stdlib re parsing + non-vacuity synthetic-fixture tests; production assertions go RED against the pre-edit tree (CIHARD-01 vacuous, CIHARD-04 + CIHARD-02 + CIHARD-03 first clause expected red; CIHARD-03 interpolation already clean)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 51-02-PLAN.md: Workflow YAML hardening, ci.yml gains top-level permissions: read-all + actionlint step (raven-actions/actionlint@205b530c... v2.1.2 with version: v1.7.12, step name Run actionlint (CIHARD-05)); every actions/checkout (5 sites) SHA-pinned to 11bd71901bbe... v4.2.2 with persist-credentials: false; every actions/setup-python (5 sites) SHA-pinned to a26af69be... v5.6.0; issue-claim-watcher.yml refactored to top-level permissions: read-all + per-job issues: write on detect-claim (preserves canned-reply behavior per Pitfall 51-E); both actions/github-script@v7 sites SHA-pinned to f28e40c7f3... v7.1.0. Job NAMES byte-identical; release_gate.py and pyproject.toml UNTOUCHED. All Plan 01 tests flip RED to GREEN.

### Phase 52: Signing substrate (`release.yml` NEW)
**Goal**: Wire keyless artifact and tag signing on a NEW `.github/workflows/release.yml` triggered by `on: release: types: [published]`. Sign wheel + sdist + SBOM JSON via sigstore-python keyless OIDC; emit SLSA Build L2 provenance via `actions/attest-build-provenance`; sign git tags via `gitsign` (no long-lived GPG keypair). Ship `scripts/verify_release.py` as the user-facing 5-check trust-chain verifier with workflow-scoped EXACT-match identity. PyPI Trusted Publishing is OUT OF SCOPE for v0.6; deferral rationale documented.
**Depends on**: Phase 51 (SHA-pin + `permissions:` baseline + `pull_request_target` lint must precede any new workflow file)
**Requirements**: SIGN-01, SIGN-02, SIGN-03, SIGN-04, SIGN-05
**Success Criteria** (what must be TRUE):
  1. `.github/workflows/release.yml` NEW with `on: release: types: [published]`, top-level `permissions: read-all`, per-job `id-token: write` only on signing job; `sigstore/gh-action-sigstore-python@<40-char-sha>` (sigstore-python >=4.2,<5) signs wheel + sdist + SBOM JSON within 5 minutes of `id-token: write` OIDC mint (TTL ~10 min); produces `.sigstore` bundles (NOT detached `.sig`) (SIGN-01)
  2. `actions/attest-build-provenance@<40-char-sha>` generates SLSA Build L2 provenance attestations bound to the GitHub workflow identity; verifiable via `gh attestation verify`; runs for every signed artifact (wheel, sdist, both SBOMs) (SIGN-02)
  3. Tag signing via `gitsign` (Sigstore keyless, OIDC); no long-lived GPG keypair required; `docs/RELEASE.md` STOP-BEFORE-TAG block documents the gitsign-configured `git tag` invocation; tag verification uses workflow-scoped identity. `docs/MAINTAINER-RUNBOOK.md` (Phase 56) documents the one-time `gitsign` configuration the maintainer runs before v0.6.0 (SIGN-03)
  4. `scripts/verify_release.py` NEW is a 5-check user-facing trust-chain verifier with workflow-scoped EXACT-match `EXPECTED_IDENTITY = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"` (no wildcards, no regex); mandatory `--cert-oidc-issuer` flag; the script refuses to run without the issuer flag. A canonical fixture in `tests/fixtures/sigstore/canonical/` is verified by the script; a wrong-identity fixture in `tests/fixtures/sigstore/wrong_identity/` is REJECTED by the script (TEST-24 owner is Phase 58; positive fixture lands here) (SIGN-04)
  5. PyPI Trusted Publishing (PEP 807) is OUT OF SCOPE for v0.6; deferral documented in `.planning/decisions/no-pypi-in-v0.6.md` with rationale (horus-os does not currently publish to PyPI; v0.7+ may revisit); decision file referenced from PROJECT.md key-decisions table (SIGN-05)
**Plans**: 2 plans

Plans:
- [x] 52-01-PLAN.md - Wave 0 RED-by-design test scaffolding (4 test files + canonical fixture README; covers SIGN-01..05 via RED-by-design production assertions + non-vacuity scanners)
- [x] 52-02-PLAN.md - Wave 1 GREEN-flip (release.yml + verify_release.py + no-pypi-in-v0.6.md + docs/RELEASE.md edits + .planning/PROJECT.md key-decisions append; depends on 52-01)

### Phase 53: SBOM + supply-chain scan substrate (`audit.yml` NEW)
**Goal**: Add release-time SBOM generation and PR-time supply-chain scanning. SBOMs are CycloneDX 1.6 JSON generated against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of the dev venv); two per release (clean + `[dev,otel]`); both signed via sigstore in the same `release.yml` job from Phase 52; SBOM attestations bind contents to the wheel. `audit.yml` NEW runs `pip-audit` dual-mode on every PR plus `dependency-review-action` with a license allowlist. `pip-audit` added to `[dev]` extras — the ONE base-dep-extras change in v0.6.
**Depends on**: Phase 51 (SHA-pin baseline; new `audit.yml` consumes the workflow-lint discipline)
**Parallelizable with**: Phase 52 (different files; SBOM signing in `release.yml` runs after Phase 52 lands the sign step, but the SBOM generation step + the `audit.yml` work proceed independently)
**Requirements**: SBOM-01, SBOM-02, SBOM-03, SUPPLY-01, SUPPLY-02, SUPPLY-03, SUPPLY-04
**Success Criteria** (what must be TRUE):
  1. `release.yml` (extended from Phase 52) runs `cyclonedx-py environment` (cyclonedx-bom >=7.3,<8) against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of the dev venv); CycloneDX 1.6 JSON format locked; SBOM signed via sigstore-python in the same job that signs the wheel (SBOM-01)
  2. Two SBOMs ship per release: clean install (`pip install <wheel>`) AND extras install (`pip install <wheel>[dev,otel]`); both attached to the GitHub Release alongside their `.sigstore` bundles; matches existing two-variant install-smoke convention (SBOM-02)
  3. `actions/attest-sbom@<40-char-sha>` generates SBOM attestations bound to the artifact each SBOM describes; release-gate diffs SBOM contents against the published wheel's actual installed dependency tree; a fixture test asserts the gate fails when the SBOM is stale relative to the wheel (SBOM-03)
  4. NEW `.github/workflows/audit.yml` triggers on every PR with `permissions: contents: read` + `persist-credentials: false`; runs `pypa/gh-action-pip-audit@<40-char-sha>` (pip-audit >=2.10,<3) dual-mode (`-s osv` AND `-s pypi`); failures block merge; `pip-audit` added to `[dev]` extras for local use (the single base-dep-extras change in v0.6) (SUPPLY-01)
  5. `actions/dependency-review-action@<40-char-sha>` runs on every PR with explicit license allowlist (Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0); rejects new deps under unlisted licenses; rejection produces a PR comment naming the offending dep + license (SUPPLY-02)
  6. `.github/pip-audit-ignore.txt` enforces mandatory dated-comment discipline: every entry includes a `# YYYY-MM-DD: <reason>` line; release-gate rejects undated entries; `.github/pip-audit-tracking/` directory carries fix-tracking docs for unfixable transitives (one file per ignored CVE) (SUPPLY-03)
  7. `pip-audit` runs on BOTH `[dev]` AND `[dev,otel]` install variants in `audit.yml`; matches the Phase 39 OTel-variant precedent + the existing two-variant install-smoke pattern (SUPPLY-04)
**Plans**: TBD

Plans:
- [ ] 53-01: TBD

### Phase 54: Dependabot tuning + zizmor
**Goal**: Configure Dependabot v2 for both `pip` and `github-actions` ecosystems with security-updates explicitly UN-grouped so CVE PRs never hide inside weekly grouped bumps. Add `zizmor` static-analysis workflow as a second layer of workflow-security enforcement complementing `actionlint`.
**Depends on**: Phase 51 (Dependabot github-actions only meaningfully bumps SHA-pinned references; security-update exclusion must land BEFORE Dependabot opens its first grouped-security PR)
**Requirements**: DEPBOT-01, DEPBOT-02, DEPBOT-03
**Success Criteria** (what must be TRUE):
  1. `.github/dependabot.yml` v2 with `package-ecosystem: pip` configured with four groups: `ai-sdks` (anthropic + google-genai to silence dual-SDK churn), `otel`, `web-stack`, `dev-tools`; cooldown 3 days default, 14 days majors; `applies-to: version-updates` on every group (DEPBOT-01)
  2. `.github/dependabot.yml` also configures `package-ecosystem: github-actions` for SHA-pin refresh on a weekly cadence; Dependabot is the canonical source of SHA-pin freshness for third-party actions (DEPBOT-01)
  3. Security updates are explicitly UN-grouped: no `applies-to: security-updates` matcher on any group; one PR per CVE; security PRs carry a distinct `security-update` label (label defined in `docs/LABEL-TAXONOMY.md` from Phase 55); fixture test asserts no group config has `applies-to: security-updates` (DEPBOT-02)
  4. `zizmor` workflow runs on every PR + on `.github/workflows/**` edits; static-analysis findings block merge; covers known-bad expression interpolation patterns (`${{ github.event.* }}` in shell, etc.) that `actionlint` does not flag; complements not duplicates Phase 51 actionlint (DEPBOT-03)
**Plans**: TBD

Plans:
- [ ] 54-01: TBD

### Phase 55: Contributor docs + templates
**Goal**: Land all contributor-facing prose with gate-flip-toggle text STAGED for activation in Phase 59. CONTRIBUTING.md rewritten with honest solo-maintainer language. PR template gains a checklist. Three issue templates land. CODEOWNERS path-scoped. `docs/TRIAGE.md` defines the label taxonomy. `docs/LABEL-TAXONOMY.md` documents each label. Five rationale files land in `.planning/decisions/`.
**Depends on**: Phase 51 (CIHARD-04 SHA-pin baseline informs CODEOWNERS workflow ownership rules)
**Parallelizable with**: Phase 56 (different files; no shared edit surface)
**Requirements**: CONTRIB-01, CONTRIB-02, CONTRIB-03, CONTRIB-04, CONTRIB-05, CONTRIB-06, CONTRIB-07
**Success Criteria** (what must be TRUE):
  1. `CONTRIBUTING.md` rewritten end-to-end: claim flow ("comment to claim, maintainer assigns"); branch policy; commit format (conventional commits, present tense, no em-dashes per CLAUDE.md hard rule 3); test/doc/changelog/license-header expectations; "aim to acknowledge within 7 days" SLO language. Anti-features explicit: NO 24-hour SLA, NO CLA, Discord optional. NOTICE block ("not accepting outside PRs") STAGED with comment marker for Phase 59 deletion (CONTRIB-01)
  2. `.github/PULL_REQUEST_TEMPLATE.md` gains a checklist (tests added/updated, docs updated if user-visible, CHANGELOG `[Unreleased]` entry added if user-visible, license header on new files), reference to CONTRIBUTING.md + CODE_OF_CONDUCT.md; NOTICE block STAGED for Phase 59 deletion (CONTRIB-02)
  3. `.github/ISSUE_TEMPLATE/` carries three forms: `bug.yml`, `feature.yml`, `security.yml` (security form redirects to GHSA private-vulnerability-reporting); banners STAGED for Phase 59 flip ("not accepting contributions" toggles off) (CONTRIB-03)
  4. `.github/CODEOWNERS` NEW with PATH-SCOPED ownership: `/.github/workflows/ @Ridou`, `/scripts/release_gate.py @Ridou`, `/scripts/verify_release.py @Ridou`, `/SECURITY.md @Ridou`, `/.planning/ @Ridou`; NO blanket `* @Ridou` assignment; reviewers auto-assigned by directory (CONTRIB-04)
  5. `docs/TRIAGE.md` NEW: label taxonomy with ≤15 hard cap (`type:bug`, `type:feature`, `area:adapters`, `area:dashboard`, `area:cli`, `good-first-issue`, `help-wanted`, `security-update`, `breaking`, `blocked`, `needs-info`, `waiting-for-author`, `accepted`, `claimed`, `wontfix`); `good-first-issue` rubric; weekly Sunday triage cadence; "may go silent up to 2 weeks" disclaimer; NO `actions/stale` auto-close (rationale: `.planning/decisions/no-stale-bot.md`) (CONTRIB-05)
  6. `docs/LABEL-TAXONOMY.md` NEW: documents the label set + when each applies + saved-reply text for common scenarios (claim accepted, claim conflict, missing repro, stale-but-real bug) (CONTRIB-06)
  7. `.planning/decisions/` directory ships five one-page rationale files: `no-cla.md`, `no-stale-bot.md`, `sigstore-keyless.md`, `sbom-cyclonedx.md`, `no-pypi-in-v0.6.md`; referenced from CONTRIBUTING.md and PROJECT.md key-decisions table (CONTRIB-07)
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 55-01: TBD

### Phase 56: SECURITY refresh + Runbook + Discussions
**Goal**: Refresh SECURITY.md disclosure flow with severity-tier SLOs and over-capacity language. Land `docs/MAINTAINER-RUNBOOK.md` as the single doc covering BOTH v0.6.0 release procedure AND post-flip operational playbook. Append one-time repo settings checklist to `docs/RELEASE.md`. Ship the rollback template. Enable GitHub Discussions (one-time settings step documented).
**Depends on**: Phase 51 (workflow-security discipline informs `docs/MAINTAINER-RUNBOOK.md` operational playbook)
**Parallelizable with**: Phase 55 (different files; no shared edit surface)
**Requirements**: SECDISC-01, SECDISC-02, SECDISC-03, SECDISC-04, RUNBOOK-01, RUNBOOK-02, DISCGH-01, DISCGH-02
**Success Criteria** (what must be TRUE):
  1. `SECURITY.md` "(not active yet)" / staged-pipeline section STAGED for Phase 59 deletion with comment marker; replacement active vulnerability-disclosure flow drafted in-place (toggle commented out until Phase 59), pointing at GitHub Security Advisories private reporting (SECDISC-01)
  2. Severity-tier SLOs land in SECURITY.md: "aim to acknowledge within 7 days"; fix targets critical 14d, high 30d, medium 90d, low no commitment; coordinated disclosure 90-day default; over-capacity acknowledgement language explicit ("if we go silent, file a public issue tagged `security-update-followup`") (SECDISC-02)
  3. Supported-versions table refreshed to cover v0.5.x and v0.6.x; clear retirement policy (only the most recent minor receives security fixes); test-advisory ritual documented ("we publish at least one rehearsal GHSA before any real CVE") (SECDISC-03)
  4. One-time GitHub repo settings checklist appended to `docs/RELEASE.md`: enable private vulnerability reporting, enable Dependabot alerts + security updates, enable secret scanning + push protection, enable Discussions; each checklist item includes a verification command (`gh api`) the maintainer runs once (SECDISC-04, DISCGH-01)
  5. NEW single `docs/MAINTAINER-RUNBOOK.md` covers BOTH the v0.6.0 release procedure (mirror of v0.5's STOP-BEFORE-TAG block, extended with the new `release.yml`-runs + signed-tag + SBOM-attach steps) AND the post-flip operational playbook (freeze triggers, throttle triggers, burnout triggers, decision matrix for "is this PR worth my time?"). Supersedes the candidate `docs/POSTFLIP-PLAYBOOK.md` name (one doc, not two) (RUNBOOK-01)
  6. `.planning/rollback/flip-gate-revert.md` carries the one-commit revert template that restores the pre-flip prose; the template is `git apply`-tested against a stale working tree as part of Phase 58 rehearsal (RUNBOOK-02)
  7. GitHub Discussions enabling is a one-time repo settings step documented in `docs/MAINTAINER-RUNBOOK.md` repo-settings checklist; categories defined (General, Q&A, Show and Tell, Ideas) (DISCGH-01). The pinned "Project Status" Discussion post is created at v0.6.0 ship as part of Phase 59 (DISCGH-02 owner is Phase 59; setup checklist lands here)
**Plans**: TBD

Plans:
- [ ] 56-01: TBD

### Phase 57: Release-gate extension (8 → 13 checks)
**Goal**: Extend `scripts/release_gate.py` from 8 checks (carried from v0.5) to 13 checks (5 new) following the Phase 49 idiom: `--check` enum APPENDED, existing 8 values byte-identical, exit codes (0/1) and env-var contract preserved. Add a two-tier execution model (pre-merge local <10s vs pre-release network ~60s) so the gate is fast enough to run on every PR but thorough enough to refuse an unsigned, un-SBOMed, or vulnerable tag.
**Depends on**: Phase 52 (signing substrate), Phase 53 (SBOM + audit substrate), Phase 54 (Dependabot config) — the new checks grep files those phases create
**Requirements**: REL-14, REL-15
**Success Criteria** (what must be TRUE):
  1. `scripts/release_gate.py` `--check` enum extended from 8 to 13 values; the existing 8 (`pricing-freshness`, `ci-two-variant-smoke`, `wheel-pricing-bundle`, `pytest-suite`, `docs-drift`, `plugin-install-smoke-ci`, `reference-plugin-manifest-valid`, `v0-4-fixture-roundtrip`) are byte-identical; the 5 new (`release-workflow-signing-present`, `release-workflow-sbom-present`, `audit-workflow-present`, `local-pip-audit-clean`, `actions-pinned-by-sha`) are appended (REL-14)
  2. `release-workflow-signing-present` greps `.github/workflows/release.yml` for sigstore-python + attest-build-provenance literals; `release-workflow-sbom-present` greps for cyclonedx-py + attest-sbom; `audit-workflow-present` greps `.github/workflows/audit.yml` for pip-audit + dependency-review-action; each check fails the gate when its target literal is absent; fixture tests prove each check individually fails the gate when its precondition is broken (REL-14)
  3. `local-pip-audit-clean` runs `pip-audit -s osv` against the current `[dev]` install and exits 0 only on a clean scan; `actions-pinned-by-sha` regex-asserts every `uses:` line in every workflow is `@<40-hex-sha>`; both checks fail the gate on first violation (REL-14)
  4. Two-tier execution: tier 1 (pre-merge, local, <10s) covers the grep-only checks + lint (`release-workflow-signing-present`, `release-workflow-sbom-present`, `audit-workflow-present`, `actions-pinned-by-sha`); tier 2 (pre-release, network, ~60s) adds `local-pip-audit-clean` (network call) + sigstore-verify on the built wheel. Tier choice via `--tier {local,release}` CLI flag (default `release` to preserve existing behavior); offline mode short-circuits tier-2 with explicit `--allow-offline` flag plus warning (REL-15)
  5. Tier-1 wall-clock budget on Ubuntu CI runner: <10s for the four grep-only checks; tier-2 wall-clock budget: <90s including pip-audit network call and sigstore-verify; both budgets asserted in CI as fixture tests (REL-15)
**Plans**: TBD

Plans:
- [ ] 57-01: TBD

### Phase 58: Soft launch + release rehearsal
**Goal**: Last opportunity to identify friction BEFORE the public flip. 3-5 invited contributors land sample PRs end-to-end through the new pipeline; the `tests/test_contribution_gate_pitfalls/` directory ships with 12+ regression tests (one per pitfall, names map 1:1 to PITFALLS.md by number — mirrors v0.5 TEST-17); sigstore identity negative-test fixtures land; first-time-contributor approval gate enabled in branch protection settings; `.planning/rollback/flip-gate-revert.md` `git apply`-tested.
**Depends on**: Phase 57 (release-gate extension green so the rehearsal exercises the same gate the real release will face)
**Requirements**: TEST-22, TEST-24, TEST-25, TEST-26, FLIP-02
**Success Criteria** (what must be TRUE):
  1. `tests/test_contribution_gate_pitfalls/` directory contains at minimum 12 regression test files, one per pitfall in `.planning/research/PITFALLS.md`; filenames match `test_pitfall_<N>_<slug>.py` 1:1 to pitfall numbers (mirrors v0.5 TEST-17 pattern); each test cites the pitfall number in its docstring (TEST-22)
  2. Sigstore identity negative-test: fixture signature signed by a different workflow identity MUST fail `scripts/verify_release.py`; positive fixture signed by the canonical identity passes; both fixtures committed under `tests/fixtures/sigstore/` (one canonical from Phase 52, one wrong-identity here). The negative test runs on every OS in the 3-OS install-smoke matrix (TEST-24)
  3. Three-OS install-smoke matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) remains green; new `verify_release.py` test runs on every OS to catch platform-specific sigstore-python regressions; existing `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` jobs byte-identical (no rename) (TEST-25)
  4. Pre-flip soft-launch rehearsal: 3-5 invited contributors land sample PRs end-to-end through the new `audit.yml` + `release.yml` + `verify_release.py` pipeline; friction findings tracked in `.planning/phases/58-*/REHEARSAL.md`; rehearsal PRs credited in CHANGELOG `[0.6.0]` draft (TEST-26)
  5. First-time-contributor approval gate enabled in branch protection settings: every fork-PR from a user without prior merged PRs requires explicit "Approve and run" before CI runs; documented in `docs/MAINTAINER-RUNBOOK.md` as the burnout-prevention step (FLIP-02)
  6. `.planning/rollback/flip-gate-revert.md` revert template `git apply`-tested against a stale working tree in this phase's rehearsal session; verification log captured in `.planning/phases/58-*/REHEARSAL.md` (RUNBOOK-02 consumer)
**Plans**: TBD

Plans:
- [ ] 58-01: TBD

### Phase 59: Gate flip + v0.6.0 release
**Goal**: One atomic commit lands all external-bit-flip prose changes; `v0.6.0` tag pushed (gitsign-signed); `release.yml` runs end-to-end; GitHub Release published with wheel + sdist + two SBOMs + four `.sigstore` bundles + SLSA attestations + SBOM attestations atomically attached. Pinned "Project Status" Discussion post created. `accepted-for-review` throttle active for first 30 days as the burnout-prevention valve.
**Depends on**: Phase 58 (soft launch + rehearsal complete; rollback template tested; release-gate 13/13 green)
**Requirements**: FLIP-01, FLIP-03, REL-13, DISCGH-02
**Success Criteria** (what must be TRUE):
  1. SINGLE atomic commit lands the gate-flip prose changes: STATUS.md TL;DR rewritten to "contributions OPEN" + milestone row marked SHIPPED; README "Project status" section + CTAs updated + badge bumped to v0.6.0; CONTRIBUTING.md NOTICE blocks deleted; PR template NOTICE block deleted; SECURITY.md "(not active yet)" section deleted; `.github/workflows/issue-claim-watcher.yml` deleted; saved replies updated; CHANGELOG `[0.6.0]` promoted from draft. No intermediate commit shows contradictory signals ("OPEN" in STATUS.md alongside "NOT accepting PRs" in CONTRIBUTING.md) (FLIP-01)
  2. `accepted-for-review` throttle active for first 30 days post-flip: branch-protection or workflow logic ensures PRs without that label do not block the queue; throttle documented in `docs/MAINTAINER-RUNBOOK.md` as the burnout-prevention valve; calendar reminder set to remove the throttle after 30 days unless retained based on PR volume (FLIP-03)
  3. `v0.6.0` tag exists on origin, gitsign-signed (verified by `git verify-tag v0.6.0` against the canonical OIDC identity); CHANGELOG has a complete `[0.6.0]` section describing the trust-substrate landing (signing + SBOM + audit + Dependabot + contributor docs + SECURITY refresh + release-gate 8→13 + gate flip) (REL-13)
  4. `docs/MIGRATION-v0.5-to-v0.6.md` documents: no schema migration, no new base dependencies (signing/SBOM/audit are CI-time), one new `[dev]` addition (`pip-audit`), the gate flip's external-facing changes (STATUS.md OPEN, CONTRIBUTING.md NOTICE removed, SECURITY.md disclosure active), tag verification command for users (REL-13)
  5. GitHub Release at the `v0.6.0` tag is published with: wheel + sdist + clean SBOM + `[dev,otel]` SBOM + four `.sigstore` bundles (one per artifact) + SLSA Build L2 provenance attestations + SBOM attestations all atomically attached; release-gate green on all 13 checks at tag time (8 carried from v0.5 + 5 new from Phase 57) (REL-13, REL-14)
  6. Pinned "Project Status" Discussion post created at v0.6.0 ship; text mirrors STATUS.md `## TL;DR` plus a "follow this post" CTA; updated at each future release (DISCGH-02)
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 59-01: TBD


## Progress

**Execution Order (v0.3):** 22 → (23 ∥ 24 ∥ 25 ∥ 26) → 27 → 28 → 29 → 30 → 31
**Execution Order (v0.4):** 32 → 33 → 34 → 35 → (36 ∥ 37) → 38 → 39
**Execution Order (v0.5):** 40 → 41 → 42 → 43 → (44 ∥ 45) → 46 → 47 → 48 → 49 → 50
**Execution Order (v0.6):** 51 → (52 ∥ 53) → 54 → (55 ∥ 56) → 57 → 58 → 59

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01-11 | v0.1 | 13/13 | Complete | 2026-05-23 |
| 12-21 | v0.2 | 11/11 | Complete | 2026-05-23 |
| 22. Adapter lifecycle hooks | v0.3 | 1/1 | Complete | 2026-05-23 |
| 23. Discord adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 24. Slack adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 25. Email adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 26. Calendar adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 27. Dashboard adapter management | v0.3 | 1/1 | Complete | 2026-05-24 |
| 28. Documentation and examples refresh | v0.3 | 1/1 | Complete | 2026-05-24 |
| 29. Test surface expansion | v0.3 | 1/1 | Complete | 2026-05-24 |
| 30. Three-OS install verification (v0.3) | v0.3 | 1/1 | Complete | 2026-05-24 |
| 31. v0.3.0 release | v0.3 | 1/1 | Complete | 2026-05-24 |
| 32. Schema migration, persistence skeleton, v0.3 baseline | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 33. Capture at the runner + SSE branch | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 34. Pricing table and cost annotation | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 35. Query module and read APIs | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 36. Observability dashboard tab | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 37. `horus-os usage` CLI subcommand | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 38. OpenTelemetry adapter | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 39. Three-OS gate, release, migration doc | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 40. v0.5 baseline artifact | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 41. Manifest schema, public API, persistence migration | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 42. Discovery + loading + failure isolation | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 43. Permission model + bounded lifecycle | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 44. Installer flow (two-phase install + upgrade diff) | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 45. REST API + `/plugins` dashboard tab + per-plugin observability | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 46. Test surface (three-tier fixtures + pitfall regression suite) | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 47. Documentation refresh (docs trio) | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 48. Reference plugin (`horus-os-example-plugin`) | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 49. Three-OS install gate + release-gate extension | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 50. v0.5.0 release | v0.5 | 1/1 | Complete   | 2026-05-27 |
| 51. CI hardening substrate | v0.6 | 2/2 | Complete   | 2026-05-29 |
| 52. Signing substrate (`release.yml` NEW) | v0.6 | 2/2 | Complete   | 2026-05-29 |
| 53. SBOM + supply-chain scan substrate (`audit.yml` NEW) | v0.6 | 0/1 | Not started | - |
| 54. Dependabot tuning + zizmor | v0.6 | 0/1 | Not started | - |
| 55. Contributor docs + templates | v0.6 | 0/1 | Not started | - |
| 56. SECURITY refresh + Runbook + Discussions | v0.6 | 0/1 | Not started | - |
| 57. Release-gate extension (8 → 13 checks) | v0.6 | 0/1 | Not started | - |
| 58. Soft launch + release rehearsal | v0.6 | 0/1 | Not started | - |
| 59. Gate flip + v0.6.0 release | v0.6 | 0/1 | Not started | - |
