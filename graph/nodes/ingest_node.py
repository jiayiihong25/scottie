"""Thin wrapper around ingest.build_index() — deterministic, no LLM."""

from __future__ import annotations

from pathlib import Path

from ingest import build_index
from graph.state import PipelineState


def ingest_node(state: PipelineState) -> dict:
    data_root = Path("data")
    index = build_index(data_root)
    return {
        "content_index": index,
        "ingest_errors": list(index.errors),
        "errors": state.get("errors", []) + list(index.errors),
    }
