import json

import pytest

from graph.nodes import batching
from graph.nodes.concept_agent import concept_agent
from graph.state import new_state
from ingest.models import MEMORIZATION


def _run(tmp_path, chunks):
    state = new_state()
    state["assigned_chunks"] = chunks
    return concept_agent(state, tmp_path / "generated.json")


def test_only_conceptual_chunks_get_questions(fake_batch_model, make_chunk, tmp_path):
    fake_batch_model(question=lambda i: f"Why {i}?")

    out = _run(tmp_path, [
        make_chunk("a.pdf", 0, content_type="conceptual"),
        make_chunk("a.pdf", 1, content_type=MEMORIZATION),
    ])

    assert [(q.chunk_id, q.question) for q in out["concept_questions"]] == [
        ("a.pdf#0", "Why a.pdf#0?")
    ]


def test_no_conceptual_chunks_means_no_calls(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(question="Why?")

    assert _run(tmp_path, [make_chunk(content_type=MEMORIZATION)])["concept_questions"] == []
    assert prompts == []


def test_one_request_per_source_file(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(question="Why?")

    out = _run(tmp_path, [make_chunk("a.pdf", i) for i in range(3)] + [make_chunk("b.pdf", 0)])

    assert len(prompts) == 2
    assert len(out["concept_questions"]) == 4


def test_review_pass_reuses_the_cached_question(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(question="Why?")

    for _ in range(3):
        out = _run(tmp_path, [make_chunk()])

    assert len(prompts) == 1
    assert [q.question for q in out["concept_questions"]] == ["Why?"]


def test_edited_source_text_is_regenerated(fake_batch_model, make_chunk, tmp_path):
    fake_batch_model(question="Old?")
    _run(tmp_path, [make_chunk(text="original text")])
    fake_batch_model(question="New?")

    out = _run(tmp_path, [make_chunk(text="revised text")])

    assert out["concept_questions"][0].question == "New?"


def test_quota_spent_before_a_failure_is_kept(monkeypatch, make_chunk, tmp_path):
    calls = []

    def call_model(*a, **k):
        calls.append(1)
        if len(calls) > 1:
            raise RuntimeError("429: quota exhausted")  # the second file's request
        return json.dumps({"summary": "S", "items": {"a.pdf#0": {"question": "Why A?"}}})

    monkeypatch.setattr(batching, "call_model", call_model)

    with pytest.raises(RuntimeError):
        _run(tmp_path, [make_chunk("a.pdf", 0), make_chunk("b.pdf", 0)])

    cache = json.loads((tmp_path / "generated.json").read_text(encoding="utf-8"))
    assert list(cache) == ["a.pdf#0"]
