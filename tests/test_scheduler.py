"""Tests for the in-process cron scheduler (REMOTE-05).

These tests cover the behaviors Plan 02 implements: coalesce-to-one
catch-up, timezone resolution (HORUS_TZ override else OS local), the
in-flight overlap guard, the HORUS_OS_DISABLE_SCHEDULER opt-out gate, and
persisting next_run_at before the run to prevent double-firing.
"""

from __future__ import annotations

import asyncio
import zoneinfo
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.scheduler_adapter import (
    DISABLE_ENV,
    TZ_ENV,
    SchedulerAdapter,
    next_fire,
    plan_fire,
    resolve_tz,
)
from horus_os.agent import AgentResult
from horus_os.config import Config
from horus_os.storage import Database
from horus_os.types import AgentProfile


def _make_context(tmp_path: Path) -> AdapterContext:
    config = Config.load(tmp_path)
    db = Database(config.db_path)
    db.init()
    return AdapterContext(
        config=config,
        data_dir=tmp_path,
        registry=AdapterRegistry(),
        tool_registry=None,
    )


def test_disable_env_makes_start_a_noop(tmp_path, monkeypatch):
    """HORUS_OS_DISABLE_SCHEDULER=true makes start() a silent no-op (D-13)."""
    monkeypatch.setenv(DISABLE_ENV, "true")
    context = _make_context(tmp_path)
    adapter = SchedulerAdapter()

    asyncio.run(adapter.start(context))

    assert adapter._task is None
    # No entry was marked running by the disabled start().
    assert context.registry.get(adapter.name) is None


def test_coalesce_fires_once_after_missed_window():
    """max(croniter_next, now) fires exactly once after one or more missed slots (D-03)."""
    tz = zoneinfo.ZoneInfo("UTC")
    # A schedule that should have fired every minute, last scheduled hours ago.
    now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=tz)
    missed_base = now - timedelta(hours=3)

    fired = next_fire("* * * * *", missed_base)
    # The naive croniter next from missed_base would be 3 hours in the past;
    # coalesce clamps it to at least the base we pass.
    assert fired >= missed_base

    # When base is now, the next fire is strictly in the future (one slot ahead),
    # never a backlog of slots.
    nxt = next_fire("* * * * *", now)
    assert nxt > now
    assert nxt - now <= timedelta(minutes=1)


def test_timezone_uses_horus_tz_override_else_local(monkeypatch):
    """tz resolution prefers HORUS_TZ, falling back to the OS local timezone (D-05)."""
    monkeypatch.setenv(TZ_ENV, "America/New_York")
    assert resolve_tz() == zoneinfo.ZoneInfo("America/New_York")

    monkeypatch.delenv(TZ_ENV, raising=False)
    local = resolve_tz()
    # Local resolution returns the OS-detected tzinfo (never None, never network).
    assert local == datetime.now().astimezone().tzinfo


def test_overlap_guard_skips_in_flight_schedule(tmp_path, monkeypatch):
    """A schedule whose prior run is still in flight is skipped this tick."""
    monkeypatch.delenv(DISABLE_ENV, raising=False)
    monkeypatch.setenv(TZ_ENV, "UTC")
    context = _make_context(tmp_path)
    db = Database(context.config.db_path)
    # A schedule that is due (next_run_at far in the past).
    past = (datetime(2026, 6, 1, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))).isoformat()
    db.create_schedule(
        "watchdog",
        cron_expression="* * * * *",
        agent_profile_name="coordinator",
        prompt="check things",
        next_run_at=past,
    )
    sched = db.get_schedule("watchdog")

    adapter = SchedulerAdapter()
    adapter._running_ids.add(sched.id)

    # _dispatch must never be called while the id is in-flight.
    with patch.object(adapter, "_dispatch") as dispatch:
        adapter._tick(db, context)
        dispatch.assert_not_called()


def test_double_fire_guard_persists_next_run_before_run(tmp_path, monkeypatch):
    """next_run_at and last_run_at are persisted BEFORE the agent run (no double-fire)."""
    monkeypatch.delenv(DISABLE_ENV, raising=False)
    monkeypatch.setenv(TZ_ENV, "UTC")
    context = _make_context(tmp_path)
    db = Database(context.config.db_path)
    past = (datetime(2026, 6, 1, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))).isoformat()
    db.create_schedule(
        "daily-report",
        cron_expression="* * * * *",
        agent_profile_name="coordinator",
        prompt="write the report",
        next_run_at=past,
    )

    call_order: list[str] = []
    real_update = db.update_schedule_run

    def tracking_update(*args, **kwargs):
        call_order.append("persist")
        return real_update(*args, **kwargs)

    adapter = SchedulerAdapter()

    def fake_dispatch(database, sched, context_arg):
        call_order.append("dispatch")

    with (
        patch.object(db, "update_schedule_run", side_effect=tracking_update),
        patch.object(adapter, "_dispatch", side_effect=fake_dispatch),
    ):
        adapter._tick(db, context)

    assert call_order == ["persist", "dispatch"], call_order
    # next_run_at was advanced off the stale past value before any dispatch.
    refreshed = db.get_schedule("daily-report")
    assert refreshed.next_run_at != past
    assert refreshed.last_run_at is not None


def test_plan_fire_honors_each_catch_up_policy():
    """plan_fire applies coalesce / all / skip semantics, defaulting to coalesce (D-04)."""
    tz = zoneinfo.ZoneInfo("UTC")
    now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=tz)
    past = datetime(2026, 6, 1, 0, 0, 0, tzinfo=tz).isoformat()

    # coalesce: fire once, collapse the backlog to the next future slot.
    fire, nxt = plan_fire("coalesce", "* * * * *", past, now)
    assert fire is True
    assert nxt > now

    # all: fire and advance only one cron step from the missed base, so the new
    # next_run_at is still in the past and the next tick keeps backfilling.
    fire, nxt = plan_fire("all", "* * * * *", past, now)
    assert fire is True
    assert nxt < now

    # skip: a genuinely-late slot does not fire; it re-arms the next future slot.
    fire, nxt = plan_fire("skip", "* * * * *", past, now)
    assert fire is False
    assert nxt > now

    # unknown policy falls back to coalesce.
    fire, nxt = plan_fire("bogus", "* * * * *", past, now)
    assert fire is True
    assert nxt > now


def test_catch_up_policy_skip_does_not_fire_missed_slot(tmp_path, monkeypatch):
    """A skip-policy schedule never fires a missed slot; it only re-arms (WR-01, D-04)."""
    monkeypatch.delenv(DISABLE_ENV, raising=False)
    monkeypatch.setenv(TZ_ENV, "UTC")
    context = _make_context(tmp_path)
    db = Database(context.config.db_path)
    past = datetime(2026, 6, 1, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")).isoformat()
    db.create_schedule(
        "watcher",
        cron_expression="* * * * *",
        agent_profile_name="coordinator",
        prompt="check things",
        next_run_at=past,
        catch_up_policy="skip",
    )

    adapter = SchedulerAdapter()
    with patch.object(adapter, "_dispatch") as dispatch:
        adapter._tick(db, context)
        dispatch.assert_not_called()

    refreshed = db.get_schedule("watcher")
    assert refreshed.next_run_at != past  # re-armed to a future slot
    assert refreshed.last_run_at is None  # never fired


def test_catch_up_policy_all_backfills_one_slot_per_tick(tmp_path, monkeypatch):
    """An all-policy schedule fires and advances one cron step (backfill), not coalesced (WR-01)."""
    monkeypatch.delenv(DISABLE_ENV, raising=False)
    monkeypatch.setenv(TZ_ENV, "UTC")
    context = _make_context(tmp_path)
    db = Database(context.config.db_path)
    past = datetime(2026, 6, 1, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")).isoformat()
    db.create_schedule(
        "backfill",
        cron_expression="* * * * *",
        agent_profile_name="coordinator",
        prompt="catch up",
        next_run_at=past,
        catch_up_policy="all",
    )

    adapter = SchedulerAdapter()
    with patch.object(adapter, "_dispatch") as dispatch:
        adapter._tick(db, context)
        dispatch.assert_called_once()

    refreshed = db.get_schedule("backfill")
    # Advanced exactly one cron minute from the missed base, still in the past.
    assert refreshed.next_run_at == "2026-06-01T00:01:00+00:00"


def test_scheduler_uses_configured_provider(tmp_path, monkeypatch):
    """Scheduled runs use config.default_provider, not a hardcoded anthropic (WR-02)."""
    monkeypatch.setenv(TZ_ENV, "UTC")
    context = _make_context(tmp_path)
    context.config.default_provider = "gemini"
    db = Database(context.config.db_path)
    db.save_profile(AgentProfile(name="coordinator", system_prompt="coordinate"))
    db.create_schedule(
        "nightly",
        cron_expression="* * * * *",
        agent_profile_name="coordinator",
        prompt="do the thing",
        next_run_at=datetime(2026, 6, 1, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")).isoformat(),
    )
    sched = db.get_schedule("nightly")

    captured: dict[str, object] = {}

    def fake_run_agent_loop(prompt, **kwargs):
        captured.update(kwargs)
        return AgentResult(text="ok", tool_uses=[])

    adapter = SchedulerAdapter()
    with patch(
        "horus_os.adapters.scheduler_adapter.run_agent_loop",
        side_effect=fake_run_agent_loop,
    ):
        asyncio.run(adapter._dispatch_async(db, sched, context))

    assert captured["provider"] == "gemini"
    assert captured["model"] == context.config.gemini_model
