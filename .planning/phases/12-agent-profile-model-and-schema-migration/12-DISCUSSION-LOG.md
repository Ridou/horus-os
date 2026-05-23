# Phase 12 Discussion Log

**Date:** 2026-05-23
**Mode:** Headless auto-mode (no user present)

---

## Areas Reviewed

### Migration mechanism
- **Options considered:** (A) Version-gated ALTER TABLE in init(), (B) numbered migration runner, (C) rely on CREATE TABLE IF NOT EXISTS
- **Selected:** C - idempotent DDL. New tables use CREATE TABLE IF NOT EXISTS; no ALTER TABLE needed because Phase 12 only adds a new table.
- **Rationale:** Three total tables after Phase 12. Migration runner is premature at this scale.

### allowed_tools storage format
- **Options considered:** (A) JSON array + NULL=unrestricted, (B) comma-separated string, (C) always present JSON array (empty = no tools, null = unrestricted)
- **Selected:** A - JSON array TEXT column, NULL = unrestricted.
- **Rationale:** Consistent with tool_uses JSON pattern in traces. NULL semantics are unambiguous.

### memory_scope semantics
- **Options considered:** (A) relative path string, (B) enum tag, (C) opaque NULL now, define later
- **Selected:** C - opaque TEXT NULL. Default agent gets NULL. Phase 13 defines the actual values.
- **Rationale:** Encoding semantics before Phase 13's delegation runtime risks the wrong contract.

### Default agent bootstrap location
- **Options considered:** (A) Database.init() via INSERT OR IGNORE, (B) run_init() CLI command only, (C) lazy on first run
- **Selected:** A - Database.init() with INSERT OR IGNORE on unique name column.
- **Rationale:** Ensures default agent exists in all contexts (tests, programmatic, adapters), not just CLI init.

### CRUD API naming
- **Options considered:** (A) ROADMAP names exactly, (B) get/put/upsert naming, (C) full CRUD with separate create/update
- **Selected:** A - load_profile, save_profile (upsert), list_profiles, delete_profile.
- **Rationale:** ROADMAP names will be referenced by Phase 13-15 plan authors; changing them creates misalignment.

### AgentProfile dataclass location
- **Options considered:** (A) types.py alongside existing types, (B) new agents.py module, (C) separate AgentProfileStore class
- **Selected:** A - types.py.
- **Rationale:** Consistent with v0.1 pattern. All public data types live in types.py.

---

## Deferred Ideas

- Per-profile tool parameter overrides
- Profile version history
- Memory scope enforcement at notes layer
- TOML/YAML profile export for human editing
