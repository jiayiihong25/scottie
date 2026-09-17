"""Shared LangGraph state schema.

See docs/orchestration-design.md ("State schema" + "Partial participation")
for the rationale. Every field a node might not populate defaults to an
empty list/None; downstream nodes must treat "empty" as normal, not an
error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TypedDict

from ingest.models import Chunk, ContentIndex


@dataclass
class ConceptQuestion:
    chunk_id: str
    course: str
    question: str
    model_alias: str


@dataclass
class AnkiCardDraft:
    chunk_id: str
    course: str
    front: str
    back: str
    model_alias: str


@dataclass
class ModelCallLog:
    task_type: str
    alias: str
    prompt_tokens: int
    completion_tokens: int


class PipelineState(TypedDict):
    # set by ingest_node
    content_index: ContentIndex
    ingest_errors: list[str]

    # set by pacing_agent
    exam_dates: dict[str, date]
    assigned_chunks: list[Chunk]
    pacing_notes: list[str]

    # set by concept_agent / card_agent — both optional, may be empty
    concept_questions: list[ConceptQuestion]
    anki_cards: list[AnkiCardDraft]

    # set by packet_writer
    packet_path: Path | None
    apkg_path: Path | None

    # cross-cutting
    errors: list[str]
    model_calls: list[ModelCallLog]


def new_state() -> PipelineState:
    return PipelineState(
        content_index=ContentIndex(),
        ingest_errors=[],
        exam_dates={},
        assigned_chunks=[],
        pacing_notes=[],
        concept_questions=[],
        anki_cards=[],
        packet_path=None,
        apkg_path=None,
        errors=[],
        model_calls=[],
    )
