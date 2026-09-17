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
    state["ingest_errors"] = list(index.errors)
    if index.errors:
        state["errors"].extend(index.errors)
    return state
