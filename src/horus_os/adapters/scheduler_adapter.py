"""In-process cron scheduler adapter (Phase 66, REMOTE-05).

A ``SchedulerAdapter`` that runs on the FastAPI lifespan, reads the
``schedules`` table on a fixed tick, and fires due agent routines with
``max(croniter_next, now)`` coalesce math so a single missed window fires
exactly once on wake-up rather than once per missed slot (D-03).

The scheduler is core-on-by-default (the inverse of the supabase opt-in
gate): it starts unless ``HORUS_OS_DISABLE_SCHEDULER`` is set to ``true``,
in which case ``start()`` is a silent no-op and the local runtime starts
cleanly with a passing health check (D-13).

Cron is evaluated in the machine's auto-detected local timezone via stdlib
``zoneinfo``, with a ``HORUS_TZ`` override (D-05). No location-aware or
phone-derived timezone is used (D-06). The adapter binds no HTTP route
(D-07, CLI-only management): ``bind()`` returns None.

next_run_at and last_run_at are persisted BEFORE the agent run so a mid-run
process restart never double-fires a schedule.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
import zoneinfo
from datetime import datetime, timedelta, tzinfo
from typing import Any

from croniter import croniter

from horus_os.adapters.base import AdapterContext
from horus_os.agent import AgentResult, run_agent_loop
from horus_os.storage import Database, ScheduleRecord

DISABLE_ENV = "HORUS_OS_DISABLE_SCHEDULER"
TZ_ENV = "HORUS_TZ"
TICK_SECS = 30


def resolve_tz() -> tzinfo:
    """Resolve the timezone cron is evaluated in (D-05).

    Prefers the ``HORUS_TZ`` override when set, otherwise falls back to the
    OS-detected local timezone via the stdlib. No network lookup and no
    location-aware resolution (D-06).
    """
    override = os.environ.get(TZ_ENV)
    if override:
        return zoneinfo.ZoneInfo(override)
    local = datetime.now().astimezone().tzinfo
    if local is None:  # pragma: no cover - astimezone always sets tzinfo
        return zoneinfo.ZoneInfo("UTC")
    return local


def next_fire(cron_expr: str, base: datetime) -> datetime:
    """Return the next fire time, coalesced so it is never in the past.

    ``max(croniter_next, base)`` collapses any backlog of missed slots into a
    single next fire so a long downtime fires exactly once on wake-up (D-03).
    croniter preserves the tzinfo of the (tz-aware) base datetime.
    """
    candidate = croniter(cron_expr, base).get_next(datetime)
    return max(candidate, base)


def _as_aware(next_run_at: str | None, now: datetime) -> datetime | None:
    """Parse an ISO next_run_at, attaching now's tzinfo when the stored value is naive."""
    if next_run_at is None:
        return None
    parsed = datetime.fromisoformat(next_run_at)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now.tzinfo)
    return parsed


def _parse_due(next_run_at: str | None, now: datetime) -> bool:
    """Return True when a schedule is due (never fired, or its next run has passed).

    The stored next_run_at is an ISO-8601 string. A schedule fires on ``<=``
    so a slot landing exactly on the tick boundary is not skipped.
    """
    parsed = _as_aware(next_run_at, now)
    if parsed is None:
        return True
    return parsed <= now


def plan_fire(
    policy: str, cron_expr: str, next_run_at: str | None, now: datetime
) -> tuple[bool, datetime]:
    """Decide whether a due schedule fires now, and its new next_run_at, per policy (D-04).

    The catch_up_policy column lets a schedule override the default behavior:

    * ``coalesce`` (default): fire exactly once and collapse any backlog of
      missed slots into the next future slot via ``max(croniter_next, now)``
      (D-03). One downtime fires once, never a flood.
    * ``all``: backfill one missed slot per tick. Fire now and advance by a
      single cron step from the slot just serviced, so any remaining missed
      slots fire on subsequent ticks until next_run_at catches up to now.
    * ``skip``: never fire a missed slot. A genuinely-late slot (older than one
      tick window) or a first-ever arming is skipped and re-armed to the next
      future slot; an on-time slot still fires.
    """
    due = _as_aware(next_run_at, now)
    if policy == "all":
        base = due or now
        return True, croniter(cron_expr, base).get_next(datetime)
    if policy == "skip":
        if due is None or due < now - timedelta(seconds=TICK_SECS):
            return False, next_fire(cron_expr, now)
        return True, next_fire(cron_expr, now)
    # coalesce (default), and any unrecognized value falls back to it.
    return True, next_fire(cron_expr, now)


class SchedulerAdapter:
    """Background adapter that fires due schedules on a fixed tick.

    With ``HORUS_OS_DISABLE_SCHEDULER=true`` set, ``start()`` returns
    immediately without launching a task or touching the adapter registry
    (D-13). Otherwise it launches a non-blocking asyncio task that ticks every
    ``TICK_SECS`` seconds, firing any due schedule's agent profile + prompt and
    recording a normal trace.
    """

    name = "scheduler"

    def __init__(self) -> None:
        self._task: asyncio.Task[Any] | None = None
        self._running_ids: set[int] = set()
        self._dispatch_tasks: set[asyncio.Task[Any]] = set()

    def bind(self, app: Any, context: AdapterContext) -> None:
        """No HTTP routes; schedules are managed via the CLI only (D-07)."""
        return None

    async def start(self, context: AdapterContext) -> None:
        """Launch the scheduler tick loop unless disabled.

        Guard 1 (D-13): ``HORUS_OS_DISABLE_SCHEDULER=true`` is a silent no-op so
        the local runtime starts cleanly with a passing health check. No task,
        no mark_running, no mark_error.
        """
        if os.environ.get(DISABLE_ENV, "").lower() == "true":
            return
        self._task = asyncio.create_task(self._scheduler_loop(context))
        context.registry.mark_running(self.name)

    async def stop(self) -> None:
        """Cancel the tick loop without raising.

        Suppress only asyncio.CancelledError (raised by the awaited cancel) and
        incidental task Exceptions. Interpreter-control signals are NOT
        suppressed so they still propagate during shutdown (mirrors
        supabase_adapter, Phase 65 WR-01).
        """
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task

    async def _scheduler_loop(self, context: AdapterContext) -> None:
        """Tick every TICK_SECS, firing any due schedule.

        One bad schedule never kills the loop: per-tick work is wrapped so any
        Exception is reported via mark_error but the loop continues.
        asyncio.CancelledError is re-raised so stop() works correctly.
        """
        db = Database(context.config.db_path)
        while True:
            try:
                context.registry.touch(self.name)
                self._tick(db, context)
                context.registry.mark_running(self.name)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                context.registry.mark_error(self.name, f"{type(exc).__name__}: {exc}")
            await asyncio.sleep(TICK_SECS)

    def _tick(self, db: Database, context: AdapterContext) -> None:
        """Evaluate every enabled schedule once and fire those that are due.

        For each due schedule:
        1. Skip it if a prior run is still in flight (overlap guard, T-66-03).
        2. Apply its catch_up_policy to decide whether to fire and the next slot (D-04).
        3. PERSIST last_run_at + next_run_at BEFORE dispatch so a mid-run restart
           does not double-fire (Pitfall 6).
        4. Dispatch the run (the dispatch coroutine tracks _running_ids), or, for a
           skipped missed slot, only advance next_run_at without firing.
        """
        tz = resolve_tz()
        now = datetime.now(tz)
        for sched in db.list_enabled_schedules():
            if sched.id in self._running_ids:
                continue  # overlap guard: prior run still in flight (T-66-03)
            if not _parse_due(sched.next_run_at, now):
                continue
            should_fire, new_next = plan_fire(
                sched.catch_up_policy or "coalesce",
                sched.cron_expression,
                sched.next_run_at,
                now,
            )
            if should_fire:
                # Persist run state BEFORE dispatch (double-fire guard, Pitfall 6).
                db.update_schedule_run(
                    sched.name,
                    last_run_at=now.isoformat(),
                    next_run_at=new_next.isoformat(),
                    last_trace_id=None,
                )
                self._dispatch(db, sched, context)
            else:
                # skip policy on a missed slot: re-arm the next future slot only,
                # leaving last_run_at and last_trace_id untouched (no fire happened).
                db.update_schedule(sched.name, next_run_at=new_next.isoformat())

    def _dispatch(self, db: Database, sched: ScheduleRecord, context: AdapterContext) -> None:
        """Schedule the async dispatch coroutine on the running loop.

        Factored from _tick so the per-tick decision logic is testable in
        isolation (the tests patch _dispatch to assert overlap/ordering without
        running an agent).

        A strong reference to the spawned task is held in _dispatch_tasks until
        it completes so the event loop never garbage-collects a running
        dispatch mid-flight.
        """
        task = asyncio.create_task(self._dispatch_async(db, sched, context))
        self._dispatch_tasks.add(task)
        task.add_done_callback(self._dispatch_tasks.discard)

    async def _dispatch_async(
        self, db: Database, sched: ScheduleRecord, context: AdapterContext
    ) -> None:
        """Run a due schedule's agent profile + prompt and record a trace.

        The schedule id is added to _running_ids before the run and discarded
        in a finally so the overlap guard releases even on failure. The
        synchronous, potentially slow run_agent_loop is offloaded with
        asyncio.to_thread so the tick loop is never blocked (Pitfall 4).
        """
        self._running_ids.add(sched.id)
        try:
            profile = db.load_profile(sched.agent_profile_name)
            if profile is None:
                context.registry.mark_error(
                    self.name,
                    f"schedule {sched.name!r}: no agent profile {sched.agent_profile_name!r}",
                )
                return
            registry = context.tool_registry or _build_default_registry(context.config)
            # Resolve provider + model from config the same way the interactive
            # run path does, so a Gemini-configured runtime's scheduled routines
            # use Gemini instead of silently defaulting to Anthropic (WR-02).
            provider = context.config.default_provider
            model = profile.default_model or _model_for(context.config, provider)
            start = time.perf_counter()
            try:
                result = await asyncio.to_thread(
                    run_agent_loop,
                    sched.prompt,
                    registry=registry,
                    provider=provider,
                    model=model,
                    system_prompt=profile.system_prompt,
                )
                latency_ms = int((time.perf_counter() - start) * 1000)
                trace_id = db.record_trace(
                    sched.prompt,
                    result,
                    latency_ms=latency_ms,
                    agent_profile_name=sched.agent_profile_name,
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - start) * 1000)
                trace_id = db.record_trace(
                    sched.prompt,
                    AgentResult(text="", tool_uses=[]),
                    latency_ms=latency_ms,
                    status="error",
                    error_message=f"{type(exc).__name__}: {exc}",
                    agent_profile_name=sched.agent_profile_name,
                )
                context.registry.mark_error(
                    self.name, f"schedule {sched.name!r}: {type(exc).__name__}: {exc}"
                )
            # Write the trace id back so the schedule row links its last run,
            # preserving the last_run_at / next_run_at already persisted by the
            # pre-dispatch double-fire guard.
            current = db.get_schedule(sched.name)
            if current is not None:
                db.update_schedule_run(
                    sched.name,
                    last_run_at=current.last_run_at,
                    next_run_at=current.next_run_at,
                    last_trace_id=trace_id,
                )
        finally:
            self._running_ids.discard(sched.id)


def _model_for(config: Any, provider: str) -> str:
    """Return the configured model for a provider (mirrors run_cmd._model_for)."""
    if provider == "anthropic":
        return config.anthropic_model
    return config.gemini_model


def _build_default_registry(config: Any) -> Any:
    """Build the default tool registry when AdapterContext.tool_registry is None.

    Lazily imports the run_cmd builder + NotesStore so this module stays light
    and import-safe (RESEARCH OQ 2: scheduler falls back to a fresh default
    registry when the context did not supply one).
    """
    from horus_os.cli.run_cmd import _build_default_registry as build_registry
    from horus_os.memory import NotesStore

    notes_store = NotesStore(config.notes_dir)
    return build_registry(config, notes_store)
