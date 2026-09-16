"""Manual pipeline run: python -m graph [--data-root data] [--out output]

Reads exam dates from data/courses.yaml (personal, gitignored — synced
from the Drive courses.yaml, same convention as course material under
data/). A course with no confirmed midterm_date but a stated exam window
falls back to worst_case_date, which must be filled in by hand until the
real date is posted.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import yaml

from .build import run_pipeline


def _load_exam_dates(courses_yaml: Path) -> dict[str, date]:
    data = yaml.safe_load(courses_yaml.read_text())
    exam_dates = {}
    for course in data["courses"]:
        name = course["name"]
        midterm = course.get("midterm_date")
        worst_case = course.get("worst_case_date")
        chosen = midterm or worst_case
        if chosen is None:
            continue  # pacing_agent logs a pacing_note and skips this course
        exam_dates[name] = date.fromisoformat(chosen)
    return exam_dates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data", type=Path)
    parser.add_argument("--courses", default="data/courses.yaml", type=Path)
    parser.add_argument("--pacing-state", default="data/pacing_state.json", type=Path)
    parser.add_argument("--out", default="output", type=Path)
    args = parser.parse_args()

    exam_dates = _load_exam_dates(args.courses)
    state = run_pipeline(args.data_root, exam_dates, args.pacing_state, args.out)

    print(f"Assigned {len(state['assigned_chunks'])} chunks")
    print(f"  concept questions: {len(state['concept_questions'])}")
    print(f"  anki cards: {len(state['anki_cards'])}")
    for note in state["pacing_notes"]:
        print(f"  - {note}")
    print(f"Packet: {state['packet_path']}")
    print(f"Deck:   {state['apkg_path']}")


if __name__ == "__main__":
    main()
