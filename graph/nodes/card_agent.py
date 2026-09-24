"""card_agent — turns memorization chunks into Anki card drafts (front/back).

Calls the model through call_model() only — never a client directly, per
docs/orchestration-design.md.

Only chunks assigned for the first time (state["new_chunk_ids"]) get cards:
Anki runs its own review schedule once a card is imported, so re-sending
a card on every pacing review pass would only pile up duplicates. A card
is generated once and served from the generation cache after that (e.g.
a rerun the same day).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ingest.models import Chunk

from ..cache import cached_output, load_cache, save_cache, store_output
from ..models import call_model
from ..state import AnkiCardDraft, PipelineState
from .content_router import split_by_content_type

_PROMPT = """You are writing one Anki flashcard from the excerpt below. \
Pick the single most important fact, term, or definition worth memorizing. \
Reply with exactly two lines, no preamble:
FRONT: <question or term>
BACK: <answer or definition>

Course: {course}
Excerpt ({unit_range}):
{text}"""


def card_agent(
    state: PipelineState, cache_path: Path, today: date | None = None
) -> PipelineState:
    today = today or date.today()
    _, memorization = split_by_content_type(state["assigned_chunks"])
    new_ids = set(state["new_chunk_ids"])
    cache = load_cache(cache_path)
    cards: list[AnkiCardDraft] = []

    for chunk in memorization:
        if chunk.chunk_id not in new_ids:
            continue  # a review pass: Anki already has this card
        output = cached_output(cache, chunk, "card")
        if output is None:
            raw = call_model(
                "card_agent",
                [{"role": "user", "content": _format_prompt(chunk)}],
                state,
            )
            front, back = _parse_card(raw)
            output = {"front": front, "back": back}
            store_output(cache, chunk, "card", output, "card_agent", today)
            # Save per call: a later failure must not waste quota already spent.
            save_cache(cache_path, cache)
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


def _format_prompt(chunk: Chunk) -> str:
    return _PROMPT.format(course=chunk.course, unit_range=chunk.unit_range, text=chunk.text)


def _parse_card(raw: str) -> tuple[str, str]:
    front, back = "", ""
    for line in raw.strip().splitlines():
        if line.upper().startswith("FRONT:"):
            front = line.split(":", 1)[1].strip()
        elif line.upper().startswith("BACK:"):
            back = line.split(":", 1)[1].strip()
    if not front or not back:
        raise ValueError(f"card_agent got unparseable model output: {raw!r}")
    return front, back
