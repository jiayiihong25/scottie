"""packet_writer — deterministic. Assembles the reading list + concept
questions into the morning-packet HTML and the Anki cards into an .apkg
via genanki. No LLM involvement.

Per docs/orchestration-design.md ("Partial participation"): a concept-only
day producing zero Anki cards (or vice versa) is valid, not a failure —
this must not assume either list is non-empty.
"""

from __future__ import annotations

from pathlib import Path

import genanki

from ..state import PipelineState

# Stable IDs so re-generating the deck doesn't create a duplicate deck in
# Anki on import — genanki requires fixed model/deck ids.
_ANKI_MODEL_ID = 1607392319
_ANKI_DECK_ID = 2059400110

_ANKI_MODEL = genanki.Model(
    _ANKI_MODEL_ID,
    "Exam Prep Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        }
    ],
)


def packet_writer(state: PipelineState, output_dir: Path) -> PipelineState:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if state["errors"]:
        # Fail loudly per CLAUDE.md — an incomplete run must not produce a
        # packet that looks complete.
        raise RuntimeError(
            f"packet_writer refusing to write output: pending errors {state['errors']!r}"
        )

    packet_path = output_dir / "morning_packet.html"
    packet_path.write_text(_render_packet_html(state))
    state["packet_path"] = packet_path

    if state["anki_cards"]:
        apkg_path = output_dir / "morning_deck.apkg"
        _write_apkg(state, apkg_path)
        state["apkg_path"] = apkg_path
    else:
        state["apkg_path"] = None

    return state


def _render_packet_html(state: PipelineState) -> str:
    chunks_by_id = {c.chunk_id: c for c in state["assigned_chunks"]}

    reading_items = "\n".join(
        f"<li>{chunk.course} — {chunk.source_file} ({chunk.unit_range})</li>"
        for chunk in state["assigned_chunks"]
    )
    question_items = "\n".join(
        f"<li>[{q.course} — {chunks_by_id[q.chunk_id].unit_range}] {q.question}</li>"
        for q in state["concept_questions"]
        if q.chunk_id in chunks_by_id
    )

    reading_section = f"<ul>{reading_items}</ul>" if reading_items else "<p>Nothing new or due today.</p>"
    question_section = (
        f"<ul>{question_items}</ul>" if question_items else "<p>No concept questions today.</p>"
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Morning Packet</title></head>
<body>
<h1>Morning Packet</h1>
<h2>Reading list</h2>
{reading_section}
<h2>Concept questions</h2>
{question_section}
</body></html>
"""


def _write_apkg(state: PipelineState, apkg_path: Path) -> None:
    deck = genanki.Deck(_ANKI_DECK_ID, "Exam Prep")
    for card in state["anki_cards"]:
        deck.add_note(genanki.Note(model=_ANKI_MODEL, fields=[card.front, card.back]))
    genanki.Package(deck).write_to_file(str(apkg_path))
