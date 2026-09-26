"""Daily request budget: pacing defers by urgency, lookahead spends the
remainder, and call_model refuses to go past the ceiling."""

import json
from datetime import date, timedelta

import pytest

from graph import models
from graph.cache import store_output
from graph.nodes.card_agent import card_agent
from graph.nodes.concept_agent import concept_agent
from graph.nodes.lookahead import lookahead
from graph.nodes.pacing_agent import pacing_agent
from graph.state import ModelCallLog, new_state
from ingest.models import MEMORIZATION, ContentIndex

TODAY = date(2026, 9, 21)
SOON, LATER = TODAY + timedelta(days=2), TODAY + timedelta(days=30)


def _one_file_per_chunk(make_chunk, course, n):
    # A chunk per file, so each costs its own request.
    return [make_chunk(f"{course}-{i:02}.pdf", 0, course=course) for i in range(n)]


def _pace(tmp_path, chunks, exams, budget, today=TODAY):
    state = new_state()
    state["content_index"] = ContentIndex(chunks=chunks)
    return pacing_agent(
        state, exams, tmp_path / "pacing.json", today, tmp_path / "generated.json", budget
    )


def test_squeeze_defers_the_course_with_the_later_exam(tmp_path, make_chunk):
    chunks = _one_file_per_chunk(make_chunk, "A", 3) + _one_file_per_chunk(make_chunk, "B", 3)
    # window 2 days -> ceil(3/2) = 2 new per course = 4 requests wanted; budget 3.
    out = _pace(tmp_path, chunks, {"A": SOON, "B": SOON + timedelta(days=0)}, 3)
    out_b_later = _pace(tmp_path / "x", chunks, {"A": SOON, "B": LATER}, 3)

    assert out["new_chunk_ids"] == ["A-00.pdf#0", "A-01.pdf#0", "B-00.pdf#0"]
    assert out["pacing_warnings"] == [
        "B: 1 new chunks deferred to tomorrow — over the daily request budget (3)"
    ]
    # B's exam is later, so it's the one squeezed even though A is listed first.
    assert out_b_later["new_chunk_ids"][:2] == ["A-00.pdf#0", "A-01.pdf#0"]


def test_deferred_chunk_is_still_new_tomorrow(tmp_path, make_chunk):
    chunks = _one_file_per_chunk(make_chunk, "A", 2)
    _pace(tmp_path, chunks, {"A": SOON}, 0)

    out = _pace(tmp_path, chunks, {"A": SOON}, 5, TODAY + timedelta(days=1))

    assert out["new_chunk_ids"] == ["A-00.pdf#0", "A-01.pdf#0"]


def test_already_cached_material_costs_nothing(tmp_path, make_chunk):
    chunks = _one_file_per_chunk(make_chunk, "A", 3)
    cache = {}
    for c in chunks:
        store_output(cache, c, "concept", {"question": "Why?"}, "concept_agent", TODAY)
    (tmp_path / "generated.json").write_text(json.dumps(cache))

    out = _pace(tmp_path, chunks, {"A": TODAY + timedelta(days=1)}, 0)

    assert len(out["new_chunk_ids"]) == 3 and out["pacing_warnings"] == []


def test_lookahead_lists_unintroduced_material_nearest_exam_first(tmp_path, make_chunk):
    chunks = _one_file_per_chunk(make_chunk, "B", 2) + _one_file_per_chunk(make_chunk, "A", 2)

    out = _pace(tmp_path, chunks, {"A": SOON, "B": LATER}, 1)

    assert out["new_chunk_ids"] == ["A-00.pdf#0"]
    assert [c.chunk_id for c in out["lookahead_chunks"]] == [
        "A-01.pdf#0", "B-00.pdf#0", "B-01.pdf#0",
    ]


def test_lookahead_spends_only_the_leftover_budget(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(question="Why?", front="q", back="a")
    state = new_state()
    state["model_calls"] = [ModelCallLog("concept_agent", "x", 0, 0)] * 3
    state["lookahead_chunks"] = _one_file_per_chunk(make_chunk, "A", 4) + [
        make_chunk("m.pdf", 0, content_type=MEMORIZATION)
    ]

    lookahead(state, tmp_path / "generated.json", 5, TODAY)

    assert len(prompts) == 2
    cache = json.loads((tmp_path / "generated.json").read_text(encoding="utf-8"))
    assert sorted(cache) == ["A-00.pdf#0", "A-01.pdf#0"]


def test_lookahead_without_a_budget_does_nothing(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(question="Why?")
    state = new_state()
    state["lookahead_chunks"] = [make_chunk()]

    lookahead(state, tmp_path / "generated.json", None, TODAY)

    assert prompts == []


def test_call_model_refuses_past_the_budget(monkeypatch):
    monkeypatch.setitem(models.MODEL_CONFIG, "budget", {"daily_request_budget": 2})
    monkeypatch.setattr(models, "_get_client", lambda: pytest.fail("must not reach the gateway"))
    state = new_state()
    state["model_calls"] = [ModelCallLog("concept_agent", "x", 0, 0)] * 2

    with pytest.raises(RuntimeError, match="daily request budget of 2"):
        models.call_model("concept_agent", [], state)


def test_thirty_days_never_exceed_the_budget_and_reviews_are_free(
    fake_batch_model, make_chunk, tmp_path
):
    prompts = fake_batch_model(question="Why?", front="q", back="a")
    budget = 4
    chunks = [
        make_chunk(f"{course}-{f:02}.pdf", o, course=course,
                   content_type=MEMORIZATION if o == 2 else "conceptual")
        for course in ("A", "B", "C") for f in range(8) for o in range(3)
    ]
    exams = {"A": TODAY + timedelta(days=12), "B": TODAY + timedelta(days=20),
             "C": TODAY + timedelta(days=40)}
    cache = tmp_path / "generated.json"

    per_day = []
    for offset in range(30):
        today = TODAY + timedelta(days=offset)
        live = {k: v for k, v in exams.items() if v >= today}
        before = len(prompts)
        state = _pace(tmp_path, chunks, live, budget, today)
        concept_agent(state, cache, today)
        card_agent(state, cache, today)
        lookahead(state, cache, budget, today)
        per_day.append(len(prompts) - before)

    assert max(per_day) <= budget
    # 24 files x (1 concept + 1 card batch) = 48 requests, paid once each.
    assert sum(per_day) == 48
