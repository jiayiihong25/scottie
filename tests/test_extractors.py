import pytest

from ingest import extractors
from ingest.errors import EmptyExtractionError, UnsupportedFormatError


def test_pdf_extract_one_unit_per_page(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    assert doc.source_type == "pdf"
    assert doc.unit_kind == "page"
    assert len(doc.units) == 3
    assert doc.units[0].number == 1
    assert "Cellular respiration" in doc.units[0].text


def test_pdf_strips_page_number_artifacts(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    for unit in doc.units:
        # the page-number footer we drew ("1", "2", "3") must not survive
        # as its own line
        lines = unit.text.splitlines()
        assert not any(line.strip().isdigit() for line in lines)


def test_pdf_detects_heading(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_reading.pdf")
    assert doc.units[0].heading == "Chapter 3: Cellular Respiration"
    assert doc.units[1].heading == "Key Terms"


def test_slides_extract_one_unit_per_slide(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_slides.pptx")
    assert doc.source_type == "slides"
    assert doc.unit_kind == "slide"
    assert len(doc.units) == 3
    assert doc.units[0].heading == "Supply and Demand"
    assert "Equilibrium" in doc.units[0].text


def test_notes_split_into_sections(fixtures_dir):
    doc = extractors.extract(fixtures_dir / "sample_notes.md")
    assert doc.source_type == "notes"
    assert doc.unit_kind == "section"
    headings = [u.heading for u in doc.units]
    assert headings == [
        "Weathering and Erosion",
        "Key Terms",
        "Comparing Weathering Types",
    ]


def test_unsupported_format_raises(tmp_path):
    bad = tmp_path / "lecture.docx"
    bad.write_text("hello")
    with pytest.raises(UnsupportedFormatError):
        extractors.extract(bad)


def test_notes_with_no_text_raises(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n\n  ")
    with pytest.raises(EmptyExtractionError):
        extractors.extract(empty)
