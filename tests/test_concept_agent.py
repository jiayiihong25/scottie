from graph.nodes import concept_agent as mod
from graph.state import new_state
from ingest.models import MEMORIZATION


def test_only_conceptual_chunks_get_questions_and_output_is_stripped(monkeypatch, make_chunk):
    monkeypatch.setattr(mod, "call_model", lambda *a, **k: "  Why does X hold?\n")
    state = new_state()
    state["assigned_chunks"] = [
        make_chunk("a.pdf", 0, content_type="conceptual"),
        make_chunk("a.pdf", 1, content_type=MEMORIZATION),
    ]

    out = mod.concept_agent(state)

    assert [(q.chunk_id, q.question) for q in out["concept_questions"]] == [
        ("a.pdf#0", "Why does X hold?")
    ]


def test_no_conceptual_chunks_means_no_calls(monkeypatch, make_chunk):
    def boom(*a, **k):
        raise AssertionError("call_model must not fire")

    monkeypatch.setattr(mod, "call_model", boom)
    state = new_state()
    state["assigned_chunks"] = [make_chunk(content_type=MEMORIZATION)]

    assert mod.concept_agent(state)["concept_questions"] == []
