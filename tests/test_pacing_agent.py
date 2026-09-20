from datetime import date

from graph.nodes.pacing_agent import pacing_agent
from graph.state import new_state
from ingest.models import Chunk, ContentIndex

TODAY = date(2026, 9, 21)


def _chunk(source_file: str, order: int) -> Chunk:
    return Chunk(
        chunk_id=f"{source_file}#{order}", course="C", topic="t",
        source_file=source_file, source_type="pdf", unit_kind="page",
        unit_start=order, unit_end=order, text="x", content_type="conceptual",
        content_type_score=1.0, word_count=1, order=order,
    )


def test_new_material_follows_teaching_order_across_files(tmp_path):
    # order restarts at 0 per file, so sorting by order alone interleaves
    # the files (week2#0, week10#0, week2#1, ...).
    chunks = [_chunk(f, o) for f in ("week10.pdf", "week2.pdf") for o in (0, 1)]
    state = new_state()
    state["content_index"] = ContentIndex(chunks=chunks)

    # One day to the exam: everything new is assigned today, in order.
    out = pacing_agent(state, {"C": TODAY}, tmp_path / "pacing.json", TODAY)

    assert [c.chunk_id for c in out["assigned_chunks"]] == [
        "week2.pdf#0", "week2.pdf#1", "week10.pdf#0", "week10.pdf#1",
    ]
