"""concept_agent — turns conceptual chunks into concept-check questions.

Calls the model through call_model() only — never a client directly, per
docs/orchestration-design.md. A chunk's question is generated once and
served from the generation cache on every review pass after that.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ingest.models import Chunk

from ..cache import cached_output, load_cache, save_cache, store_output
from ..models import call_model
from ..state import ConceptQuestion, PipelineState
from .content_router import split_by_content_type

_PROMPT = """You are writing one concept-check question for a student studying \
for an exam. Base it only on the excerpt below. The question should test \
understanding, not rote recall — ask "why" or "how", not "what is the \
definition of X". Reply with just the question, no preamble.

Course: {course}
Excerpt ({unit_range}):
{text}"""


def concept_agent(
    state: PipelineState, cache_path: Path, today: date | None = None
) -> PipelineState:
    today = today or date.today()
    conceptual, _ = split_by_content_type(state["assigned_chunks"])
    cache = load_cache(cache_path)
    questions: list[ConceptQuestion] = []

    for chunk in conceptual:
        output = cached_output(cache, chunk, "concept")
        if output is None:
            question_text = call_model(
                "concept_agent",
                [{"role": "user", "content": _format_prompt(chunk)}],
                state,
            )
            output = {"question": question_text.strip()}
            store_output(cache, chunk, "concept", output, "concept_agent", today)
            # Save per call: a later failure must not waste quota already spent.
            save_cache(cache_path, cache)
        questions.append(
            ConceptQuestion(
                chunk_id=chunk.chunk_id,
                course=chunk.course,
                question=output["question"],
                model_alias="concept_agent",
            )
        )

    state["concept_questions"] = questions
    return state


def _format_prompt(chunk: Chunk) -> str:
    return _PROMPT.format(course=chunk.course, unit_range=chunk.unit_range, text=chunk.text)
