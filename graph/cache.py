"""Generation cache: each chunk's model output is paid for once.

Free-tier providers cap requests per day, and a chunk comes back for up to
four review passes (pacing_agent.REVIEW_OFFSETS_DAYS). Regenerating on
every pass cost ~5 requests per chunk; the cache makes reviews free.

Persisted at data/generated.json (gitignored, synced with Drive like
pacing_state.json). Entries are keyed by chunk_id and carry a hash of the
chunk's text, so an edited source file gets regenerated instead of
serving a question about text that no longer exists. Pushing this file
never advances pacing, so it's safe to save after every call and to push
even after a failed run — spent quota isn't thrown away.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from ingest.models import Chunk

Cache = dict[str, dict]


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def load_cache(path: Path) -> Cache:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: Cache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cached_output(cache: Cache, chunk: Chunk, kind: str) -> dict | None:
    """The stored output for this chunk, or None if missing or stale."""
    entry = cache.get(chunk.chunk_id)
    if entry is None or entry["kind"] != kind or entry["text_hash"] != text_hash(chunk.text):
        return None
    return entry["output"]


def store_output(
    cache: Cache,
    chunk: Chunk,
    kind: str,
    output: dict,
    model_alias: str,
    today: date,
    summary: str | None = None,
) -> None:
    """summary is the overview of the batch this chunk was generated in,
    stored on each of the batch's chunks so it goes stale with them."""
    cache[chunk.chunk_id] = {
        "kind": kind,
        "text_hash": text_hash(chunk.text),
        "output": output,
        "summary": summary,
        "model_alias": model_alias,
        "generated_on": today.isoformat(),
    }


def file_summary(cache: Cache, file_chunks: list[Chunk]) -> str | None:
    """A source file's summary: the distinct batch summaries stored on its
    (fresh) chunks, in chunk order. None if nothing's summarized yet.
    """
    parts: list[str] = []
    for chunk in file_chunks:
        entry = cache.get(chunk.chunk_id)
        if entry is None or entry["text_hash"] != text_hash(chunk.text):
            continue
        summary = entry.get("summary")
        if summary and summary not in parts:
            parts.append(summary)
    return "\n\n".join(parts) or None
