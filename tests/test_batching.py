import json

import pytest

from graph.nodes.batching import make_batches, parse_batch


def test_batches_split_by_file_then_by_word_budget(make_chunk):
    words = "w " * 40
    chunks = [make_chunk("a.pdf", i, text=words) for i in range(5)] + [make_chunk("b.pdf", 0)]

    batches = make_batches(chunks, max_words=100)

    assert [[c.chunk_id for c in b] for b in batches] == [
        ["a.pdf#0", "a.pdf#1"], ["a.pdf#2", "a.pdf#3"], ["a.pdf#4"], ["b.pdf#0"],
    ]


def test_oversized_chunk_goes_alone_and_is_never_split(make_chunk):
    big = make_chunk("a.pdf", 0, text="w " * 500)

    assert make_batches([big, make_chunk("a.pdf", 1)], max_words=100) == [
        [big], [make_chunk("a.pdf", 1)],
    ]


def test_interleaved_files_still_share_a_batch(make_chunk):
    chunks = [make_chunk("a.pdf", 0), make_chunk("b.pdf", 0), make_chunk("a.pdf", 1)]

    assert [len(b) for b in make_batches(chunks, max_words=100)] == [2, 1]


def test_parses_summary_and_items_and_strips_whitespace():
    raw = json.dumps(
        {"summary": " Covers X. ", "items": {"a#0": {"front": " q ", "back": "a: b"}}}
    )
    assert parse_batch(raw, ["a#0"], ("front", "back"), "card_agent") == (
        "Covers X.", {"a#0": {"front": "q", "back": "a: b"}}
    )


def test_tolerates_a_code_fence():
    raw = '```json\n{"summary": "S", "items": {"a#0": {"question": "Why?"}}}\n```'
    assert parse_batch(raw, ["a#0"], ("question",), "concept_agent") == (
        "S", {"a#0": {"question": "Why?"}}
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "Sure, here are your cards.",
        "[]",
        '{"summary": "S", "a#0": {"question": "Why?"}}',         # no "items" wrapper
        '{"summary": "S", "items": {}}',                          # chunk missing
        '{"summary": "S", "items": {"a#0": {}}}',                 # field missing
        '{"summary": "S", "items": {"a#0": {"question": "  "}}}', # blank field
        '{"summary": "S", "items": {"a#0": {"question": 3}}}',    # not a string
        '{"items": {"a#0": {"question": "Why?"}}}',               # no summary
        '{"summary": " ", "items": {"a#0": {"question": "Why?"}}}',  # blank summary
    ],
)
def test_malformed_output_raises_rather_than_making_blank_output(raw):
    with pytest.raises(ValueError, match="unparseable"):
        parse_batch(raw, ["a#0"], ("question",), "concept_agent")
