"""Pipeline state threaded through every LangGraph node."""

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
    topic: str
    question: str
    answer: str
    source_ref: str


@dataclass
class AnkiCardDraft:
    chunk_id: str
    course: str
    topic: str
    front: str
    back: str
    source_ref: str


@dataclass
class ModelCallLog:
    content_type: str
    alias: str
    prompt_tokens: int
    completion_tokens: int


class PipelineState(TypedDict, total=False):
    # ingest_node
    content_index: ContentIndex
    ingest_errors: list[str]

    # pacing_agent
    exam_dates: dict[str, date]
    assigned_chunks: list[Chunk]
    pacing_notes: list[str]

    # generate_agent
    concept_questions: list[ConceptQuestion]
    anki_cards: list[AnkiCardDraft]

    # packet_writer
    packet_path: Path | None
    apkg_path: Path | None

    # cross-cutting
    errors: list[str]
    model_calls: list[ModelCallLog]
