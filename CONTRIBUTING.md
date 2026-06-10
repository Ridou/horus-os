<p align="center"><img src="assets/horus-eye.svg" alt="" width="64"></p>

# Contributing to horus-os

## Status: open for contributions

`horus-os` accepts outside contributions as of 2026-06-10. The
supply-chain readiness gate that held the door shut (the v0.6
Contribution Gate milestone: keyless sigstore signing, CycloneDX
SBOMs, pip-audit scanning, SHA-pinned actions, sandboxed forked-PR
CI) shipped, and the flow below is live.

Where to start:
- **Pick an issue** labeled `good-first-issue` or `help-wanted`, and
  comment to claim it. The claim flow below explains how assignment
  works.
- **File issues** for real bugs you hit running `horus-os` locally.
- **Open Discussions** for design questions or scope proposals
  before writing code.
- **Join the [community Discord](https://discord.gg/vwX9WvwQhp)**
  for questions and help while you work.
- **Run the project for real** and write up your experience. Real-use
  feedback still shapes the roadmap more than anything else.

Honest expectations before you start: horus-os is solo-maintained.
Triage targets a weekly Sunday pass and may go quiet for up to two
weeks (see `docs/TRIAGE.md`). Every PR runs the full three-OS CI
matrix, and forked-PR builds run with restricted tokens that never
see repository secrets.

If anything in this guide is wrong, unclear, or out of date, open an
issue.

## Contribution flow

The day-to-day flow is:

1. **Pick or open an issue.** New contributors should look for
   `good-first-issue` and `help-wanted` labels. Read
   `docs/TRIAGE.md` for the label rubric and what each label
   means.
2. **Comment to claim, maintainer assigns.** Comment "I would like
   to take this" on the issue. The maintainer reviews recent
   contribution history (for first-time contributors, may suggest a
   smaller intro task first) and adds the `claimed` label plus
   issue-assignment. Until assigned, the issue is not claimed.
3. **Open a draft PR within 7 days.** If the draft PR does not
   appear within 7 days, the `claimed` label is removed and the
   issue returns to the queue.
4. **CI must pass.** Ubuntu, macOS, Windows on Python 3.11 and
   3.12, plus the install-smoke matrix and the supply-chain
   scanning workflow (`pip-audit` dual-mode +
   `dependency-review-action` license allowlist). The release-gate
   check suite (`scripts/release_gate.py`, 15 checks) must pass for
   any change that touches the release pipeline.
5. **Code review.** Path-scoped reviewers are auto-assigned per
   `.github/CODEOWNERS`. Workflow changes, release scripts, and the
   SECURITY policy require the maintainer.
6. **Merge.** No auto-merge. The maintainer hits the button after
   review-pass and CI-green.

### Service-level objective

The maintainer will aim to acknowledge within 7 days of receiving a new issue or PR.
That is a target, not a guarantee; there is no 24-hour SLA on this
project. Honest expectations:

- Weekly Sunday triage is the target cadence.
- The queue may go silent up to 2 weeks (travel, deep work on an
  in-flight phase, life). After 2 weeks of silence, a polite ping
  on the issue resurfaces it.
- The full triage policy lives in `docs/TRIAGE.md`.

### Anti-features

These features are intentionally absent. The rationale is documented
in `.planning/decisions/` so the absence is a decision, not a gap.

- **No CLA.** Apache 2.0 inbound-equals-outbound is the only
  licensing requirement. See `.planning/decisions/no-cla.md`.
- **No 24-hour SLA.** See the SLO language above.
- **No `actions/stale` auto-close.** Aging issues are real signal,
  not bot noise. See `.planning/decisions/no-stale-bot.md`.
- **Discord is optional.** GitHub Issues and Discussions are the
  canonical surfaces. No Discord-only conversations on roadmap
  changes.

## Related decisions

The following one-page rationale files document load-bearing
project choices. Read them before opening a PR that questions any
of them:

- `.planning/decisions/no-cla.md`: why no Contributor License
  Agreement.
- `.planning/decisions/no-stale-bot.md`: why no `actions/stale`
  auto-close.
- `.planning/decisions/sigstore-keyless.md`: why we sign with
  keyless OIDC sigstore rather than long-lived GPG keys.
- `.planning/decisions/sbom-cyclonedx.md`: why CycloneDX 1.6 JSON
  is the SBOM format.
- `.planning/decisions/no-pypi-in-v0.6.md`: why PyPI Trusted
  Publishing was deferred past v0.6 (installs come from source or
  GitHub Releases for now).

## Scope check

Before opening a substantial PR, read:

1. `PROJECT.md`, the project intent and out-of-scope list.
2. `ROADMAP.md`, the current milestone and phases.
3. `ARCHITECTURE.md`, the technical shape.

Changes that align with an open phase or a clearly stated roadmap item
get reviewed fast. Changes that expand scope or fork project direction
need a roadmap update first. Open an issue and propose the scope change
before writing the code.

## Dev setup

```
git clone https://github.com/Ridou/horus-os.git
cd horus-os
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

That installs the package in editable mode, plus pytest, ruff, and the
optional FastAPI surface used by the dashboard tests.

To exercise the full provider stack locally:

```
pip install -e '.[all]'
export ANTHROPIC_API_KEY=sk-ant-...     # optional
export GEMINI_API_KEY=...               # optional
```

The test suite does not require live API keys. Provider tests use
recorded responses and adapters.

## Workflow

1. **Pick or open an issue.** New contributors should look for the
   `good-first-issue` and `help-wanted` labels.
2. **Branch from `main`.** Branch names use the pattern
   `<type>/<short-slug>`, for example `feat/streaming-responses` or
   `fix/wizard-windows-paths`. Long-lived forks of project direction
   are not accepted without a roadmap update first.
3. **Make your change.** Keep PRs focused. One concern per branch.
4. **Add at least one regression test** when you can. The test
   directory mirrors the source layout under `tests/`.
5. **Run the local checks** before pushing:
   ```
   ruff check .
   ruff format --check .
   pytest
   ```
6. **Open a PR.** Fill out the template. Link the issue you are
   closing.
7. **CI must be green.** The matrix runs Ubuntu, macOS, and Windows
   on Python 3.11 and 3.12. The `install-smoke` job verifies a fresh
   `pip install` works on every supported OS. PRs that break the
   matrix are not merged.

## Code style

- **Linter and formatter:** ruff. Configuration is in `pyproject.toml`.
- **Line length:** 100, enforced by `ruff format`.
- **Imports:** ruff handles ordering via the `I` rule set.
- **Type hints:** use them on every new public function. Internal
  helpers can skip them if obvious.
- **Paths:** always `pathlib.Path`, never raw string concatenation.
  Cross-OS regressions are caught by CI on Windows.
- **No em-dashes** in committed prose. Use commas, periods, or
  hyphens. This applies to code comments, docs, commit messages, and
  user-visible strings.

## Commit style

Conventional commits, present tense, with an optional phase prefix
when the change belongs to a tracked phase:

```
feat(02): agent runtime supports async tool execution
fix(07): cli init handles a pre-existing config file
docs: refresh architecture diagram
test(05): cover memory read with unicode filenames
```

Prefixes in use: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`,
`build`, `ci`, `perf`.

## What does not get merged

- **Personal information** in committed text. Names, emails, phone
  numbers, IP addresses, host names, vault paths, API keys, account
  identifiers. Use placeholder values like `your-api-key`,
  `your-project-name`, or `~/.config/horus-os/`.
- **AI provider abstractions** that hide the SDK from the caller. The
  Anthropic and Google SDKs are first-class. Wrappers that obscure
  cost, latency, or capabilities are rejected.
- **SaaS-only features.** Optional cloud integrations are fine when
  opt-in. Required cloud dependencies are not.
- **Em-dashes.** See above. CI does not catch this; reviewers do.

## License and attribution

Apache 2.0 applies to every contribution. By opening a PR you confirm
you have the right to license the change under Apache 2.0.

New files do not require a per-file license header for v0.x. The
top-level `LICENSE` covers the whole repository.

## How to add a new provider

1. Open an issue and propose the provider. Confirm it fits
   `PROJECT.md` scope.
2. Add the SDK as an optional dependency group in `pyproject.toml`
   (`[<provider>]` and the `[all]` aggregate).
3. Implement under `src/horus_os/_providers/_<provider>.py` matching
   the existing Anthropic and Gemini surface (sync + async, plus a
   `Conversation` class).
4. Register the provider in the agent runtime dispatch table.
5. Add provider-specific tests under `tests/_providers/`.

## How to add a new tool

1. Implement a factory in `src/horus_os/tools/builtin.py` (built-in)
   or in your own module if external.
2. The factory returns a `Tool` registered through `ToolRegistry`.
3. Every tool invocation must be loggable. Side effects on disk must
   land in the writes audit table when relevant.
4. Add tests under `tests/tools/`.

## How to add a CLI subcommand

1. Create `src/horus_os/cli/<name>_cmd.py` with a `run()` function.
2. Wire it into the argparse tree in `src/horus_os/cli/__init__.py`.
3. Tests go under `tests/cli/`. Use the `CliRunner` fixture pattern
   from existing tests.

## How to edit the documentation site

The official docs at [docs.horus-demo.com](https://docs.horus-demo.com) are
built from `docs-site/`, a static Next.js app that is separate from the Python
package and from the bundled dashboard.

1. **Content** lives as markdown in
   `docs-site/content/docs/<section>/<page>.md`, with `title` and `description`
   frontmatter. The body starts at an `##` heading; the page title comes from
   the frontmatter, so do not add a top-level `#` heading.
2. **Navigation, order, and the sidebar** are defined in
   `docs-site/lib/nav.ts`. To add a page, create the markdown file and add its
   slug there.
3. **Run it locally:**
   ```
   cd docs-site
   npm install
   npm run dev        # http://localhost:3000
   ```
4. **Conventions:** no em-dashes, no personal data, internal links are absolute
   and end with a slash (for example `/guides/cli/`), and every code fence
   carries a language tag.
5. **Deploy:** the site static-exports to `docs-site/out/` and deploys to
   Vercel as its own project. See `docs-site/DEPLOY.md`.

## Where to discuss

- **Bugs and concrete proposals:** GitHub issues.
- **Design questions and longer-form discussion:** GitHub Discussions
  (enabled on the repo).
- **Security reports:** see `SECURITY.md`.

Pull requests are not the right place to negotiate scope. If a PR
reveals a scope question, the review will pause until an issue
captures the decision.
