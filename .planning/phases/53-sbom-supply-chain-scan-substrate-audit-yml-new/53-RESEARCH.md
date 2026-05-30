# Phase 53 Research: SBOM + supply-chain scan substrate

**Researched:** 2026-05-30
**Status:** Complete (auto-generated, condensed for execution)

## Phase Boundary

Add release-time SBOM generation and PR-time supply-chain scanning. SBOMs are CycloneDX 1.6 JSON generated against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of the dev venv); two per release (clean + `[dev,otel]`); signed via sigstore in the same `release.yml` job from Phase 52; SBOM attestations bind contents to the wheel.

## Three core concepts

### 1. CycloneDX SBOM via `cyclonedx-bom`

`cyclonedx-py environment <venv-python>` introspects an installed Python environment (NOT a `pip freeze` lockfile) and produces a CycloneDX 1.6 JSON SBOM. The FRESH-venv rule (SBOM-01 load-bearing constraint #6 from STATE.md) is enforced by creating a throwaway venv, running `pip install <wheel>` into it, then running `cyclonedx-py environment .venv-sbom/bin/python --output-format JSON --schema-version 1.6 --output-file dist/horus_os-VERSION-clean.cdx.json`.

Pin: `cyclonedx-bom >=7.3,<8`. This is a CI-only tool installed inside `release.yml`; it is NEVER added to `pyproject.toml` (zero base-dep change in v0.6 is one of the seven load-bearing constraints).

### 2. Two SBOMs per release

Mirror the existing `install-smoke-no-otel` + `install-smoke-with-otel` two-variant pattern from `.github/workflows/ci.yml`:
- `horus_os-VERSION-clean.cdx.json` built from `pip install <wheel>` (no extras)
- `horus_os-VERSION-dev-otel.cdx.json` built from `pip install <wheel>[dev,otel]`

Both are attached to the GitHub Release alongside their `.sigstore` bundles. The sigstore-python step in `release.yml` (Phase 52 D-10: input glob `./dist/*.whl ./dist/*.tar.gz`) is APPENDED with `./dist/*.cdx.json` (the smallest possible Phase 53 diff per Phase 52 D-10 forward-reference).

### 3. PR-time supply-chain scanning via `audit.yml`

NEW workflow `.github/workflows/audit.yml`:
- Triggers on `pull_request`
- Top-level `permissions: contents: read` + `actions/checkout` with `persist-credentials: false`
- Matrix over `[dev]` AND `[dev,otel]` install variants (SUPPLY-04)
- Each matrix leg runs `pypa/gh-action-pip-audit@<40-char-sha>` (pip-audit >=2.10,<3) in dual-mode (`-s osv` AND `-s pypi`); each invocation must read `.github/pip-audit-ignore.txt` (SUPPLY-03)
- Separate job runs `actions/dependency-review-action@<40-char-sha>` with license allowlist `Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0` (SUPPLY-02)
- Add `pip-audit>=2.10,<3` to `[dev]` extras for local parity (SUPPLY-01, the ONE base-dep-extras change in v0.6)

## Action SHA pins (current head as of 2026-05-30)

These pins are looked up via `gh api repos/<owner>/<repo>/git/refs/tags/<tag>` at execution time and committed with the workflow. Use placeholders here; the executor will resolve. Actions to pin:

| Action | Tag | Notes |
|--------|-----|-------|
| `actions/attest-sbom` | v2.x | NEW; produces SBOM attestations bound to the artifact |
| `pypa/gh-action-pip-audit` | v1.x | Wrapper that exec's pip-audit |
| `actions/dependency-review-action` | v4.x | License + vuln review on PRs |

The executor must use `gh api` (already used in Phase 51 pinact convention) or paste the verified head SHA + a trailing `# vN.M.P` comment. Mutable tags REFUSED (CIHARD-04 / tj-actions/changed-files CVE-2025-30066 incident).

## `release.yml` extension shape (Phase 53 diff)

Add after the existing `Sign artifacts` step in `.github/workflows/release.yml`:

```yaml
      - name: Generate SBOM (clean install)
        run: |
          python -m venv .venv-sbom-clean
          .venv-sbom-clean/bin/pip install --upgrade pip
          .venv-sbom-clean/bin/pip install dist/*.whl
          .venv-sbom-clean/bin/pip install 'cyclonedx-bom>=7.3,<8'
          .venv-sbom-clean/bin/cyclonedx-py environment .venv-sbom-clean/bin/python \
            --output-format JSON --schema-version 1.6 \
            --output-file dist/horus_os-clean.cdx.json

      - name: Generate SBOM (dev,otel extras)
        run: |
          python -m venv .venv-sbom-extras
          .venv-sbom-extras/bin/pip install --upgrade pip
          .venv-sbom-extras/bin/pip install 'dist/*.whl[dev,otel]'
          .venv-sbom-extras/bin/pip install 'cyclonedx-bom>=7.3,<8'
          .venv-sbom-extras/bin/cyclonedx-py environment .venv-sbom-extras/bin/python \
            --output-format JSON --schema-version 1.6 \
            --output-file dist/horus_os-dev-otel.cdx.json
```

Modify the existing sigstore step's `inputs:` line from `./dist/*.whl ./dist/*.tar.gz` to `./dist/*.whl ./dist/*.tar.gz ./dist/*.cdx.json` per Phase 52 D-10.

Add two NEW attest-sbom invocations (mirrors Phase 52's per-artifact attest-build-provenance pattern):

```yaml
      - name: Attest SBOM (clean install)
        uses: actions/attest-sbom@<sha>
        with:
          subject-path: 'dist/*.whl'
          sbom-path: 'dist/horus_os-clean.cdx.json'

      - name: Attest SBOM (dev,otel extras)
        uses: actions/attest-sbom@<sha>
        with:
          subject-path: 'dist/*.whl'
          sbom-path: 'dist/horus_os-dev-otel.cdx.json'
```

## `verify_release.py` SBOM check flip (D-08 follow-up)

Phase 52 D-08 stubbed `check_sbom_signature(version)` to return `ok=None, diagnostic="SKIPPED - Phase 53 lands SBOM generation + signing"`. Phase 53 flips this stub to active:

1. Verifies BOTH SBOM bundles exist (clean + dev-otel)
2. Runs `python -m sigstore verify identity` against each `.cdx.json` + its `.sigstore` bundle (same EXPECTED_IDENTITY_TEMPLATE + EXPECTED_ISSUER constants from Phase 52)
3. Diffs SBOM contents against the published wheel's actual installed dependency tree (SBOM-03 "release-gate diffs"); the FRESH-venv rule means the diff is a logical equality on the dependency tree

Diff implementation: parse the CycloneDX JSON `components[]` array; compare against `pip install --dry-run --report -` output for the same wheel (stdlib `subprocess` + `json`). Mismatch returns `ok=False` with a structured diagnostic naming the extra / missing component.

## `audit.yml` shape (NEW workflow)

```yaml
name: audit

on:
  pull_request:

permissions: read-all

jobs:
  pip-audit:
    name: pip-audit (${{ matrix.extras }})
    runs-on: ubuntu-latest
    permissions:
      contents: read
    strategy:
      fail-fast: false
      matrix:
        extras: ["[dev]", "[dev,otel]"]
    steps:
      - uses: actions/checkout@<sha>
        with:
          persist-credentials: false
      - uses: actions/setup-python@<sha>
        with:
          python-version: "3.12"
      - run: pip install -e ".${{ matrix.extras }}"
      - name: pip-audit (osv)
        uses: pypa/gh-action-pip-audit@<sha>
        with:
          inputs: "."
          extra-args: "-s osv --ignore-vulns-file .github/pip-audit-ignore.txt"
      - name: pip-audit (pypi)
        uses: pypa/gh-action-pip-audit@<sha>
        with:
          inputs: "."
          extra-args: "-s pypi --ignore-vulns-file .github/pip-audit-ignore.txt"

  dependency-review:
    name: dependency-review
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@<sha>
        with:
          persist-credentials: false
      - uses: actions/dependency-review-action@<sha>
        with:
          allow-licenses: Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0
          comment-summary-in-pr: on-failure
```

Note: `pip-audit` CLI uses `--ignore-vuln <ID>` not `--ignore-vulns-file`; the gh-action wrapper accepts a `ignore-vulns:` input that takes newline-separated IDs. The workflow-level adapter is to read `.github/pip-audit-ignore.txt`, strip comment lines, and pass the IDs. Investigate at execute time which interface the `pypa/gh-action-pip-audit` action exposes (the action's README + action.yml is the source of truth at SHA-pin lookup time).

## `.github/pip-audit-ignore.txt` discipline (SUPPLY-03)

File format: one CVE / GHSA / PYSEC ID per line. Every entry MUST be preceded by a `# YYYY-MM-DD: <reason>` comment line. The release-gate `local-pip-audit-clean` check (lands in Phase 57) parses this file and rejects entries lacking a dated reason comment.

Tracking directory: `.github/pip-audit-tracking/` holds one Markdown file per ignored CVE (filename `<ID>.md`), documenting:
- The vulnerability
- Why it cannot be fixed (typically a transitive dep awaiting upstream patch)
- The upstream tracker URL
- The condition under which the ignore expires (when the transitive lands the fix)

For v0.6 launch, this directory + ignore file MAY be empty (no known ignores at launch); the discipline lands now so the tooling is wired for the first real CVE.

## Pitfalls

1. **PITFALL: `pip freeze` of the dev venv.** This produces an SBOM that reflects the maintainer's editor extras, not what users actually install. SBOM-01 enforces FRESH-venv via `cyclonedx-py environment <venv>` against a `pip install <wheel>` venv. Tests assert the release.yml step creates `.venv-sbom-*` venvs explicitly.
2. **PITFALL: mutable action tags.** Same as Phase 51 (tj-actions/changed-files CVE-2025-30066). All NEW `uses:` lines in `audit.yml` and the SBOM steps in `release.yml` must be 40-char hex SHAs.
3. **PITFALL: per-job `id-token: write` in `audit.yml`.** `audit.yml` runs on PRs from forks; granting `id-token: write` there would allow fork PRs to mint sigstore identities. The workflow ONLY needs `contents: read` (plus `pull-requests: write` on the dep-review job for PR comments). No `id-token: write` anywhere in `audit.yml`.
4. **PITFALL: `pip-audit` over-pinning.** The pin `pip-audit>=2.10,<3` permits patch upgrades within v2; Dependabot (Phase 54) will tick the minor version forward inside the range without breaking the action interface.
5. **PITFALL: CycloneDX schema version.** Default is whatever the cyclonedx-bom release emits; lock to `--schema-version 1.6` explicitly so a future cyclonedx-bom 8.x default change does not silently shift the SBOM contract.

## Validation Architecture

The phase has both Automated-by-CI checks (most tests) and Manual-Only Verifications (SBOM-03 release-gate diff requires a real signed release).

### Per-task verification map

| Task | Requirement | Verification | Type |
|------|-------------|--------------|------|
| Wave 0 tests (Plan 01) | SBOM-01, SBOM-02, SBOM-03, SUPPLY-01..04 | pytest RED-by-design + non-vacuity fixtures | Automated |
| release.yml SBOM steps (Plan 02) | SBOM-01, SBOM-02, SBOM-03 | regex scan of release.yml + Plan 01 tests flip GREEN | Automated |
| audit.yml (Plan 02) | SUPPLY-01, SUPPLY-02, SUPPLY-04 | regex scan of audit.yml + Plan 01 tests flip GREEN | Automated |
| pyproject [dev] extras (Plan 02) | SUPPLY-01 | pyproject parse + assert `pip-audit` in dev | Automated |
| pip-audit-ignore + tracking (Plan 02) | SUPPLY-03 | file existence + dated-comment lint | Automated |
| verify_release.py check_sbom_signature flip (Plan 02) | SBOM-03 | test calls function directly + asserts behavior | Automated |

### Manual-Only Verifications (recorded at v0.6.0-rc1 rehearsal)

| What | When | Recorded by |
|------|------|-------------|
| `actions/attest-sbom` integration produces a verifiable attestation | v0.6.0-rc1 rehearsal | Maintainer; `gh attestation verify` against the published release |
| Sigstore SBOM bundle binary fixture (`*.cdx.json.sigstore`) | v0.6.0-rc1 rehearsal | Same procedure as Phase 52 Plan 01 canonical fixture (binary lands at rehearsal time) |

These are pre-existing human UAT items carried into Phase 58 / 59 from the v0.6 milestone exit criteria.
