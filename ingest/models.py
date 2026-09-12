"""Normalized content model shared by every extractor.

Per-format extraction differs (pdfplumber vs. python-pptx vs. plain text),
but everything downstream — pacing, generation — only ever sees `SourceUnit`
and `Chunk`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

INDEX_SCHEMA_VERSION = 1

# Content-type tags. `generate/` routes on these: memorization-tagged chunks
# become Anki cards, conceptual ones become concept-check questions.
CONCEPTUAL = "conceptual"
MEMORIZATION = "memorization"


@dataclass(frozen=True)
class SourceUnit:
    """One addressable piece of a source file: a PDF page, a slide, or a
    heading-delimited section of a notes file.

    `number` is 1-based and is what a page/slide range in the morning packet
    refers to, so it must stay faithful to the original document.
    """

    number: int
    text: str
    heading: str | None = None

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class Document:
    """A single extracted source file."""

    path: Path
    source_type: str  # "pdf" | "slides" | "notes"
    units: list[SourceUnit]
    unit_kind: str  # "page" | "slide" | "section"


@dataclass
class Chunk:
    """A contiguous run of source units, sized for one sitting of study.

    Chunks never straddle two source files and never split a single unit, so
    the page/slide range printed in the morning packet is always something the
    user can physically open.
    """

    chunk_id: str
    course: str
    topic: str
    source_file: str
    source_type: str
    unit_kind: str
    unit_start: int
    unit_end: int
    text: str
    content_type: str
    content_type_score: float
    word_count: int
    order: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def unit_range(self) -> str:
        """Human-readable range for the morning packet, e.g. "pages 4-7"."""
        if self.unit_start == self.unit_end:
            return f"{self.unit_kind} {self.unit_start}"
        return f"{self.unit_kind}s {self.unit_start}-{self.unit_end}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["unit_range"] = self.unit_range
        return data


def make_chunk_id(source_file: str, unit_start: int, unit_end: int) -> str:
    """Stable id derived from location, not content.

    Pacing state (what's been seen, what's due for review) is keyed by chunk
    id, so re-ingesting after a typo fix in the source must not orphan a
    chunk's review history.
    """
    digest = hashlib.sha1(
        f"{source_file}:{unit_start}:{unit_end}".encode()
    ).hexdigest()
    return digest[:12]


@dataclass
class ContentIndex:
    """The full normalized index — the handoff to `pacing/`."""

    chunks: list[Chunk] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def courses(self) -> list[str]:
        return sorted({c.course for c in self.chunks})

    def for_course(self, course: str) -> list[Chunk]:
        return [c for c in self.chunks if c.course == course]

    def to_dict(self) -> dict:
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "chunks": [c.to_dict() for c in self.chunks],
            "errors": list(self.errors),
        }

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: Path) -> ContentIndex:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        version = data.get("schema_version")
        if version != INDEX_SCHEMA_VERSION:
            raise ValueError(
                f"content index at {path} has schema_version {version!r}, "
                f"expected {INDEX_SCHEMA_VERSION} — re-run ingestion"
            )
        chunks = []
        for raw in data["chunks"]:
            raw = {k: v for k, v in raw.items() if k != "unit_range"}
            chunks.append(Chunk(**raw))
        return cls(chunks=chunks, errors=list(data.get("errors", [])))
