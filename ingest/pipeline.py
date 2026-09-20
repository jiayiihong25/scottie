"""Top-level ingestion: walk a course-material directory, extract, chunk,
and produce a ContentIndex.

Directory convention (see README): `data/<course>/<topic>/<file>`. Course
and topic come from directory names, not filenames, so course material can
keep its original filenames.

Errors from a single bad file never abort the run — they're recorded in
`ContentIndex.errors` and the run continues, but the pipeline's caller
(the daily cron entry point) treats a non-empty error list as loud failure
per CLAUDE.md: an incomplete index should not silently produce a thin
morning packet.
"""

from __future__ import annotations

from pathlib import Path

from . import extractors
from .chunk import DEFAULT_TARGET_WORDS, chunk_document
from .errors import IngestError
from .models import ContentIndex


def _iter_source_files(root: Path):
    """Yield (course, topic, file_path) for every supported file under root.

    Layout: root/<course>/<topic>/<file>. Files directly under a course
    directory (no topic subfolder) get topic "general".
    """
    for course_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        course = course_dir.name
        for entry in sorted(course_dir.rglob("*")):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in extractors.supported_extensions():
                continue
            rel_parts = entry.relative_to(course_dir).parts
            topic = rel_parts[0] if len(rel_parts) > 1 else "general"
            yield course, topic, entry


def build_index(
    data_root: Path,
    target_words: int = DEFAULT_TARGET_WORDS,
) -> ContentIndex:
    data_root = Path(data_root)
    if not data_root.is_dir():
        raise IngestError(f"data root {data_root} does not exist or is not a directory")

    course_dirs = [p for p in data_root.iterdir() if p.is_dir()]
    if not course_dirs:
        raise IngestError(
            f"data root {data_root} has no course subdirectories — "
            "an unsynced or empty Drive pull would otherwise look like "
            "'nothing due today' instead of failing loudly"
        )

    index = ContentIndex()
    for course, topic, path in _iter_source_files(data_root):
        try:
            doc = extractors.extract(path)
            index.chunks.extend(
                chunk_document(doc, course=course, topic=topic, target_words=target_words)
            )
        except IngestError as exc:
            index.errors.append(f"{path}: {exc}")

    return index
