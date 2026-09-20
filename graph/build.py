"""Assembles the StateGraph. Entry point: run_pipeline().

content_router (ingest/models.py's content_type tag) isn't wired as a
separate LangGraph conditional edge — concept_agent and card_agent each
filter assigned_chunks by content_type internally (see
nodes/content_router.py's split_by_content_type) and simply produce an
empty list when nothing of their type is assigned today. That's the same
"skipped node is fine" behavior the design doc calls for, without the
extra graph wiring.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from langgraph.graph import END, StateGraph

from .nodes.card_agent import card_agent
from .nodes.concept_agent import concept_agent
from .nodes.ingest_node import ingest_node
from .nodes.packet_writer import packet_writer
from .nodes.pacing_agent import pacing_agent
from .state import PipelineState, new_state


def build_graph(
    data_root: Path,
    exam_dates: dict[str, date],
    pacing_state_path: Path,
    output_dir: Path,
    today: date | None = None,
):
    graph = StateGraph(PipelineState)

    graph.add_node("ingest", lambda s: ingest_node(s, data_root))
    graph.add_node(
        "pacing", lambda s: pacing_agent(s, exam_dates, pacing_state_path, today)
    )
    graph.add_node("concept", concept_agent)
    graph.add_node("card", card_agent)
    graph.add_node("packet", lambda s: packet_writer(s, output_dir, today))

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "pacing")
    graph.add_edge("pacing", "concept")
    graph.add_edge("concept", "card")
    graph.add_edge("card", "packet")
    graph.add_edge("packet", END)

    return graph.compile()


def run_pipeline(
    data_root: Path,
    exam_dates: dict[str, date],
    pacing_state_path: Path,
    output_dir: Path,
    today: date | None = None,
) -> PipelineState:
    compiled = build_graph(data_root, exam_dates, pacing_state_path, output_dir, today)
    return compiled.invoke(new_state())
