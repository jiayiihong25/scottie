"""CLI entry point: python -m graph [--courses-yaml path]"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

from graph.build import run_sequential


def _load_courses_yaml(path: Path) -> tuple[dict[str, date], dict]:
    if not path.exists():
        print(f"Warning: {path} not found, running without exam dates", file=sys.stderr)
        return {}, {}

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    exam_dates: dict[str, date] = {}
    courses_config: dict = {}

    for course, info in data.items():
        if not isinstance(info, dict):
            continue
        courses_config[course] = info
        exams = info.get("exams", {})
        if isinstance(exams, dict):
            for exam_name, exam_date in exams.items():
                key = f"{course}/{exam_name}"
                if isinstance(exam_date, date):
                    exam_dates[key] = exam_date
                elif isinstance(exam_date, str) and "PLACEHOLDER" not in exam_date:
                    try:
                        exam_dates[key] = date.fromisoformat(exam_date)
                    except ValueError:
                        pass

    return exam_dates, courses_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Scottie daily brief pipeline")
    parser.add_argument(
        "--courses-yaml",
        type=Path,
        default=Path("config/courses.yaml"),
        help="Path to courses.yaml with exam dates",
    )
    args = parser.parse_args()

    exam_dates, courses_config = _load_courses_yaml(args.courses_yaml)

    print("Running Scottie daily brief pipeline...")
    state = run_sequential(exam_dates=exam_dates, courses_config=courses_config)

    errors = state.get("errors", [])
    questions = state.get("concept_questions", [])
    cards = state.get("anki_cards", [])
    packet = state.get("packet_path")
    apkg = state.get("apkg_path")

    print(f"\nResults:")
    print(f"  Chunks assigned: {len(state.get('assigned_chunks', []))}")
    print(f"  Concept questions: {len(questions)}")
    print(f"  Anki cards: {len(cards)}")
    print(f"  Packet: {packet}")
    print(f"  Anki deck: {apkg}")

    if errors:
        print(f"\n  {len(errors)} error(s):")
        for e in errors:
            print(f"    - {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
