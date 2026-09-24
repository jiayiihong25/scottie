import json
from datetime import date

from graph.cache import file_summary, store_output
from graph.nodes.concept_agent import concept_agent
from graph.nodes.packet_writer import packet_writer
from graph.nodes.summaries import summaries
from graph.state import new_state
from ingest.models import ContentIndex

TODAY = date(2026, 9, 21)


def _state(chunks, assigned, new_ids):
    state = new_state()
    state["content_index"] = ContentIndex(chunks=chunks)
    state["assigned_chunks"] = assigned
    state["new_chunk_ids"] = new_ids
    return state


def test_summary_comes_from_the_same_request_as_the_questions(
    fake_batch_model, make_chunk, tmp_path
):
    prompts = fake_batch_model(question="Why?")
    chunks = [make_chunk("a.pdf", 0), make_chunk("a.pdf", 1)]
    cache = tmp_path / "generated.json"
    state = _state(chunks, chunks[:1], ["a.pdf#0"])
    state["lookahead_chunks"] = chunks[1:]

    concept_agent(state, cache, TODAY)
    summaries(state, cache)

    assert len(prompts) == 1 and '"summary"' in prompts[0]
    # The file companion rode along, so the summary covers the whole file.
    assert state["file_summaries"] == {"a.pdf": "Summary of a.pdf#0, a.pdf#1."}


def test_only_files_with_new_chunks_today_get_a_summary(make_chunk, tmp_path):
    a, b = make_chunk("a.pdf", 0), make_chunk("b.pdf", 0)
    cache = {}
    store_output(cache, a, "concept", {"question": "?"}, "x", TODAY, "About A.")
    store_output(cache, b, "concept", {"question": "?"}, "x", TODAY, "About B.")
    (tmp_path / "g.json").write_text(json.dumps(cache))

    state = summaries(_state([a, b], [a, b], ["b.pdf#0"]), tmp_path / "g.json")

    assert state["file_summaries"] == {"b.pdf": "About B."}


def test_multi_batch_file_joins_distinct_summaries_in_order_and_skips_stale(make_chunk):
    c0, c1, c2 = (make_chunk("a.pdf", i, text=f"t{i}") for i in range(3))
    cache = {}
    store_output(cache, c0, "concept", {}, "x", TODAY, "Part one.")
    store_output(cache, c1, "concept", {}, "x", TODAY, "Part one.")
    store_output(cache, c2, "concept", {}, "x", TODAY, "Part two.")

    assert file_summary(cache, [c0, c1, c2]) == "Part one.\n\nPart two."
    edited = make_chunk("a.pdf", 2, text="rewritten")
    assert file_summary(cache, [c0, c1, edited]) == "Part one."


def test_old_cache_entries_without_a_summary_are_fine(make_chunk):
    c = make_chunk()
    cache = {}
    store_output(cache, c, "concept", {"question": "?"}, "x", TODAY)

    assert file_summary(cache, [c]) is None


def test_packet_shows_summaries_in_html_and_json(tmp_path):
    state = new_state()
    state["file_summaries"] = {"dir/lecture-03.pdf": "Covers <supply> curves.\n\nThen demand."}

    packet_writer(state, tmp_path, TODAY)

    page = (tmp_path / "morning_packet.html").read_text(encoding="utf-8")
    assert "lecture-03.pdf" in page and "Covers &lt;supply&gt; curves." in page
    packet = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    assert packet["summaries"] == [
        {"source_file": "lecture-03.pdf", "summary": "Covers <supply> curves.\n\nThen demand."}
    ]
