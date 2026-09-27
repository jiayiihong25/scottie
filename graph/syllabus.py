"""Syllabus planner: what the syllabus says you're supposed to be doing
this week. Deterministic, no model calls.

pacing_agent decides what to read at your speed; this doesn't pace
anything. It reads data/schedule.yaml (hand-checked, synced from Drive
next to courses.yaml) and lists, per course, this week's items and every
earlier week's items, each with a stable id. You tick items off on the
Daybook page (its database, collection `syllabus_done`, keyed by that
id), and the page works out what's behind. This side never knows what
you've done. Sent as the packet's `syllabus` field
(scottie-display/docs/scottie-contract.md).

schedule.yaml:

    courses:
      MOS2320:
        - week: 1
          starts: 2026-09-08        # a week runs until the next one starts
          label: Week 1             # optional, default "Week <n>"
        - week: reading-week        # a break: a name instead of a number, no items
          starts: 2026-10-12
          topic: What is marketing? # optional
          summary: ...              # optional, from the syllabus
          items:
            - title: Grewal Ch. 1
              files: [Grewal2026R_PPT_Ch01.pdf]   # names as in Drive
            - title: Read Ch. 1 in Connect         # no files: not a Drive item

Item states say where the material is, not whether it's done:
`in_drive` (every listed file is in Drive), `missing` (a listed file
isn't, so upload it), `offline` (no files listed, e.g. a paywalled
textbook or a film).

An item's id is built from course, week and title, so renaming an item's
title in schedule.yaml clears its tick.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from ingest.models import ContentIndex

IN_DRIVE, MISSING, OFFLINE = "in_drive", "missing", "offline"


@dataclass
class ScheduleItem:
    title: str
    files: list[str] = field(default_factory=list)


@dataclass
class ScheduleWeek:
    week: int
    starts: date
    ends: date
    label: str
    topic: str = ""
    summary: str = ""
    items: list[ScheduleItem] = field(default_factory=list)


@dataclass
class Schedule:
    courses: dict[str, list[ScheduleWeek]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ScheduleError(ValueError):
    pass


def load_schedule(path: Path) -> Schedule:
    """A missing file is an empty schedule (not set up yet). A broken one is
    ignored with a warning: it shouldn't cost the day's reading list.
    """
    path = Path(path)
    if not path.exists():
        return Schedule()
    try:
        return Schedule(courses=_parse(yaml.safe_load(path.read_text(encoding="utf-8"))))
    except (ScheduleError, yaml.YAMLError) as exc:
        return Schedule(warnings=[f"schedule.yaml ignored: {exc}"])


def _parse(raw: object) -> dict[str, list[ScheduleWeek]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("courses"), dict):
        raise ScheduleError("expected a top-level 'courses:' mapping")
    courses = {}
    for course, weeks in raw["courses"].items():
        if not isinstance(weeks, list) or not weeks:
            raise ScheduleError(f"{course}: expected a list of weeks")
        parsed: list[ScheduleWeek] = []
        for i, w in enumerate(weeks):
            parsed.append(_parse_week(course, i, w, parsed[-1].week if parsed else 1))
        for prev, nxt in zip(parsed, parsed[1:]):
            if nxt.starts <= prev.starts:
                raise ScheduleError(f"{course}: weeks must be in date order ({nxt.label})")
            prev.ends = nxt.starts - timedelta(days=1)
        courses[str(course)] = parsed
    return courses


def _parse_week(course: str, i: int, w: object, previous: int) -> ScheduleWeek:
    where = f"{course} week #{i + 1}"
    if not isinstance(w, dict):
        raise ScheduleError(f"{where}: expected a mapping")
    number = w.get("week")
    default_label = f"Week {number}"
    if isinstance(number, str) and number.strip():
        # A break (reading week, exam week): a name instead of a number. It has
        # nothing to tick, and keeps the previous week's number.
        if w.get("items"):
            raise ScheduleError(f"{where}: a week named {number!r} can't have items; number it")
        default_label = number.replace("-", " ").title()
        number = previous
    elif not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ScheduleError(f"{where}: 'week' must be a positive integer, or a name like reading-week")
    starts = _date(w.get("starts"), where)
    items = []
    for j, it in enumerate(w.get("items") or []):
        if isinstance(it, str):
            it = {"title": it}
        if not isinstance(it, dict) or not isinstance(it.get("title"), str):
            raise ScheduleError(f"{where} item #{j + 1}: needs a 'title'")
        files = it.get("files") or []
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            raise ScheduleError(f"{where} item #{j + 1}: 'files' must be a list of file names")
        items.append(ScheduleItem(it["title"], files))
    return ScheduleWeek(
        week=number,
        starts=starts,
        ends=starts + timedelta(days=6),  # the last week; others end where the next starts
        label=str(w.get("label") or default_label),
        topic=str(w.get("topic") or ""),
        summary=str(w.get("summary") or "").strip(),
        items=items,
    )


def _date(value: object, where: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ScheduleError(f"{where}: 'starts' must be YYYY-MM-DD, got {value!r}") from None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].rstrip("-") or "x"


def _items(course: str, week: ScheduleWeek, in_drive: set[str]) -> list[dict]:
    out, seen = [], set()
    for item in week.items:
        item_id = f"{_slug(course)}--w{week.week}--{_slug(item.title)}"
        n = 2
        while item_id in seen:  # two items with the same title in one week
            item_id = f"{_slug(course)}--w{week.week}--{_slug(item.title)}-{n}"
            n += 1
        seen.add(item_id)
        if not item.files:
            state = OFFLINE
        else:
            state = IN_DRIVE if all(f in in_drive for f in item.files) else MISSING
        out.append({"id": item_id, "title": item.title, "state": state})
    return out


def syllabus_view(schedule: Schedule | None, index: ContentIndex, today: date) -> list[dict]:
    """One entry per course that's inside its schedule today, in schedule order."""
    out = []
    for course, weeks in (schedule.courses if schedule else {}).items():
        current = next((w for w in weeks if w.starts <= today <= w.ends), None)
        if current is None:
            continue  # before week 1 or after the last week
        in_drive = {Path(c.source_file).name for c in index.for_course(course)}
        out.append(
            {
                "course": course,
                "week": current.week,
                "label": current.label,
                "starts": current.starts.isoformat(),
                "ends": current.ends.isoformat(),
                "topic": current.topic,
                "summary": current.summary,
                "items": _items(course, current, in_drive),
                "earlier": [
                    {**item, "week": w.week, "label": w.label}
                    for w in weeks
                    if w.ends < today
                    for item in _items(course, w, in_drive)
                ],
            }
        )
    return out
