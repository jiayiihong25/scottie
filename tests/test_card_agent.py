from graph.nodes.card_agent import card_agent
from graph.state import new_state
from ingest.models import MEMORIZATION


def _run(tmp_path, chunks, new_ids):
    state = new_state()
    state["assigned_chunks"] = chunks
    state["new_chunk_ids"] = new_ids
    return card_agent(state, tmp_path / "generated.json")


def test_only_memorization_chunks_get_cards(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(front="q", back="a")

    out = _run(tmp_path, [
        make_chunk("a.pdf", 0, content_type=MEMORIZATION, text="term one"),
        make_chunk("a.pdf", 1, content_type="conceptual"),
    ], ["a.pdf#0", "a.pdf#1"])

    assert [(c.chunk_id, c.front, c.back) for c in out["anki_cards"]] == [("a.pdf#0", "q", "a")]
    assert len(prompts) == 1 and "term one" in prompts[0]


def test_nothing_memorization_means_no_calls_and_empty_list(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(front="q", back="a")

    assert _run(tmp_path, [make_chunk(content_type="conceptual")], ["f.pdf#0"])["anki_cards"] == []
    assert prompts == []


def test_review_pass_makes_no_card_because_anki_already_has_it(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(front="q", back="a")

    assert _run(tmp_path, [make_chunk(content_type=MEMORIZATION)], [])["anki_cards"] == []
    assert prompts == []


def test_same_day_rerun_reuses_the_cached_card(fake_batch_model, make_chunk, tmp_path):
    prompts = fake_batch_model(front="q", back="a")

    for _ in range(2):
        out = _run(tmp_path, [make_chunk(content_type=MEMORIZATION)], ["f.pdf#0"])

    assert len(prompts) == 1
    assert [(c.front, c.back) for c in out["anki_cards"]] == [("q", "a")]
