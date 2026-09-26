"""concept_agent — turns conceptual chunks into concept-check questions.

Calls the model through call_model() only (via batching.generate_batch),
never a client directly, per docs/orchestration-design.md. A chunk's
question is generated once and served from the generation cache on every
review pass after that. Misses are batched per source file, one request
per batch.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..cache import cached_output, load_cache
from ..state import ConceptQuestion, PipelineState
from .batching import GenerationSpec, fill_cache
from .content_router import split_by_content_type

_INSTRUCTIONS = """You are writing concept-check questions for a student \
studying for an exam. For each excerpt, write one question that tests \
understanding, not rote recall. Ask "why" or "how", not "what is the \
definition of X"."""

CONCEPT_SPEC = GenerationSpec("concept_agent", "concept", _INSTRUCTIONS, ("question",))


def concept_agent(
    state: PipelineState, cache_path: Path, today: date | None = None
) -> PipelineState:
    today = today or date.today()
    conceptual, _ = split_by_content_type(state["assigned_chunks"])
    cache = load_cache(cache_path)

    upcoming, _ = split_by_content_type(state["lookahead_chunks"])
    fill_cache(CONCEPT_SPEC, conceptual, cache, cache_path, state, today, pool=upcoming)

    state["concept_questions"] = [
        ConceptQuestion(
            chunk_id=chunk.chunk_id,
            course=chunk.course,
            question=cached_output(cache, chunk, "concept")["question"],
            model_alias="concept_agent",
        )
        for chunk in conceptual
    ]
    return state
