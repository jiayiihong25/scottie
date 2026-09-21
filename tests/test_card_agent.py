import pytest

from graph.nodes import card_agent as mod
from graph.nodes.card_agent import _parse_card
from graph.state import new_state
from ingest.models import MEMORIZATION


def test_parses_front_and_back():
    assert _parse_card("FRONT: What is X?\nBACK: A thing") == ("What is X?", "A thing")


def test_tolerates_case_whitespace_and_colons_in_the_answer():
    raw = "\n  front:  Ratio?  \nBack: a: b: c\n"
    assert _parse_card(raw) == ("Ratio?", "a: b: c")


@pytest.mark.parametrize(
    "raw",
    ["", "just some prose", "FRONT: only a front", "BACK: only a back", "FRONT:\nBACK: x"],
)
def test_malformed_output_raises_rather_than_making_a_blank_card(raw):
    with pytest.raises(ValueError, match="unparseable"):
        _parse_card(raw)


def test_only_memorization_chunks_get_cards(monkeypatch, make_chunk):
    prompts = []

    def fake_call_model(task_type, messages, state, **kw):
        prompts.append((task_type, messages[0]["content"]))
        return "FRONT: q\nBACK: a"

    monkeypatch.setattr(mod, "call_model", fake_call_model)
    state = new_state()
    state["assigned_chunks"] = [
        make_chunk("a.pdf", 0, content_type=MEMORIZATION, text="term one"),
        make_chunk("a.pdf", 1, content_type="conceptual"),
    ]

    out = mod.card_agent(state)

    assert [c.chunk_id for c in out["anki_cards"]] == ["a.pdf#0"]
    assert len(prompts) == 1 and prompts[0][0] == "card_agent"
    assert "term one" in prompts[0][1]


def test_nothing_memorization_means_no_calls_and_empty_list(monkeypatch, make_chunk):
    def boom(*a, **k):
        raise AssertionError("call_model must not fire")

    monkeypatch.setattr(mod, "call_model", boom)
    state = new_state()
    state["assigned_chunks"] = [make_chunk(content_type="conceptual")]

    assert mod.card_agent(state)["anki_cards"] == []


def test_unparseable_model_output_stops_the_run(monkeypatch, make_chunk):
    monkeypatch.setattr(mod, "call_model", lambda *a, **k: "Sure, here is a card.")
    state = new_state()
    state["assigned_chunks"] = [make_chunk(content_type=MEMORIZATION)]

    with pytest.raises(ValueError):
        mod.card_agent(state)
