import dataclasses
import json
from datetime import date

import pytest

from graph.knowledge import knowledge, write_knowledge
from graph.nodes.packet_writer import packet_writer
from graph.state import new_state
from ingest.models import ContentIndex

TODAY = date(2026, 9, 21)


def test_every_chunk_becomes_a_passage_grouped_by_course(make_chunk):
    index = ContentIndex(chunks=[
        make_chunk("b/lec2.pdf", 1, course="B", text="second  page\n\ntext"),
        make_chunk("a/lec1.pdf", 0, course="A", text="first"),
        make_chunk("b/lec1.pdf", 0, course="B", text="first of B"),
    ])

    k = knowledge(index, TODAY)

    assert k["schema_version"] == 1
    assert k["date"] == "2026-09-21"
    assert [(p["course"], p["source_file"]) for p in k["passages"]] == [
        ("A", "lec1.pdf"), ("B", "lec1.pdf"), ("B", "lec2.pdf"),
    ]
    assert k["passages"][2] == {
        "id": "b/lec2.pdf#1", "course": "B", "topic": "t", "source_file": "lec2.pdf",
        "unit_range": "page 2", "text": "second page text",  # whitespace collapsed
    }


def test_default_topic_uses_file_name_and_blank_chunks_are_dropped(make_chunk):
    flat = dataclasses.replace(make_chunk("Grewal Ch01.pdf", 0), topic="general")
    index = ContentIndex(chunks=[flat, make_chunk("blank.pdf", 0, text="  \n ")])

    passages = knowledge(index, TODAY)["passages"]

    assert [p["topic"] for p in passages] == ["Grewal Ch01"]


def test_empty_index_is_a_valid_empty_file(tmp_path):
    path = write_knowledge(ContentIndex(), tmp_path, TODAY)

    assert json.loads(path.read_text(encoding="utf-8"))["passages"] == []


def test_packet_writer_writes_knowledge_next_to_packet(tmp_path, make_chunk):
    state = new_state()
    state["content_index"] = ContentIndex(chunks=[make_chunk("a.pdf", 0, text="hello")])

    packet_writer(state, tmp_path, TODAY)

    k = json.loads((tmp_path / "knowledge.json").read_text(encoding="utf-8"))
    assert [p["text"] for p in k["passages"]] == ["hello"]


def test_failed_run_leaves_no_stale_knowledge(tmp_path):
    (tmp_path / "knowledge.json").write_text("{}")
    state = new_state()
    state["errors"] = ["boom"]

    with pytest.raises(RuntimeError):
        packet_writer(state, tmp_path, TODAY)

    assert not (tmp_path / "knowledge.json").exists()
