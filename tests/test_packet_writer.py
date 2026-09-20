import json
from datetime import date

import pytest

from graph.nodes.packet_writer import packet_writer
from graph.state import AnkiCardDraft, new_state

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
