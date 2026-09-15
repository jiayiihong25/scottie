"""Assemble the morning packet (HTML) and Anki deck (.apkg)."""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

import genanki

from graph.state import AnkiCardDraft, ConceptQuestion, PipelineState

OUTPUT_DIR = Path("output")

ANKI_MODEL = genanki.Model(
    1607392319,
    "Scottie Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        }
    ],
)


def _build_html(
    questions: list[ConceptQuestion],
    cards: list[AnkiCardDraft],
    pacing_notes: list[str],
    today: date,
) -> str:
    lines = [
        f"<title>Morning Packet — {today.isoformat()}</title>",
        "<style>",
        "  :root { --bg: #fafaf9; --fg: #1c1917; --accent: #2563eb; --muted: #78716c; }",
        "  @media (prefers-color-scheme: dark) { :root:not([data-theme='light']) { --bg: #1c1917; --fg: #fafaf9; --accent: #60a5fa; --muted: #a8a29e; } }",
        "  :root[data-theme='dark'] { --bg: #1c1917; --fg: #fafaf9; --accent: #60a5fa; --muted: #a8a29e; }",
        "  body { background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; max-width: 640px; margin: 0 auto; padding: 16px; }",
        "  h1 { font-size: 1.4rem; } h2 { font-size: 1.1rem; color: var(--accent); margin-top: 2rem; }",
        "  .source { color: var(--muted); font-size: 0.85rem; }",
        "  details { margin: 0.8rem 0; } summary { cursor: pointer; }",
        "  .note { color: var(--muted); font-size: 0.8rem; }",
        "</style>",
        f"<h1>Morning Packet — {today.strftime('%A, %B %d')}</h1>",
    ]

    if questions:
        lines.append("<h2>Concept Questions</h2>")
        for q in questions:
            lines.append(f"<details><summary><strong>{q.course}</strong> — {q.topic}</summary>")
            lines.append(f"<p><strong>Q:</strong> {q.question}</p>")
            lines.append(f"<p><strong>A:</strong> {q.answer}</p>")
            lines.append(f'<p class="source">{q.source_ref}</p>')
            lines.append("</details>")

    if cards:
        lines.append("<h2>Anki Cards Preview</h2>")
        for c in cards:
            lines.append(f"<details><summary><strong>{c.course}</strong> — {c.topic}</summary>")
            lines.append(f"<p><strong>Front:</strong> {c.front}</p>")
            lines.append(f"<p><strong>Back:</strong> {c.back}</p>")
            lines.append(f'<p class="source">{c.source_ref}</p>')
            lines.append("</details>")

    if not questions and not cards:
        lines.append("<p>No new material or reviews due today.</p>")

    if pacing_notes:
        lines.append("<h2>Pacing Log</h2>")
        lines.append("<ul>")
        for n in pacing_notes:
            lines.append(f'<li class="note">{n}</li>')
        lines.append("</ul>")

    return "\n".join(lines)


def _build_apkg(cards: list[AnkiCardDraft], today: date) -> Path | None:
    if not cards:
        return None

    deck = genanki.Deck(2059400110, f"Scottie — {today.isoformat()}")
    for c in cards:
        note = genanki.Note(model=ANKI_MODEL, fields=[c.front, c.back])
        deck.add_note(note)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"scottie_{today.isoformat()}.apkg"
    genanki.Package(deck).write_to_file(str(path))
    return path


def packet_writer(state: PipelineState) -> dict:
    today = date.today()
    questions = state.get("concept_questions", [])
    cards = state.get("anki_cards", [])
    pacing_notes = state.get("pacing_notes", [])
    errors = list(state.get("errors", []))

    html = _build_html(questions, cards, pacing_notes, today)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    packet_path = OUTPUT_DIR / f"packet_{today.isoformat()}.html"
    packet_path.write_text(html, encoding="utf-8")

    apkg_path = _build_apkg(cards, today)

    if errors:
        html_note = (
            f"\n<!-- {len(errors)} error(s) during this run — "
            f"check logs -->\n"
        )
        with open(packet_path, "a") as f:
            f.write(html_note)

    return {
        "packet_path": packet_path,
        "apkg_path": apkg_path,
    }
