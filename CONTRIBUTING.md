# Contributing to horus-os

## Status: not currently accepting outside contributions

`horus-os` is in a solo development phase as of v0.3.0. The project
was open-sourced out of a working private command center, and the
maintainer is still moving fast through the early milestones (v0.4
Observability is in planning right now). Outside pull requests will
not be merged at this time, and "I want to claim this issue"
comments will not be assigned.

This guide stays public so the standards are clear in advance, and so
contributors can mirror them locally if they want to. **Treat
everything below as the contract that will apply once the project
opens for contributions, not as an invitation to open a PR today.**

What you can do today:
- **File issues** for real bugs you hit running `horus-os` locally.
- **Open Discussions** for design questions or scope proposals.
- **Star or watch** the repo to follow along.
- **Run the project for real** and write up your experience. That
  feedback is the most valuable input at this stage.

What is not currently accepted:
- Pull requests from forks. They will be acknowledged and closed.
- Issue claims ("on it", "working on this", "assign to me"). The
  maintainer keeps the issue queue and assigns work to themselves.
- Scope-expansion proposals via PR. Use Discussions instead.

The maintainer will update this banner once the internal
readiness gate is met. Most likely milestone for that is **v0.6
or later**; not promised, not scheduled.

If anything in this guide is wrong, unclear, or out of date, open an
issue.

## Future contribution flow (not active yet)

When the project opens up, every incoming PR will go through:

1. **Author vetting.** Maintainer checks GitHub account history and
   prior public work. First-time contributors get a small intro task
   (typo fix, doc tweak) before any code review on substantive
   changes.
2. **Automated review.** Incoming PRs go through a private
   pre-review process before any human review. Details are
   intentionally not published.
3. **Sandboxed CI.** Forked-PR CI runs with restricted tokens. No
   repository secrets are exposed to fork builds.
4. **Maintainer review.** Human review only after the above gates
   pass. No auto-merge.
5. **Graduated trust.** Repeated quality contributions move a
   contributor from "unknown" to "intro-task-passed" to
   "reviewed-PR-merged" to "trusted". Trust level affects which
   labels and review depth apply.

The rest of this document covers the workflow, code style, and
standards. Everything below is still accurate for code already in
the repo and for the maintainer's own development.

## Scope check

Before opening a substantial PR (once the project is open for
contributions), read:

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
   `good first issue` and `help wanted` labels.
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

## Releasing

Releases are built by `.github/workflows/release.yml`.

To create a GitHub Release with versioned artifacts:

1. Update the version in `pyproject.toml` and add release notes to
   `CHANGELOG.md`.
2. Commit and merge the release prep to `main`.
3. Create and push a semantic version tag:
   ```
   git tag v0.1.0
   git push origin v0.1.0
   ```
4. The release workflow builds a wheel and source distribution with
   `python -m build`, then attaches both files from `dist/` to the
   matching GitHub Release.

PyPI publishing is manual by default. Run the `Release` workflow from
GitHub Actions with `publish_pypi` enabled only after the tag artifact
build is correct and the repository secret `PYPI_API_TOKEN` exists.
If the secret is missing, the PyPI job is skipped and the GitHub
Release artifact build still works.

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

## Where to discuss

- **Bugs and concrete proposals:** GitHub issues.
- **Design questions and longer-form discussion:** GitHub Discussions
  (enabled on the repo).
- **Security reports:** see `SECURITY.md`.

Pull requests are not the right place to negotiate scope. If a PR
reveals a scope question, the review will pause until an issue
captures the decision.
