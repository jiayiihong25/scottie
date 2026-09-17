"""content_router — a conditional edge, not an agent.

Routes each assigned chunk to concept_agent or card_agent by its existing
content_type tag (set deterministically by ingest/classify.py). See
docs/orchestration-design.md — a content type with nothing due today
means that agent just doesn't fire; that's normal, not a bug.
"""

from __future__ import annotations

from ingest.models import CONCEPTUAL, MEMORIZATION, Chunk


def split_by_content_type(chunks: list[Chunk]) -> tuple[list[Chunk], list[Chunk]]:
    """Returns (conceptual_chunks, memorization_chunks)."""
    conceptual = [c for c in chunks if c.content_type == CONCEPTUAL]
    memorization = [c for c in chunks if c.content_type == MEMORIZATION]
    return conceptual, memorization
