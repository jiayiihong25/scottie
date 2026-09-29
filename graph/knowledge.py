"""knowledge.json: all ingested course material, for daybook's Ask panel.

Deterministic, no LLM. The content index as plain passages (one per chunk,
whitespace collapsed) so the Daybook page can search them in the browser and
hand the relevant ones to Claude when you ask a question. The schema is
owned by scottie-display: scottie-display/docs/scottie-contract.md
("knowledge.json").
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ingest.models import ContentIndex
from ingest.pipeline import GENERAL_TOPIC

KNOWLEDGE_NAME = "knowledge.json"
KNOWLEDGE_SCHEMA_VERSION = 1


def knowledge(index: ContentIndex, today: date) -> dict:
    chunks = sorted(index.chunks, key=lambda c: (c.course, c.order))
    return {
        "schema_version": KNOWLEDGE_SCHEMA_VERSION,
        "date": today.isoformat(),
        "passages": [
            {
                "id": c.chunk_id,
                "course": c.course,
                # Same title rule as packet.json's reading list.
                "topic": Path(c.source_file).stem if c.topic == GENERAL_TOPIC else c.topic,
                "source_file": Path(c.source_file).name,
                "unit_range": c.unit_range,
                "text": " ".join(c.text.split()),
            }
            for c in chunks
            if c.text.strip()
        ],
    }


def write_knowledge(index: ContentIndex, output_dir: Path, today: date) -> Path:
    path = Path(output_dir) / KNOWLEDGE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    # Compact: this file is embedded in the Daybook page as-is.
    path.write_text(
        json.dumps(knowledge(index, today), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return path
