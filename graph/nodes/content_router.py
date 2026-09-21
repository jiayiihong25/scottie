"""content_router — a plain helper, not a LangGraph edge or an agent.

Splits assigned chunks by their existing content_type tag (set
deterministically by ingest/classify.py). concept_agent and card_agent each
call it and take their own half; a type with nothing due today yields an
empty list and that agent does no work — normal, not a bug. See
docs/orchestration-design.md ("Graph structure") for why this is a chain
rather than a conditional edge.
"""

from __future__ import annotations

from ingest.models import CONCEPTUAL, MEMORIZATION, Chunk


def split_by_content_type(chunks: list[Chunk]) -> tuple[list[Chunk], list[Chunk]]:
    """Returns (conceptual_chunks, memorization_chunks)."""
    conceptual = [c for c in chunks if c.content_type == CONCEPTUAL]
    memorization = [c for c in chunks if c.content_type == MEMORIZATION]
    return conceptual, memorization
