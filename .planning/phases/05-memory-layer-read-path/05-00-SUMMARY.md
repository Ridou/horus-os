---
phase: 05-memory-layer-read-path
plan: "00"
subsystem: memory
tags: [memory, notes, markdown, search, read-only]

# Dependency graph
requires:
  - phase: "04-tool-registry"
    provides: "Tool dataclass and the registry that holds bound tools"
provides:
  - "horus_os.memory.NotesStore, list / read / search over a markdown folder"
  - "horus_os.memory.search_notes_tool / read_note_tool / list_notes_tool factories"
  - "horus_os.types.NoteRef dataclass"
affects:
  - "Phase 06 (memory layer write path) will add append_note tool plus a structured trail"
  - "Phase 07 (CLI) wires NotesStore into the default registry"
  - "Phase 08 (dashboard) will render NoteRef previews and link to full content"

# Tech tracking
tech-stack:
  added: []  # pure stdlib pathlib + datetime
  patterns:
    - "Read-only store first. Mutations land in a sibling phase to keep this surface simple."
    - "Substring search ranked by hit count. Cheap, deterministic, ships today without a vector store."
    - "Per-tool factories that close over a NotesStore. The registry holds whatever you bind."

key-files:
  created:
    - "src/horus_os/memory/__init__.py, 14 lines, re-exports"
    - "src/horus_os/memory/notes.py, 97 lines, NotesStore and title extractor"
    - "src/horus_os/memory/tools.py, 78 lines, three Tool factories"
    - "tests/test_notes_store.py, 128 lines, 15 tests"
    - "tests/test_memory_tools.py, 65 lines, 7 tests"
  modified:
    - "src/horus_os/types.py, added NoteRef dataclass"
    - "src/horus_os/__init__.py, re-exports NotesStore, NoteRef, three tool factories"

key-decisions:
  - "Substring search over FTS5 for v0.1. FTS5 is a one-liner SQLite migration once the dashboard needs sub-second latency on tens of thousands of notes. Today the corpus fits in memory."
  - "Title extraction is first-H1 with filename stem fallback. No frontmatter parsing in v0.1; notes without an H1 fall back to the stem and the dashboard can render that cleanly."
  - "Empty-query short-circuit. The model can otherwise dump the entire corpus through context by asking for an empty search. Phase 06 may add a `list_notes(limit)` tool for the same reason."
  - "Path escape blocking applies to read_note and to any path the model returns from search_notes. The model could not escape via the rel_path alone because search_notes never emits a path outside the root."
  - "Markdown filenames only (`*.md`). Other formats (txt, html) defer to a follow-up. The user can convert anything they want into markdown for the agent to see."

patterns-established:
  - "Store + bound tools split. The store does the heavy lifting and exposes a Python API. The tools wrap it for agent consumption. This isolates the security and IO concerns from the agent-facing schema."
  - "Recursive `rglob` for discovery. Future phases that add filters can switch to a generator without changing the public surface."

requirements-completed:
  - MEM-01  # Agent can search a markdown notes folder and read individual files

known-limitations:
  - "No frontmatter parsing. Tags, aliases, and Obsidian-style metadata are invisible. v0.x can add a parser."
  - "No incremental indexing. Every search re-reads every file. Acceptable up to about 5,000 notes on a laptop."
  - "Symlinks inside notes_dir that point outside it are followed by Path.resolve(). The path-escape check still catches the symlinked target. Symlinks inside notes_dir that loop infinitely would hang rglob; v0.1 trusts that the user does not configure such a folder."
  - "No write path. read_only by design. MEM-02 ships in Phase 06."

# Metrics
duration: 24m
completed: 2026-05-23
commit-count: 1
test-count: 22 (76 total cumulative)
lint-issues: 0
new-public-api-symbols: 5 (NotesStore, NoteRef, search_notes_tool, read_note_tool, list_notes_tool)
