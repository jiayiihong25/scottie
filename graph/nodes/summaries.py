"""summaries: per-file overviews for today's reading list.

Deterministic. No model call here: each summary was written in the same
batched request that produced the file's questions or cards
(batching.generate_batch) and stored in the generation cache. This node
only gathers them for the source files with new chunks today. Summaries
come from the raw text, not the other way round. Questions are never
generated from a summary, since that would lose detail and save nothing
under a request-count (not token) limit.
"""

from __future__ import annotations

from pathlib import Path

from ..cache import file_summary, load_cache
from ..state import PipelineState


def summaries(state: PipelineState, cache_path: Path) -> PipelineState:
    cache = load_cache(cache_path)
    new_ids = set(state["new_chunk_ids"])
    new_files = []
    for chunk in state["assigned_chunks"]:
        if chunk.chunk_id in new_ids and chunk.source_file not in new_files:
            new_files.append(chunk.source_file)

    result: dict[str, str] = {}
    for source_file in new_files:
        file_chunks = [
            c for c in state["content_index"].chunks if c.source_file == source_file
        ]
        summary = file_summary(cache, sorted(file_chunks, key=lambda c: c.order))
        if summary:
            result[source_file] = summary
    state["file_summaries"] = result
    return state
