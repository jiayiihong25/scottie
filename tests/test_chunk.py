from ingest import extractors
from ingest.chunk import chunk_document


def test_chunks_never_split_a_unit(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    chunks = chunk_document(doc, course="bio101", topic="cell_respiration", target_words=10)
    # target_words is tiny, so every unit should end up as its own chunk,
    # never a fragment smaller than one page
    for chunk in chunks:
        assert chunk.unit_end >= chunk.unit_start
        matching_units = [u for u in doc.units if chunk.unit_start <= u.number <= chunk.unit_end]
        assert "".join(u.text for u in matching_units) != ""


def test_chunks_cover_every_unit_exactly_once(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    chunks = chunk_document(doc, course="bio101", topic="cell_respiration")
    covered = []
    for chunk in chunks:
        covered.extend(range(chunk.unit_start, chunk.unit_end + 1))
    assert covered == [u.number for u in doc.units]


def test_chunk_id_stable_across_reingestion(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    chunks_a = chunk_document(doc, course="bio101", topic="x")
    chunks_b = chunk_document(doc, course="bio101", topic="x")
    assert [c.chunk_id for c in chunks_a] == [c.chunk_id for c in chunks_b]


def test_chunk_id_independent_of_course_topic(fixtures_dir):
    # pacing state is keyed by chunk_id; re-tagging a course/topic in config
    # should not orphan review history for the same underlying content.
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    chunks_a = chunk_document(doc, course="bio101", topic="unit1")
    chunks_b = chunk_document(doc, course="bio101-renamed", topic="unit2")
    assert [c.chunk_id for c in chunks_a] == [c.chunk_id for c in chunks_b]


def test_content_type_assigned_per_chunk(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    chunks = chunk_document(doc, course="bio101", topic="x")
    assert all(c.content_type in ("conceptual", "memorization") for c in chunks)


def test_unit_range_formatting(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    chunks = chunk_document(doc, course="bio101", topic="x", target_words=10000)
    assert len(chunks) == 1
    assert chunks[0].unit_range == "pages 1-3"
