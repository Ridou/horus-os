---
gsd_state_version: 1.0
milestone: v0.6
milestone_name: Contribution Gate
status: executing
last_updated: "2026-05-29T02:42:21.410Z"
last_activity: 2026-05-29 -- Phase 51 planning complete
progress:
  total_phases: 38
  completed_phases: 29
  total_plans: 31
  completed_plans: 29
  percent: 94
---

# Project State

## Project Reference

See: .planning/PROJECT.md and .planning/README.md.

**Core value:** Run a personal team of AI agents on your laptop, with full transparency over every action.
**Current focus:** v0.6 Contribution Gate milestone in planning. Roadmap shaped: 9 phases (51-59), all 46 v0.6 requirements covered at 100%. Next step: `/gsd-plan-phase 51` for the CI hardening substrate.

## Current Position

Phase: 51 (CI hardening substrate) — not yet started
Plan: —
Status: Ready to execute
Last activity: 2026-05-29 -- Phase 51 planning complete

## Prior Milestones

- **v0.1 Foundation** (Phases 01-11): SHIPPED 2026-05-23 as v0.1.0. 175 tests, 3-OS install-smoke green.
- **v0.2 Multi-Agent + Streaming** (Phases 12-21): SHIPPED 2026-05-23 as v0.2.0. 319 tests, 3-OS install-smoke green. Multi-agent runtime, streaming, adapter contract, HMAC webhook reference adapter, dashboard SSE + agents view.
- **v0.3 Adapter Ecosystem** (Phases 22-31): SHIPPED 2026-05-24 as v0.3.0. 447 tests, 3-OS install-smoke green. Adapter lifecycle hooks, Discord + Slack + Email + Calendar adapters, AdapterRegistry, Dashboard Adapters tab, four per-adapter setup guides, four runnable examples, v0.2-to-v0.3 migration guide.
- **v0.4 Observability** (Phases 32-39): SHIPPED 2026-05-26 as v0.4.0. ObservationBus + SQLitePersister, llm_calls + tool_invocations child tables, bundled pricing.json with cache-aware cost annotation, /observability dashboard tab + horus-os usage CLI, opt-in OtelAdapter behind [otel] extra with default-deny content capture + bounded shutdown, scripts/release_gate.py with pricing freshness + two-variant install-smoke matrix.
- **v0.5 Plugin System** (Phases 40-50): SHIPPED 2026-05-27 as v0.5.0. 1011 tests green, 3-OS install-smoke green including the new install-smoke-plugin matrix. TOML manifest contract (pydantic v2), entry-point + filesystem discovery, default-deny capability grants pinned to manifest-hash with re-prompt on upgrade, two-phase `pip install` flow with sdist + `.pth` + runtime-dep-downgrade refusals, bounded `asyncio.wait_for(start, timeout=2.0)` failure isolation, `/plugins` dashboard tab + per-plugin observability attribution, reference plugin (`examples/horus-os-example-plugin/`) demonstrating four scenarios with the two-layer TID251 + source-tree-grep API surface lock, docs trio (`docs/PLUGINS.md` + `docs/PLUGIN-SECURITY.md` + `docs/MIGRATION-v0.4-to-v0.5.md`), `scripts/release_gate.py` extended from 4 to 8 checks. Two new base direct deps: `pydantic>=2.7,<3` + `packaging>=24.0`. v5->v6 schema migration additive only.

## v0.6 Contribution Gate — Milestone Plan

**9 phases (51-59)**, all 46 v0.6 requirements covered at 100%. Execution order:

  51 → (52 ∥ 53) → 54 → (55 ∥ 56) → 57 → 58 → 59

**Phase 52 / Fork-PR CI split consolidated:** Research SUMMARY flagged a standalone Phase 52 (fork-PR label-gate scaffolding) as optional and recommended SKIP/MERGE since v0.5 tests use recorded provider responses and require no live secrets in fork CI. Adopted: the `pull_request_target` lint and fork-safe interpolation discipline (CIHARD-01..03) land inside Phase 51 instead of a stand-alone phase. v0.6 ships with ZERO `pull_request_target` triggers. Result: a 9-phase shape (51-59) instead of 10. If v0.7+ ever needs live secrets in fork CI, the `safe-to-test` label-gate pattern can be reintroduced as its own phase then.

**Seven load-bearing constraints carried across phases:**

1. `pyproject.toml` base `[project.dependencies]` adds NOTHING in v0.6 (Phase 53 adds `pip-audit>=2.10,<3` to `[dev]` extras — the single base-dep-extras change)
2. `ci.yml` job names are byte-identity contracts: `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` are grep'd by `scripts/release_gate.py`. v0.6 adds `permissions: read-all` + SHA-pins every existing `uses:` (Phase 51) but does NOT rename or remove jobs
3. `release_gate.py` 8 existing `--check` enum values are APPENDED to in Phase 57, NEVER renamed (Phase 49 idiom continues; 8 → 13 checks total)
4. Every third-party `uses:` is pinned to a 40-character commit SHA (CIHARD-04, Phase 51); tj-actions/changed-files CVE-2025-30066 (~23k repos compromised) is the cited incident
5. Sigstore verification uses workflow-scoped EXACT-match identity (SIGN-04, Phase 52): no wildcards, no regex, mandatory `--cert-oidc-issuer`; wrong-identity negative test (TEST-24, Phase 58) MUST fail
6. SBOM generated against a FRESH `pip install <wheel>` venv (SBOM-01, Phase 53), NEVER `pip freeze` of the dev venv; CycloneDX 1.6 JSON locked; two SBOMs per release (clean + `[dev,otel]`)
7. The gate flip is ONE ATOMIC COMMIT (FLIP-01, Phase 59): STATUS.md, README, CONTRIBUTING.md NOTICE deletion, PR template NOTICE deletion, SECURITY.md "(not active yet)" deletion, `issue-claim-watcher.yml` deletion, saved replies, CHANGELOG promotion all land together. Contributors never see contradictory signals.

**Phase-by-phase requirement coverage (46/46):**

| Phase | Requirements | Count |
|-------|--------------|-------|
| 51 CI hardening substrate | CIHARD-01..05, TEST-23 | 6 |
| 52 Signing substrate | SIGN-01..05 | 5 |
| 53 SBOM + supply-chain scan substrate | SBOM-01..03, SUPPLY-01..04 | 7 |
| 54 Dependabot tuning + zizmor | DEPBOT-01..03 | 3 |
| 55 Contributor docs + templates | CONTRIB-01..07 | 7 |
| 56 SECURITY refresh + Runbook + Discussions | SECDISC-01..04, RUNBOOK-01..02, DISCGH-01 | 7 |
| 57 Release-gate extension | REL-14, REL-15 | 2 |
| 58 Soft launch + release rehearsal | TEST-22, TEST-24, TEST-25, TEST-26, FLIP-02 | 5 |
| 59 Gate flip + v0.6.0 release | FLIP-01, FLIP-03, REL-13, DISCGH-02 | 4 |
| **Total** | | **46** |

## Last Activity

2026-05-29, v0.6 roadmap landed. 9 phases (51-59), 46 v0.6 requirements mapped 1:1 with zero orphans. Phase 52 absorbed into Phase 51 per research SUMMARY's SKIP/MERGE recommendation (v0.5 tests use recorded provider responses; no live-secret fork-CI path needed in v0.6). Execution order 51 → (52 ∥ 53) → 54 → (55 ∥ 56) → 57 → 58 → 59 mirrors v0.5's 44 ∥ 45 parallelization idiom in two places: signing substrate (`release.yml` NEW) parallel with SBOM + supply-chain scan substrate (`audit.yml` NEW), and contributor docs + templates parallel with SECURITY refresh + Runbook + Discussions. Phase 51 lands first because PITFALL 1 (`pull_request_target` + checkout-PR-head leaks secrets — Ultralytics 8.3.41/42, "testedbefore" Mar 2026, Spotipy GHSA) and PITFALL 2 (mutable action tag pin same as not pinning — tj-actions/changed-files CVE-2025-30066, ~23k repos compromised) are both addressed there as precondition for everything downstream. Phase 57 (release-gate extension 8 → 13 checks) lands after 52-54 because the 5 new checks (`release-workflow-signing-present`, `release-workflow-sbom-present`, `audit-workflow-present`, `local-pip-audit-clean`, `actions-pinned-by-sha`) grep files those phases create. Phase 58 (soft launch) is the dress rehearsal — 3-5 invited contributors land sample PRs end-to-end through the new `audit.yml` + `release.yml` + `verify_release.py` pipeline; 12+ pitfall regression tests in `tests/test_contribution_gate_pitfalls/` mirror v0.5 TEST-17; sigstore negative-identity fixture lands; first-time-contributor branch-protection gate enabled; rollback template `git apply`-tested. Phase 59 lands the SINGLE ATOMIC COMMIT gate flip: STATUS.md TL;DR + milestone row, README CTAs + badge, CONTRIBUTING.md NOTICE deletion, PR template NOTICE deletion, SECURITY.md "(not active yet)" deletion, `issue-claim-watcher.yml` deletion, saved replies, CHANGELOG promotion all together. `v0.6.0` tag (gitsign-signed) pushed; `release.yml` runs end-to-end; GitHub Release atomically attaches wheel + sdist + two SBOMs + four `.sigstore` bundles + SLSA Build L2 attestations + SBOM attestations; `accepted-for-review` throttle active 30 days as burnout-prevention valve; pinned "Project Status" Discussion post created.

Prior: 2026-05-27, v0.5.0 shipped (tag pushed, GitHub Release published). 1011 tests passing, 3-OS install-smoke green including the new install-smoke-plugin matrix; release-gate 8/8 checks active.
