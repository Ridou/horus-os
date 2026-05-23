# Phase 12: Agent Profile Model and Schema Migration - Research

**Researched:** 2026-05-23
**Domain:** SQLite schema extension, Python dataclass, CRUD API design
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Migration mechanism** - Rely on `CREATE TABLE IF NOT EXISTS` in `SCHEMA_SQL` for idempotency. No separate migration runner. Bump `SCHEMA_VERSION` from 2 to 3.

2. **`allowed_tools` storage format** - TEXT column storing a JSON array of tool name strings. NULL means "unrestricted" (all registered tools available).

3. **`memory_scope` semantics at Phase 12** - TEXT column, NULL by default. Store as an opaque tag; defer actual isolation logic to Phase 13+.

4. **Default agent bootstrap location** - Bootstrap in `Database.init()` using `INSERT OR IGNORE` on the unique `name` column. Name the default agent `"default"`. Values: `system_prompt="You are a helpful assistant."`, `default_model=NULL`, `allowed_tools=NULL`, `memory_scope=NULL`.

5. **CRUD API naming and semantics** - `load_profile(name) -> AgentProfile | None`, `save_profile(profile) -> None` (upsert with INSERT OR REPLACE semantics), `list_profiles() -> list[AgentProfile]` ordered by name, `delete_profile(name) -> bool`.

6. **`AgentProfile` dataclass location** - Add to `src/horus_os/types.py`. Fields: `name`, `system_prompt`, `default_model`, `allowed_tools`, `memory_scope`, `created_at`, `updated_at`.

### Claude's Discretion

None specified.

### Deferred Ideas (OUT OF SCOPE)

- Per-profile tool parameter overrides
- Profile versioning / history of system prompt changes
- Memory scope isolation enforcement at the notes layer (Phase 13+)
- Exporting profiles to TOML/YAML for human editing (Phase 15+)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MA-01 | Named agent profiles persist in SQLite (name, system prompt, default model, allowed tools, memory scope) | `agent_profiles` table schema + `AgentProfile` dataclass + CRUD methods on `Database` |
| MA-04 | At least one default agent profile is auto-created on `horus-os init` | `INSERT OR IGNORE` bootstrap in `Database.init()` triggered by `run_init()` in `cli/init_cmd.py` |
| MIG-01 | v0.1 SQLite database upgrades to v0.2 schema idempotently | `CREATE TABLE IF NOT EXISTS` in existing `SCHEMA_SQL` handles this; existing `traces` and `note_writes` rows survive |
| MIG-02 | v0.1 single-agent traces remain readable in the v0.2 dashboard | No schema changes to `traces` table; read path is unaffected; verified by existing `test_storage.py` tests continuing to pass |
</phase_requirements>

---

## Summary

Phase 12 is a pure Python/SQLite extension. There are no new external dependencies. The work extends three existing modules (`storage.py`, `types.py`, `__init__.py`) and adds tests to `tests/test_storage.py`.

The existing codebase provides the complete blueprint. `SCHEMA_SQL` already uses `CREATE TABLE IF NOT EXISTS` throughout; adding `agent_profiles` there is safe. The `SCHEMA_VERSION` pattern (single-row `schema_version` table, updated from 2 to 3 in `init()`) follows the same logic already used for v1-to-v2. The `Database` class already has `_row_to_trace()` and `_row_to_write()` static methods as the precedent for `_row_to_profile()`. `AgentResult`, `NoteWrite`, etc. in `types.py` are the precedent for `AgentProfile`.

The one nuance not resolved in CONTEXT.md is `created_at` preservation on upsert. `INSERT OR REPLACE` deletes and reinserts the conflicting row, resetting `created_at`. SQLite 3.24+ `ON CONFLICT DO UPDATE` preserves it. The local SQLite version is 3.45.3 [VERIFIED: `sqlite3.sqlite_version` at runtime], so the UPSERT syntax is available.

**Primary recommendation:** Implement `save_profile` with `INSERT INTO ... ON CONFLICT(name) DO UPDATE SET ...` to preserve `created_at` on update. This satisfies the "upsert semantics" decision in CONTEXT.md while producing correct timestamps.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Agent profile schema | Database / Storage | - | DDL belongs in `storage.py` alongside existing schema |
| `AgentProfile` dataclass | Shared types layer | - | Consistent with `AgentResult`, `NoteWrite`, `ToolUse` all living in `types.py` |
| CRUD API | Database / Storage | - | `Database` class owns all reads and writes; no business logic needed at this phase |
| Default agent bootstrap | Database / Storage | CLI entry point triggers | `Database.init()` owns creation; `run_init()` in CLI just calls `db.init()` |
| Public export | Package `__init__.py` | - | `AgentProfile` must be exported alongside other public types |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | stdlib (Python 3.11+, SQLite 3.45.3 local) | Persistence | Already in use; no new dep [VERIFIED: codebase] |
| `json` | stdlib | Serialize `allowed_tools` list | Already used for `tool_uses` column in `traces` [VERIFIED: codebase] |
| `dataclasses` | stdlib | `AgentProfile` dataclass | Pattern established by all existing types [VERIFIED: codebase] |
| `datetime` | stdlib | `created_at`/`updated_at` timestamps | `_now_iso()` already defined in `storage.py` [VERIFIED: codebase] |
| `pytest` | >=8.0 (dev dep) | Tests | Already configured [VERIFIED: pyproject.toml] |

### Supporting
None. No new packages required.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `sqlite3` | SQLAlchemy ORM | ORM adds a dependency and abstraction overhead not needed for 3-4 tables; raw sqlite3 already proven in 11 phases |
| `ON CONFLICT DO UPDATE` (UPSERT) | `INSERT OR REPLACE` | OR REPLACE deletes+reinserts (resets `created_at`); UPSERT preserves it. UPSERT requires SQLite 3.24+ which is met. |

**Installation:** No new packages. All required modules are Python stdlib.

---

## Architecture Patterns

### System Architecture Diagram

```
horus-os init
     |
     v
run_init() [cli/init_cmd.py]
     |
     v
Database(config.db_path).init()
     |
     +-- executescript(SCHEMA_SQL)        # CREATE TABLE IF NOT EXISTS agent_profiles
     |                                    # (idempotent; existing tables untouched)
     |
     +-- UPDATE schema_version -> 3      # bumps version counter
     |
     +-- INSERT OR IGNORE agent_profiles  # bootstraps default agent
         WHERE name = 'default'
         (no-op if already exists)

Agent runtime (Phase 13+)
     |
     v
Database.load_profile(name)  -->  agent_profiles table  -->  AgentProfile dataclass
Database.save_profile(p)     -->  UPSERT on name unique constraint
Database.list_profiles()     -->  all rows, ORDER BY name
Database.delete_profile(name) --> DELETE WHERE name = ?; return bool
```

### Recommended Project Structure
No structural changes. Modifications are localized to:
```
src/horus_os/
├── types.py          # ADD AgentProfile dataclass
├── storage.py        # ADD: agent_profiles table DDL, bump SCHEMA_VERSION, CRUD methods
└── __init__.py       # ADD: AgentProfile to imports and __all__
tests/
└── test_storage.py   # ADD: agent profile tests (idempotency, CRUD, migration)
```

### Pattern 1: Extending SCHEMA_SQL

Append the new table to the existing `SCHEMA_SQL` string. `CREATE TABLE IF NOT EXISTS` makes it safe to run on a v0.1 database that already has `traces` and `note_writes`.

```python
# Source: VERIFIED from src/horus_os/storage.py
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version ( ... );
CREATE TABLE IF NOT EXISTS traces ( ... );
CREATE TABLE IF NOT EXISTS note_writes ( ... );

CREATE TABLE IF NOT EXISTS agent_profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    system_prompt TEXT NOT NULL,
    default_model TEXT,
    allowed_tools TEXT,
    memory_scope  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_name ON agent_profiles(name);
"""

SCHEMA_VERSION = 3
```

### Pattern 2: CRUD via `_row_to_profile()` static method

Match the `_row_to_trace()` and `_row_to_write()` precedent exactly.

```python
# Source: VERIFIED from src/horus_os/storage.py pattern
@staticmethod
def _row_to_profile(row: sqlite3.Row) -> AgentProfile:
    try:
        allowed_tools = json.loads(row["allowed_tools"]) if row["allowed_tools"] else None
    except json.JSONDecodeError:
        allowed_tools = None
    return AgentProfile(
        name=row["name"],
        system_prompt=row["system_prompt"],
        default_model=row["default_model"],
        allowed_tools=allowed_tools,
        memory_scope=row["memory_scope"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

### Pattern 3: UPSERT with `created_at` preservation

```python
# Source: ASSUMED - CONTEXT.md says "INSERT OR REPLACE" but UPSERT is the correct implementation
def save_profile(self, profile: AgentProfile) -> None:
    now = _now_iso()
    allowed_tools_json = json.dumps(profile.allowed_tools) if profile.allowed_tools is not None else None
    with self._connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_profiles
                (name, system_prompt, default_model, allowed_tools, memory_scope, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                system_prompt = excluded.system_prompt,
                default_model = excluded.default_model,
                allowed_tools = excluded.allowed_tools,
                memory_scope  = excluded.memory_scope,
                updated_at    = excluded.updated_at
            """,
            (profile.name, profile.system_prompt, profile.default_model,
             allowed_tools_json, profile.memory_scope, now, now),
        )
```

### Pattern 4: Default agent bootstrap in `Database.init()`

Place the `INSERT OR IGNORE` immediately after `executescript(SCHEMA_SQL)` but before the version counter update.

```python
# Source: VERIFIED from CONTEXT.md Decision 4
def init(self) -> None:
    self.path.parent.mkdir(parents=True, exist_ok=True)
    with self._connect() as conn:
        conn.executescript(SCHEMA_SQL)
        # bootstrap default agent
        now = _now_iso()
        conn.execute(
            """
            INSERT OR IGNORE INTO agent_profiles
                (name, system_prompt, default_model, allowed_tools, memory_scope, created_at, updated_at)
            VALUES ('default', 'You are a helpful assistant.', NULL, NULL, NULL, ?, ?)
            """,
            (now, now),
        )
        # version counter (existing pattern)
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row[0] < SCHEMA_VERSION:
            conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
```

### Pattern 5: `AgentProfile` dataclass in `types.py`

```python
# Source: VERIFIED from CONTEXT.md Decision 6 + types.py pattern
@dataclass
class AgentProfile:
    name: str
    system_prompt: str
    default_model: str | None = None
    allowed_tools: list[str] | None = None   # None = unrestricted
    memory_scope: str | None = None           # None = global
    created_at: str = ""                      # ISO-8601 UTC, set by DB layer
    updated_at: str = ""                      # ISO-8601 UTC, set by DB layer
```

### Anti-Patterns to Avoid

- **`INSERT OR REPLACE` for profiles with timestamps:** Deletes and reinserts the row, resetting `created_at` to now. Use `ON CONFLICT DO UPDATE` instead.
- **Setting `created_at`/`updated_at` in the dataclass caller:** Timestamps must be set by `save_profile()` / bootstrap, not passed in by callers. The dataclass defaults to `""` as a sentinel that the DB layer will overwrite.
- **Storing `allowed_tools = []` to mean "no tools":** An empty list is ambiguous. The spec reserves `NULL` for "unrestricted" and a non-empty JSON array for explicit allowlists. An empty array `[]` would mean "no tools allowed" which is a valid but different state.
- **Running DDL inside a parameterized `conn.execute()`:** `executescript()` is used for multi-statement DDL. Never mix it with user-supplied data (it doesn't support parameters). Bootstrap data goes in separate `conn.execute()` calls with `?` placeholders.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migration runner | Custom migration class with up/down methods | `CREATE TABLE IF NOT EXISTS` + `SCHEMA_VERSION` bump | Three tables total; a migration runner is premature at this scale; existing pattern proven across 11 phases |
| Timestamp generation | `time.time()`, `time.strftime()` | `_now_iso()` already in `storage.py` | Consistent ISO-8601 UTC format required across all tables; function already exists |
| JSON serialization for `allowed_tools` | Custom encoding | `json.dumps()` / `json.loads()` | Same pattern as `tool_uses` column in `traces` [VERIFIED: codebase] |

**Key insight:** Every pattern needed for Phase 12 already exists in `storage.py`. This phase is an extension, not a redesign.

---

## Runtime State Inventory

> This section is required because Phase 12 touches the SQLite schema (a rename from v0.1 to v0.2 schema).

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | SQLite `horus.sqlite` in user's data dir (`~/.local/share/horus-os/` or `~/.horus-os/`). Contains `schema_version=2`, `traces`, `note_writes`. No `agent_profiles` table. | `Database.init()` will `CREATE TABLE IF NOT EXISTS agent_profiles` - pure additive, no rows migrated |
| Live service config | Dashboard (FastAPI + Next.js) served locally on demand. No persistent service config stores schema version. | None - restart restarts from scratch |
| OS-registered state | None found. horus-os has no OS-level registrations (no launchd plists, no systemd units, no Task Scheduler entries) [VERIFIED: codebase, no such files]. | None |
| Secrets/env vars | `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` in `.env` - no rename involved. | None |
| Build artifacts | `horus_os.egg-info/` generated by `pip install -e '.[dev]'`. No stale references to schema version. | None - reinstall not required |

**v0.1 trace rows:** Existing `traces` and `note_writes` rows are fully preserved. No column changes. MIG-02 is automatically satisfied.

**Nothing found in categories: OS-registered state, Secrets/env vars, Build artifacts** - verified by codebase inspection.

---

## Common Pitfalls

### Pitfall 1: `INSERT OR REPLACE` resets `created_at`
**What goes wrong:** `INSERT OR REPLACE` is implemented by SQLite as `DELETE` + `INSERT`. The old row's `created_at` is lost. Every call to `save_profile()` on an existing profile resets `created_at` to now.
**Why it happens:** SQLite's `REPLACE` conflict resolution is an alias for `DELETE + INSERT`, not an in-place update.
**How to avoid:** Use `INSERT INTO ... ON CONFLICT(name) DO UPDATE SET ...` (UPSERT syntax, SQLite 3.24+). Only update the mutable columns (`system_prompt`, `default_model`, `allowed_tools`, `memory_scope`, `updated_at`). Leave `created_at` untouched.
**Warning signs:** Test assertions that `created_at` is preserved after a second `save_profile()` call will fail.

### Pitfall 2: `executescript()` autocommit behavior
**What goes wrong:** `executescript()` issues an implicit `COMMIT` before running, and the script runs outside the normal connection context manager. If `init()` uses `with conn:` (which sets `isolation_level=None` in this codebase), there is no active transaction to commit.
**Why it happens:** Python's `sqlite3.Connection.executescript()` commits any pending transaction unconditionally before running.
**How to avoid:** Run DDL via `executescript()` first, then run parameterized DML (bootstrap insert, version update) via separate `conn.execute()` calls. This matches the existing pattern in `init()` [VERIFIED: storage.py:109-115].

### Pitfall 3: NULL vs `[]` for `allowed_tools`
**What goes wrong:** Storing `[]` (empty JSON array) for a new agent where the intent was "unrestricted." Phase 13 code that does `if allowed_tools is not None: filter(registry)` will find a list, filter to nothing, and the agent will have zero tools.
**Why it happens:** Callers that construct `AgentProfile` without setting `allowed_tools` get `None` (correct), but callers that pass `[]` explicitly create an agent with no tools.
**How to avoid:** Validate in `save_profile()`: treat `allowed_tools=[]` as `None` or document the distinction clearly. The bootstrap in `init()` uses `NULL` (correct).

### Pitfall 4: `schema_version` row missing on upgrade
**What goes wrong:** A v0.1 database has exactly one row in `schema_version` with `version=2`. After `executescript(SCHEMA_SQL)`, the `schema_version` table still has that one row. The `init()` logic must hit the `elif row[0] < SCHEMA_VERSION` branch to update it to 3.
**Why it happens:** If a test or codebase path skips version tracking entirely, Phase 13+ code that reads `schema_version` may find `2` and behave incorrectly.
**How to avoid:** The existing `init()` pattern [VERIFIED: storage.py:111-115] already handles this correctly. The test for v1-to-v2 upgrade (`test_schema_v1_database_upgrades_to_v2`) must be replicated for v2-to-v3.

### Pitfall 5: `_now_iso()` placement
**What goes wrong:** Calling `_now_iso()` outside the `with self._connect() as conn:` block means the timestamp is captured before the connection opens. For bootstrapping in `init()`, this is fine; for `save_profile()`, timestamps should be captured inside the connection context to avoid subtle time drift.
**Why it happens:** Code review miss.
**How to avoid:** Capture `now = _now_iso()` at the top of each method body, not inside nested blocks.

---

## Code Examples

### Full `delete_profile` implementation
```python
# Source: VERIFIED from CONTEXT.md Decision 5 + codebase pattern
def delete_profile(self, name: str) -> bool:
    with self._connect() as conn:
        cursor = conn.execute(
            "DELETE FROM agent_profiles WHERE name = ?", (name,)
        )
        return cursor.rowcount > 0
```

### Full `load_profile` implementation
```python
def load_profile(self, name: str) -> AgentProfile | None:
    with self._connect() as conn:
        row = conn.execute(
            """
            SELECT name, system_prompt, default_model, allowed_tools,
                   memory_scope, created_at, updated_at
            FROM agent_profiles
            WHERE name = ?
            """,
            (name,),
        ).fetchone()
        return self._row_to_profile(row) if row is not None else None
```

### Full `list_profiles` implementation
```python
def list_profiles(self) -> list[AgentProfile]:
    with self._connect() as conn:
        cursor = conn.execute(
            """
            SELECT name, system_prompt, default_model, allowed_tools,
                   memory_scope, created_at, updated_at
            FROM agent_profiles
            ORDER BY name
            """
        )
        return [self._row_to_profile(row) for row in cursor.fetchall()]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `INSERT OR REPLACE` for upsert | `INSERT ... ON CONFLICT DO UPDATE` | SQLite 3.24 (2018) | Preserves `id`, `created_at` on conflict; no DELETE + INSERT overhead |
| Separate migration files (Alembic, etc.) | Idempotent `CREATE TABLE IF NOT EXISTS` | Already established in this project | Simpler; sufficient for small table count |

**Deprecated/outdated:**
- `INSERT OR REPLACE` for tables with auto-generated timestamps: replaced by UPSERT syntax.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `save_profile` should use `ON CONFLICT DO UPDATE` rather than `INSERT OR REPLACE` to preserve `created_at` | Pattern 3, Pitfall 1 | If callers don't care about `created_at` preservation, `INSERT OR REPLACE` is simpler and matches CONTEXT.md verbatim |
| A2 | `AgentProfile` should be exported from `__init__.py` alongside other public types | Architecture | If downstream code only imports from `horus_os.types` directly, the export is not strictly needed for Phase 12 |

---

## Open Questions

1. **`created_at` behavior on `save_profile`**
   - What we know: CONTEXT.md says "upsert (INSERT OR REPLACE)"; `INSERT OR REPLACE` resets `created_at`
   - What's unclear: Whether preserving the original `created_at` matters for Phase 12 (Phase 15 CLI is where users edit profiles)
   - Recommendation: Use `ON CONFLICT DO UPDATE` (preserves `created_at`); no downside vs `INSERT OR REPLACE`

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Runtime | Yes | 3.12.7 | - |
| SQLite 3.24+ | UPSERT syntax | Yes | 3.45.3 | Fall back to `INSERT OR REPLACE` (simpler, resets created_at) |
| pytest 8+ | Tests | Yes | configured in pyproject.toml | - |

**No missing dependencies.** Phase 12 is stdlib-only.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_storage.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MA-01 | `agent_profiles` table created after `db.init()` | unit | `pytest tests/test_storage.py::test_init_creates_agent_profiles_table -x` | Wave 0 |
| MA-01 | `save_profile` + `load_profile` round-trip | unit | `pytest tests/test_storage.py::test_save_and_load_profile_round_trip -x` | Wave 0 |
| MA-01 | `list_profiles` returns all profiles ordered by name | unit | `pytest tests/test_storage.py::test_list_profiles_ordered_by_name -x` | Wave 0 |
| MA-01 | `delete_profile` returns True when deleted, False when missing | unit | `pytest tests/test_storage.py::test_delete_profile_returns_bool -x` | Wave 0 |
| MA-01 | `allowed_tools=None` round-trips as None | unit | `pytest tests/test_storage.py::test_allowed_tools_null_round_trip -x` | Wave 0 |
| MA-01 | `allowed_tools=["read_file"]` round-trips as list | unit | `pytest tests/test_storage.py::test_allowed_tools_list_round_trip -x` | Wave 0 |
| MA-01 | `save_profile` preserves `created_at` on update | unit | `pytest tests/test_storage.py::test_save_profile_preserves_created_at -x` | Wave 0 |
| MA-04 | Default agent `"default"` exists after `db.init()` | unit | `pytest tests/test_storage.py::test_init_creates_default_agent -x` | Wave 0 |
| MA-04 | Second `db.init()` does not duplicate default agent | unit | `pytest tests/test_storage.py::test_init_default_agent_idempotent -x` | Wave 0 |
| MIG-01 | v0.1 (schema_version=2) DB upgrades to v3 with `agent_profiles` | unit | `pytest tests/test_storage.py::test_schema_v2_database_upgrades_to_v3 -x` | Wave 0 |
| MIG-02 | v0.1 traces remain readable after `db.init()` on upgraded DB | unit | `pytest tests/test_storage.py::test_v1_traces_readable_after_v3_upgrade -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_storage.py -x`
- **Per wave merge:** `pytest`

### Wave 0 Gaps
- [ ] `tests/test_storage.py` - all test functions listed above (add to existing file; file exists but none of the Phase 12 test functions exist yet)
- [ ] No framework install needed - pytest already in dev deps

---

## Sources

### Primary (HIGH confidence)
- `src/horus_os/storage.py` [VERIFIED: read in session] - existing `SCHEMA_SQL`, `SCHEMA_VERSION`, `Database._connect()`, `Database.init()`, `_row_to_trace()` patterns
- `src/horus_os/types.py` [VERIFIED: read in session] - existing dataclass patterns (`AgentResult`, `NoteWrite`, etc.)
- `src/horus_os/__init__.py` [VERIFIED: read in session] - public export pattern
- `tests/test_storage.py` [VERIFIED: read in session] - test conventions and coverage patterns
- `.planning/phases/12-agent-profile-model-and-schema-migration/12-CONTEXT.md` [VERIFIED: read in session] - all locked decisions
- `pyproject.toml` [VERIFIED: read in session] - Python 3.11+ requirement, pytest 8+ config
- `sqlite3.sqlite_version` = 3.45.3 [VERIFIED: runtime check] - confirms UPSERT syntax available

### Secondary (MEDIUM confidence)
- SQLite `ON CONFLICT DO UPDATE` syntax: available since SQLite 3.24.0 (2018-06-04). Confirmed available given local 3.45.3.

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all stdlib, all verified in codebase
- Architecture: HIGH - every pattern is a direct extension of existing code
- Pitfalls: HIGH - `INSERT OR REPLACE` behavior is SQLite-documented; others verified from code
- Test map: HIGH - test names derived from existing `test_storage.py` conventions

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (stable stdlib domain; patterns driven by locked decisions)
