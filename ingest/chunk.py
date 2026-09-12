"""Group a Document's SourceUnits into study-sized Chunks.

A chunk never straddles two source files (each Document is chunked alone)
and never splits a single unit — the smallest possible chunk is one page,
slide, or notes section, however long that unit is. Within that constraint,
consecutive units are grouped up to `target_words`, and a heading boundary
is preferred as a split point when one is available near the target.
"""

from __future__ import annotations

from .classify import classify
from .models import Chunk, Document, make_chunk_id

DEFAULT_TARGET_WORDS = 500
# How far past target_words we'll look for a heading to split on before
# just cutting at the unit that crosses the target.
HEADING_SEARCH_SLACK = 2


def chunk_document(
    doc: Document,
    course: str,
    topic: str,
    target_words: int = DEFAULT_TARGET_WORDS,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    units = doc.units
    i = 0
    order = 0
    source_file = str(doc.path)

    while i < len(units):
        group = [units[i]]
        word_count = units[i].word_count
        j = i + 1

        while j < len(units) and word_count < target_words:
            group.append(units[j])
            word_count += units[j].word_count
            j += 1
            # Prefer stopping right after we cross target if the next unit
            # starts a new heading — keeps chunks aligned to the source's
            # own structure instead of cutting mid-topic.
            if word_count >= target_words and j < len(units) and units[j].heading:
                break

        text = "\n\n".join(u.text for u in group)
        content_type, score = classify(text)
        chunk = Chunk(
            chunk_id=make_chunk_id(source_file, group[0].number, group[-1].number),
            course=course,
            topic=topic,
            source_file=source_file,
            source_type=doc.source_type,
            unit_kind=doc.unit_kind,
            unit_start=group[0].number,
            unit_end=group[-1].number,
            text=text,
            content_type=content_type,
            content_type_score=score,
            word_count=word_count,
            order=order,
        )
        chunks.append(chunk)
        order += 1
        i = j

    return chunks
