import shutil

import pytest

from ingest.errors import IngestError
from ingest.models import ContentIndex
from ingest.pipeline import build_index


@pytest.fixture
def data_root(tmp_path, fixtures_dir):
    root = tmp_path / "data"
    (root / "bio101" / "cell_respiration").mkdir(parents=True)
    (root / "econ201").mkdir(parents=True)

    shutil.copy(
        fixtures_dir / "sample_reading.pdf",
        root / "bio101" / "cell_respiration" / "reading.pdf",
    )
    shutil.copy(
        fixtures_dir / "sample_slides.pptx",
        root / "econ201" / "slides.pptx",
    )
    return root


def test_build_index_walks_course_topic_layout(data_root):
    index = build_index(data_root)
    assert index.errors == []
    assert set(index.courses) == {"bio101", "econ201"}

    bio_chunks = index.for_course("bio101")
    assert all(c.topic == "cell_respiration" for c in bio_chunks)

    econ_chunks = index.for_course("econ201")
    assert all(c.topic == "general" for c in econ_chunks)


def test_build_index_missing_root_raises(tmp_path):
    with pytest.raises(IngestError):
        build_index(tmp_path / "does-not-exist")


def test_build_index_records_per_file_errors_without_aborting(data_root):
    bad_dir = data_root / "bio101" / "broken"
    bad_dir.mkdir()
    (bad_dir / "empty.txt").write_text("   ")

    index = build_index(data_root)
    assert len(index.errors) == 1
    assert "empty.txt" in index.errors[0]
    # the good files still got ingested despite the bad one
    assert len(index.chunks) > 0


def test_index_json_round_trip(data_root, tmp_path):
    index = build_index(data_root)
    out_path = tmp_path / "content_index.json"
    index.write(out_path)

    loaded = ContentIndex.load(out_path)
    assert len(loaded.chunks) == len(index.chunks)
    assert [c.chunk_id for c in loaded.chunks] == [c.chunk_id for c in index.chunks]
    assert loaded.courses == index.courses
