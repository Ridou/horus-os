# .planning/ Layout

This directory tracks the project's planning artifacts. If you are
new to the repo or coming back after a break, read these in order.

## Where things live

```
.planning/
├── README.md          # this file: layout and conventions
├── STATE.md           # current milestone, phase, and status
├── ROADMAP.md         # active milestone with phase parallelization
├── REQUIREMENTS.md    # all requirement IDs and phase mapping
├── PROJECT.md         # mirror of repo-root PROJECT.md, for tooling
├── config.json        # GSD workflow toggles (executor model, etc)
└── phases/
    ├── 01-<slug>/
    │   ├── 01-00-PLAN.md      # detailed plan written before exec
    │   └── 01-00-SUMMARY.md   # outcome after exec
    ├── 02-<slug>/
    └── ...

# Repo root mirrors the public-facing slice
ROADMAP.md               # public roadmap, locked decisions, future milestones
PROJECT.md               # project intent, scope, anti-goals
ARCHITECTURE.md          # technical shape as shipped
CHANGELOG.md             # release notes (Keep a Changelog format)
```

## Reading order on context reset

1. **`.planning/STATE.md`**, tells you which milestone is active and
   what phase the work is at. Single source of truth for "what now."
2. **`.planning/ROADMAP.md`**, shows the active milestone's phases
   with their parallelization graph. Marks shipped vs in-progress vs
   queued.
3. **`.planning/REQUIREMENTS.md`**, cross-reference between
   requirement IDs (`MA-01`, `STREAM-02`, etc) and the phases that
   deliver them.
4. **`.planning/phases/<N>-<slug>/<N>-00-PLAN.md`**, read the plan
   for the active phase before executing.

The repo-root `ROADMAP.md` is the public-facing version. Both
mirror each other for phase status, but the public roadmap also
captures locked-in decisions and future-milestone placeholders.

## Naming conventions

- **Phase folders:** `<NN>-<kebab-slug>/`. Numbers are zero-padded
  to two digits so directory listings stay sorted.
- **Plan files:** `<NN>-<MM>-PLAN.md` where `MM` is the plan number
  within the phase (most phases have one plan, `00`).
- **Summary files:** `<NN>-<MM>-SUMMARY.md` written after execution.
- **Requirement IDs:** `<CATEGORY>-<NN>` where category is a short
  uppercase code (`CORE`, `AGENT`, `MA`, `STREAM`, etc).

## Milestone shape (matches v0.1)

Each milestone has:

1. **Goal**, one sentence describing what shipping the milestone
   delivers.
2. **Locked decisions**, architectural choices that will not be
   reopened during the milestone. Things like "Anthropic + Gemini
   both first-class" or "no PyPI publish in this milestone."
3. **Phases**, numbered work units, each with a clear deliverable.
   Phases are sequenced for parallelization; the graph is in
   `.planning/ROADMAP.md`.
4. **Requirements**, numbered IDs mapped to one or more phases.

## How a new phase starts

1. Add the phase to `.planning/ROADMAP.md` and the public
   `ROADMAP.md`.
2. Add or link its requirements in `.planning/REQUIREMENTS.md`.
3. Create the folder `.planning/phases/<N>-<slug>/`.
4. Run `/gsd-plan-phase <N>` (or write the `<N>-00-PLAN.md` by
   hand) to generate the executable plan.
5. Run `/gsd-execute-phase <N>` (or follow the plan manually).
6. Write `<N>-00-SUMMARY.md` after completion.
7. Update `.planning/STATE.md` to advance to the next phase.

## How a new milestone starts

1. Pick the milestone's goal and locked-in decisions.
2. Draft the phase list (typically 8 to 12 phases).
3. Draft requirements with IDs and phase mapping.
4. Update `ROADMAP.md` (root) and `.planning/ROADMAP.md`.
5. Update `.planning/REQUIREMENTS.md`.
6. Update `.planning/STATE.md` to mark the milestone active.
7. Optionally create a matching milestone on GitHub for issue
   assignment.
