"""Reading-only run: python -m graph.packet_only [--data-root data] [--out output]

Writes daybook's packet.json and knowledge.json
(scottie-display/docs/scottie-contract.md) from ingest + pacing alone. No model calls, so no OmniRoute: questions
are [] and deck is null. Stopgap until the full pipeline (python -m graph)
runs daily.

Advances pacing: today's new chunks are marked first-seen and today's due
reviews are recorded in --pacing-state, exactly as a full run would. Push
that file back to Drive (python -m drive_sync push) only after the packet
has been delivered. --dry-run prints the same assignment without saving
pacing state or writing packet.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from .__main__ import _load_exam_dates, _load_exams
from .knowledge import write_knowledge
from .nodes.ingest_node import ingest_node
from .nodes.pacing_agent import pacing_agent
from .nodes.packet_writer import _DAYBOOK_PACKET_NAME, _MANIFEST_NAME, _daybook_packet
from .state import PipelineState, new_state
from .syllabus import load_schedule

READING_ONLY_WARNING = (
    "Concept questions and flashcards not generated yet (reading-only mode)."
)


def run_reading_only(
    data_root: Path,
    courses_yaml: Path,
    pacing_state_path: Path,
    today: date | None = None,
    schedule_path: Path | None = None,
) -> tuple[PipelineState, dict]:
    """Returns the pipeline state and the packet dict. Saves pacing state."""
    today = today or date.today()
    state = new_state()
    state["exams"] = _load_exams(courses_yaml)
    state["schedule"] = load_schedule(schedule_path) if schedule_path else None
    state = ingest_node(state, data_root)
    # request_budget=None: the budget caps model requests, and this run makes none.
    state = pacing_agent(state, _load_exam_dates(courses_yaml, today), pacing_state_path, today)
    packet = _daybook_packet(state, today)
    packet["warnings"].append(READING_ONLY_WARNING)
    return state, packet


def write_packet(packet: dict, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # A delivery.json left by an earlier full run would tell the Routine to
    # deliver that day's packet and deck again.
    (output_dir / _MANIFEST_NAME).unlink(missing_ok=True)
    path = output_dir / _DAYBOOK_PACKET_NAME
    path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data", type=Path)
    parser.add_argument("--courses", default="data/courses.yaml", type=Path)
    parser.add_argument("--pacing-state", default="data/pacing_state.json", type=Path)
    parser.add_argument("--schedule", default="data/schedule.yaml", type=Path)
    parser.add_argument("--out", default="output", type=Path)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="show today's assignment without saving pacing state or writing packet.json",
    )
    args = parser.parse_args()

    if args.dry_run:
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "pacing_state.json"
            if args.pacing_state.exists():
                shutil.copy(args.pacing_state, scratch)
            state, packet = run_reading_only(args.data_root, args.courses, scratch, schedule_path=args.schedule)
    else:
        state, packet = run_reading_only(
            args.data_root, args.courses, args.pacing_state, schedule_path=args.schedule
        )

    new_ids = set(state["new_chunk_ids"])
    print(f"Assigned {len(state['assigned_chunks'])} chunks ({len(new_ids)} new)")
    for c in state["assigned_chunks"]:
        kind = "new   " if c.chunk_id in new_ids else "review"
        print(f"  {kind} {c.course:<14} {Path(c.source_file).name} ({c.unit_range})")
    for w in packet["warnings"]:
        print(f"  ! {w}")

    if args.dry_run:
        print("Dry run: pacing state not saved, packet.json not written")
    else:
        print(f"Packet: {write_packet(packet, args.out)}")
        print(f"Knowledge: {write_knowledge(state['content_index'], args.out, date.fromisoformat(packet['date']))}")
        print(f"Pacing advanced in {args.pacing_state} (push it after delivering)")


if __name__ == "__main__":
    main()
