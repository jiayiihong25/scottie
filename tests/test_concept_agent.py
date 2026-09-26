import json

import pytest

from graph.nodes import concept_agent as mod
from graph.state import new_state
from ingest.models import MEMORIZATION


def test_only_conceptual_chunks_get_questions_and_output_is_stripped(monkeypatch, make_chunk, tmp_path):
    monkeypatch.setattr(mod, "call_model", lambda *a, **k: "  Why does X hold?\n")
    state = new_state()
    state["assigned_chunks"] = [
        make_chunk("a.pdf", 0, content_type="conceptual"),
        make_chunk("a.pdf", 1, content_type=MEMORIZATION),
    ]

    out = mod.concept_agent(state, tmp_path / "generated.json")

    assert [(q.chunk_id, q.question) for q in out["concept_questions"]] == [
        ("a.pdf#0", "Why does X hold?")
    ]


def test_no_conceptual_chunks_means_no_calls(monkeypatch, make_chunk, tmp_path):
    def boom(*a, **k):
        raise AssertionError("call_model must not fire")

    monkeypatch.setattr(mod, "call_model", boom)
    state = new_state()
    state["assigned_chunks"] = [make_chunk(content_type=MEMORIZATION)]

    assert mod.concept_agent(state, tmp_path / "generated.json")["concept_questions"] == []


def test_review_pass_reuses_the_cached_question(monkeypatch, make_chunk, tmp_path):
    calls = []
    monkeypatch.setattr(mod, "call_model", lambda *a, **k: calls.append(1) or "Why?")
    cache = tmp_path / "generated.json"

    for _ in range(3):
        state = new_state()
        state["assigned_chunks"] = [make_chunk()]
        out = mod.concept_agent(state, cache)

    assert len(calls) == 1
    assert [q.question for q in out["concept_questions"]] == ["Why?"]


def test_edited_source_text_is_regenerated(monkeypatch, make_chunk, tmp_path):
    answers = iter(["Old?", "New?"])
    monkeypatch.setattr(mod, "call_model", lambda *a, **k: next(answers))
    cache = tmp_path / "generated.json"

    for text in ("original text", "revised text"):
        state = new_state()
        state["assigned_chunks"] = [make_chunk(text=text)]
        out = mod.concept_agent(state, cache)

    assert out["concept_questions"][0].question == "New?"


def test_quota_spent_before_a_failure_is_kept(monkeypatch, make_chunk, tmp_path):
    answers = iter(["Why A?"])

    def call(*a, **k):
        answer = next(answers, None)
        if answer is None:
            raise RuntimeError("429: quota exhausted")  # the second chunk
        return answer

    monkeypatch.setattr(mod, "call_model", call)
    cache = tmp_path / "generated.json"
    state = new_state()
    state["assigned_chunks"] = [make_chunk("a.pdf", 0), make_chunk("a.pdf", 1)]

    with pytest.raises(RuntimeError):
        mod.concept_agent(state, cache)

    assert list(json.loads(cache.read_text(encoding="utf-8"))) == ["a.pdf#0"]
