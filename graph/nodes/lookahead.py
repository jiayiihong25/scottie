"""lookahead — spends leftover request budget pre-generating future chunks.

Runs after concept_agent / card_agent. Whatever's left of today's
request budget goes on material pacing hasn't introduced yet
(state["lookahead_chunks"], nearest exam first). The output lands in the
generation cache only, not in today's packet, so a later heavy day costs
nothing. Cards are pre-generated too: every lookahead chunk is new when
it's introduced, so it will need one. Without a budget there's no
"leftover", so this does nothing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..cache import load_cache
from ..state import PipelineState
from .batching import fill_cache
from .card_agent import CARD_SPEC
from .concept_agent import CONCEPT_SPEC
from .content_router import split_by_content_type


def lookahead(
    state: PipelineState,
    cache_path: Path,
    request_budget: int | None,
    today: date | None = None,
) -> PipelineState:
    if request_budget is None:
        return state
    today = today or date.today()
    leftover = request_budget - len(state["model_calls"])
    if leftover <= 0 or not state["lookahead_chunks"]:
        return state

    cache = load_cache(cache_path)
    conceptual, memorization = split_by_content_type(state["lookahead_chunks"])
    made = fill_cache(CONCEPT_SPEC, conceptual, cache, cache_path, state, today, leftover)
    made += fill_cache(CARD_SPEC, memorization, cache, cache_path, state, today, leftover - made)
    if made:
        state["pacing_notes"].append(
            f"lookahead: pre-generated {made} batches of upcoming material "
            f"with leftover request budget"
        )
    return state
