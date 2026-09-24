"""pacing_agent — decides new-today vs. due-for-review, per chunk.

Deterministic and inspectable per CLAUDE.md: "start with a fixed
first-pass + N-review-pass cadence before anything adaptive." No
call_model() involvement. It does estimate how many requests today's
assignment will cost (same batching as the agents) to keep within the
daily request budget.

Persisted state (data/pacing_state.json, gitignored — personal, same as
the rest of data/) tracks, per chunk_id, the date it was first assigned
and the dates it's been reviewed on. That's what makes "due for review"
possible across daily runs without redoing today's whole history.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ingest.models import Chunk

from ..cache import load_cache
from ..state import PipelineState
from .batching import estimated_requests

# Fixed review cadence: N days after first-seen. Simple, debuggable,
# matches CLAUDE.md's "start simple" convention — not spaced-repetition
# optimization.
REVIEW_OFFSETS_DAYS = (1, 3, 7, 14)

# New material is introduced within this many days of first appearing (or
# by the exam, if that's sooner) rather than spread all the way to the
# exam. Material keeps arriving through the term, so spreading to the exam
# only sees today's corpus: early weeks run light and each upload gets
# smeared across months. This keeps study in step with lectures.
NEW_MATERIAL_WINDOW_DAYS = 7


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


def _natural_key(text: str) -> list[object]:
    """Sort key where digit runs compare numerically: week2 < week10."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def _course_order(chunk: Chunk) -> tuple[list[object], int]:
    # `order` restarts at 0 in every source file (ingest/chunk.py), so it is
    # only meaningful within a file. Filename order is the proxy for teaching
    # order across files, which assumes names like lecture-01.pdf.
    return (_natural_key(chunk.source_file), chunk.order)


def pacing_agent(
    state: PipelineState,
    exam_dates: dict[str, date],
    pacing_state_path: Path,
    today: date | None = None,
    cache_path: Path | None = None,
    request_budget: int | None = None,
) -> PipelineState:
    """request_budget caps today's model requests (config budget.daily_request_budget).
    If today's new material would cost more than that, courses get the
    budget in order of nearest exam first. The rest are deferred: they stay
    "new" for tomorrow, with a pacing note saying so. Reviews always go
    ahead, since they're normally served from the generation cache for free.
    None means no cap.
    """
    today = today or date.today()
    state["exam_dates"] = exam_dates
    pacing_state = _load_pacing_state(pacing_state_path)
    cache = load_cache(cache_path) if cache_path else {}

    notes: list[str] = []
    warnings: list[str] = []
    candidates: dict[str, list[Chunk]] = {}  # course -> today's new-chunk quota
    reviews: dict[str, list[Chunk]] = {}
    not_yet_new: dict[str, list[Chunk]] = {}  # course -> every unintroduced chunk
    spread_note: dict[str, str] = {}

    for course in state["content_index"].courses:
        chunks = sorted(state["content_index"].for_course(course), key=_course_order)
        exam_date = exam_dates.get(course)
        if exam_date is None:
            notes.append(f"{course}: no exam date known — skipping pacing for this course")
            continue

        days_remaining = max((exam_date - today).days, 1)
        window_days = min(days_remaining, NEW_MATERIAL_WINDOW_DAYS)
        new_chunks = [c for c in chunks if c.chunk_id not in pacing_state]
        # Spread new material evenly across the window.
        new_today_budget = math.ceil(len(new_chunks) / window_days) if new_chunks else 0
        candidates[course] = new_chunks[:new_today_budget]
        not_yet_new[course] = new_chunks
        spread_note[course] = (
            f"{len(new_chunks)} new chunks left, spread over {window_days} days "
            f"({days_remaining} to {exam_date.isoformat()})"
        )

        reviews[course] = []
        for chunk in chunks:
            cps = pacing_state.get(chunk.chunk_id)
            if cps is not None and _next_review_due(cps, today):
                cps.reviewed_on.append(today)
                reviews[course].append(chunk)
                notes.append(
                    f"{course} {chunk.chunk_id}: due for review "
                    f"(pass {len(cps.reviewed_on)}/{len(REVIEW_OFFSETS_DAYS)})"
                )

    accepted: dict[str, list[Chunk]] = {course: [] for course in candidates}

    def assemble() -> list[Chunk]:
        # One fixed order (course index order, new before reviews) so the
        # cost estimate batches exactly as the agents will.
        return [c for course in candidates for c in accepted[course] + reviews[course]]

    def cost() -> int:
        new_ids = {c.chunk_id for chunks in accepted.values() for c in chunks}
        return estimated_requests(assemble(), new_ids, cache, pool)

    # Nearest exam first, so a squeeze defers the material with the most slack.
    by_urgency = sorted(candidates, key=lambda course: (exam_dates[course], course))
    # Everything not yet introduced; the agents generate a file's upcoming
    # chunks alongside today's (see batching.with_file_companions).
    pool = [c for course in by_urgency for c in not_yet_new[course]]
    for course in by_urgency:
        for i, chunk in enumerate(candidates[course]):
            accepted[course].append(chunk)
            if request_budget is not None and cost() > request_budget:
                accepted[course].pop()
                deferred = len(candidates[course]) - i
                warning = (
                    f"{course}: {deferred} new chunks deferred to tomorrow — "
                    f"over the daily request budget ({request_budget})"
                )
                notes.append(warning)
                warnings.append(warning)
                break  # keep teaching order: nothing later in this course jumps ahead

    new_ids: list[str] = []
    for course in candidates:
        for chunk in accepted[course]:
            pacing_state[chunk.chunk_id] = ChunkPacingState(first_seen=today)
            new_ids.append(chunk.chunk_id)
            notes.append(f"{course} {chunk.chunk_id}: new — {spread_note[course]}")

    introduced = set(new_ids)
    state["assigned_chunks"] = assemble()
    state["new_chunk_ids"] = new_ids
    state["lookahead_chunks"] = [
        c
        for course in by_urgency
        for c in not_yet_new[course]
        if c.chunk_id not in introduced
    ]
    state["pacing_notes"] = notes
    state["pacing_warnings"] = warnings
    _save_pacing_state(pacing_state_path, pacing_state)
    return state
