"""Thin wrapper around ingest.build_index() — deterministic, no LLM.

See docs/orchestration-design.md ("What stays deterministic"): this node
calls the already-built ingest pipeline exactly as it exists today.
"""

from __future__ import annotations

from pathlib import Path

from ingest.pipeline import build_index

from ..state import PipelineState


def ingest_node(state: PipelineState, data_root: Path) -> PipelineState:
    index = build_index(data_root)
    state["content_index"] = index
    # Per-file extraction failures are warnings: the rest of the index is
    # sound, so they go to ingest_errors and packet_writer shows them as a
    # banner. Only an index with nothing in it is fatal.
    state["ingest_errors"] = list(index.errors)
    if not index.chunks:
        detail = f": {index.errors!r}" if index.errors else ""
        raise RuntimeError(
            f"ingest produced no chunks from {data_root}{detail} — refusing to "
            "continue rather than emit a 'nothing due today' packet"
        )
    return state
