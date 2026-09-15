"""Generate concept questions or Anki card drafts per assigned chunk.

Branches on content_type: conceptual → question, memorization → card.
Both empty lists are normal (partial participation).
"""

from __future__ import annotations

import json
import re

from ingest.models import CONCEPTUAL, MEMORIZATION
from graph.models import call_model
from graph.state import AnkiCardDraft, ConceptQuestion, ModelCallLog, PipelineState

CONCEPT_PROMPT = """You are helping a university student prepare for exams.
Given the following study material, write ONE clear concept-check question
that tests understanding (not just recall). Include a concise model answer.

Study material:
{text}

Course: {course}
Topic: {topic}
Source: {source_ref}

Respond in JSON: {{"question": "...", "answer": "..."}}"""

ANKI_PROMPT = """You are helping a university student create Anki flashcards.
Given the following study material, write ONE flashcard suitable for spaced
repetition. The front should be a specific, unambiguous prompt. The back
should be a concise, complete answer.

Study material:
{text}

Course: {course}
Topic: {topic}
Source: {source_ref}

Respond in JSON: {{"front": "...", "back": "..."}}"""


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group())
    raise ValueError(f"No JSON object found in model response: {text[:200]}")


def generate_agent(state: PipelineState) -> dict:
    assigned = state.get("assigned_chunks", [])
    questions: list[ConceptQuestion] = []
    cards: list[AnkiCardDraft] = []
    model_calls: list[ModelCallLog] = state.get("model_calls", [])
    errors: list[str] = list(state.get("errors", []))

    for chunk in assigned:
        source_ref = f"{chunk.source_file} {chunk.unit_range}"

        try:
            if chunk.content_type == CONCEPTUAL:
                prompt = CONCEPT_PROMPT.format(
                    text=chunk.text[:3000],
                    course=chunk.course,
                    topic=chunk.topic,
                    source_ref=source_ref,
                )
                resp_text, log = call_model(
                    CONCEPTUAL,
                    [{"role": "user", "content": prompt}],
                )
                model_calls.append(log)
                parsed = _parse_json_response(resp_text)
                questions.append(
                    ConceptQuestion(
                        chunk_id=chunk.chunk_id,
                        course=chunk.course,
                        topic=chunk.topic,
                        question=parsed["question"],
                        answer=parsed["answer"],
                        source_ref=source_ref,
                    )
                )

            elif chunk.content_type == MEMORIZATION:
                prompt = ANKI_PROMPT.format(
                    text=chunk.text[:3000],
                    course=chunk.course,
                    topic=chunk.topic,
                    source_ref=source_ref,
                )
                resp_text, log = call_model(
                    MEMORIZATION,
                    [{"role": "user", "content": prompt}],
                )
                model_calls.append(log)
                parsed = _parse_json_response(resp_text)
                cards.append(
                    AnkiCardDraft(
                        chunk_id=chunk.chunk_id,
                        course=chunk.course,
                        topic=chunk.topic,
                        front=parsed["front"],
                        back=parsed["back"],
                        source_ref=source_ref,
                    )
                )

        except Exception as exc:
            errors.append(
                f"generate_agent: chunk {chunk.chunk_id} "
                f"({chunk.course}/{chunk.topic}): {exc}"
            )

    return {
        "concept_questions": questions,
        "anki_cards": cards,
        "model_calls": model_calls,
        "errors": errors,
    }
