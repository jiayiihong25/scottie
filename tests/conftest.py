from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def make_chunk():
    """Factory for a Chunk; only the fields a test cares about need passing."""
    from ingest.models import Chunk

    def _make(source_file="f.pdf", order=0, course="C", content_type="conceptual", text="x"):
        return Chunk(
            chunk_id=f"{source_file}#{order}", course=course, topic="t",
            source_file=source_file, source_type="pdf", unit_kind="page",
            unit_start=order + 1, unit_end=order + 1, text=text,
            content_type=content_type, content_type_score=1.0,
            word_count=len(text.split()), order=order,
        )

    return _make
