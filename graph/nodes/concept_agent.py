"""concept_agent — turns conceptual chunks into concept-check questions.

Calls the model through call_model() only — never a client directly, per
docs/orchestration-design.md.
"""

from __future__ import annotations

from ingest.models import Chunk

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


def concept_agent(state: PipelineState) -> PipelineState:
    conceptual, _ = split_by_content_type(state["assigned_chunks"])
    questions: list[ConceptQuestion] = []

    for chunk in conceptual:
        question_text = call_model(
            "concept_agent",
            [{"role": "user", "content": _format_prompt(chunk)}],
            state,
        )
        questions.append(
            ConceptQuestion(
                chunk_id=chunk.chunk_id,
                course=chunk.course,
                question=question_text.strip(),
                model_alias="concept_agent",
            )
        )

    state["concept_questions"] = questions
    return state


def _format_prompt(chunk: Chunk) -> str:
    return _PROMPT.format(course=chunk.course, unit_range=chunk.unit_range, text=chunk.text)
