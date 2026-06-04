---
title: "Contributing"
description: "How to set up a horus-os dev environment, run the lint and test checks, follow the commit conventions, and the hard rules every contribution must meet."
---

## Status

`horus-os` is in a solo development phase. The project was open-sourced from a working private command center, and the maintainer is moving through the milestones toward the contribution gate. Outside pull requests are not merged yet, and "I want to claim this issue" comments are not assigned yet.

This guide stays public so the standards are clear in advance, and so you can mirror them locally if you want to. Treat everything below as the contract that will apply once the project opens for contributions, not as an invitation to open a PR today.

> [!NOTE]
> If anything in this guide is wrong, unclear, or out of date, open an issue on [GitHub](https://github.com/Ridou/horus-os).

### What you can do today

- File issues for real bugs you hit running `horus-os` locally.
- Open Discussions for design questions or scope proposals.
- Star or watch the repo to follow along.
- Run the project for real and write up your experience. That feedback is the most valuable input at this stage.

### What is not currently accepted

- Pull requests from forks. They are acknowledged and closed.
- Issue claims ("on it", "working on this", "assign to me"). The maintainer keeps the issue queue and assigns work to themselves.
- Scope-expansion proposals via PR. Use Discussions instead.

## Dev setup

Clone the repo, create a virtual environment, and install the package in editable mode with the dev extras.

```bash
git clone https://github.com/Ridou/horus-os.git
cd horus-os
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

That installs the package in editable mode, plus pytest, ruff, and the optional FastAPI surface used by the dashboard tests.

To exercise the full provider stack locally, install the `all` extra and export your provider keys.

```bash
pip install -e '.[all]'
export ANTHROPIC_API_KEY=your-anthropic-key     # optional
export GEMINI_API_KEY=your-gemini-key           # optional
```

The test suite does not require live API keys. Provider tests use recorded responses and adapters.

> [!TIP]
> `horus-os` runs on Python 3.11+. CI exercises both Python 3.11 and 3.12, so develop against a version in that range.

## Workflow

1. **Pick or open an issue.** New contributors should look for the `good first issue` and `help wanted` labels.
2. **Branch from `main`.** Branch names use the pattern `<type>/<short-slug>`, for example `feat/streaming-responses` or `fix/wizard-windows-paths`. Long-lived forks of project direction are not accepted without a roadmap update first.
3. **Make your change.** Keep PRs focused. One concern per branch.
4. **Add at least one regression test** when you can. The test directory mirrors the source layout under `tests/`.
5. **Run the local checks** before pushing (see below).
6. **Open a PR.** Fill out the template. Link the issue you are closing.
7. **CI must be green.** The matrix runs Ubuntu, macOS, and Windows on Python 3.11 and 3.12. The `install-smoke` job verifies a fresh `pip install` works on every supported OS. PRs that break the matrix are not merged.

## Lint and format

`horus-os` uses [ruff](https://docs.astral.sh/ruff/) as both linter and formatter. Configuration lives in `pyproject.toml`.

- **Line length:** 100, enforced by `ruff format`.
- **Imports:** ruff handles ordering via the `I` rule set.
- **Type hints:** use them on every new public function. Internal helpers can skip them if obvious.
- **Paths:** always `pathlib.Path`, never raw string concatenation. Cross-OS regressions are caught by CI on Windows.

Run the formatter and linter before you push.

```bash
ruff check .
ruff format --check .
```

## Testing

pytest runs from the repo root. The test directory mirrors the source layout under `tests/`, and code changes ship with at least one regression test when feasible.

```bash
pytest
```

CI runs the suite as a three-OS matrix. Every change is exercised on Ubuntu, macOS, and Windows, each on Python 3.11 and Python 3.12. A separate `install-smoke` job verifies that a fresh `pip install` works on each supported OS. A PR that breaks any cell of the matrix is not merged.

## Commit style

Use conventional commits in present tense, with an optional phase prefix when the change belongs to a tracked phase.

```text
feat(02): agent runtime supports async tool execution
fix(07): cli init handles a pre-existing config file
docs: refresh architecture diagram
test(05): cover memory read with unicode filenames
```

Prefixes in use: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `build`, `ci`, `perf`.

## Hard rules

These rules are non-negotiable. Reviewers enforce them, and some are enforced by CI.

### No em-dashes

Do not use em-dash characters in committed prose. Use commas, periods, or hyphens instead. This applies to code comments, docs, commit messages, and any user-visible string.

### No personal information

Do not commit personal information in any file. That includes names, emails, phone numbers, IP addresses, host names, vault paths, API keys, and account identifiers. Use placeholder values like `your-api-key`, `your-project-name`, or `~/.config/horus-os/`.

### Apache 2.0

Apache 2.0 applies to every contribution. By opening a PR you confirm you have the right to license the change under Apache 2.0. There is no separate Contributor License Agreement: Apache 2.0 inbound-equals-outbound is the only licensing requirement.

New files do not require a per-file license header for v0.x. The top-level `LICENSE` covers the whole repository.

## What does not get merged

- **Personal information** in committed text. See the hard rules above.
- **AI provider abstractions** that hide the SDK from the caller. The Anthropic and Google SDKs are first-class. Wrappers that obscure cost, latency, or capabilities are rejected.
- **SaaS-only features.** Optional cloud integrations are fine when opt-in. Required cloud dependencies are not.
- **Em-dashes.** See the hard rules above.

## Scope check

Before opening a substantial PR (once the project is open for contributions), read:

1. `PROJECT.md`, the project intent and out-of-scope list.
2. `ROADMAP.md`, the current milestone and phases.
3. `ARCHITECTURE.md`, the technical shape.

Changes that align with an open phase or a clearly stated roadmap item get reviewed fast. Changes that expand scope or fork project direction need a roadmap update first. Open an issue and propose the scope change before writing the code.

> [!IMPORTANT]
> Pull requests are not the right place to negotiate scope. If a PR reveals a scope question, the review pauses until an issue captures the decision.

## Where to discuss

- **Bugs and concrete proposals:** GitHub issues.
- **Design questions and longer-form discussion:** GitHub Discussions (enabled on the repo).
- **Questions, help, and casual discussion:** the [community Discord](https://discord.gg/vwX9WvwQhp), where `#help` is a searchable forum.
- **Security reports:** see the [security policy](/project/security-policy/).

## See also

- [Code of Conduct](/project/code-of-conduct/)
- [Maintainer Runbook](/operations/maintainer-runbook/)
- [Roadmap](/project/roadmap/)
- [Security Policy](/project/security-policy/)
