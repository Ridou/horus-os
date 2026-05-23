# Phase 18 Context: Documentation and examples refresh

## Why this phase

Phases 12 through 17 expanded the public API surface significantly:
agent profiles, delegation, streaming, the multi-agent CLI, the
dashboard SSE chat, and the adapter contract. None of that surface is
reflected in the top-level docs yet. v0.1 users picking up `horus-os`
today would walk into `run_agent_stream`, `Adapter`,
`make_delegate_tool`, and `horus-os agents` with no in-tree
introduction.

Phase 18 is the docs pass that closes the gap before Phase 19
(test surface expansion) and Phase 20 (three-OS verification).
Requirements MIG-03 (migration documented) and REL-04 (migration
notes for v0.1 users) both land here.

## Design decisions

### Examples use the public API only

The three example scripts (`multi_agent.py`, `streaming.py`,
`custom_adapter.py`) import only from `horus_os` and `horus_os.adapters`.
They do not reach into private modules. If a behavior is not exposed at
the package level it does not appear in an example.

### Examples are runnable offline

Every example must run end to end with no API keys, no network, no
adapter installs. We achieve this by:

1. Monkey patching provider modules at the top of each script the same
   way the existing tests do (`monkeypatch.setattr` is a pytest fixture
   so we replicate the pattern by importing the provider module and
   assigning the stub). This is honest: the user can read the docstring
   to see how to swap the stub for a real provider call.
2. For the custom adapter example, registering the adapter through an
   in-script `entry_points` stub rather than requiring `pip install -e`
   of a sibling package.

The point is showing the shape, not making a live call.

### Migration guide lives under `docs/`

`docs/MIGRATION-v0.1-to-v0.2.md` rather than top-level. Reasons:

- Top-level files are scoped to "everyone needs to read this." A v0.1
  to v0.2 migration is a transient concern; once a user is on v0.2 they
  do not need to see it again.
- Future migrations (v0.2 to v0.3, etc.) can sit beside it under
  `docs/`.
- README links to it explicitly.

### ARCHITECTURE refresh additive, not rewrite

The v0.1 architecture file describes the single-agent shape clearly.
The refresh adds three new sections (multi-agent shape, streaming
surface, adapter interface) and updates two existing ones (Module
layout to include `adapters/`, What is not in vN to reflect v0.2). The
v0.1 sections remain accurate because the single-agent path was not
broken, only extended.

### CHANGELOG entries land in `[Unreleased]`

Phase 21 owns the `[0.2.0]` heading and the release tag. Phase 18 puts
the v0.2 deliverables under `[Unreleased]` so the changelog accurately
reflects the work that has shipped on `main` but is not yet tagged.

## Constraints

- No em-dashes in any committed prose. Use commas, periods, hyphens.
- No personal information.
- Conventional commits prefixed with `docs(18):`.
- Examples must execute cleanly with `python examples/<name>.py`.
- `ruff check .` and `ruff format --check .` must remain green.
- The full pytest suite must remain at 302 passing.

## Out of scope for Phase 18

- New requirements (covered by Phase 19+).
- Vector search, observability, additional adapters (v0.3+).
- Updating CONTRIBUTING.md beyond what the public surface needs.
- A docsite build (not until at least v0.3).
