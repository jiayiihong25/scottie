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
from .nodes.batching import daily_request_budget
from .nodes.ingest_node import ingest_node
from .nodes.lookahead import lookahead
from .nodes.packet_writer import packet_writer
from .nodes.pacing_agent import pacing_agent
from .nodes.summaries import summaries
from .state import PipelineState, new_state


def build_graph(
    data_root: Path,
    exam_dates: dict[str, date],
    pacing_state_path: Path,
    output_dir: Path,
    cache_path: Path,
    today: date | None = None,
):
    request_budget = daily_request_budget()
    graph = StateGraph(PipelineState)

    graph.add_node("ingest", lambda s: ingest_node(s, data_root))
    graph.add_node(
        "pacing",
        lambda s: pacing_agent(
            s, exam_dates, pacing_state_path, today, cache_path, request_budget
        ),
    )
    graph.add_node("concept", lambda s: concept_agent(s, cache_path, today))
    graph.add_node("card", lambda s: card_agent(s, cache_path, today))
    graph.add_node("lookahead", lambda s: lookahead(s, cache_path, request_budget, today))
    graph.add_node("summaries", lambda s: summaries(s, cache_path))
    graph.add_node("packet",lambda s: packet_writer(s, output_dir, today))

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "pacing")
    graph.add_edge("pacing", "concept")
    graph.add_edge("concept", "card")
    graph.add_edge("card", "lookahead")
    graph.add_edge("lookahead", "summaries")
    graph.add_edge("summaries", "packet")
    graph.add_edge("packet", END)

    return graph.compile()


def run_pipeline(
    data_root: Path,
    exam_dates: dict[str, date],
    pacing_state_path: Path,
    output_dir: Path,
    cache_path: Path,
    today: date | None = None,
    exams: list[dict] | None = None,
) -> PipelineState:
    compiled = build_graph(
        data_root, exam_dates, pacing_state_path, output_dir, cache_path, today
    )
    state = new_state()
    state["exams"] = exams or []
    return compiled.invoke(state)
