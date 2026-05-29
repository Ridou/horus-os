# Feature Research

**Domain:** Contribution-gate readiness for a self-hosted OSS Python project (horus-os v0.6, flipping from solo-dev to outside-PRs-welcome)
**Researched:** 2026-05-29
**Confidence:** HIGH for table-stakes mechanics (sigstore, dependabot, fork-PR hardening), MEDIUM for which differentiators are worth horus-os's CI minutes, HIGH for the anti-feature list (CLA, mandatory DCO, mandatory Slack are well-documented anti-patterns).

## Scope

The v0.6 milestone flips ONE bit externally ("outside PRs welcomed and safe to merge") and lands the infrastructure that makes the flip safe internally. This document inventories the features that any mature 2026 OSS Python project must, should, or must-not ship to support that flip, grouped into seven categories:

1. CI signing + signed releases
2. Supply-chain hygiene (SBOM, vulnerability scanning, Dependabot)
3. Fork-PR hardening
4. Contributor experience (CONTRIBUTING.md, PR template, issue templates)
5. SECURITY.md + disclosure
6. CODEOWNERS + triage
7. Gate-flip mechanics (external surface changes when v0.6.0 ships)

Existing v0.5.0 baseline is already partial: bug/feature issue templates exist, PR template exists, saved replies exist, claim-watcher workflow exists, basic SECURITY.md and CONTRIBUTING.md exist. The gaps below are the v0.6 delta.

## Feature Landscape

### Table Stakes (Users Expect These)

Mature OSS Python projects in 2026 are expected to have all of the following. A first-time outside contributor checks for them before opening a PR, and a security-conscious downstream consumer checks for them before adding the package to their stack. Missing any of these in v0.6 means the gate-flip is incomplete.

| # | Feature | Why Expected | Complexity | Shipped definition |
|---|---------|--------------|------------|--------------------|
| T1 | **PyPI Trusted Publishing via OIDC** (`pypa/gh-action-pypi-publish`) | Long-lived PyPI API tokens are the #1 supply-chain compromise vector in 2025-2026. Trusted Publishing eliminates the stored credential. About 22% of PyPI repos have already migrated. | LOW | `release.yml` workflow publishes to PyPI with `id-token: write`; no `PYPI_API_TOKEN` secret exists in the repo. Configured in PyPI project settings as "Trusted Publisher: GitHub > Ridou/horus-os > release.yml > pypi". Exemplar: every modern PyPA project, e.g. `psf/black`. |
| T2 | **PEP 740 attestations on every release artifact** | `pypa/gh-action-pypi-publish` generates and uploads Sigstore-backed PEP 740 attestations automatically with no extra config when `id-token: write` is set. PyPI rejects manual non-Trusted-Publisher attestations. GA since Nov 2024. | LOW (free with T1) | Every wheel + sdist on PyPI has a green "verified" attestation badge on `https://pypi.org/project/horus-os/<version>/`. Verifiable via `python -m pypi_attestations verify pypi --repository https://github.com/Ridou/horus-os horus_os-0.6.0-py3-none-any.whl`. Exemplar: `pip install pypi-attestations && pypi-attestations verify pypi --repository https://github.com/pypa/sampleproject sampleproject-*.whl`. |
| T3 | **Signed git tags** (sigstore-keyless or GPG) | A signed release tag binds the released code to a verifiable maintainer identity. Required by SLSA L2+ and by most downstream rebuild auditors. | LOW | Release workflow runs `git tag -s v0.6.0` (GPG) OR a sigstore-keyless tag attestation is uploaded as a release asset. Verifiable via `git verify-tag v0.6.0`. Exemplar: `cryptography` project signs tags. |
| T4 | **SBOM generated and attached to the GitHub Release** | Required by US Executive Order 14028 ecosystem and increasingly mandated for any package included in a regulated stack. CycloneDX is the de facto standard in the Python ecosystem (per Sbomify's 2026-03 PyPI scan: of the 1.58% of packages shipping SBOMs, ALL are CycloneDX, ZERO are SPDX). | LOW | `release.yml` runs `cyclonedx-py environment` (or `cyclonedx-py requirements`), uploads `horus-os-0.6.0.cdx.json` as a release asset via `softprops/action-gh-release`, and the release-gate refuses to ship a tag without it. CycloneDX 1.6+ JSON. Exemplar: projects shipping via `cyclonedx-bom` integrated through `softprops/action-gh-release`. |
| T5 | **pip-audit gating on every PR** (PyPA-blessed scanner, OSV-backed) | Dependabot alerts catch known-bad versions in the dep tree but only AFTER merge. pip-audit blocks the PR if a vuln is present. PyPA-blessed, no third-party paid account required. | LOW | `.github/workflows/security.yml` runs `pypa/gh-action-pip-audit@v1` on every PR. Default fail-on-vuln (NOT `internal-be-careful-allow-failure`). Required status check on `main` branch protection. Exemplar: `pypa/pip-audit` itself dogfoods this. |
| T6 | **Dependabot config for `pip` and `github-actions`** | The 2026 standard is `version: 2` with `package-ecosystem: pip` AND `package-ecosystem: github-actions`, both on `weekly` cadence, with grouped updates. GitHub Actions ecosystem is critical — unpinned action references are how supply-chain attacks land. | LOW | `.github/dependabot.yml` with two ecosystems, weekly schedule, grouped patterns (one PR per ecosystem per week, not N PRs). Cooldown of 5 days on Actions to dodge zero-day-malicious releases. Exemplar: `dependabot/dependabot-core/.github/dependabot.yml`. |
| T7 | **All GitHub Actions pinned to full commit SHA** | Tag references (`@v4`) are mutable. SHA pinning is the only immutable reference and is required by SLSA, OpenSSF Scorecard, and StepSecurity. Dependabot can still update the SHAs via PR. | MEDIUM (initial conversion is one-time grunt work; `pinact` or `zizmor` automates it) | Every `uses:` line in `.github/workflows/*.yml` references a 40-char SHA with a `# v4.1.7` comment. `zizmor .github/workflows/` passes clean in CI. Exemplar: `pip-audit`'s own workflows. |
| T8 | **`pull_request_target` is metadata-only OR absent entirely** (no fork-code checkout in trusted context) | This is the #1 fork-PR security mistake of the last three years (the "Pwn Request" class). Still hitting major projects in 2026. | LOW | The fork-CI pipeline uses `pull_request` (untrusted token, no secrets) for code execution. If `pull_request_target` is used at all, it ONLY runs metadata steps (labeling, commenting) and never `actions/checkout` of `pull_request.head.sha`. Exemplar: `numpy/numpy` audit-passed pattern. |
| T9 | **First-time-contributor approval gate enabled** | GitHub-native feature, no code needed. Default since 2021. Set "Require approval for first-time contributors" in repo Settings → Actions → General. Approval is per-workflow-run, so every push re-triggers it. | LOW | Repo setting verified at gate-flip time and documented in `docs/MAINTAINER-RUNBOOK.md`. Exemplar: any well-run public project. |
| T10 | **Branch protection on `main`** with required status checks | Without this, the maintainer can accidentally merge a red PR. Status check names must match exactly (matrix jobs need their full name including the OS+Python suffix). | LOW | `main` is protected: required reviews ≥1, required status checks include `lint+test / ubuntu-latest / Python 3.12`, `install-smoke / *`, `install-smoke-plugin / *`, `pip-audit`, dismiss stale reviews, no force-push. Documented in `docs/MAINTAINER-RUNBOOK.md`. Exemplar: standard GitHub setup. |
| T11 | **`SECURITY.md` with private channel + acknowledgement SLO** | Industry convention: 48h acknowledgement, 7d initial response, 90d coordinated disclosure. GHSA is the table-stakes channel (no separate PGP key needed). | LOW | Existing `SECURITY.md` upgraded: 7d ack → **48h ack** (industry norm in 2026), explicit 90d disclosure window, scope expanded to cover plugins (v0.5), reproducer-required language. Exemplar: `pydantic/pydantic` SECURITY.md is minimal-but-correct ("use the Security tab"). horus-os expands slightly because its threat surface (capability grants, fork PRs) is larger. |
| T12 | **`CONTRIBUTING.md` with claim flow, branch policy, commit format, test/doc expectations** | Existing file already covers most of this. v0.6 delta: remove the "not accepting outside PRs" banner, add a "first PR walkthrough" subsection. | LOW | Banner rewritten ("contributions welcomed"). New sections: "Your first PR: end-to-end walkthrough", "What happens after you open a PR" (label, automated checks, review SLA, merge cadence). Existing scope-check, dev-setup, workflow, code-style sections retained verbatim. Exemplar: `encode/httpx/docs/contributing.md` ("contributions should generally start out with a discussion"). |
| T13 | **PR template with `Closes #`, test plan, checklist** | Existing file is well-structured. v0.6 delta: remove "NOTICE: not accepting outside PRs" HTML comment, add explicit "I have read CONTRIBUTING.md" checkbox. | LOW | Existing PULL_REQUEST_TEMPLATE.md gets the contribution banner removed and gets one new checkbox: `[ ] I have read CONTRIBUTING.md and CODE_OF_CONDUCT.md`. Exemplar: the existing template is already at the bar set by `pydantic/pydantic`. |
| T14 | **Issue templates: bug, feature, security pointer** | Existing bug + feature templates work. v0.6 delta: update the "heads-up: not accepting PRs" markdown blocks to "first-time contributors welcome; read CONTRIBUTING.md before substantial PRs." `config.yml` already points security reports to GHSA correctly. | LOW | Both YAML templates updated. `config.yml` unchanged. Exemplar: existing `config.yml` matches the pydantic pattern. |
| T15 | **CODEOWNERS** with maintainer auto-assignment | Auto-assigns the maintainer as reviewer on every PR, no exceptions. For a solo maintainer, this is one line: `* @Ridou`. | LOW | `.github/CODEOWNERS` ships with `* @Ridou` plus area-specific overrides (`/docs/ @Ridou`, `/src/horus_os/plugins/ @Ridou`). Trivial today; valuable if a second maintainer joins. Exemplar: `python/cpython/.github/CODEOWNERS`. |
| T16 | **CODE_OF_CONDUCT.md with a reporting address** | Existing file references Contributor Covenant 2.1 but says "no public reporting address until v0.1 ships." That deadline has long passed. Reporting channel must be filled in. | LOW | Existing file edited: reporting channel becomes "open a private GHSA-style advisory at https://github.com/Ridou/horus-os/security/advisories/new, mark the title `[conduct]`" OR a dedicated email if the maintainer has one. The "private GHSA" route reuses existing infra. Exemplar: `psf/black` uses `psf-conduct@python.org`. |
| T17 | **STATUS.md TL;DR rewritten** to "contributions OPEN" | The single externally-visible bit-flip. STATUS.md is what every contributor reads first (linked from README banner, saved replies, claim-watcher, etc.). | LOW | TL;DR rewritten: "horus-os v0.6.0 opens for outside contributions. PRs from forks are reviewed. Issue claims via the `claim:` label or by maintainer assignment are honored. See CONTRIBUTING.md." Milestone table gets v0.6 marked SHIPPED. "How to follow along" section gets a new "How to contribute" subsection. Pinned Discussion gets a follow-up reply. Exemplar: the existing STATUS.md is already structured to make this flip a single-file edit. |
| T18 | **README "Project status" section rewritten** with contributor CTAs | Today's README hard-redirects to "outside PRs not merged." That section must flip to invite contribution. | LOW | "Project status" section rewritten: "Active milestone: v0.7 (TBD). Outside contributions welcome — start with `good first issue`, read CONTRIBUTING.md, file an issue first for substantial changes." Release-badge update to v0.6.0. Exemplar: `httpx` README pattern. |
| T19 | **Saved replies updated** to reflect open-contribution mode | Saved replies #1, #2, #3 are written for the closed-contribution era and would be wrong if pasted post-v0.6. Reply #4 (low-effort AI PR) and #5 (stale issue) stay correct. | LOW | Saved replies #1-#3 rewritten or removed. New replies added: "PR welcome but needs an issue first", "PR is good but rebase/squash", "first-time contributor — here's the merge path". Exemplar: maintainer's discretion. |
| T20 | **Issue-claim watcher disabled or repurposed** | The existing claim-watcher workflow auto-replies to "I'll take this" with "claims are not honored." Post-v0.6, claims ARE honored (via a `claim:` label or just maintainer assignment). The workflow must be disabled or rewritten. | LOW | `.github/workflows/issue-claim-watcher.yml` either deleted or rewritten to instead post a "thanks — please confirm you have read CONTRIBUTING.md and I'll assign in 48h" reply, with a different marker. Recommendation: delete it; the v0.5 maintainer workflow doesn't need automation here. Exemplar: most projects don't have a claim-watcher at all. |

### Differentiators (Mature Projects Have These; Optional but Valuable)

Features that signal "this is a serious project, not a hobby repo" and that increase the trust budget of outside contributors and downstream consumers. They have real cost (CI minutes, maintenance burden, complexity) so each should be evaluated for fit.

| # | Feature | Value Proposition | Complexity / Cost | Shipped definition |
|---|---------|-------------------|-------------------|--------------------|
| D1 | **SLSA L3 build provenance** (`slsa-framework/slsa-github-generator`) | One level above PEP 740 attestations. PEP 740 proves "this artifact came from this GitHub workflow"; SLSA L3 additionally proves "in an isolated builder that the maintainer cannot tamper with mid-build." Required by regulated downstream consumers. | MEDIUM (~3-5 min added per release; one-time workflow integration) | `release.yml` invokes `slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.x.y` to emit `*.intoto.jsonl` provenance, attached as a release asset. Verifiable via `slsa-verifier verify-artifact horus_os-0.6.0-py3-none-any.whl --provenance horus_os-0.6.0.intoto.jsonl --source-uri github.com/Ridou/horus-os`. Exemplar: `sigstore/sigstore-python`. **Worth it for horus-os?** Borderline. PEP 740 attestations are ~80% of the SLSA-L3 value at 5% of the implementation cost. Recommendation: ship PEP 740 in v0.6; consider SLSA L3 in v0.7+ if a downstream user asks for it. |
| D2 | **OpenSSF Scorecard with public badge** | Public scorecard score (e.g. 8.2/10) on README. Drives a 6-12 month feedback loop on supply-chain hygiene. Free, automated, no maintenance. | LOW (one workflow, one badge URL) | `.github/workflows/scorecard.yml` runs weekly, publishes results to `https://api.securityscorecards.dev`. Badge in README. Initial target: 7.5+. Exemplar: `pypa/pip` scores 8.6. **Cost:** ~2 min/week CI. **Worth it for horus-os?** YES — the badge is a strong external trust signal and surfaces concrete improvements (pinning, dependency review). |
| D3 | **CodeQL code scanning on every PR** | GitHub-native SAST for Python. Catches taint flows, injection, deserialization issues. Free for public repos. | HIGH (~15-30 min added per PR run; configure language matrix) | `.github/workflows/codeql.yml` with `language: python` and the default queryset. Required status check on `main`. Results in the Security tab. **Cost:** ~15 min/PR (CodeQL on dynamic languages is significantly slower than the lint+test matrix). **Worth it for horus-os?** MEDIUM. CodeQL on Python is less valuable than on compiled languages, and 15 min/PR doubles CI wait time. Recommendation: include in v0.6 but only on `push` to `main` and on a weekly schedule, NOT as a required PR check. Defer the PR-gate decision to v0.7 once horus-os has data on false-positive rate. |
| D4 | **`safe-to-test` label gate for fork PRs needing real CI** | Fork PRs run a reduced CI (no secrets, no LLM calls, no live-provider tests). A maintainer-applied `safe-to-test` label triggers the full CI in `pull_request_target` context. The label is auto-removed after each run to force re-vetting on every push. | MEDIUM (one workflow file + label management discipline) | `.github/workflows/fork-pr-full-ci.yml` uses `nilsreichardt/verify-safe-to-test-label` action. Label managed by maintainer. Documented in `docs/MAINTAINER-RUNBOOK.md`. Exemplar: `dvc/dvc` ships this pattern. **Worth it for horus-os?** Conditional — only if any test in the suite needs real LLM API keys or other secrets. The existing v0.5 suite says "provider tests use recorded responses and adapters" — meaning **NO secrets needed in PR CI**. Recommendation: **SKIP this feature** unless a v0.7 test needs live keys. The cheaper path is "fork PRs never see secrets, full stop." See A3 in anti-features. |
| D5 | **`workflow_run` pattern for trusted post-test reporting** | Used when fork-CI needs to comment on the PR or post results that require write access (e.g. perf regression numbers). Workflow A runs untrusted on `pull_request`, uploads artifacts. Workflow B runs trusted on `workflow_run: completed`, downloads artifacts, comments. | MEDIUM | Two workflow files: `fork-ci.yml` (untrusted, runs the matrix on fork PRs), `fork-ci-report.yml` (trusted, downloads artifacts via `actions/download-artifact`, posts a comment). **Worth it for horus-os?** Only if a v0.7 metric (e.g. capture-overhead benchmark numbers) needs PR-side commentary. v0.6 doesn't need it; existing `pytest tests/perf/test_capture_overhead.py` job is fine running in-PR. Recommendation: SKIP for v0.6. |
| D6 | **Triage SLA doc + label taxonomy** | `docs/TRIAGE.md` documents the triage cadence ("48h initial label, 7d substantive response"), label taxonomy (`type:bug`, `type:feature`, `area:cli`, `area:dashboard`, `area:plugins`, `area:adapters`, `area:observability`, `priority:p1/p2/p3`, `good first issue`, `help wanted`, `needs-info`, `wontfix`), and the maintainer's saved-replies inventory. | LOW (writing prose) | `docs/TRIAGE.md` shipped, label list applied to the repo, `good first issue` and `help wanted` labels seeded on 3-5 actual issues. Exemplar: `python/devguide/triaging.rst`. **Worth it for horus-os?** YES — without it, "good first issue" is a lie. Need at least 3 real `good first issue` candidates at gate-flip time. |
| D7 | **Dependency Review action on every PR** | GitHub-native check that calls out new vulnerable dependencies introduced by the PR diff. Free for public repos. Complements pip-audit (which checks the existing tree). | LOW | `actions/dependency-review-action` step in lint-and-test workflow. Required status check. Exemplar: GitHub's own docs ship the pattern. **Worth it for horus-os?** YES — table-stakes-adjacent, near-zero cost. Borderline-table-stakes; defer to differentiator only because it's a thin layer on top of pip-audit. |
| D8 | **`zizmor` audit in CI** | Static analyzer for GitHub Actions security issues (pwn-request, unpinned actions, missing permissions). Single command, single workflow file. | LOW | `.github/workflows/zizmor.yml` runs `zizmor .github/workflows/` on every PR. Required status check. Exemplar: `pip-audit` itself runs zizmor. **Worth it for horus-os?** YES — locks in the fork-PR hardening choices once made. Roughly the SAST equivalent of pip-audit for workflows. |
| D9 | **`CITATION.cff`** for academic-citation metadata | Makes the repo citeable as a software artifact in academic contexts. Plain YAML, no CI cost. | LOW | `CITATION.cff` at repo root. Exemplar: many Python research projects. **Worth it for horus-os?** UNLIKELY — horus-os is not academic. Skip unless someone asks. |
| D10 | **`FUNDING.yml`** with GitHub Sponsors / Ko-fi link | Surfaces a sponsorship button on the repo. Useful if the maintainer wants to accept sponsorship. | LOW | `.github/FUNDING.yml` with `github: [Ridou]` or `custom: [...]` link. **Worth it for horus-os?** Maintainer's call — purely a policy decision, no engineering cost. Recommend: defer. |
| D11 | **Discussions enabled with categories pre-seeded** | Discussions is the right home for design questions, real-use feedback, and "is this in scope?" conversations — keeps the issue tracker focused on actionable defects. STATUS.md and CONTRIBUTING.md already direct users here. | LOW (repo setting) | Discussions enabled. Categories: Announcements (pinned: Project Status), Q&A, Ideas (scope proposals), Show and Tell (real-use writeups). Existing pinned STATUS post updated for v0.6.0 flip. Exemplar: `pydantic/pydantic` uses this exact category set. **Worth it for horus-os?** YES — referenced by every other contributor-facing doc; without it, the redirects are broken. |
| D12 | **Pinned "Project Status" Discussion** | The existing `DISCUSSION_STATUS_POST.md` draft is ready. Posting it and pinning it at v0.6.0 ship turns it into the rolling external update channel. | LOW (one-time post + pin) | Post the draft (now updated for v0.6), pin in Announcements category, reply to the existing pinned post (if one exists) announcing the flip. Exemplar: the draft itself. |
| D13 | **Reviewers SLA pinned in CONTRIBUTING.md** ("expect a first response within 7 days") | Sets realistic contributor expectations. Sub-100% adherence is fine if the doc says "best effort, solo maintainer." | LOW | New "Response SLA" section in CONTRIBUTING.md: "First triage label within 7 days. Substantive review within 14 days. Solo maintainer; cadence depends on what's on the active milestone." Exemplar: `psf/black` is honest about its review backlog. |
| D14 | **`auto-merge` for Dependabot grouped PRs after CI** | Mature pattern: Dependabot opens a grouped PR weekly, CI passes, auto-merge fires. Reduces maintainer toil to zero on green updates. | LOW | `.github/workflows/dependabot-auto-merge.yml` that calls `gh pr merge --auto --squash` for Dependabot PRs that are patch/minor only. Major bumps still need manual review. **Worth it for horus-os?** YES once the supply-chain checks are sturdy enough to trust. Recommendation: defer to v0.6.x patch release, not v0.6.0 itself — flip the gate first, automate the green path second. |
| D15 | **Maintainer runbook** (`docs/MAINTAINER-RUNBOOK.md`) | Internal-facing doc that captures: release procedure, triage routine, fork-PR review checklist, security-advisory drafting steps, branch-protection settings, "what to do when X breaks." Reduces the keep-this-in-my-head burden. | LOW (writing prose) | `docs/MAINTAINER-RUNBOOK.md` shipped (in the repo, public — no secrets in it). Exemplar: `python/cpython/Doc/howto` series. **Worth it for horus-os?** YES — solo maintainer, no team Slack, no Notion. This file is the institutional memory. |

### Anti-Features (Commonly Adopted, Actively Wrong For horus-os)

Features that are common in older or corporate-OSS projects but are recognized in 2026 as friction or anti-patterns. horus-os should explicitly NOT ship these. Naming them explicitly is more useful than silently skipping them — it documents the decision so it doesn't get re-litigated.

| # | Anti-Feature | Why Sometimes Requested | Why Wrong for horus-os | What to Do Instead |
|---|--------------|-------------------------|------------------------|---------------------|
| A1 | **CLA (Contributor License Agreement)** | Corporate-OSS pattern (Apache Foundation, OpenStack, Google projects). Provides extra legal cover for relicensing and patent grants. | The Linux kernel community rejected CLAs; the broader 2026 consensus is that Apache 2.0's existing patent-grant clause IS the patent license, and a CLA is redundant friction. Apache 2.0 already requires the inbound-equals-outbound license for any contribution. CLAs add an out-of-band signing portal that blocks first-time contributors and breaks the "drive-by typo fix" flow. | **Rely on Apache 2.0's inbound-equals-outbound rule as documented in CONTRIBUTING.md.** Existing line ("By opening a PR you confirm you have the right to license the change under Apache 2.0") is sufficient. No CLA bot, no signing portal. |
| A2 | **Mandatory DCO (`Signed-off-by` on every commit)** | Linux kernel convention; recommended by Linux Foundation. Provides a per-commit assertion of right-to-contribute. | DCO is strictly better than CLA but still adds friction for one-line typo fixes via the GitHub web UI (the web UI cannot append `-s`). For a project flipping its first contribution gate, the marginal legal protection is small and the friction cost is large. | **Do NOT require DCO.** If a corporate user needs DCO for their own internal policy, they can run `git commit -s` voluntarily; horus-os does not gate on it. Document the decision in CONTRIBUTING.md so it doesn't get re-litigated. |
| A3 | **Fork-PR access to repository secrets** (via `pull_request_target` + checkout-of-PR-SHA) | "I want my full E2E suite to run on fork PRs." | The "Pwn Request" attack class. Still hitting major projects in 2026 (the GitHub Security Lab and Trail of Bits writeups remain the standard references). Even with `safe-to-test` labels, the attack surface is wider than the maintainer's review bandwidth. | **No repo secrets exposed to fork builds.** Fork PRs run the matrix with `pull_request` (no secrets, no live-provider tests). Existing v0.5 suite ALREADY works this way ("provider tests use recorded responses"). Document this as an explicit non-goal. If a v0.7 test ever needs live keys, push that test to a `nightly.yml` workflow on `main`, never to PR CI. |
| A4 | **Mandatory Discord/Slack/Matrix join to contribute** | Common in corporate-OSS or community-led projects where governance happens in chat. | The chat-as-gateway pattern excludes async contributors and creates a parallel context that the GitHub timeline can't see. STATUS.md and the pinned Discussion already capture project state in public. | **All project discussion happens on GitHub (issues + Discussions).** No required chat join. Document explicitly: "All design conversations land in GitHub Discussions so future contributors have searchable context." |
| A5 | **Auto-assignment of first PR to a "newcomer mentor"** | Some projects pair every first-time contributor with a designated mentor. Reduces drop-off. | Requires a mentor pool. horus-os is solo-maintainer. Promising a mentor relationship the project cannot deliver is worse than not promising it. | **Honest "solo maintainer, best-effort cadence" framing in CONTRIBUTING.md.** Direct first-time contributors to `good first issue` labels (which ARE real, vetted tasks). |
| A6 | **`requires-changes` blocker labels with auto-close at N days** | Saves maintainer attention by auto-closing stale PRs. | Auto-close-on-stale is read as hostile by contributors and trains them not to bother opening PRs at all. The signal-to-toil ratio is bad. | **No auto-close on stale PRs.** Existing saved reply #5 ("polite ping when an issue is going stale") is the right pattern — manual nudge, not automated close. Use `stale` label as a maintainer-facing signal only. |
| A7 | **Required squash-merge on every PR** | Cleaner main-branch history. | Loses the "this contributor made these N commits" attribution and the conventional-commit history. horus-os has used conventional commits since v0.1 and they show up in CHANGELOG generation. | **Rebase-and-merge by default; squash only when commit history is genuinely messy.** Document the policy in CONTRIBUTING.md. Exemplar: `psf/black` does NOT require squash. |
| A8 | **Coverage gate ("PR must not decrease coverage")** | Common in mid-size Python projects. Surface appeal: "tests have value." | Coverage % is a poor proxy for test quality. Brittle in practice (false-positive PR failures on refactors that move covered code around). horus-os already has a strong testing culture (1011 tests at v0.5.0) without a coverage gate. | **No coverage gate. Existing "ship at least one regression test when feasible" rule in CONTRIBUTING.md is the policy.** |
| A9 | **`linkcheck` or external-link-validity gate** | "Docs links should not 404." | Network-dependent, flaky, often blocks PRs on third-party outages. The signal is weak and the noise is high. | **No linkcheck in PR CI.** Run linkcheck nightly on `main` if at all; report the result as an issue, not a PR block. |
| A10 | **"You must rebase before merging" enforced by required check** | Clean linear history. | GitHub's merge queue exists if linear history is genuinely required. For horus-os, the cost of forcing rebase on every PR exceeds the benefit. | **Branch-protection setting "Require linear history" can be set without making it a contributor responsibility.** GitHub handles the rebase automatically. |
| A11 | **GPG-keyed maintainer release signing as the primary signing identity** | Traditional approach pre-Sigstore. Maintainer-controlled key. | Long-lived keys are the #1 OSS-supply-chain compromise vector. Key loss, key theft, key-rotation discipline are all real problems. OIDC-keyless (Sigstore) is the 2026 standard. | **Sigstore keyless via GitHub OIDC is the primary signing identity.** GPG-signed tags are optional secondary (verified by `git verify-tag`). PROJECT.md already records this decision direction; v0.6 should lock it. |
| A12 | **Required PR description "novel" sections (testing strategy, design alternatives, security review)** | Mature projects sometimes require all four sections on every PR. | High friction for small-PR contributors. The existing PULL_REQUEST_TEMPLATE.md already covers "what / why / test plan / checklist" which is the right floor. | **Existing PR template is correct. Don't add required sections that small PRs will skip anyway.** |

## Feature Dependencies

```
Trusted Publishing (T1)
    └──enables──> PEP 740 attestations (T2)  (free with T1)
                       └──enables──> verify command works (T2 verification)

Signed git tags (T3)  (independent of T1/T2 but ships in same release.yml)

SBOM at release (T4)  (independent, in release.yml)

pip-audit on PRs (T5)
    └──blocks──> release-gate signature-present check (T4 attachment check)

Dependabot config (T6)
    └──requires──> SHA-pinned actions (T7)
                       └──verified-by──> zizmor (D8)

pull_request hardening (T8)
    └──verified-by──> zizmor (D8)

First-time-contributor gate (T9)  (repo setting; instant)

Branch protection (T10)
    └──requires──> stable status-check names from T5, T6, T7, T8 jobs

SECURITY.md update (T11)
CONTRIBUTING.md update (T12)
PR template update (T13)
Issue templates update (T14)
CODEOWNERS (T15)
CODE_OF_CONDUCT.md fix (T16)

STATUS.md flip (T17)
    └──requires-all-of──> T1..T16 GREEN before the bit-flips
README rewrite (T18)  └──same prerequisite──>
Saved replies (T19)   └──same prerequisite──>
Claim watcher disable (T20)  └──same prerequisite──>

Pinned Discussion (D12) flip
    └──requires──> T17 (STATUS.md flipped first; pin post replies "STATUS flipped on YYYY-MM-DD")

CodeQL (D3) — independent, can land any time
OSSF Scorecard (D2) — independent, free badge
SLSA L3 (D1) — defer to v0.7
safe-to-test (D4) — SKIP unless test needs secrets
workflow_run (D5) — SKIP for v0.6
Triage docs (D6) — recommend at gate-flip time
Dependency Review (D7) — bundle with T5
zizmor (D8) — bundle with T7 and T8
auto-merge dependabot (D14) — defer to v0.6.x
Maintainer runbook (D15) — recommend at gate-flip time
```

### Dependency Notes

- **T1 → T2 (free)**: `pypa/gh-action-pypi-publish` does PEP 740 automatically when `id-token: write` is set; no separate step needed. Lock T1 first, T2 follows.
- **T4 SBOM + T3 signed-tag both ride in `release.yml`**: bundle them in one release-pipeline overhaul rather than three separate phases.
- **T7 (SHA pinning) must precede T6 (Dependabot)**: Dependabot for GitHub Actions only works meaningfully against SHA-pinned references. Convert all `uses:` lines to SHA-pinned FIRST, then turn on Dependabot. Reverse order produces noisy PRs with no anchoring SHA.
- **T8 (fork-PR hardening) must precede T17 (STATUS.md flip)**: the moment STATUS.md says "PRs welcome," the first malicious fork PR can land. The fork-PR pipeline must be hardened FIRST. This is the single most important ordering constraint in v0.6.
- **T10 (branch protection) must come LAST among the CI changes**: the required-status-check list can only stabilize after all the new workflows are named and known-passing. Lock workflow names first, then turn on branch protection.
- **T17-T20 (the external bit-flips) ship ATOMICALLY at v0.6.0 release**: all four files change in one commit/release. If STATUS.md says "open" but the issue-claim-watcher still auto-closes, contributors see contradictory signals.
- **D12 (pinned Discussion update) replies on the existing pinned post**: it does NOT create a new pinned post. Existing thread continuity is valuable; the v0.6 update is a reply, not a fresh announcement.

## MVP Definition (v0.6 ship contents)

### Launch With (v0.6.0)

The minimum set required to flip the gate honestly. If any of these is missing, the v0.6.0 release is incomplete and the gate should not flip.

- [ ] **T1 Trusted Publishing** — no stored PyPI token, OIDC trusted publisher configured
- [ ] **T2 PEP 740 attestations** — automatic on every release artifact (free with T1)
- [ ] **T3 Signed git tags** — sigstore-keyless or GPG, verifiable from outside
- [ ] **T4 SBOM at release** — CycloneDX 1.6 JSON, attached as release asset, release-gate refuses tag without it
- [ ] **T5 pip-audit gating** — PR-blocking, required status check
- [ ] **T6 Dependabot config** — `pip` + `github-actions`, weekly grouped
- [ ] **T7 SHA-pinned actions** — every `uses:` references a 40-char SHA
- [ ] **T8 Fork-PR pipeline hardened** — `pull_request_target` is metadata-only or absent, no secrets in fork CI
- [ ] **T9 First-time-contributor gate** — repo setting enabled
- [ ] **T10 Branch protection** — required reviews + required status checks on `main`
- [ ] **T11 SECURITY.md** — 48h ack, 90d disclosure, scope-expanded for plugins
- [ ] **T12 CONTRIBUTING.md** — banner flipped, first-PR walkthrough section, SLA noted
- [ ] **T13 PR template** — banner removed, CONTRIBUTING/CoC checkbox added
- [ ] **T14 Issue templates** — banners flipped to welcome contributors
- [ ] **T15 CODEOWNERS** — minimum `* @Ridou`
- [ ] **T16 CODE_OF_CONDUCT.md** — reporting channel filled in (GHSA `[conduct]` title route)
- [ ] **T17 STATUS.md flipped** — TL;DR rewritten, milestone table updated, v0.6 SHIPPED
- [ ] **T18 README rewritten** — "Project status" section invites contributors, badge updated to v0.6.0
- [ ] **T19 Saved replies updated** — closed-contribution replies retired, open-contribution replies added
- [ ] **T20 Claim watcher** — deleted or repurposed (recommend: delete)
- [ ] **D6 Triage doc + labels** — `docs/TRIAGE.md` + label taxonomy applied + 3-5 `good first issue` candidates labelled
- [ ] **D7 Dependency Review** — action in PR workflow (cheap, bundle with T5)
- [ ] **D8 zizmor in CI** — locks in T7 and T8 choices
- [ ] **D11 Discussions enabled** — categories pre-seeded, pinned STATUS post in place
- [ ] **D12 Pinned Discussion updated** — follow-up reply announcing the v0.6.0 flip
- [ ] **D15 Maintainer runbook** — `docs/MAINTAINER-RUNBOOK.md` shipped

That is 20 table-stakes plus 6 high-value differentiators. Each is concretely defined, each is testable, each has a release-gate check that can refuse v0.6.0 if it slips.

### Add After Validation (v0.6.x)

Features to add once the gate is open and the first cohort of outside PRs has shown what actually breaks.

- [ ] **D2 OSSF Scorecard badge** — wait two weeks post-flip to let scores stabilize, then publish
- [ ] **D13 Response SLA** explicitly stated in CONTRIBUTING.md once a baseline cadence is established
- [ ] **D14 auto-merge Dependabot grouped PRs** — once you have one Dependabot cycle of evidence the CI checks catch regressions

### Future Consideration (v0.7+)

Features that buy real value but at real cost. Defer until v0.6 has data.

- [ ] **D1 SLSA L3 provenance** — defer until a downstream consumer asks for it
- [ ] **D3 CodeQL as a required PR check** — start in v0.6 as scheduled-only; promote to required if FP rate is low
- [ ] **D4 safe-to-test label gating** — only if a v0.7+ test needs live keys
- [ ] **D5 workflow_run trusted reporter** — only if PR-side automated commentary becomes valuable

## Feature Prioritization Matrix

| # | Feature | User Value | Implementation Cost | Priority |
|---|---------|------------|---------------------|----------|
| T1 | Trusted Publishing | HIGH | LOW | P1 |
| T2 | PEP 740 attestations | HIGH | LOW | P1 |
| T3 | Signed git tags | HIGH | LOW | P1 |
| T4 | SBOM at release | HIGH | LOW | P1 |
| T5 | pip-audit gating | HIGH | LOW | P1 |
| T6 | Dependabot | HIGH | LOW | P1 |
| T7 | SHA-pinned actions | HIGH | MEDIUM | P1 |
| T8 | Fork-PR hardening | HIGH | LOW | P1 |
| T9 | First-time-contributor gate | HIGH | LOW | P1 |
| T10 | Branch protection | HIGH | LOW | P1 |
| T11 | SECURITY.md update | HIGH | LOW | P1 |
| T12-T16 | Contributor docs | HIGH | LOW | P1 |
| T17-T20 | External-surface flip | HIGH | LOW | P1 |
| D6 | Triage doc + labels | HIGH | LOW | P1 (ship with v0.6) |
| D7 | Dependency Review | MEDIUM | LOW | P1 (ship with v0.6) |
| D8 | zizmor | MEDIUM | LOW | P1 (ship with v0.6) |
| D11 | Discussions enabled | HIGH | LOW | P1 (ship with v0.6) |
| D12 | Pinned Discussion update | HIGH | LOW | P1 (ship with v0.6) |
| D15 | Maintainer runbook | HIGH | LOW | P1 (ship with v0.6) |
| D2 | OSSF Scorecard | MEDIUM | LOW | P2 (v0.6.x) |
| D13 | SLA in CONTRIBUTING | MEDIUM | LOW | P2 (v0.6.x) |
| D14 | Auto-merge Dependabot | MEDIUM | LOW | P2 (v0.6.x) |
| D1 | SLSA L3 | LOW | MEDIUM | P3 (v0.7+) |
| D3 | CodeQL required check | LOW | HIGH | P3 (v0.7+) |
| D4 | safe-to-test label | LOW | MEDIUM | P3 (only if needed) |
| D5 | workflow_run reporter | LOW | MEDIUM | P3 (only if needed) |
| D9 | CITATION.cff | LOW | LOW | Skip |
| D10 | FUNDING.yml | LOW | LOW | Maintainer call |

**Priority key:**
- P1: Must have for v0.6.0 launch
- P2: Should have, add in v0.6.x patch window
- P3: Nice to have, future consideration

## Exemplar Repo Analysis (for direct reference)

| Feature | Exemplar | What to Borrow |
|---------|----------|----------------|
| Trusted Publishing + PEP 740 | `pypa/sampleproject` | The reference `release.yml` workflow. Copy structure, adapt the version-extraction step. |
| SBOM at release | `CycloneDX/cyclonedx-python` self-hosting | `cyclonedx-py environment` invocation. |
| pip-audit gating | `pypa/pip-audit` itself | Uses `pypa/gh-action-pip-audit@v1` in its own CI; copy the workflow. |
| Dependabot grouped | `dependabot/dependabot-core` | The grouped weekly config pattern. |
| SHA-pinned actions | `pypa/pip-audit`, `sigstore/sigstore-python` | All actions pinned, Dependabot maintains SHAs. |
| Fork-PR hardening | `numpy/numpy` | Audit-passed `pull_request` (not `pull_request_target`) pattern. |
| SECURITY.md | `pydantic/pydantic` | Minimal-but-correct ("use the Security tab"). horus-os adds scope notes for plugins. |
| CONTRIBUTING.md (existing already strong) | `encode/httpx`, `astral-sh/uv` | "Start with a discussion" framing (httpx); "Finding ways to help" + "Use of AI" sections (uv). |
| PR template (existing already strong) | `pydantic/pydantic` | Existing template is at the bar. |
| Issue templates | Existing horus-os templates | Already at the bar; just flip the banners. |
| CODEOWNERS | `python/cpython` | Single-line root + area-based overrides. |
| CODE_OF_CONDUCT.md | `psf/black` | Contributor Covenant 2.1 + named reporting address. |
| Triage labels | `python/devguide` | `type:`, `area:`, `priority:`, plus `good first issue` + `help wanted`. |
| Discussions categories | `pydantic/pydantic` | Announcements + Q&A + Ideas + Show and Tell. |
| zizmor in CI | `pypa/pip-audit` | One workflow file. |
| OSSF Scorecard badge | `pypa/pip` (scores ~8.6) | Weekly workflow + README badge. |
| SLSA L3 builder (deferred) | `sigstore/sigstore-python` | Reference if v0.7 needs it. |

## Open Questions for Requirements Phase

These are decisions that need to be locked at requirements time, not assumed by research:

1. **Signing identity**: Sigstore keyless via GitHub OIDC (recommended by PROJECT.md, recommended by this research) vs GPG vs both. PROJECT.md already records the lean toward keyless; lock it.
2. **SBOM format**: CycloneDX (recommended — every Python-ecosystem SBOM on PyPI is CycloneDX, zero SPDX per the Sbomify 2026 scan) vs SPDX. PROJECT.md already leans CycloneDX; lock CycloneDX 1.6 JSON.
3. **Supply-chain scanner**: pip-audit (P1 — PyPA-blessed, OSV-backed, zero-config) vs pip-audit + safety as second opinion vs pip-audit + osv-scanner. Recommendation: pip-audit alone for v0.6, defer second-opinion to v0.7 if a real CVE is missed.
4. **Fork-PR gating mechanism**: NO secrets in fork CI (recommended, simpler, safer) vs `safe-to-test` label gate (more flexibility, more attack surface). Recommendation: no-secrets-in-fork-CI is the right v0.6 choice; revisit only if v0.7 introduces a test that needs live keys.
5. **DCO requirement**: Recommendation: NO. Document the decision in CONTRIBUTING.md.
6. **CLA requirement**: Recommendation: NO. Apache 2.0 inbound=outbound handles it.
7. **CodeQL scope**: Recommendation: scheduled-only + push-to-main in v0.6; defer required-PR-check decision to v0.7.
8. **Maintainer runbook visibility**: public-in-repo (recommended for transparency) vs private. Recommendation: public — nothing in v0.6 maintainer ops is secret.
9. **Conduct reporting channel**: GHSA-style private advisory with `[conduct]` title (recommended, reuses existing infra, no new email needed) vs a dedicated email. Lock at requirements time.
10. **`claim:` label adoption** post-flip: recommendation: simple maintainer-assigns-by-comment model in v0.6, deferring any label-driven claim automation to v0.7 once there's data on claim cadence.

## Sources

### PyPI Trusted Publishing + PEP 740 Attestations

- [PyPI Docs: Producing Attestations](https://docs.pypi.org/attestations/producing-attestations/)
- [PyPI Docs: Attestation Security Model](https://docs.pypi.org/attestations/security-model/)
- [pypi/pypi-attestations on GitHub](https://github.com/pypi/pypi-attestations)
- [Sigstore blog: PyPI's Sigstore-powered attestations are GA](https://blog.sigstore.dev/pypi-attestations-ga/)
- [PyPI blog: PyPI now supports digital attestations (2024-11-14)](https://blog.pypi.org/posts/2024-11-14-pypi-now-supports-digital-attestations/)
- [Trail of Bits: Attestations, a new generation of signatures on PyPI](https://blog.trailofbits.com/2024/11/14/attestations-a-new-generation-of-signatures-on-pypi/)
- [pypa/gh-action-pypi-publish on GitHub](https://github.com/pypa/gh-action-pypi-publish)
- [sigstore/gh-action-sigstore-python on GitHub](https://github.com/sigstore/gh-action-sigstore-python)

### SLSA + Build Provenance

- [slsa-framework/slsa-github-generator on GitHub](https://github.com/slsa-framework/slsa-github-generator)
- [SLSA blog: Build your own SLSA 3+ provenance builder on GitHub Actions](https://slsa.dev/blog/2023/08/bring-your-own-builder-github)
- [Seth Larson: Python and SLSA](https://sethmlarson.dev/python-and-slsa)
- [Attest build provenance for a Python package in GitHub actions](https://browniebroke.com/blog/2024-08-08-attest-build-provenance-for-a-python-package-in-github-actions/)

### SBOM (CycloneDX vs SPDX, Python tooling)

- [CycloneDX/cyclonedx-python on GitHub](https://github.com/CycloneDX/cyclonedx-python)
- [Sbomify: CycloneDX vs SPDX comparison (2026-01-15)](https://sbomify.com/2026/01/15/sbom-formats-cyclonedx-vs-spdx/)
- [Sbomify: SBOM Adoption on PyPI Is at 1.58% (2026-03-12)](https://sbomify.com/2026/03/12/pypi-sbom-analysis/)
- [Sbomify: SBOM Generation Tools Compared (2026-01-26)](https://sbomify.com/2026/01/26/sbom-generation-tools-comparison/)
- [SoftwareSeni: SBOM Generation in CI/CD with GitHub Actions](https://www.softwareseni.com/sbom-generation-in-ci-cd-complete-github-actions-implementation-tutorial/)

### Supply-Chain Scanning (pip-audit)

- [pypa/pip-audit on GitHub](https://github.com/pypa/pip-audit)
- [pypa/gh-action-pip-audit on GitHub](https://github.com/pypa/gh-action-pip-audit)
- [McGarrah: Using GitHub Actions with pip-audit for PR auditing](https://mcgarrah.org/github-actions-pip-audit-pr/)

### Fork-PR Hardening + `pull_request_target` security

- [GitHub Security Lab: Keeping your GitHub Actions secure, Part 1 — Preventing pwn requests](https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/)
- [SecureBin: The Pwn Request Attack — How GitHub Actions PRs Steal Your Secrets](https://securebin.ai/blog/github-actions-pwn-request-attack/)
- [Paul Serban: Auditing your GitHub Actions for the pull_request_target flaw](https://www.paulserban.eu/blog/post/am-i-vulnerable-how-to-audit-your-github-actions-for-the-pullrequesttarget-flaw/)
- [Michael Heap: Accessing secrets from forks safely](https://michaelheap.com/access-secrets-from-forks/)
- [DVC blog: Testing external contributions using GitHub Actions secrets](https://dvc.org/blog/testing-external-contributions-using-github-actions-secrets/)
- [GitHub Marketplace: nilsreichardt/verify-safe-to-test-label](https://github.com/marketplace/actions/verify-safe-to-test-label)
- [DEV: pull_request_target Without Regret — Secure Fork PRs](https://dev.to/ollieb89/pullrequesttarget-without-regret-secure-fork-prs-in-github-actions-1jpi)
- [GitHub Docs: Approving workflow runs from forks](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
- [GitHub Changelog: Maintainers must approve first-time contributor workflow runs (2021-04-22)](https://github.blog/changelog/2021-04-22-github-actions-maintainers-must-approve-first-time-contributor-workflow-runs/)

### Action Pinning + Hardening (zizmor, StepSecurity, Dependabot)

- [StepSecurity: Pinning GitHub Actions for Enhanced Security](https://www.stepsecurity.io/blog/pinning-github-actions-for-enhanced-security-a-complete-guide)
- [Matthias Schoettle: Harden your GitHub Actions Workflows with zizmor (2026-03-28)](https://mattsch.com/blog/2026/03/28/harden-your-github-actions-workflows-with-zizmor-dependency-pinning-and-dependency-cooldowns/)
- [GitHub Changelog: Actions policy supports SHA pinning enforcement (2025-08-15)](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)
- [Wiz: Hardening GitHub Actions, Lessons from Recent Attacks](https://www.wiz.io/blog/github-actions-security-guide)
- [step-security/secure-repo on GitHub](https://github.com/step-security/secure-repo)
- [Pydevtools: How to pin GitHub Actions by SHA for Python projects](https://pydevtools.com/handbook/how-to/how-to-pin-github-actions-by-sha-for-python-projects/)
- [GitHub Docs: Keeping your actions up to date with Dependabot](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot)
- [StepSecurity: Dependabot Configuration Enhancements — Cooldown and Group Support](https://www.stepsecurity.io/blog/announcing-dependabot-configuration-enhancements-cooldown-and-group-support)

### Branch Protection + Required Status Checks

- [GitHub Docs: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Docs: Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
- [GitHub Docs: Troubleshooting required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)

### Contributor Experience (Exemplars)

- [astral-sh/uv CONTRIBUTING.md](https://github.com/astral-sh/uv/blob/main/CONTRIBUTING.md)
- [encode/httpx contributing guide](https://github.com/encode/httpx/blob/master/docs/contributing.md)
- [psf/black CONTRIBUTING.md](https://github.com/psf/black/blob/main/CONTRIBUTING.md)
- [pydantic/pydantic security policy](https://github.com/pydantic/pydantic/security/policy)
- [GitHub Docs: About issue and pull request templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)

### CODEOWNERS, Triage, Labels

- [Python devguide: GitHub labels](https://devguide.python.org/triage/labels/)
- [Python devguide: Triaging an Issue](https://devguide.python.org/triaging/)
- [pip docs: Issue Triage](https://pip.pypa.io/en/latest/development/issue-triage/)

### Security Policy + Coordinated Disclosure

- [GitHub Docs: About coordinated disclosure of security vulnerabilities](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/about-coordinated-disclosure-of-security-vulnerabilities)
- [GitHub Docs: Privately reporting a security vulnerability](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
- [GitHub Blog: Coordinated vulnerability disclosure (CVD) for open source](https://github.blog/security/vulnerability-research/coordinated-vulnerability-disclosure-cvd-open-source-projects/)

### CLA / DCO Anti-Pattern

- [Opensource.com: Why CLAs aren't good for open source](https://opensource.com/article/19/2/cla-problems)
- [Opensource.com: CLA vs DCO — What's the difference?](https://opensource.com/article/18/3/cla-vs-dco-whats-difference)
- [FINOS: CLAs And DCOs](https://osr.finos.org/docs/bok/artifacts/clas-and-dcos)
- [ConsortiumInfo: All About CLAs and DCOs](https://consortiuminfo.org/open-source/all-about-clas-and-dcos/)

### OSSF Scorecard

- [ossf/scorecard on GitHub](https://github.com/ossf/scorecard)
- [OpenSSF Scorecard project page](https://openssf.org/projects/scorecard/)
- [ossf/scorecard-action on GitHub](https://github.com/ossf/scorecard-action)

### CodeQL

- [GitHub Docs: About code scanning with CodeQL](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql)
- [GitHub: github/codeql](https://github.com/github/codeql)

### Repository Metadata

- [Citation File Format (CFF)](https://citation-file-format.github.io/)

---
*Feature research for: contribution-gate readiness, horus-os v0.6*
*Researched: 2026-05-29*
