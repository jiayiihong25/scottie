"""card_agent — turns memorization chunks into Anki card drafts (front/back).

Calls the model through call_model() only (via batching.generate_batch),
never a client directly, per docs/orchestration-design.md.

Only chunks assigned for the first time (state["new_chunk_ids"]) get cards:
Anki runs its own review schedule once a card is imported, so re-sending
a card on every pacing review pass would only pile up duplicates. A card
is generated once and served from the generation cache after that (e.g.
a rerun the same day). Misses are batched per source file.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..cache import cached_output, load_cache
from ..state import AnkiCardDraft, PipelineState
from .batching import GenerationSpec, fill_cache
from .content_router import split_by_content_type

_INSTRUCTIONS = """You are writing Anki flashcards. For each excerpt, pick \
the single most important fact, term, or definition worth memorizing. \
"front" is the question or term; "back" is the answer or definition."""

CARD_SPEC = GenerationSpec("card_agent", "card", _INSTRUCTIONS, ("front", "back"))


def card_agent(
    state: PipelineState, cache_path: Path, today: date | None = None
) -> PipelineState:
    today = today or date.today()
    _, memorization = split_by_content_type(state["assigned_chunks"])
    new_ids = set(state["new_chunk_ids"])
    # Review passes are skipped: Anki already has those cards.
    new_memorization = [c for c in memorization if c.chunk_id in new_ids]
    cache = load_cache(cache_path)

    _, upcoming = split_by_content_type(state["lookahead_chunks"])
    fill_cache(CARD_SPEC, new_memorization, cache, cache_path, state, today, pool=upcoming)

    cards = []
    for chunk in new_memorization:
        output = cached_output(cache, chunk, "card")
        cards.append(
            AnkiCardDraft(
                chunk_id=chunk.chunk_id,
                course=chunk.course,
                front=output["front"],
                back=output["back"],
                model_alias="card_agent",
            )
        )
    state["anki_cards"] = cards
    return state
