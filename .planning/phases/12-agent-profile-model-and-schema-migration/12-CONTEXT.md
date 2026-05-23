# Phase 12 Context: Agent profile model and schema migration

**Date:** 2026-05-23
**Phase:** 12
**Status:** Context captured (headless auto-mode)

---

## Domain

Phase 12 delivers the persistent `agent_profiles` table in SQLite, an idempotent forward migration from the v0.1 schema, a CRUD API (`load_profile`, `save_profile`, `list_profiles`, `delete_profile`) on the `Database` class, and automatic creation of a default agent on `init`. This is the storage-layer hard gate for all of Phase 13-17.

---

## Canonical Refs

- `.planning/ROADMAP.md` - Phase 12 success criteria and dependency chain
- `.planning/REQUIREMENTS.md` - MA-01, MA-04, MIG-01, MIG-02
- `src/horus_os/storage.py` - Existing Database class and schema pattern to extend
- `src/horus_os/types.py` - Where new AgentProfile dataclass will live
- `src/horus_os/cli/init_cmd.py` - Entry point that calls Database.init()

---

## Decisions

### 1. Migration mechanism

**Decision:** Rely on `CREATE TABLE IF NOT EXISTS` in `SCHEMA_SQL` for idempotency. No separate migration runner.

The existing `SCHEMA_SQL` string uses `CREATE TABLE IF NOT EXISTS` throughout. Running `init()` on a v0.1 database that already has `traces` and `note_writes` will create the new `agent_profiles` table without touching existing rows. Bump `SCHEMA_VERSION` from 2 to 3. The version update signals the upgrade happened; no structural ALTER TABLE statements are needed because we are only adding a new table, not modifying existing ones.

**Why:** A migration runner would be premature. The project has three tables total after Phase 12. The existing pattern of idempotent DDL is sufficient and has already proven correct through 11 shipped phases.

### 2. `allowed_tools` storage format

**Decision:** TEXT column storing a JSON array of tool name strings. NULL means "unrestricted" (all registered tools available).

Example: `'["read_file", "write_note"]'` restricts the agent to those two tools. `NULL` grants access to all tools in the registry at runtime. This is consistent with how `tool_uses` is stored in the `traces` table (JSON text column).

**Why:** NULL-as-unrestricted is semantically clean and avoids the ambiguity of an empty array (which could mean "no tools allowed"). Downstream phases (Phase 13 `delegate_to_agent`, Phase 15 CLI) can filter `registry.list()` using `json.loads(allowed_tools)` when the field is non-null.

### 3. `memory_scope` semantics at Phase 12

**Decision:** TEXT column, NULL by default. Store as an opaque tag; defer actual isolation logic to Phase 13+.

Phase 12 must persist the column per the success criteria and MA-01, but the memory isolation behavior is Phase 13/15's concern. The default agent has `memory_scope = NULL`, meaning "use the global notes directory." The column exists so Phase 13 can query and act on it without a schema change.

**Why:** Defining the semantics now (before Phase 13's delegation runtime) risks encoding the wrong contract. Keeping it an opaque nullable string lets Phase 13 define the actual values ("global", "isolated", "shared:<name>") without a migration.

### 4. Default agent bootstrap location

**Decision:** Bootstrap in `Database.init()` using `INSERT OR IGNORE` on the unique `name` column. Name the default agent `"default"`.

`Database.init()` is called from `run_init()` in `cli/init_cmd.py`, from tests, and from any future programmatic startup path. Putting the bootstrap there means the default agent always exists whenever the database is initialized, regardless of how it was created. Subsequent calls to `init()` silently skip the insert because of `INSERT OR IGNORE`.

Default agent values:
- `name`: `"default"`
- `system_prompt`: `"You are a helpful assistant."` (minimal; users can override via Phase 15 CLI)
- `default_model`: NULL (inherits from `Config.anthropic_model` / `Config.gemini_model` at runtime)
- `allowed_tools`: NULL (unrestricted)
- `memory_scope`: NULL (global)

**Why:** Putting bootstrap in `Database.init()` rather than `run_init()` ensures the default agent exists in any context, including tests and future adapters that initialize the DB directly. Option B (CLI-only bootstrap) would leave the DB without a default agent in programmatic use cases.

### 5. CRUD API naming and semantics

**Decision:** Follow the ROADMAP names exactly: `load_profile`, `save_profile`, `list_profiles`, `delete_profile` as methods on the `Database` class.

- `load_profile(name: str) -> AgentProfile | None` - fetch by name
- `save_profile(profile: AgentProfile) -> None` - upsert (INSERT OR REPLACE)
- `list_profiles() -> list[AgentProfile]` - all profiles, ordered by name
- `delete_profile(name: str) -> bool` - remove by name, return True if deleted

**Why:** The ROADMAP names are already in the Phase 13 success criteria and will be referenced by plan authors for Phases 13-15. Renaming them now creates misalignment. Upsert semantics for `save_profile` matches the "create or update" intent from the CLI perspective (Phase 15).

### 6. `AgentProfile` dataclass location

**Decision:** Add `AgentProfile` to `src/horus_os/types.py`, alongside the existing `Tool`, `ToolUse`, `AgentResult`, etc.

Fields:
```python
@dataclass
class AgentProfile:
    name: str
    system_prompt: str
    default_model: str | None = None
    allowed_tools: list[str] | None = None   # None = unrestricted
    memory_scope: str | None = None           # None = global
    created_at: str = ""                      # ISO-8601 UTC, set by DB
    updated_at: str = ""                      # ISO-8601 UTC, set by DB
```

**Why:** Consistent with v0.1 pattern. All public data types live in `types.py`. A separate module would add import complexity for no gain at this scale.

---

## Deferred Ideas

- Per-profile tool parameter overrides (e.g., "this agent can only read from /tmp/") - future phase
- Profile versioning / history of system prompt changes - future phase
- Memory scope isolation enforcement at the notes layer - Phase 13+
- Exporting profiles to TOML/YAML for human editing outside the wizard - Phase 15+

---

## Gray Areas Decided Autonomously

This context was captured in headless auto-mode. The following areas were identified and decided without user input:

| Area | Decision |
|------|----------|
| Migration mechanism | Idempotent DDL in SCHEMA_SQL; no migration runner; SCHEMA_VERSION 2 -> 3 |
| allowed_tools format | JSON array TEXT, NULL = unrestricted |
| memory_scope semantics | Opaque TEXT NULL; defer isolation logic to Phase 13 |
| Default agent bootstrap | In Database.init() via INSERT OR IGNORE; name="default" |
| CRUD API naming | Follow ROADMAP: load_profile, save_profile, list_profiles, delete_profile |
| AgentProfile location | types.py, consistent with existing pattern |
