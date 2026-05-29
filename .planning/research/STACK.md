# Stack Research — v0.6 Contribution Gate

**Domain:** supply-chain / contribution-readiness infrastructure (additions to the existing horus-os Python 3.11+ runtime)
**Researched:** 2026-05-29
**Confidence:** HIGH

This file documents ONLY the v0.6 contribution-gate additions. The validated application stack (FastAPI, SQLite, aiosqlite, Anthropic + Gemini SDKs, pydantic, ruff, pytest, GitHub Actions on ubuntu/macos/windows × 3.11/3.12) is unchanged. Treat the tables below as the additive surface that lands during the v0.6 milestone.

---

## Recommended Stack

### Core Technologies (v0.6 additions)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `actions/attest-build-provenance` (GitHub Action) | `v4.1.0` (2025-02-26) | Generate SLSA build-provenance attestations for `dist/*.whl` and `dist/*.tar.gz` and persist them to the GitHub attestations store. Signs keylessly via Sigstore's public-good instance using the workflow's OIDC token. | First-party GitHub action; integrates `id-token: write` + `attestations: write` to produce a verifiable SLSA v1.0 Build Level 2 provenance with `gh attestation verify` as the consumer-side check. No long-lived keys. Direct support for PyPI Trusted Publisher attestations when that comes online. |
| `sigstore/gh-action-sigstore-python` (GitHub Action) | `v3.0.0` line, latest `v3.3.0` (2024-03-26; ships sigstore-python 4.2.0 internally) | Sign and verify arbitrary file artifacts (wheel, sdist, SBOM JSON) with sigstore-python in CI. Produces a portable `.sigstore` bundle on disk. | Independent of GitHub's attestation store, useful if the project later mirrors signatures off-GitHub. Pair with `attest-build-provenance` (which speaks to GitHub's attestation API) so we have BOTH a GitHub-native attestation AND a standalone Sigstore bundle. |
| `sigstore` (Python library) | `>=4.2.0,<5` (released 2026-01-26; requires Python ≥3.10) | The actual signer that the GH action wraps; also runnable from `scripts/release_gate.py` for verify-locally smoke before tagging. | Trail of Bits + Sigstore stewardship; keyless OIDC flow is the de-facto Python signing standard in 2026. The Action and the library agree on the same bundle format. |
| `pip-audit` (Python tool) | `>=2.10.0,<3` (released 2025-12-01) | Scan `pyproject.toml` + resolved deps on every PR; scan installed env at release-gate time. Queries the Python Packaging Advisory Database (PyPI) + OSV. | PyPA-owned, Apache 2.0, NO paid account required, transparent vulnerability database. The `safety` alternative requires a paid Pyup account for commercial use. pip-audit's `--require-hashes` + `--no-deps` modes integrate cleanly with the existing `pyproject.toml`. |
| `pypa/gh-action-pip-audit` (GitHub Action) | `v1.1.0` (2024-08-08; latest tagged release as of 2026-05) | The pre-built GHA wrapper around `pip-audit`. | Same PyPA stewardship as the CLI; one-step integration into a fork-PR-safe `pull_request` workflow. |
| `cyclonedx-bom` (Python tool, command `cyclonedx-py`) | `>=7.3.0,<8` (released 2026-03-30) | Generate a CycloneDX 1.6 JSON SBOM from the installed env (the `environment` subcommand) at release time. Attach to the GitHub Release alongside the wheel + sdist. | CycloneDX over SPDX for Python: cyclonedx-py is the OWASP-stewarded native Python generator, ships `environment` / `requirements` / `poetry` subcommands, and emits the format the broader supply-chain tool surface (osv-scanner, grype, dependency-track) consumes by default. SPDX is acceptable but the Python tooling for it is thinner. CycloneDX schema 1.6 is current; cyclonedx-py 7.3 emits 1.6 by default. |
| Dependabot (GitHub-native, no install) | `version: 2` schema | Automated PRs for `pip` runtime + dev deps and `github-actions` workflow files. | Free, native, no third-party account. Native support for both ecosystems horus-os depends on. Groups + cooldown + ignore patterns let us silence the AI SDK churn (anthropic + google-genai release weekly minor bumps that would otherwise drown out everything else). |
| `actions/dependency-review-action` (GitHub Action) | `v5.0.0` (2026-05-08) | PR-time gate: fail the PR if it introduces a new dep with a known vulnerability or a license outside the allowlist. | First-party GitHub action; runs against the GitHub Advisory DB. Free on public repos with no Advanced Security license required (the GHAS gate only applies to private repos). Complements pip-audit by inspecting the dep diff specifically rather than the resolved set. |
| `pinact` (CLI for SHA pinning + maintenance) | `>=4.0.0,<5` (released 2026-05-25; Go binary, no Python install footprint) | Convert every `uses: org/action@vN.N.N` reference in `.github/workflows/*.yml` to `uses: org/action@<full-40-char-sha> # vN.N.N`. Maintain pinned refs as new versions are released. | GitHub explicitly documents "pinning to a full-length commit SHA is currently the only way to use an action as an immutable release"; pinact automates that operation AND the diffable update. The `dependabot` `github-actions` ecosystem then proposes SHA bumps as PRs that pinact validates. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pypi-attestations` (CLI) | latest from PyPI | Generate / verify PyPI Trusted Publisher attestations from a wheel + sdist when publishing. | OPTIONAL — only if v0.6 also lights up PyPI Trusted Publishing in the same milestone. If PyPI publishing remains a future milestone, defer. |
| `cyclonedx-python-lib` | `>=10` | Library backing cyclonedx-bom; also usable directly if a future script needs to assemble a custom SBOM. | INDIRECT — pulled transitively by cyclonedx-bom. Do not depend on it directly in v0.6. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pip-audit` in `[dev]` extras | Run as part of every `pip install -e '.[dev]'` venv so contributors can scan locally before pushing. | Add to `pyproject.toml` `[project.optional-dependencies].dev`. Cost is one transitive dep tree; the binary is small. |
| `cyclonedx-bom` invoked from CI only | Avoid bloating `[dev]`. SBOM generation is a release-time concern, not a per-commit one. | Install on the fly in the release workflow: `pip install cyclonedx-bom>=7.3,<8`. |
| Signed git tags via Sigstore-git (`gitsign`) | OUT OF SCOPE for v0.6. | RECOMMEND: keep existing annotated `git tag -a` shape for v0.6 (the existing tags v0.1..v0.5 are unsigned per the milestone context). The artifact-side attestation already provides a verifiable release signature. Sigstore-signed tags is a post-v0.6 nice-to-have. |

---

## Installation

### `pyproject.toml` additions (runtime-side)

```toml
# Add to existing [project.optional-dependencies] table:
[project.optional-dependencies]
dev = [
    # ...existing entries...
    "pip-audit>=2.10,<3",
]
```

### CI-side (pinned at SHA in actual workflows; tags shown here for readability)

```bash
# pip-audit is in [dev]; nothing to install in the audit workflow beyond:
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip_audit -s osv .                # or pip-audit .

# SBOM generation (release.yml only; install on the fly):
python -m pip install 'cyclonedx-bom>=7.3,<8'
python -m cyclonedx_py environment --of JSON -o dist/horus-os-${{ github.ref_name }}-sbom.cyclonedx.json
```

### Local maintainer tools (one-time setup)

```bash
# pinact (Go binary; install via release page or brew):
brew install pinact   # or: go install github.com/suzuki-shunsuke/pinact/v4/cmd/pinact@latest

# Verify pinning is current before opening a PR:
pinact run --check .github/workflows/*.yml
```

---

## Integration step shapes (GitHub Actions YAML outlines)

Each snippet uses readable tags for clarity; in the actual workflow files, every third-party `uses:` MUST be SHA-pinned per the "What NOT to Use" table. First-party `actions/*` and `github/*` may stay on a major tag (GitHub's own policy permits this) but the project should still pin them for consistency.

### 1. Supply-chain scan on every PR (fork-safe)

File: `.github/workflows/audit.yml`

```yaml
name: audit
on:
  pull_request:        # safe trigger: runs in fork context, NO secrets, read-only GITHUB_TOKEN
    branches: [main]
  push:
    branches: [main]
permissions:
  contents: read       # least-privilege default; no secrets needed for pip-audit
jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha> # v5
        with:
          persist-credentials: false
      - uses: actions/setup-python@<sha> # v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: python -m pip install --upgrade pip && python -m pip install -e ".[dev]"
      - uses: pypa/gh-action-pip-audit@<sha> # v1.1.0
        with:
          inputs: .                    # audits pyproject.toml-resolved deps
          vulnerability-service: osv
  dep-review:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@<sha> # v5
        with:
          persist-credentials: false
      - uses: actions/dependency-review-action@<sha> # v5.0.0
        with:
          fail-on-severity: moderate
          comment-summary-in-pr: on-failure
          # license allowlist — Apache-2.0, MIT, BSD-2/3, ISC, PSF-2.0
          allow-licenses: Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0
```

### 2. Release-time signing + SBOM (push of `vX.Y.Z` tag)

File: `.github/workflows/release.yml`

```yaml
name: release
on:
  push:
    tags: ['v*.*.*']
permissions:
  contents: write       # for the GitHub Release upload
  id-token: write       # for Sigstore OIDC keyless signing
  attestations: write   # for attest-build-provenance
jobs:
  build-sign-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha> # v5
        with:
          persist-credentials: false
      - uses: actions/setup-python@<sha> # v5
        with:
          python-version: "3.12"
      - run: python -m pip install --upgrade pip build && python -m build
      # Generates and uploads a SLSA Build L2 provenance attestation to GH.
      - uses: actions/attest-build-provenance@<sha> # v4.1.0
        with:
          subject-path: 'dist/*'
      # ALSO produces a portable .sigstore bundle on disk (belt-and-braces).
      - uses: sigstore/gh-action-sigstore-python@<sha> # v3.3.0
        with:
          inputs: ./dist/*.whl ./dist/*.tar.gz
      - name: Generate CycloneDX SBOM
        run: |
          python -m pip install 'cyclonedx-bom>=7.3,<8'
          python -m pip install -e '.[all]'
          python -m cyclonedx_py environment \
            --of JSON \
            -o dist/horus-os-${{ github.ref_name }}-sbom.cyclonedx.json
      - uses: actions/attest-build-provenance@<sha> # v4.1.0
        with:
          subject-path: 'dist/horus-os-*-sbom.cyclonedx.json'
      - name: Upload to GitHub Release
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release upload ${{ github.ref_name }} dist/* --clobber
```

### 3. Dependabot config

File: `.github/dependabot.yml`

```yaml
version: 2
updates:

  # Runtime + dev Python deps
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    groups:
      ai-sdks:                                # the weekly-churn group
        patterns: ["anthropic", "google-genai"]
        update-types: ["minor", "patch"]
      otel:
        patterns: ["opentelemetry-*"]
      web-stack:
        patterns: ["fastapi", "uvicorn", "httpx", "pydantic", "starlette"]
      dev-tools:
        patterns: ["pytest*", "ruff", "pip-audit", "cyclonedx-bom"]
    cooldown:
      default-days: 3              # smooth out same-day point releases
      semver-major-days: 14
    ignore:
      # Block accidental drift past upper bounds the runtime pins.
      - dependency-name: "pydantic"
        versions: [">=3"]
      - dependency-name: "opentelemetry-sdk"
        versions: [">=2"]
      - dependency-name: "opentelemetry-exporter-otlp-proto-http"
        versions: [">=2"]

  # GitHub Actions used in .github/workflows/*
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    groups:
      actions:
        patterns: ["*"]
```

### 4. Fork-PR hardening pattern

| Pattern | Why | Wire-in |
|---------|-----|---------|
| Default trigger = `pull_request`, NEVER `pull_request_target` | `pull_request_target` runs in the BASE-repo context with SECRETS available — multiple 2026 CVEs (Trivy, TanStack Mini Shai-Hulud) trace to this trigger. `pull_request` runs in fork context with a read-only `GITHUB_TOKEN` and no secrets. | Already the case for the existing `ci.yml`; assert this in CIHARD-* requirements. |
| `permissions:` block on every job | Default `GITHUB_TOKEN` write permissions are scoped down to `contents: read` unless the job actually needs more. | Add to all existing jobs in `ci.yml`; require for every new workflow. |
| `safe-to-test` label gate for expensive fork-PR jobs | If the milestone needs jobs that DO need secrets (e.g., an integration test against a real provider), gate them behind a maintainer-applied label. | Workflow snippet: `if: github.event.pull_request.head.repo.fork == false || contains(github.event.pull_request.labels.*.name, 'safe-to-test')`. For v0.6 specifically, NO such job exists yet — keep all CI fork-safe by default and document the pattern in CONTRIBUTING.md for future use. |
| `actions/checkout@... with: persist-credentials: false` | Prevents the default GITHUB_TOKEN from being written into `.git/config` where a later step could exfiltrate it. | Add to every checkout step in every workflow. |
| Workflow file pinning via pinact | Mutable tags can be force-moved by a compromised action publisher. SHA pinning makes the action immutable. | Run `pinact run .github/workflows/*.yml` as a local pre-commit; CI can verify with `pinact run --check`. |
| `workflow_run` for write-back actions (PR comments, label automation) | Lets the fork-PR's `pull_request` job stay read-only and the privileged write happens in a separate workflow triggered by the read-only run's completion, with no access to fork code. | Not required for v0.6 (no PR-commenting bot yet). Document in CONTRIBUTING.md as the canonical pattern for future expansion. |

---

## Release-gate wire-in (additions to `scripts/release_gate.py`)

The existing release gate runs 8 checks (4 v0.4 + 4 v0.5). v0.6 should add five more checks driven by the SIGN, SUPPLY, and CIHARD requirements. Each follows the existing `CheckResult` dataclass shape and the `--check {name}` CLI flag pattern at `scripts/release_gate.py:680-756`.

| New check | Function name (proposed) | What it asserts | Diagnostic on fail |
|-----------|--------------------------|-----------------|--------------------|
| `release-workflow-present` | `check_release_workflow_present` | `.github/workflows/release.yml` exists AND contains both `attest-build-provenance` AND `sigstore-python` literals. Mirrors the existing `check_ci_two_variant_smoke_present` pattern (string-grep the workflow file). | `release.yml missing attest-build-provenance + sigstore-python literals` |
| `audit-workflow-present` | `check_audit_workflow_present` | `.github/workflows/audit.yml` exists AND contains `pip-audit` literal AND `dependency-review-action` literal. | `audit.yml missing pip-audit + dependency-review-action` |
| `local-pip-audit-clean` | `check_local_pip_audit_clean` | `pip-audit -s osv .` exits 0 against the current pyproject. Catches vulnerable transitive deps before the maintainer cuts a tag. | `pip-audit reports N vulnerability/ies in deps: <first 5 IDs>` |
| `dependabot-config-present` | `check_dependabot_config_present` | `.github/dependabot.yml` exists AND `version: 2` AND has BOTH `package-ecosystem: pip` and `package-ecosystem: github-actions` entries. | `dependabot.yml missing required ecosystems` |
| `actions-pinned-by-sha` | `check_actions_pinned_by_sha` | Every `uses: <org>/<action>@<ref>` in `.github/workflows/*.yml` uses a 40-char hex SHA (regex `@[0-9a-f]{40}\b`). | `Unpinned action references: <list>` |

Total release-gate surface after v0.6: 8 (v0.4 + v0.5) + 5 (v0.6) = 13 checks.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `actions/attest-build-provenance@v4` (GitHub-native attestation) | `slsa-framework/slsa-github-generator` reusable workflow (v2.1.0) | Use slsa-github-generator if the project needs SLSA Build Level 3 (isolated builder). For v0.6, Level 2 via attest-build-provenance is sufficient and one fewer moving part. Level 3 can be a v0.7 upgrade. |
| `sigstore/gh-action-sigstore-python@v3` | `sigstore/cosign-installer` + `cosign sign-blob` | Use cosign if the artifact set extends to OCI containers in a future milestone. For Python wheels + sdists + an SBOM JSON, sigstore-python is the more idiomatic and Python-aligned choice. |
| `pip-audit` (PyPA, OSV + PyPI DB) | `safety` (Pyup.io) | NEVER. Safety 3.x requires authentication, the free tier is non-commercial only, and the project's anti-goal explicitly bans paid-account dependencies. pip-audit is the only valid choice. |
| `cyclonedx-bom` / `cyclonedx-py` | `syft` (Anchore, Go binary, v1.44.0) | Use syft if the project also ships container images or needs SPDX output alongside CycloneDX. For a pure Python-source artifact, cyclonedx-py inspects the same source-of-truth (`pyproject.toml` + installed env) without a Go toolchain in CI and produces richer Python-specific metadata. |
| CycloneDX 1.6 JSON | SPDX 2.3 JSON | Use SPDX if a downstream consumer (e.g., a US-federal procurement requirement) mandates SPDX specifically. CycloneDX is the OWASP / Python-ecosystem default; downstream conversion via `cyclonedx-cli convert` is trivial if SPDX is needed later. |
| Native Dependabot | `renovatebot/renovate` (self-hosted GitHub App) | Use Renovate ONLY if Dependabot's grouping turns out insufficient (Renovate has more advanced rules). For v0.6, Dependabot's groups + cooldown + ignore cover the AI-SDK churn problem cleanly and require zero installation. |
| `pinact` | `sethvargo/ratchet` (Go binary) or manual SHA edits | Both pinact and ratchet are valid. pinact is newer (v4.0.0 May 2026) and actively maintained; ratchet is fine if a maintainer already uses it. Manual edits are out — too easy to drift. |
| Annotated git tags (existing maintainer shape) | Sigstore-signed tags via `gitsign` | Defer to v0.7+. The artifact attestation already gives us a verifiable, signed release; signing the tag itself is a separable concern, and `gitsign` adds a build-time cosign dependency the project does not otherwise need. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `pull_request_target` trigger | Runs untrusted fork code with BASE-repo secrets available. The 2026 Trivy and TanStack Mini Shai-Hulud incidents both trace to misuse of this trigger. | `pull_request` (default for ALL v0.6 jobs) + `workflow_run` if write-back is needed later. |
| `safety` (paid-tier, account-locked Pyup database) | Free tier is non-commercial-only and requires login; violates the horus-os "no paid third-party account" anti-goal explicitly listed in PROJECT.md and the milestone context. | `pip-audit` — Apache 2.0, no account, transparent OSV + PyPI DB. |
| Hosted SBOM / scanning SaaS (Snyk, Black Duck, FOSSA, Mend, Sonatype Lifecycle, Dependency-Track SaaS) | All require paid accounts or per-seat licensing; violate the anti-goal. | `cyclonedx-bom` generates the SBOM locally; attach to the GitHub Release. Self-hosted Dependency-Track is fine as a private maintainer convenience but should never be a release dependency. |
| Mutable action references (`uses: foo/bar@v1`) without SHA pin | A compromised action publisher can move tags; the project trusted-base then runs arbitrary code. GitHub's own security guide labels SHA pinning as "the only way to use an action as an immutable release." | `uses: foo/bar@<40-char-sha> # v1` — enforced by the new `actions-pinned-by-sha` release-gate check; auto-maintained by pinact + Dependabot github-actions. |
| Long-lived signing keys (maintainer-controlled GPG / cosign keypair) | Key rotation is a manual maintenance burden, and a leaked key is silent. Keyless OIDC via Sigstore binds signatures to the workflow identity, so revocation = repo settings change. | Sigstore OIDC (attest-build-provenance + gh-action-sigstore-python). |
| SBOM as XML | The Python supply-chain tooling overwhelmingly defaults to JSON; XML is a CycloneDX option but adds friction for verifiers. | CycloneDX JSON (`--of JSON`). |
| `actions/checkout` without `persist-credentials: false` on fork-PR jobs | Default writes the GITHUB_TOKEN into `.git/config`; a later malicious step in the same job can exfiltrate it. | Always set `persist-credentials: false` on workflows that handle fork code. |
| Combined release+publish in one workflow with PyPI Trusted Publishing | PyPI Trusted Publishing is OUT OF SCOPE for v0.6 (the project does not currently publish to PyPI; the milestone focus is contribution-gate readiness). | Stage PyPI publishing as a separate post-v0.6 milestone; v0.6 only signs and attaches artifacts to the GitHub Release. |
| GHAS-gated features (Code Scanning, Secret Scanning, Push Protection) for private-repo licensing | These features are free on public repos for some surfaces, but `dependency-review-action` is the only GHAS-adjacent action we rely on, and it works free on public repos. Don't anchor any v0.6 requirement on a GHAS license. | Stick to the public-repo-free feature set: dependency-review-action, attest-build-provenance, dependabot. |

---

## Stack Patterns by Variant

**If a v0.6 deliverable adds CHANGELOG-driven PR automation (e.g., a release-note bot that comments on merged PRs):**
- Use a `workflow_run` trigger consuming the `audit` workflow's completion event, with explicit `permissions: pull-requests: write`.
- The fork-PR's own `pull_request` job stays read-only; only the `workflow_run` job (which runs from the BASE-repo, NOT the fork) gets write scope. The fork's code is never executed in the privileged context.

**If the project later decides to publish to PyPI:**
- Add a third job to `release.yml`: `pypa/gh-action-pypi-publish@release/v1` using OIDC Trusted Publishing (no API token).
- The existing `attest-build-provenance` step generates PyPI Trusted Publisher attestations automatically; PyPI surfaces them on the project page.
- This is a v0.7+ concern; v0.6 stops at "signed, attested, SBOM-attached artifacts on the GitHub Release."

**If the maintainer wants stricter SLSA Build L3 in a later milestone:**
- Replace the inline `release.yml` build step with `slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.1.0` as a reusable workflow.
- v0.6 baseline = L2 (sufficient for the contribution-gate goal); L3 is a documented v0.7 option, not a v0.6 requirement.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `sigstore-python 4.2.0` | Python ≥3.10 | Project already requires Python ≥3.11, so this is satisfied. Drop sigstore < 4 from any historical references; the 3.x line is end-of-life. |
| `gh-action-sigstore-python v3.x` | `sigstore-python 4.x` | The v3.x action pins to sigstore-python 4.2.0 internally. Tying the action major version to the lib major version is the project's stated contract. |
| `cyclonedx-bom 7.3` | `cyclonedx-python-lib >=10` | Transitive; do not pin the lib in `pyproject.toml`. |
| `pip-audit 2.10` | Python ≥3.8 | No constraint conflict; pip-audit's OSV mode requires network access in CI but no GitHub-specific token. |
| `actions/attest-build-provenance v4` | Requires `id-token: write` + `attestations: write` workflow permissions | v4 changed the underlying implementation to wrap `actions/attest`; functionally equivalent to the v1/v2 attestation shape from a consumer's perspective. |
| `dependency-review-action v5` | Requires Node 24 runner (Runner v2.327.1+) | GitHub-hosted runners satisfy this in May 2026; no concern. |
| `pinact v4` | Self-contained Go binary; no Python compatibility surface | Compatible with all GHA YAML versions; no upper bound. |

---

## Anti-goal callouts (explicit, per quality-gate)

These were considered and explicitly rejected to honor the milestone's anti-goals:

- **No paid SBOM / scanning service.** Dependency-Track SaaS, Snyk, Black Duck, FOSSA, Mend, Sonatype Lifecycle — all require commercial licensing or per-seat billing. The recommended stack is 100% free / OSS / GitHub-native.
- **No safety (the Pyup tool).** Even though it is a frequently-cited "second opinion" to pip-audit, the post-3.x license model makes it a paid-account dependency for any commercial use; it has no place in horus-os.
- **No GitHub Advanced Security (GHAS) features for public-repo use.** The recommended `dependency-review-action` works free on public repos; we do not rely on Code Scanning, Secret Scanning, or Push Protection features that GHAS gates on a license for private repos.
- **No PyPI publishing in v0.6.** The milestone scope is contribution-gate readiness; PyPI publishing is a separable downstream concern. Including it would force a Trusted Publisher setup that adds review surface without serving the v0.6 goal.
- **No sigstore-git / gitsign for tag signing in v0.6.** Annotated tags + the existing maintainer-shape signature (or unsigned-but-annotated if the maintainer has not yet generated a keypair) is sufficient; the artifact-side signature carries the verifiable release identity. Tag-signing is a v0.7+ option.

---

## Sources

- `/sigstore/docs` (Context7) — verified `gh-action-sigstore-python` v3.0.0 / v3.1.0 / v3.3.0 step shape, Python signing API.
- `/pypa/pip-audit` (Context7) — verified `--require-hashes`, `--no-deps`, `-s {pypi,osv,esms}`, `--fix`, `--disable-pip`, and the `pypa/gh-action-pip-audit@v1.1.0` step shape.
- `/cyclonedx/cyclonedx-python-lib` (Context7) — verified `cyclonedx-python-lib` install and validator API; confirmed `cyclonedx-bom` (`cyclonedx-py`) CLI is the user-facing tool.
- [sigstore on PyPI](https://pypi.org/project/sigstore/) — confirmed v4.2.0 (2026-01-26), Production/Stable, requires Python ≥3.10.
- [pip-audit on PyPI](https://pypi.org/project/pip-audit/) — confirmed v2.10.0 (2025-12-01).
- [cyclonedx-bom on PyPI](https://pypi.org/project/cyclonedx-bom/) — confirmed v7.3.0 (2026-03-30), subcommands `environment`/`requirements`/`pipenv`/`poetry`.
- [safety on PyPI](https://pypi.org/project/safety/) — confirmed paid-account requirement, disqualifying for the horus-os anti-goal.
- [actions/attest-build-provenance releases](https://github.com/actions/attest-build-provenance/releases) — confirmed v4.1.0 (2025-02-26).
- [sigstore/gh-action-sigstore-python releases](https://github.com/sigstore/gh-action-sigstore-python/releases) — confirmed v3.3.0 (2024-03-26) ships sigstore-python 4.2.0.
- [pypa/gh-action-pip-audit releases](https://github.com/pypa/gh-action-pip-audit/releases) — confirmed v1.1.0 (2024-08-08) is the latest stable.
- [actions/dependency-review-action](https://github.com/actions/dependency-review-action) — confirmed v5.0.0 (2026-05-08), runs on Node 24 runner.
- [GitHub docs: configuration options for dependabot.yml](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file) — confirmed v2 schema, groups / cooldown / ignore / open-pull-requests-limit fields.
- [GitHub docs: security hardening for GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions) — confirmed "pin to full-length commit SHA is currently the only way to use an action as an immutable release."
- [suzuki-shunsuke/pinact](https://github.com/suzuki-shunsuke/pinact) — confirmed v4.0.0 (2026-05-25), `@<sha> # <tag>` rewrite shape.
- [slsa.dev spec v1.0 levels](https://slsa.dev/spec/v1.0/levels) — verified Build L1/L2/L3 definitions; L2 = hosted build platform with signed provenance (achievable via attest-build-provenance); L3 = hardened/isolated builder (achievable via slsa-github-generator reusable workflow).
- [slsa-framework/slsa-github-generator](https://github.com/slsa-framework/slsa-github-generator) — confirmed v2.1.0 (2025-02-24), generic generator achieves SLSA Build L3.
- [browniebroke.com — attest build provenance for a Python package](https://browniebroke.com/blog/2024-08-08-attest-build-provenance-for-a-python-package-in-github-actions/) — corroborated end-to-end Python wheel attestation flow.
- [GitHub Docs: artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations) — confirmed `gh attestation verify` consumer-side check.
- [sixfeetup.com — Safety and pip-audit: Comparing Security Tools](https://sixfeetup.com/blog/safety-pip-audit-python-security-tools) — corroborated pip-audit-over-safety recommendation; transparent DB management, no commercial subscription.
- [earezki.com — Secure GitHub Actions: Implementing pull_request_target Without Supply Chain Risks (2026-03)](https://earezki.com/ai-news/2026-03-21-pullrequesttarget-without-regret-secure-fork-prs-in-github-actions/) — corroborated fork-PR hardening pattern, recent CVE references (Trivy March 2026, TanStack Mini Shai-Hulud May 2026).
- [GitHub community discussion #180109 — disallow access to secrets for pull_request trigger](https://github.com/orgs/community/discussions/180109) — corroborated `pull_request` = read-only token + no secrets by default.
- [Sbomify — SBOM Generation Tools Compared: Syft, Trivy, cdxgen (2026-01-26)](https://sbomify.com/2026/01/26/sbom-generation-tools-comparison/) — corroborated cyclonedx-py vs syft tradeoff for Python-only projects.

---
*Stack research for: v0.6 contribution-gate additions to the horus-os Python 3.11+ supply chain.*
*Researched: 2026-05-29 — confidence HIGH (every version verified against PyPI or the upstream release page; every step shape verified against Context7 or official GitHub docs).*
