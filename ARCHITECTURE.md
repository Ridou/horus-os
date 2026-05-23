# Architecture

This document is a placeholder. The architecture is selected during the first planning phase. See `ROADMAP.md` for the current planning state.

## High-level shape (anticipated)

```
  +----------------------+        +------------------+
  |  Chat surface(s)     |        |  Web dashboard   |
  |  (CLI, web chat)     |        |  (Next.js)       |
  +----------+-----------+        +---------+--------+
             |                              |
             v                              v
  +----------------------------------------------------+
  |               Local API server (FastAPI)           |
  |  - request routing                                 |
  |  - auth                                            |
  |  - trace recording                                 |
  +----------+----------------------------+------------+
             |                            |
             v                            v
  +----------------------+        +------------------+
  |  Agent runtime       |        |  Knowledge base  |
  |  - tool registry     |        |  - markdown      |
  |  - memory pipeline   |        |  - SQLite        |
  |  - LLM client(s)     |        |  - vector store  |
  +----------------------+        +------------------+
```

Subject to revision after the first planning pass.

## Design principles

1. **Default to local.** Cloud dependencies are opt-in and replaceable.
2. **Explicit tools.** Every capability an agent has is registered, named, and traced.
3. **Reviewable memory.** Every write to long-term storage is a record the user can inspect and revert.
4. **Single binary install, eventually.** Today `pip install -e .` plus a script. Long term, a single binary or container is the target.
5. **No silent network calls.** A user can run the system offline-by-default after configuration; outbound calls require user-supplied keys and visible config.
