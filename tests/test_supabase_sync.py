"""Mocked-httpx sync tests for SupabaseAdapter.

Verifies:
- SUPA-05: With no Supabase env vars, start() is a silent no-op.
- SUPA-01: _sync_table pushes new rows with the correct PostgREST headers.
- Cursor advances after a successful push.
- No POST is made when list_rows_after returns no rows.
- The service key appears only in Authorization/apikey headers, never in a URL.

All tests use a fake httpx.AsyncClient -- no live Supabase connection is required.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.supabase_adapter import (
    SUPABASE_KEY_ENV,
    SUPABASE_URL_ENV,
    SupabaseAdapter,
    _push_sync_health,
    _sync_headers,
    _sync_table,
)
from horus_os.config import Config
from horus_os.storage import Database

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(tmp_path: Path) -> AdapterContext:
    """Build an AdapterContext backed by a real tmp-dir config."""
    cfg = Config(
        db_path=tmp_path / "t.db",
        data_dir=tmp_path,
        notes_dir=tmp_path / "notes",
    )
    registry = AdapterRegistry()
    registry.register("supabase")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=registry)


def _seed_trace(db_path: Path, trace_id: str, created_at: str) -> None:
    """Insert a minimal trace row directly into the SQLite database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO traces "
        "(trace_id, created_at, provider, model, prompt) "
        "VALUES (?, ?, 'anthropic', 'claude-3', 'hello')",
        (trace_id, created_at),
    )
    conn.commit()
    conn.close()


def _seed_agent_profile(db_path: Path, name: str, updated_at: str) -> None:
    """Insert a minimal agent_profiles row directly into the SQLite database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO agent_profiles (name, system_prompt, created_at, updated_at) "
        "VALUES (?, 'sys', ?, ?)",
        (name, updated_at, updated_at),
    )
    conn.commit()
    conn.close()


def _seed_task(db_path: Path, task_id: str, updated_at: str) -> None:
    """Insert a minimal tasks row directly into the SQLite database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO tasks (task_id, title, status, created_at, updated_at) "
        "VALUES (?, 'title', 'pending', ?, ?)",
        (task_id, updated_at, updated_at),
    )
    conn.commit()
    conn.close()


class FakeResponse:
    """Minimal fake httpx.Response with a no-op raise_for_status."""

    def raise_for_status(self) -> None:
        pass


def _make_fake_client() -> tuple[MagicMock, list[tuple]]:
    """Return a fake AsyncClient and the list that records all post calls.

    Each post call appends (url, json, headers) to the list so tests
    can assert on the captured arguments.
    """
    calls: list[tuple] = []

    async def _post(url: str, *, json: object, headers: dict) -> FakeResponse:
        calls.append((url, json, headers))
        return FakeResponse()

    client = MagicMock()
    client.post = _post
    return client, calls


# ---------------------------------------------------------------------------
# Test: silent no-op with no env vars (SUPA-05)
# ---------------------------------------------------------------------------


class TestNoEnvVarsNoStart:
    """With no Supabase env vars the adapter must be a silent no-op."""

    async def test_no_env_vars_no_start(self, tmp_path, monkeypatch):
        """start() leaves the registry untouched and creates no background task."""
        monkeypatch.delenv(SUPABASE_URL_ENV, raising=False)
        monkeypatch.delenv(SUPABASE_KEY_ENV, raising=False)

        adapter = SupabaseAdapter()
        ctx = _make_context(tmp_path)
        ctx.registry.register("supabase")

        await adapter.start(ctx)

        entry = ctx.registry.get("supabase")
        assert entry is not None
        assert entry.status != "running", "status must NOT be running"
        assert entry.error_count == 0, "error_count must stay 0 (silent no-op)"
        assert adapter._task is None, "no background task must be created"

    async def test_only_url_set_is_still_noop(self, tmp_path, monkeypatch):
        """start() is a no-op when only SUPABASE_URL is set (key missing)."""
        monkeypatch.setenv(SUPABASE_URL_ENV, "https://example.supabase.co")
        monkeypatch.delenv(SUPABASE_KEY_ENV, raising=False)

        adapter = SupabaseAdapter()
        ctx = _make_context(tmp_path)

        await adapter.start(ctx)

        assert adapter._task is None
        entry = ctx.registry.get("supabase")
        assert entry is None or entry.error_count == 0

    async def test_only_key_set_is_still_noop(self, tmp_path, monkeypatch):
        """start() is a no-op when only SUPABASE_SERVICE_KEY is set (URL missing)."""
        monkeypatch.delenv(SUPABASE_URL_ENV, raising=False)
        monkeypatch.setenv(SUPABASE_KEY_ENV, "fake-key-abc")

        adapter = SupabaseAdapter()
        ctx = _make_context(tmp_path)

        await adapter.start(ctx)

        assert adapter._task is None
        entry = ctx.registry.get("supabase")
        assert entry is None or entry.error_count == 0


# ---------------------------------------------------------------------------
# Test: sync loop pushes new rows with correct headers
# ---------------------------------------------------------------------------


class TestSyncLoopPushesNewRows:
    """_sync_table must POST seeded rows to the correct PostgREST URL."""

    async def test_sync_loop_pushes_new_rows(self, tmp_path):
        """A single _sync_table pass POSTs the seeded trace row."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        created_at = "2026-01-01T12:00:00.000000Z"
        _seed_trace(db_path, "trace-push-001", created_at)

        url = "https://example.supabase.co"
        key = "fake-service-key-xyz"
        client, calls = _make_fake_client()

        await _sync_table(db, client, url, key, "traces", "created_at")

        assert len(calls) == 1, "exactly one POST must be made"
        post_url, post_json, _post_headers = calls[0]
        assert post_url == f"{url}/rest/v1/traces"
        assert isinstance(post_json, list)
        assert len(post_json) == 1
        assert post_json[0]["trace_id"] == "trace-push-001"

    async def test_headers_have_correct_shape(self, tmp_path):
        """The POST headers must include Authorization Bearer, apikey, and Prefer."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        _seed_trace(db_path, "trace-hdr-001", "2026-01-02T00:00:00.000000Z")

        url = "https://example.supabase.co"
        key = "my-secret-key"
        client, calls = _make_fake_client()

        await _sync_table(db, client, url, key, "traces", "created_at")

        assert len(calls) == 1
        _, _, headers = calls[0]
        assert headers["Authorization"] == f"Bearer {key}"
        assert headers["apikey"] == key
        assert headers["Prefer"] == "resolution=merge-duplicates"
        assert headers["Content-Type"] == "application/json"

    async def test_service_key_not_in_url(self, tmp_path):
        """The service key must never appear as a substring of the POST URL."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        _seed_trace(db_path, "trace-sec-001", "2026-01-03T00:00:00.000000Z")

        url = "https://example.supabase.co"
        key = "super-secret-service-key-12345"
        client, calls = _make_fake_client()

        await _sync_table(db, client, url, key, "traces", "created_at")

        assert len(calls) == 1
        post_url = calls[0][0]
        assert key not in post_url, (
            f"service key must never appear in the POST URL; found in: {post_url!r}"
        )


# ---------------------------------------------------------------------------
# Test: cursor advances after sync
# ---------------------------------------------------------------------------


class TestCursorAdvancesAfterSync:
    """After a successful _sync_table pass the cursor must advance."""

    async def test_cursor_advances_after_sync(self, tmp_path):
        """get_sync_cursor returns the composite (created_at|id) of the last row."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        # Seed two rows with different created_at values.
        _seed_trace(db_path, "trace-cur-001", "2026-01-01T10:00:00.000000Z")
        _seed_trace(db_path, "trace-cur-002", "2026-01-01T11:00:00.000000Z")

        url = "https://example.supabase.co"
        key = "fake-key"
        client, _ = _make_fake_client()

        await _sync_table(db, client, url, key, "traces", "created_at")

        # The cursor is now a composite "<timestamp>|<id>" keyset (Phase 65 CR-02).
        new_cursor = db.get_sync_cursor("traces")
        ts, sep, id_part = new_cursor.rpartition("|")
        assert sep == "|", f"cursor must be composite; got {new_cursor!r}"
        assert ts == "2026-01-01T11:00:00.000000Z", (
            f"cursor timestamp must advance to max created_at; got {ts!r}"
        )
        assert int(id_part) >= 1, "cursor id segment must be a positive surrogate id"

    async def test_cursor_unchanged_before_sync(self, tmp_path):
        """Before any sync the cursor must return the epoch default."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        cursor = db.get_sync_cursor("traces")
        assert cursor == "1970-01-01T00:00:00.000000Z"


# ---------------------------------------------------------------------------
# Test: no rows means no POST and no cursor change
# ---------------------------------------------------------------------------


class TestNoRowsNoPost:
    """When list_rows_after returns empty, no POST must be made."""

    async def test_no_rows_no_post(self, tmp_path):
        """Empty table: _sync_table must not call client.post."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        url = "https://example.supabase.co"
        key = "fake-key"
        client, calls = _make_fake_client()

        await _sync_table(db, client, url, key, "traces", "created_at")

        assert calls == [], "no POST must be made when there are no new rows"

    async def test_no_rows_cursor_unchanged(self, tmp_path):
        """Empty table: cursor must stay at the epoch default."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        url = "https://example.supabase.co"
        key = "fake-key"
        client, _ = _make_fake_client()

        await _sync_table(db, client, url, key, "traces", "created_at")

        cursor = db.get_sync_cursor("traces")
        assert cursor == "1970-01-01T00:00:00.000000Z", (
            "cursor must not change when there are no new rows"
        )


# ---------------------------------------------------------------------------
# Test: _sync_headers helper
# ---------------------------------------------------------------------------


class TestSyncHeadersShape:
    """_sync_headers must return the expected PostgREST header dict."""

    def test_headers_shape(self):
        """_sync_headers returns the four required PostgREST upsert headers."""
        key = "test-service-key"
        headers = _sync_headers(key)

        assert headers["Authorization"] == f"Bearer {key}"
        assert headers["apikey"] == key
        assert headers["Content-Type"] == "application/json"
        assert headers["Prefer"] == "resolution=merge-duplicates"

    def test_key_not_in_authorization_url_form(self):
        """The service key must appear only in header values, not in any URL string."""
        key = "my-private-key"
        headers = _sync_headers(key)

        for header_name, header_value in headers.items():
            # The key may appear as a value but never as part of a URL-like string
            if "key" in header_name.lower() or "auth" in header_name.lower():
                continue  # expected to carry the key
            if "http" in header_value:
                assert key not in header_value, (
                    f"key found in URL-like header {header_name!r}: {header_value!r}"
                )


# ---------------------------------------------------------------------------
# Test: POST payload never carries the local surrogate id (CR-01)
# ---------------------------------------------------------------------------


class TestPayloadHasNoLocalId:
    """The remote tables have no id column; the POST body must never include id."""

    async def test_traces_payload_has_no_id(self, tmp_path):
        """A traces sync POST body must not contain an 'id' key."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()
        _seed_trace(db_path, "trace-noid-001", "2026-02-01T00:00:00.000000Z")

        client, calls = _make_fake_client()
        await _sync_table(db, client, "https://example.supabase.co", "k", "traces", "created_at")

        assert len(calls) == 1
        _, post_json, _ = calls[0]
        assert all("id" not in row for row in post_json), (
            "traces POST payload must not include the local surrogate id"
        )

    async def test_agent_profiles_payload_has_no_id(self, tmp_path):
        """An agent_profiles sync POST body must not contain an 'id' key."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()
        _seed_agent_profile(db_path, "prof-noid", "2026-02-01T00:00:00.000000Z")

        client, calls = _make_fake_client()
        await _sync_table(
            db, client, "https://example.supabase.co", "k", "agent_profiles", "updated_at"
        )

        assert len(calls) == 1
        _, post_json, _ = calls[0]
        assert all("id" not in row for row in post_json), (
            "agent_profiles POST payload must not include the local surrogate id"
        )

    async def test_tasks_payload_has_no_id(self, tmp_path):
        """A tasks sync POST body must not contain an 'id' key."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()
        _seed_task(db_path, "task-noid", "2026-02-01T00:00:00.000000Z")

        client, calls = _make_fake_client()
        await _sync_table(db, client, "https://example.supabase.co", "k", "tasks", "updated_at")

        assert len(calls) == 1
        _, post_json, _ = calls[0]
        assert all("id" not in row for row in post_json), (
            "tasks POST payload must not include the local surrogate id"
        )

    async def test_natural_key_preserved_in_payload(self, tmp_path):
        """Stripping id must keep the natural key column the remote upsert needs."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()
        _seed_trace(db_path, "trace-keep-key", "2026-02-01T00:00:00.000000Z")

        client, calls = _make_fake_client()
        await _sync_table(db, client, "https://example.supabase.co", "k", "traces", "created_at")

        _, post_json, _ = calls[0]
        assert post_json[0]["trace_id"] == "trace-keep-key"


# ---------------------------------------------------------------------------
# Test: drain + lossless keyset pagination within a single tick (CR-02)
# ---------------------------------------------------------------------------


class TestDrainAndKeyset:
    """One tick must drain a backlog larger than one page without skipping ties."""

    async def test_one_tick_drains_backlog_with_boundary_ties(self, tmp_path):
        """>500 rows, including a block sharing one timestamp that straddles the
        500-row page boundary, must ALL sync in a single tick with none skipped."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        # Seed 700 traces. Rows 480..520 share one identical timestamp so the
        # tie block straddles the 500-row page boundary; the rest are unique.
        tie_ts = "2026-03-01T12:00:00.000000Z"
        conn = sqlite3.connect(str(db_path))
        total = 700
        for i in range(total):
            if 480 <= i <= 520:
                created_at = tie_ts
            else:
                created_at = f"2026-03-01T12:00:{i:02d}.{i:06d}Z"
            conn.execute(
                "INSERT INTO traces (trace_id, created_at, provider, model, prompt) "
                "VALUES (?, ?, 'anthropic', 'claude-3', 'hello')",
                (f"trace-{i:04d}", created_at),
            )
        conn.commit()
        conn.close()

        client, calls = _make_fake_client()
        await _sync_table(db, client, "https://example.supabase.co", "k", "traces", "created_at")

        # Multiple pages POSTed in one tick (700 rows / 500 per page = 2 pages).
        assert len(calls) >= 2, "a >500 backlog must drain across multiple pages per tick"

        # Every seeded trace_id must appear exactly once across all POST bodies.
        posted_ids = [row["trace_id"] for _, body, _ in calls for row in body]
        assert len(posted_ids) == total, f"all {total} rows must be pushed; got {len(posted_ids)}"
        assert set(posted_ids) == {f"trace-{i:04d}" for i in range(total)}, (
            "no row may be skipped, including boundary ties"
        )
        assert len(set(posted_ids)) == total, "no row may be sent twice within the tick"

    async def test_second_tick_after_drain_sends_nothing(self, tmp_path):
        """After a full drain, a second tick with no new rows must POST nothing."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()

        conn = sqlite3.connect(str(db_path))
        for i in range(600):
            conn.execute(
                "INSERT INTO traces (trace_id, created_at, provider, model, prompt) "
                "VALUES (?, ?, 'anthropic', 'claude-3', 'hello')",
                (f"t2-{i:04d}", f"2026-04-01T00:00:{i % 60:02d}.{i:06d}Z"),
            )
        conn.commit()
        conn.close()

        client, calls = _make_fake_client()
        await _sync_table(db, client, "https://example.supabase.co", "k", "traces", "created_at")
        first_tick_posts = len(calls)
        assert first_tick_posts >= 1

        await _sync_table(db, client, "https://example.supabase.co", "k", "traces", "created_at")
        assert len(calls) == first_tick_posts, (
            "a steady-state tick with no new rows must not re-send anything"
        )


# ---------------------------------------------------------------------------
# Test: sync_health push carries the synced_tables list (WR-04 / D2)
# ---------------------------------------------------------------------------


class TestSyncHealthCarriesSyncedTables:
    """_push_sync_health must encode the list of cleanly-synced tables."""

    async def test_synced_tables_json_encoded(self):
        """The sync_health row must carry synced_tables as a JSON-encoded string."""
        client, calls = _make_fake_client()
        await _push_sync_health(client, "https://example.supabase.co", "k", ["traces", "tasks"])

        assert len(calls) == 1
        url, body, _ = calls[0]
        assert url.endswith("/rest/v1/sync_health")
        assert json.loads(body[0]["synced_tables"]) == ["traces", "tasks"]

    async def test_synced_tables_defaults_to_empty(self):
        """Omitting synced_tables must serialize an empty JSON list, not null."""
        client, calls = _make_fake_client()
        await _push_sync_health(client, "https://example.supabase.co", "k")

        _, body, _ = calls[0]
        assert json.loads(body[0]["synced_tables"]) == []


# ---------------------------------------------------------------------------
# Helpers for driving a bounded number of _sync_loop ticks
# ---------------------------------------------------------------------------


class _FailingFakeClient:
    """Fake AsyncClient whose .post fails for URLs containing any fail-substring."""

    def __init__(self, fail_url_substrings: tuple[str, ...] = ()) -> None:
        self.fail_url_substrings = fail_url_substrings
        self.calls: list[tuple] = []

    async def __aenter__(self) -> _FailingFakeClient:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def post(self, url: str, *, json: object, headers: dict) -> FakeResponse:
        self.calls.append((url, json, headers))
        if any(sub in url for sub in self.fail_url_substrings):
            raise RuntimeError(f"simulated POST failure for {url}")
        return FakeResponse()


def _install_fake_httpx(client: _FailingFakeClient):
    """Install a fake httpx module exposing AsyncClient() -> client. Returns a restorer."""
    fake = MagicMock()
    fake.AsyncClient = MagicMock(return_value=client)
    old = sys.modules.get("httpx")
    sys.modules["httpx"] = fake  # type: ignore[assignment]

    def _restore() -> None:
        if old is None:
            sys.modules.pop("httpx", None)
        else:
            sys.modules["httpx"] = old

    return _restore


def _bounded_sleep(max_ticks: int):
    """Return an async sleep stub that raises CancelledError after max_ticks calls."""
    state = {"n": 0}

    async def _sleep(_secs: float) -> None:
        state["n"] += 1
        if state["n"] >= max_ticks:
            raise asyncio.CancelledError

    return _sleep


# ---------------------------------------------------------------------------
# Test: WR-04 - one table failing still pushes health and touches
# ---------------------------------------------------------------------------


class TestPerTableFailureDoesNotSuppressTick:
    """A single table's failure must not hide the health push or the touch."""

    async def test_failing_table_still_pushes_health_and_touch(self, tmp_path, monkeypatch):
        """When the tasks POST fails, sync_health is still pushed and touch() runs."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()
        # Seed one row per synced table so every table attempts a POST.
        _seed_trace(db_path, "tr-1", "2026-05-01T00:00:00.000000Z")
        _seed_agent_profile(db_path, "prof-1", "2026-05-01T00:00:00.000000Z")
        _seed_task(db_path, "task-1", "2026-05-01T00:00:00.000000Z")

        client = _FailingFakeClient(fail_url_substrings=("/rest/v1/tasks",))
        restore = _install_fake_httpx(client)
        monkeypatch.setattr(asyncio, "sleep", _bounded_sleep(1))
        try:
            adapter = SupabaseAdapter()
            ctx = _make_context(tmp_path)
            with contextlib_suppress_cancelled():
                await adapter._sync_loop("https://example.supabase.co", "k", ctx)
        finally:
            restore()

        posted_urls = [c[0] for c in client.calls]
        # traces and agent_profiles synced, tasks failed, but health STILL pushed.
        assert any(u.endswith("/rest/v1/sync_health") for u in posted_urls), (
            "sync_health must still be pushed even when one table fails (WR-04)"
        )
        # synced_tables reflects only the tables that synced cleanly.
        health_body = next(
            body for url, body, _ in client.calls if url.endswith("/rest/v1/sync_health")
        )
        synced = json.loads(health_body[0]["synced_tables"])
        assert "traces" in synced and "agent_profiles" in synced
        assert "tasks" not in synced, "a failed table must not appear in synced_tables"

        entry = ctx.registry.get("supabase")
        assert entry is not None
        assert entry.last_activity_at is not None, "touch() must run despite a table failure"
        assert entry.status == "error", "a tick with a failure must mark error"


# ---------------------------------------------------------------------------
# Test: WR-05 - error state clears after a subsequent clean tick
# ---------------------------------------------------------------------------


class TestErrorStateClearsOnRecovery:
    """After an errored tick, a fully-clean tick must clear the error state."""

    async def test_clean_tick_after_error_clears_status(self, tmp_path, monkeypatch):
        """Tick 1 fails on tasks, tick 2 is clean: status must return to running."""
        db_path = tmp_path / "t.db"
        db = Database(str(db_path))
        db.init()
        _seed_trace(db_path, "tr-r1", "2026-05-02T00:00:00.000000Z")
        _seed_task(db_path, "task-r1", "2026-05-02T00:00:00.000000Z")

        # Tick 1: tasks POST fails. Tick 2: nothing fails (cursor already advanced
        # for traces; tasks now succeeds and there are no new rows to fail on).
        class _FlakyClient(_FailingFakeClient):
            def __init__(self) -> None:
                super().__init__()
                self.tick = 0

            async def post(self, url: str, *, json: object, headers: dict) -> FakeResponse:
                self.calls.append((url, json, headers))
                # Fail the tasks POST only on the first time it is attempted.
                if "/rest/v1/tasks" in url and self.tick == 0:
                    raise RuntimeError("simulated first-tick tasks failure")
                return FakeResponse()

        client = _FlakyClient()

        # Advance the tick counter inside the bounded sleep so the second tick
        # sees self.tick == 1 and stops after two ticks.
        async def _sleep(_secs: float) -> None:
            client.tick += 1
            if client.tick >= 2:
                raise asyncio.CancelledError

        restore = _install_fake_httpx(client)
        monkeypatch.setattr(asyncio, "sleep", _sleep)
        try:
            adapter = SupabaseAdapter()
            ctx = _make_context(tmp_path)
            with contextlib_suppress_cancelled():
                await adapter._sync_loop("https://example.supabase.co", "k", ctx)
        finally:
            restore()

        entry = ctx.registry.get("supabase")
        assert entry is not None
        assert entry.error_count >= 1, "the first tick failure must have been recorded"
        assert entry.status == "running", (
            "a subsequent fully-clean tick must clear the error state (WR-05)"
        )


def contextlib_suppress_cancelled():
    """Tiny helper: suppress asyncio.CancelledError raised by the bounded sleep."""
    import contextlib

    return contextlib.suppress(asyncio.CancelledError)
