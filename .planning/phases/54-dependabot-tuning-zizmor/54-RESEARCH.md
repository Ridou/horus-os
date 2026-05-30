# Phase 54 Research: Dependabot tuning + zizmor

**Researched:** 2026-05-30 (auto-generated, condensed for execution)

## Phase Boundary

Land `.github/dependabot.yml` v2 covering pip + github-actions ecosystems with grouped version updates + un-grouped security updates; add `.github/workflows/zizmor.yml` as a static-analysis second layer over actionlint.

## Dependabot v2 shape

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
    cooldown:
      default-days: 3
      semver-major-days: 14
    groups:
      ai-sdks:
        applies-to: version-updates
        patterns:
          - "anthropic"
          - "google-genai"
      otel:
        applies-to: version-updates
        patterns:
          - "opentelemetry-*"
      web-stack:
        applies-to: version-updates
        patterns:
          - "fastapi"
          - "uvicorn"
          - "httpx"
      dev-tools:
        applies-to: version-updates
        patterns:
          - "pytest*"
          - "ruff"
          - "pip-audit"
    labels:
      - "dependencies"
      - "type:dev"

  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
    labels:
      - "dependencies"
      - "github-actions"
```

The key rule (DEPBOT-02): NO `applies-to: security-updates` matcher on any group. Dependabot's default is one PR per security advisory when no security-update group matcher is defined. Security PRs get `security-update` label via the per-update `labels:` block + Dependabot's automatic label inheritance from advisory type. The test fixture (Plan 01) scans the file and asserts no `applies-to: security-updates` substring anywhere.

The pin reference (anthropic) covers the v0.5 base-deps stub; google-genai is in [gemini] extras; opentelemetry-* covers [otel]; fastapi/uvicorn/httpx covers [dashboard] + [dev]; pytest*/ruff/pip-audit covers [dev]. Discord and Slack are intentionally omitted (rarely-updated and their churn is low signal).

## zizmor workflow shape

`.github/workflows/zizmor.yml`:

```yaml
name: zizmor

on:
  pull_request:
    paths:
      - ".github/workflows/**"
      - ".github/workflows/zizmor.yml"
  push:
    branches: [main]
    paths:
      - ".github/workflows/**"

permissions: read-all

jobs:
  zizmor:
    name: zizmor static analysis
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
      - uses: zizmorcore/zizmor-action@5f14fd08f7cf1cb1609c1e344975f152c7ee938d # v0.5.6
```

Per-job `security-events: write` only on this job (mirrors Phase 51 actionlint per-job permission shape). zizmor reads workflow files and emits SARIF; the action handles SARIF upload to the Security tab via GHA's code-scanning interface (no separate upload step needed).

## Test files for Wave 0

- `tests/test_dependabot_yml_structure.py`: parses YAML via the project's PyYAML if installed else stdlib (PyYAML is not a horus-os dep so use a substring approach mirroring Phase 53's release.yml regex pattern); asserts the version, ecosystem entries, group names, NO `applies-to: security-updates`.
- `tests/test_zizmor_workflow_structure.py`: scans `.github/workflows/zizmor.yml`; asserts the trigger, permissions, action invocation, SHA-pin.

Wave 0 tests RED-by-design until Plan 02 creates the files. Non-vacuity scanners via tmp_path proven to fire.

## Pitfalls

1. **PITFALL: `applies-to: security-updates` group matcher** would bundle multiple CVEs into one PR. DEPBOT-02 forbids this; test asserts the literal string is absent from the file.
2. **PITFALL: zizmor runs on fork PRs** triggering `pull_request` could allow fork code to influence analysis. Mitigated by: workflow itself has `permissions: read-all` + `contents: read`, no checkout-PR-head into a privileged context (CIHARD-01).
3. **PITFALL: cooldown 0** would let Dependabot churn PRs on every micro-release. The 3-day default + 14-day major-bump cooldown matches industry baselines.
