import pytest

from graph.nodes import ingest_node as mod
from graph.state import new_state
from ingest.models import Chunk, ContentIndex


def _chunk():
    return Chunk(
        chunk_id="c1", course="C", topic="t", source_file="f.pdf",
        source_type="pdf", unit_kind="page", unit_start=1, unit_end=1,
        text="x", content_type="conceptual", content_type_score=1.0, word_count=1,
    )


def test_partial_failures_are_warnings_not_errors(monkeypatch, tmp_path):
    index = ContentIndex(chunks=[_chunk()], errors=["bad.pdf: unreadable"])
    monkeypatch.setattr(mod, "build_index", lambda _root: index)

    state = mod.ingest_node(new_state(), tmp_path)

    assert state["ingest_errors"] == ["bad.pdf: unreadable"]
    assert state["errors"] == []


def test_empty_index_is_fatal(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "build_index", lambda _root: ContentIndex(errors=["bad.pdf: x"]))

    with pytest.raises(RuntimeError, match="no chunks"):
        mod.ingest_node(new_state(), tmp_path)
