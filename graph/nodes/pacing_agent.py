"""Deterministic pacing — decides which chunks to study today.

Review-state tracking: a JSON file (`data/review_state.json`) persists
what's been shown and when. On each run the pacing agent:
  1. Loads review state (or starts fresh).
  2. Introduces NEW_PER_DAY unseen chunks per course.
  3. Pulls back chunks due for spaced review (intervals: 1, 3, 7, 14, 30 days).
  4. Respects final_cumulative — if false, pre-midterm chunks stop
     reviewing after the midterm passes.
  5. Saves updated state back.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from ingest.models import Chunk, ContentIndex
from graph.state import PipelineState

REVIEW_STATE_PATH = Path("data/review_state.json")
NEW_PER_DAY = 5
REVIEW_INTERVALS = [1, 3, 7, 14, 30]


def _load_review_state(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_review_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, default=str) + "\n", encoding="utf-8"
    )


def _parse_exam_dates(raw: dict[str, str | date]) -> dict[str, date]:
    out = {}
    for course, d in raw.items():
        if isinstance(d, date):
            out[course] = d
        else:
            out[course] = date.fromisoformat(str(d))
    return out


def _chunk_is_reviewable(
    chunk: Chunk,
    today: date,
    exam_dates: dict[str, date],
    courses_config: dict,
) -> bool:
    """Check if a chunk should still be in the review rotation."""
    course_cfg = courses_config.get(chunk.course, {})
    final_cumulative = course_cfg.get("final_cumulative", True)

    if final_cumulative is None:
        final_cumulative = True

    if final_cumulative:
        return True

    midterm_dates = [
        date.fromisoformat(str(d))
        for name, d in exam_dates.items()
        if name.startswith(chunk.course) and "midterm" in name.lower()
    ]
    if not midterm_dates:
        return True

    latest_midterm = max(midterm_dates)
    if today <= latest_midterm:
        return True

    return False


def pacing_agent(state: PipelineState) -> dict:
    today = date.today()
    content_index: ContentIndex = state["content_index"]
    exam_dates = state.get("exam_dates", {})
    courses_config = state.get("courses_config", {})

    review_state = _load_review_state(REVIEW_STATE_PATH)
    assigned: list[Chunk] = []
    notes: list[str] = []

    for course in content_index.courses:
        course_chunks = content_index.for_course(course)

        seen_ids = {
            cid
            for cid, info in review_state.items()
            if info.get("course") == course
        }
        unseen = [c for c in course_chunks if c.chunk_id not in seen_ids]
        new_today = unseen[:NEW_PER_DAY]

        for chunk in new_today:
            assigned.append(chunk)
            review_state[chunk.chunk_id] = {
                "course": chunk.course,
                "first_seen": str(today),
                "last_reviewed": str(today),
                "review_count": 0,
            }
            notes.append(
                f"NEW: {chunk.course}/{chunk.topic} {chunk.unit_range}"
            )

        for cid, info in review_state.items():
            if info.get("course") != course:
                continue
            if cid in {c.chunk_id for c in new_today}:
                continue

            last = date.fromisoformat(info["last_reviewed"])
            count = info.get("review_count", 0)
            interval_idx = min(count, len(REVIEW_INTERVALS) - 1)
            due_date = last + timedelta(days=REVIEW_INTERVALS[interval_idx])

            if today < due_date:
                continue

            matching = [c for c in course_chunks if c.chunk_id == cid]
            if not matching:
                continue
            chunk = matching[0]

            if not _chunk_is_reviewable(
                chunk, today, exam_dates, courses_config
            ):
                notes.append(
                    f"SKIP (post-midterm wind-down): {chunk.course}/{chunk.topic}"
                )
                continue

            assigned.append(chunk)
            info["last_reviewed"] = str(today)
            info["review_count"] = count + 1
            notes.append(
                f"REVIEW (pass {count + 1}): {chunk.course}/{chunk.topic} "
                f"{chunk.unit_range}"
            )

    _save_review_state(REVIEW_STATE_PATH, review_state)

    return {
        "assigned_chunks": assigned,
        "pacing_notes": notes,
    }
