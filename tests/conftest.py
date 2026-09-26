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


@pytest.fixture
def fake_batch_model(monkeypatch):
    """Stubs batching.call_model with a model that answers every chunk_id
    in the prompt. `fields` maps field name -> value (a callable gets the
    chunk_id). Returns the list of prompts sent, one per request.
    """
    import json
    import re

    from graph.nodes import batching
    from graph.state import ModelCallLog

    def install(**fields):
        prompts = []

        def call_model(task_type, messages, state, **kwargs):
            prompt = messages[0]["content"]
            prompts.append(prompt)
            # Log like the real call_model, so budget accounting sees it.
            state["model_calls"].append(ModelCallLog(task_type, "fake", 0, 0))
            ids = re.findall(r"^### chunk_id: (\S+)", prompt, flags=re.MULTILINE)
            items = {
                i: {k: (v(i) if callable(v) else v) for k, v in fields.items()} for i in ids
            }
            return json.dumps({"summary": f"Summary of {', '.join(ids)}.", "items": items})

        monkeypatch.setattr(batching, "call_model", call_model)
        return prompts

    return install
