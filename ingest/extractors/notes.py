"""Plain-text / Markdown notes extraction.

Notes files have no fixed page/slide grid, so a SourceUnit here is a
heading-delimited section instead. A file with no headings at all becomes
one section covering the whole document.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..errors import EmptyExtractionError, ExtractionError
from ..models import Document, SourceUnit

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# Bare all-caps or Title Case line acting as a heading in plain .txt notes.
_TXT_HEADING = re.compile(r"^[A-Z][A-Za-z0-9 ,'/&-]{2,79}:?$")


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    lines = text.splitlines()
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush():
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_heading, body))

    for line in lines:
        md_match = _MD_HEADING.match(line)
        is_txt_heading = (
            md_match is None
            and _TXT_HEADING.match(line.strip())
            and len(line.strip().split()) <= 8
        )
        if md_match or is_txt_heading:
            flush()
            current_heading = (md_match.group(2) if md_match else line.strip()).rstrip(":")
            current_lines = []
        else:
            current_lines.append(line)
    flush()
    return [(h, b) for h, b in sections]


def extract(path: Path) -> Document:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ExtractionError(f"could not read notes file {path}: {exc}") from exc

    sections = _split_sections(text)
    if not sections:
        raise EmptyExtractionError(f"{path} has no extractable text")

    units = [
        SourceUnit(number=i, text=body, heading=heading)
        for i, (heading, body) in enumerate(sections, start=1)
    ]
    return Document(path=path, source_type="notes", units=units, unit_kind="section")
