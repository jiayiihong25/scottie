"""card_agent — turns memorization chunks into Anki card drafts (front/back).

Calls the model through call_model() only — never a client directly, per
docs/orchestration-design.md.
"""

from __future__ import annotations

from ingest.models import Chunk

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


def card_agent(state: PipelineState) -> PipelineState:
    _, memorization = split_by_content_type(state["assigned_chunks"])
    cards: list[AnkiCardDraft] = []

    for chunk in memorization:
        raw = call_model(
            "card_agent",
            [{"role": "user", "content": _format_prompt(chunk)}],
            state,
        )
        front, back = _parse_card(raw)
        cards.append(
            AnkiCardDraft(
                chunk_id=chunk.chunk_id,
                course=chunk.course,
                front=front,
                back=back,
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
