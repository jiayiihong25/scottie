"""pacing_agent — decides new-today vs. due-for-review, per chunk.

Deterministic and inspectable per CLAUDE.md: "start with a fixed
first-pass + N-review-pass cadence before anything adaptive." No
call_model() involvement.

Persisted state (data/pacing_state.json, gitignored — personal, same as
the rest of data/) tracks, per chunk_id, the date it was first assigned
and the dates it's been reviewed on. That's what makes "due for review"
possible across daily runs without redoing today's whole history.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ingest.models import Chunk

from ..state import PipelineState

# Fixed review cadence: N days after first-seen. Simple, debuggable,
# matches CLAUDE.md's "start simple" convention — not spaced-repetition
# optimization.
REVIEW_OFFSETS_DAYS = (1, 3, 7, 14)


@dataclass
class ChunkPacingState:
    first_seen: date
    reviewed_on: list[date] = field(default_factory=list)


def _load_pacing_state(path: Path) -> dict[str, ChunkPacingState]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {
        chunk_id: ChunkPacingState(
            first_seen=date.fromisoformat(v["first_seen"]),
            reviewed_on=[date.fromisoformat(d) for d in v["reviewed_on"]],
        )
        for chunk_id, v in raw.items()
    }


def _save_pacing_state(path: Path, pacing_state: dict[str, ChunkPacingState]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        chunk_id: {
            "first_seen": v.first_seen.isoformat(),
            "reviewed_on": [d.isoformat() for d in v.reviewed_on],
        }
        for chunk_id, v in pacing_state.items()
    }
    path.write_text(json.dumps(raw, indent=2) + "\n")


def _next_review_due(cps: ChunkPacingState, today: date) -> bool:
    """True if today is on/after the next unreviewed offset from first_seen."""
    n_done = len(cps.reviewed_on)
    if n_done >= len(REVIEW_OFFSETS_DAYS):
        return False  # cadence exhausted, chunk is "graduated"
    due_date = cps.first_seen + timedelta(days=REVIEW_OFFSETS_DAYS[n_done])
    return today >= due_date


def pacing_agent(
    state: PipelineState,
    exam_dates: dict[str, date],
    pacing_state_path: Path,
    today: date | None = None,
) -> PipelineState:
    today = today or date.today()
    state["exam_dates"] = exam_dates
    pacing_state = _load_pacing_state(pacing_state_path)

    assigned: list[Chunk] = []
    notes: list[str] = []

    for course in state["content_index"].courses:
        chunks = sorted(state["content_index"].for_course(course), key=lambda c: c.order)
        exam_date = exam_dates.get(course)
        if exam_date is None:
            notes.append(f"{course}: no exam date known — skipping pacing for this course")
            continue

        days_remaining = max((exam_date - today).days, 1)
        new_chunks = [c for c in chunks if c.chunk_id not in pacing_state]
        # Spread remaining new material evenly across remaining days.
        new_today_budget = math.ceil(len(new_chunks) / days_remaining) if new_chunks else 0

        new_today = new_chunks[:new_today_budget]
        for chunk in new_today:
            pacing_state[chunk.chunk_id] = ChunkPacingState(first_seen=today)
            assigned.append(chunk)
            notes.append(
                f"{course} {chunk.chunk_id}: new — {len(new_chunks)} new chunks left, "
                f"{days_remaining} days to {exam_date.isoformat()}"
            )

        for chunk in chunks:
            cps = pacing_state.get(chunk.chunk_id)
            if cps is None or chunk in new_today:
                continue
            if _next_review_due(cps, today):
                cps.reviewed_on.append(today)
                assigned.append(chunk)
                notes.append(
                    f"{course} {chunk.chunk_id}: due for review "
                    f"(pass {len(cps.reviewed_on)}/{len(REVIEW_OFFSETS_DAYS)})"
                )

    state["assigned_chunks"] = assigned
    state["pacing_notes"] = notes
    _save_pacing_state(pacing_state_path, pacing_state)
    return state
