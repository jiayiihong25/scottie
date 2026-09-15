"""Assemble the LangGraph StateGraph and expose a run() entry point."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from graph.state import PipelineState
from graph.nodes.ingest_node import ingest_node
from graph.nodes.pacing_agent import pacing_agent
from graph.nodes.generate_agent import generate_agent
from graph.nodes.packet_writer import packet_writer


def build_graph():
    """Build and return the compiled LangGraph pipeline.

    Requires langgraph to be installed. Falls back to a simple
    sequential runner if langgraph is not available.
    """
    try:
        from langgraph.graph import StateGraph, END

        builder = StateGraph(PipelineState)
        builder.add_node("ingest", ingest_node)
        builder.add_node("pacing", pacing_agent)
        builder.add_node("generate", generate_agent)
        builder.add_node("packet", packet_writer)

        builder.set_entry_point("ingest")
        builder.add_edge("ingest", "pacing")
        builder.add_edge("pacing", "generate")
        builder.add_edge("generate", "packet")
        builder.add_edge("packet", END)

        return builder.compile()
    except ImportError:
        return None


def run_sequential(
    exam_dates: dict[str, date] | None = None,
    courses_config: dict | None = None,
) -> PipelineState:
    """Run the pipeline as plain sequential function calls.

    Works without langgraph installed — useful for testing and for
    the Routine environment where adding langgraph is overhead.
    """
    state: PipelineState = {
        "errors": [],
        "model_calls": [],
        "exam_dates": exam_dates or {},
        "courses_config": courses_config or {},
    }

    for node_fn in [ingest_node, pacing_agent, generate_agent, packet_writer]:
        result = node_fn(state)
        state.update(result)

    return state


def run(
    exam_dates: dict[str, date] | None = None,
    courses_config: dict | None = None,
) -> PipelineState:
    """Run the full pipeline. Uses LangGraph if available, else sequential."""
    graph = build_graph()
    if graph is not None:
        initial: PipelineState = {
            "errors": [],
            "model_calls": [],
            "exam_dates": exam_dates or {},
            "courses_config": courses_config or {},
        }
        return graph.invoke(initial)

    return run_sequential(exam_dates, courses_config)
