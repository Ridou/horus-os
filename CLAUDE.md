# horus-os, Project Rules for Claude

## What this project is

`horus-os` is an open-source autonomous AI command center, built public-from-day-one. It is a **sibling** of a private project (`~/Projects/horus`), not a fork, snapshot, or extract of it.

## Hard rules

1. **No personal information of the maintainer ever enters this tree.** Names, locations, phone numbers, server IPs, vault paths, API keys, account-bound credentials are all forbidden. If a piece of code from the private sibling depends on any of those, it does not get copied; it gets re-implemented cleanly here.

2. **No git operations touch the private sibling.** Do not run `git pull`, `git fetch`, `git remote add`, or any cross-repo operation that bridges `~/Projects/horus` and `~/Projects/horus-os`. They are independent.

3. **No automatic push to GitHub.** This repo has no remote configured intentionally. A remote is added by the maintainer when (and only when) the project is ready to publish.

4. **No reference to the private sibling in committed text.** Commit messages, code comments, docs, planning artifacts must not name the private project, the maintainer, the maintainer's machines, or the maintainer's daily-driver workflow. Treat this repo as if a stranger will read every file someday.

5. **No em-dashes in committed prose.** Use commas, periods, or hyphens. Same rule as the maintainer's private projects.

## What this project is NOT

- Not a port of any private codebase. Code is written here from the start.
- Not a derived snapshot. There is no extraction pipeline.
- Not a public mirror with private upstream. There is no upstream.

## Layout

Same disk as the private sibling at `~/Projects/horus-os/`, but the two are completely independent git repos. The `.git` directories are separate. There is no shared remote, no shared history.

## Next steps for any new Claude session

1. Read `PROJECT.md` for the project vision and scope.
2. Read `ROADMAP.md` for the current phase plan.
3. Read `ARCHITECTURE.md` for the technical shape.
4. Read `.planning/STATE.md` for the in-flight status (if it exists).
5. Ask the maintainer before assuming anything about the private sibling. The private sibling is not consulted, not referenced, not pulled from.
