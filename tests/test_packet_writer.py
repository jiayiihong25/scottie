import json
from datetime import date

import pytest

from graph.nodes.packet_writer import packet_writer
from graph.state import AnkiCardDraft, ConceptQuestion, new_state
from ingest.models import MEMORIZATION, ContentIndex

TODAY = date(2026, 9, 21)


def test_empty_day_writes_packet_and_manifest_without_deck(tmp_path):
    state = packet_writer(new_state(), tmp_path, TODAY)

    assert state["apkg_path"] is None
    assert not (tmp_path / "morning_deck.apkg").exists()
    manifest = json.loads((tmp_path / "delivery.json").read_text())
    assert manifest == {"date": "2026-09-21", "packet": "morning_packet.html", "apkg": None}
    assert "Monday, September 21, 2026" in (tmp_path / "morning_packet.html").read_text(
        encoding="utf-8"
    )


def test_cards_produce_deck_listed_in_manifest(tmp_path):
    state = new_state()
    state["anki_cards"] = [AnkiCardDraft("c1", "PHILOSOP1230", "Q", "A", "alias")]

    packet_writer(state, tmp_path, TODAY)

    assert (tmp_path / "morning_deck.apkg").exists()
    manifest = json.loads((tmp_path / "delivery.json").read_text())
    assert manifest["apkg"] == "morning_deck.apkg"


def test_errors_raise_and_leave_no_stale_manifest(tmp_path):
    (tmp_path / "delivery.json").write_text("{}")
    state = new_state()
    state["errors"] = ["boom"]

    with pytest.raises(RuntimeError):
        packet_writer(state, tmp_path, TODAY)

    # A stale manifest from a prior day must not survive a failed run.
    assert not (tmp_path / "delivery.json").exists()


def test_ingest_warnings_render_as_banner_not_failure(tmp_path):
    state = new_state()
    state["ingest_errors"] = ["data/x/lecture-04.pdf: unreadable <scan>"]

    packet_writer(state, tmp_path, TODAY)

    page = (tmp_path / "morning_packet.html").read_text(encoding="utf-8")
    assert "lecture-04.pdf" in page
    assert "&lt;scan&gt;" in page  # escaped, not injected


def test_no_warnings_means_no_banner(tmp_path):
    packet_writer(new_state(), tmp_path, TODAY)
    page = (tmp_path / "morning_packet.html").read_text(encoding="utf-8")
    assert "could not be read" not in page


def test_concept_only_day_has_questions_and_no_deck(tmp_path, make_chunk):
    state = new_state()
    state["assigned_chunks"] = [make_chunk("a.pdf", 0)]
    state["concept_questions"] = [ConceptQuestion("a.pdf#0", "C", "Why X?", "alias")]

    packet_writer(state, tmp_path, TODAY)

    page = (tmp_path / "morning_packet.html").read_text(encoding="utf-8")
    assert "Why X?" in page
    assert state["apkg_path"] is None
    assert json.loads((tmp_path / "delivery.json").read_text())["apkg"] is None


def test_card_only_day_has_reading_list_but_placeholder_questions(tmp_path, make_chunk):
    state = new_state()
    state["assigned_chunks"] = [make_chunk("a.pdf", 0, content_type=MEMORIZATION)]
    state["anki_cards"] = [AnkiCardDraft("a.pdf#0", "C", "Q", "A", "alias")]

    packet_writer(state, tmp_path, TODAY)

    page = (tmp_path / "morning_packet.html").read_text(encoding="utf-8")
    assert "a.pdf" in page
    assert "No concept questions today." in page
    assert (tmp_path / "morning_deck.apkg").exists()


def test_daybook_packet_follows_the_contract(tmp_path, make_chunk):
    state = new_state()
    state["content_index"] = ContentIndex(chunks=[make_chunk("a.pdf", 0), make_chunk("x.pdf", 0, course="D")])
    state["exam_dates"] = {"C": date(2026, 10, 1)}
    state["exams"] = [{"course": "C", "name": "Midterm", "date": "2026-10-01"}]
    state["assigned_chunks"] = [make_chunk("a.pdf", 0), make_chunk("dir/b.pdf", 1)]
    state["new_chunk_ids"] = ["a.pdf#0"]
    state["concept_questions"] = [ConceptQuestion("a.pdf#0", "C", "Why X?", "alias")]
    state["anki_cards"] = [AnkiCardDraft("dir/b.pdf#1", "C", "Q", "A", "alias")]

    packet_writer(state, tmp_path, TODAY)

    packet = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    assert packet["schema_version"] == 1
    assert packet["date"] == "2026-09-21"
    assert packet["exams"] == [{"course": "C", "name": "Midterm", "date": "2026-10-01"}]
    assert [(r["source_file"], r["kind"]) for r in packet["reading"]] == [
        ("a.pdf", "new"), ("b.pdf", "review")
    ]
    assert packet["reading"][0]["unit_range"] == "page 1"
    assert packet["questions"] == [{"course": "C", "unit_range": "page 1", "question": "Why X?"}]
    assert packet["deck"] == {"new_cards": 1, "file": "morning_deck.apkg"}
    # Course D has material but no exam date, so it's silently unpaced otherwise.
    assert packet["warnings"] == ["D: no exam date in courses.yaml, so it isn't in today's prep"]


def test_empty_day_daybook_packet_has_every_key(tmp_path):
    packet_writer(new_state(), tmp_path, TODAY)

    packet = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    assert packet["reading"] == [] and packet["questions"] == []
    assert packet["exams"] == [] and packet["warnings"] == []
    assert packet["deck"] is None


def test_failed_run_leaves_no_stale_daybook_packet(tmp_path):
    (tmp_path / "packet.json").write_text("{}")
    state = new_state()
    state["errors"] = ["boom"]

    with pytest.raises(RuntimeError):
        packet_writer(state, tmp_path, TODAY)

    assert not (tmp_path / "packet.json").exists()
