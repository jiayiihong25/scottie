"""PDF extraction via pdfplumber. One page -> one SourceUnit."""

from __future__ import annotations

import re
from pathlib import Path

from ..errors import EmptyExtractionError, ExtractionError
from ..models import Document, SourceUnit

# Page numbers, running headers and slide-handout footers add noise to every
# page; they inflate the memorization signal and waste question-generation
# context.
_PAGE_ARTIFACT = re.compile(
    r"^\s*(page\s+)?\d{1,4}\s*(/\s*\d{1,4})?\s*$", re.IGNORECASE
)


def _clean_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _PAGE_ARTIFACT.match(line):
            continue
        lines.append(line)
    return lines


def _looks_like_heading(line: str) -> bool:
    if not (3 <= len(line) <= 80):
        return False
    if line.endswith((".", ",", ";", ":")) and not line.endswith(":"):
        return False
    words = line.split()
    if len(words) > 12:
        return False
    # Title Case, ALL CAPS, or a numbered section heading.
    if re.match(r"^\d+(\.\d+)*[\).]?\s+\S", line):
        return True
    letters = [c for c in line if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return True
    capitalized = sum(1 for w in words if w[:1].isupper())
    return len(words) >= 2 and capitalized / len(words) >= 0.6


def extract(path: Path) -> Document:
    import pdfplumber  # imported lazily so notes-only runs need no PDF stack

    units: list[SourceUnit] = []
    try:
        with pdfplumber.open(path) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                lines = _clean_lines(page.extract_text() or "")
                if not lines:
                    continue
                heading = lines[0] if _looks_like_heading(lines[0]) else None
                units.append(
                    SourceUnit(
                        number=number,
                        text="\n".join(lines),
                        heading=heading,
                    )
                )
    except Exception as exc:  # pdfplumber raises a wide variety of types
        raise ExtractionError(f"could not read PDF {path}: {exc}") from exc

    if not units:
        raise EmptyExtractionError(
            f"{path} produced no text — it is probably a scanned/image-only "
            f"PDF and needs OCR before it can be ingested"
        )
    return Document(path=path, source_type="pdf", units=units, unit_kind="page")
