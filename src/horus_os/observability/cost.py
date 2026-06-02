"""CostAnnotator: mutate LLMCallEvent.cost_usd from token counts.

Subscriber for the ObservationBus. Sits BEFORE SQLitePersister in the
dispatch chain (subscribe order is dispatch order) so the persister
reads the populated `cost_usd` and `pricing_missing` fields and writes
them to the `llm_calls` row.

NULL is honest; zero or a partial number is a lie (Pitfall 5). When the
model is not in the pricing table the annotator sets `cost_usd = None`
(literal None, never 0 or 0.0) and `pricing_missing = True`. The
persister then writes NULL to the cost_usd column; the all-or-nothing
aggregate in `_rollup_trace` forces `traces.total_cost_usd` to NULL for
the whole trace, which the dashboard surfaces as "pricing unknown"
rather than misreporting a partial total.

Cache-aware math: Anthropic prompt-caching produces four distinct token
counters (input, output, cache_creation, cache_read) each priced at its
own per-million rate. Treating them as one or skipping cache_*
counters undercounts cost (PITFALLS.md Pitfall 5 cache-handling notes).

Local-provider contract (PITFALLS.md LP-2): a provider == "local" call is
genuinely free, so it is annotated with cost_usd = 0.0 (a real float zero,
not NULL, not pricing_missing) before the pricing-table lookup. This keeps
an unrecognized local model name out of the Pitfall 5 None path so the
dashboard renders "local (free)" rather than "pricing unknown".
"""

from __future__ import annotations

from horus_os.observability.bus import LLMCallEvent, ObservationEvent
from horus_os.observability.pricing import PricingTable


class CostAnnotator:
    """Subscribe to an ObservationBus to populate cost_usd on each LLM call.

    Holds a PricingTable resolved at construction time (bundled or user
    override path). Mutation is in-place on the event so the next
    subscriber in the dispatch chain (SQLitePersister) sees the populated
    fields and writes them to SQLite.
    """

    def __init__(self, pricing_table: PricingTable) -> None:
        self._table = pricing_table

    def on_event(self, event: ObservationEvent) -> None:
        """Annotate one LLMCallEvent in place; ignore other event kinds.

        Pitfall 5 enforcement: unknown models get cost_usd = None
        (literal None, never 0 or 0.0) and pricing_missing = True.
        """
        if not isinstance(event, LLMCallEvent):
            return
        if event.provider == "local":
            # PITFALLS.md LP-2: a local run is genuinely free. Emit a real
            # zero (LLM-04 distinguishes 0.0 from NULL) and never flag it
            # pricing_missing, so an unrecognized local model name (e.g.
            # "llama3.1:8b") never falls into the Pitfall 5 None path and
            # the dashboard renders "local (free)" not "pricing unknown".
            event.cost_usd = 0.0
            event.pricing_missing = False
            return
        pricing = self._table.get(event.model)
        if pricing is None:
            event.cost_usd = None
            event.pricing_missing = True
            return
        raw = (
            event.input_tokens * pricing.input_per_million
            + event.output_tokens * pricing.output_per_million
            + event.cache_creation_input_tokens * pricing.cache_write_per_million
            + event.cache_read_input_tokens * pricing.cache_read_per_million
        ) / 1_000_000
        event.cost_usd = round(raw, 6)
        event.pricing_missing = False


__all__ = ["CostAnnotator"]
