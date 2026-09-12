"""Per-format extractors.

Each extractor exposes `extract(path: Path) -> Document` and does nothing
else — chunking and classification are format-agnostic and live in
`ingest.chunk` / `ingest.classify`.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import UnsupportedFormatError
from ..models import Document
from . import notes, pdf, slides

_BY_EXTENSION = {
    ".pdf": pdf.extract,
    ".pptx": slides.extract,
    ".ppt": slides.extract,
    ".txt": notes.extract,
    ".md": notes.extract,
}


def extract(path: Path) -> Document:
    path = Path(path)
    extractor = _BY_EXTENSION.get(path.suffix.lower())
    if extractor is None:
        raise UnsupportedFormatError(
            f"no extractor registered for {path.suffix!r} ({path})"
        )
    return extractor(path)


def supported_extensions() -> set[str]:
    return set(_BY_EXTENSION)


__all__ = ["extract", "supported_extensions", "Document"]
