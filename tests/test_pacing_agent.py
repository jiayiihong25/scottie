import json
from datetime import date, timedelta

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


def _run(chunks, tmp_path, today, exam=date(2026, 10, 15), course="C"):
    state = new_state()
    state["content_index"] = ContentIndex(chunks=chunks)
    return pacing_agent(state, {course: exam}, tmp_path / "pacing.json", today)


def _ids(state):
    return [c.chunk_id for c in state["assigned_chunks"]]


def test_new_material_is_spread_across_days_to_the_exam(tmp_path, make_chunk):
    chunks = [make_chunk(order=i) for i in range(4)]

    # 2 days to the exam, 4 new chunks: ceil(4/2) = 2 today.
    out = _run(chunks, tmp_path, TODAY, exam=date(2026, 9, 23))

    assert _ids(out) == ["f.pdf#0", "f.pdf#1"]


def test_chunk_returns_for_review_on_the_cadence_and_graduates(tmp_path, make_chunk):
    chunk = make_chunk()
    hits = []
    for offset in range(16):
        out = _run([chunk], tmp_path, TODAY + timedelta(days=offset), exam=date(2027, 1, 1))
        if out["assigned_chunks"]:
            hits.append(offset)

    # First seen day 0, then reviewed at +1, +3, +7, +14 and never again.
    assert hits == [0, 1, 3, 7, 14]


def test_missed_review_day_is_picked_up_late_not_dropped(tmp_path, make_chunk):
    chunk = make_chunk()
    _run([chunk], tmp_path, TODAY)

    # Skipped day +1 entirely; the review is still due on day +2.
    out = _run([chunk], tmp_path, TODAY + timedelta(days=2))

    assert _ids(out) == ["f.pdf#0"]
    assert "due for review" in out["pacing_notes"][0]


def test_state_persists_so_seen_chunk_is_not_new_again(tmp_path, make_chunk):
    chunk = make_chunk()
    _run([chunk], tmp_path, TODAY)

    out = _run([chunk], tmp_path, TODAY)  # same day, second run

    assert out["assigned_chunks"] == []
    saved = json.loads((tmp_path / "pacing.json").read_text())
    assert saved["f.pdf#0"]["first_seen"] == "2026-09-21"


def test_course_without_exam_date_is_skipped_with_a_note(tmp_path, make_chunk):
    state = new_state()
    state["content_index"] = ContentIndex(chunks=[make_chunk()])

    out = pacing_agent(state, {}, tmp_path / "pacing.json", TODAY)

    assert out["assigned_chunks"] == []
    assert "no exam date known" in out["pacing_notes"][0]
    assert json.loads((tmp_path / "pacing.json").read_text()) == {}


def test_past_exam_date_still_assigns_new_material(tmp_path, make_chunk):
    # days_remaining is floored at 1, so a past exam date must not divide by
    # zero or hide material.
    chunks = [make_chunk(order=i) for i in range(3)]

    out = _run(chunks, tmp_path, TODAY, exam=date(2026, 9, 1))

    assert len(out["assigned_chunks"]) == 3


def test_courses_are_paced_independently(tmp_path, make_chunk):
    chunks = [make_chunk("a.pdf", 0, course="A"), make_chunk("b.pdf", 0, course="B")]
    state = new_state()
    state["content_index"] = ContentIndex(chunks=chunks)

    out = pacing_agent(state, {"A": TODAY}, tmp_path / "pacing.json", TODAY)

    assert _ids(out) == ["a.pdf#0"]
    assert any(n.startswith("B: no exam date") for n in out["pacing_notes"])


def test_new_chunk_ids_mark_first_pass_not_reviews(tmp_path, make_chunk):
    chunks = [make_chunk(order=0)]
    _run(chunks, tmp_path, TODAY)
    chunks.append(make_chunk(order=1))

    out = _run(chunks, tmp_path, TODAY + timedelta(days=1))

    assert _ids(out) == ["f.pdf#1", "f.pdf#0"]
    assert out["new_chunk_ids"] == ["f.pdf#1"]
