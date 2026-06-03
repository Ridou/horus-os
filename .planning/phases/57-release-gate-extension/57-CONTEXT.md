# Phase 57: Release-gate extension (8 → 13 checks) - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped)

<domain>
## Phase Boundary

Extend `scripts/release_gate.py` from 8 checks (carried from v0.5) to 13 checks (5 new) following the Phase 49 idiom: `--check` enum APPENDED, existing 8 values byte-identical, exit codes (0/1) and env-var contract preserved. Add a two-tier execution model (pre-merge local <10s vs pre-release network ~60s).

</domain>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (REL-14, REL-15)
- `.planning/ROADMAP.md` (Phase 57)
- `.planning/STATE.md` (load-bearing constraint #3: existing 8 `--check` values byte-identical)
- `scripts/release_gate.py` (existing 8-check script; line 685 enum; line 678 main())
- `.github/workflows/release.yml` (Phase 52 + 53 substrate the new checks grep)
- `.github/workflows/audit.yml` (Phase 53 substrate the new checks grep)

</canonical_refs>

<decisions>
## Implementation Decisions (2 requirements; multi-clause)

### REL-14 (8 → 13 checks)

The 5 new check identifiers (kebab-case long names per REQUIREMENTS.md text):

1. `release-workflow-signing-present` (greps release.yml for sigstore-python + attest-build-provenance literals)
2. `release-workflow-sbom-present` (greps release.yml for cyclonedx-py + attest-sbom)
3. `audit-workflow-present` (greps audit.yml for pip-audit + dependency-review-action)
4. `local-pip-audit-clean` (runs `pip-audit -s osv` against current [dev] install; fails on non-clean scan)
5. `actions-pinned-by-sha` (regex-asserts every uses: line in every workflow is @<40-hex-sha>)

Each grep-only check fails the gate when its target literal is absent.

The existing 8 enum values are byte-identical. Short-name convention (`pricing`, `wheel`, etc.) preserved; the 5 new values use kebab-case long names per the requirements text. Both forms can coexist in the enum tuple. **The `selected in (None, "<name>")` dispatch pattern still works.**

### REL-15 (two-tier execution)

- `--tier {local,release}` CLI flag (default `release` to preserve existing behavior)
- Tier 1 (local, <10s): the four grep-only checks (`release-workflow-signing-present`, `release-workflow-sbom-present`, `audit-workflow-present`, `actions-pinned-by-sha`)
- Tier 2 (release, ~60s): tier-1 plus `local-pip-audit-clean` (network) plus sigstore-verify on the built wheel
- `--allow-offline` short-circuits tier-2 with a warning when network unavailable
- Tier-1 wall-clock budget <10s on Ubuntu CI; tier-2 wall-clock <90s including pip-audit network + sigstore-verify. Both asserted via fixture tests.

### Claude's Discretion

Implementation of the wall-clock budget assertions (likely via `time.monotonic()` deltas wrapped around the dispatcher and tested with synthetic fixtures); exact prose of the `--tier` help text.

</decisions>

<specifics>
## Specific Constraints

1. STATE.md load-bearing #3: the 8 existing `--check` values byte-identical. Append, never rename.
2. CLAUDE.md HR3: no em-dashes.
3. The existing CheckResult dataclass + _print_result formatter are reused.
4. `local-pip-audit-clean` requires the pip-audit Python package which Phase 53 added to [dev] extras. Test invocation should subprocess-shell out to `pip-audit -s osv ...` (mirrors the existing release_gate subprocess pattern) and accept exit 0 only.
5. `actions-pinned-by-sha` reuses the regex pattern from `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py` for consistency.

</specifics>

<deferred>
## Deferred Ideas

The SBOM-03 dependency-tree diff (deferred from Phase 53 Plan 02 per RESEARCH.md note) could live here as a sixth new check (`sbom-vs-wheel-dependency-tree-diff`), but the v0.6 ROADMAP REL-14 list specifies exactly 5 new checks. The diff stays deferred to a future phase rather than expanding scope mid-execute.

</deferred>
