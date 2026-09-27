import shutil
from datetime import date

from graph.packet_only import run_reading_only
from graph.syllabus import load_schedule, syllabus_view
from ingest.models import ContentIndex

SCHEDULE = """\
courses:
  MOS 2320:
    - week: 1
      starts: 2026-09-07
      topic: Intro
      items:
        - title: Lecture 1
          files: [lec1.pdf]
        - title: Read Ch. 1 in Connect
    - week: 2
      starts: 2026-09-14
      label: Unit 2
      summary: "  Markets and demand.  "
      items:
        - title: Lecture 2
          files: [lec2.pdf]
        - title: Lecture 2
          files: [lec2.pdf, lec3.pdf]
        - Watch the film
    - week: 3
      starts: 2026-09-28
      items: []
"""


def _index(make_chunk, *files):
    index = ContentIndex()
    for name in files:
        index.chunks.append(make_chunk(source_file=name, course="MOS 2320"))
    return index


def _schedule(tmp_path, text=SCHEDULE):
    path = tmp_path / "schedule.yaml"
    path.write_text(text)
    return load_schedule(path)


def test_current_week_and_earlier_items(tmp_path, make_chunk):
    index = _index(make_chunk, "lec1.pdf", "lec2.pdf")

    [view] = syllabus_view(_schedule(tmp_path), index, date(2026, 9, 16))

    assert (view["course"], view["week"], view["label"]) == ("MOS 2320", 2, "Unit 2")
    # A week runs until the next one starts, so week 2 absorbs the gap week.
    assert (view["starts"], view["ends"]) == ("2026-09-14", "2026-09-27")
    assert view["summary"] == "Markets and demand."
    assert view["items"] == [
        {"id": "mos-2320--w2--lecture-2", "title": "Lecture 2", "state": "in_drive"},
        {"id": "mos-2320--w2--lecture-2-2", "title": "Lecture 2", "state": "missing"},
        {"id": "mos-2320--w2--watch-the-film", "title": "Watch the film", "state": "offline"},
    ]
    assert view["earlier"] == [
        {"id": "mos-2320--w1--lecture-1", "title": "Lecture 1", "state": "in_drive",
         "week": 1, "label": "Week 1"},
        {"id": "mos-2320--w1--read-ch-1-in-connect", "title": "Read Ch. 1 in Connect",
         "state": "offline", "week": 1, "label": "Week 1"},
    ]


def test_ids_are_stable_across_days(tmp_path, make_chunk):
    schedule = _schedule(tmp_path)
    monday = syllabus_view(schedule, _index(make_chunk), date(2026, 9, 14))[0]["items"]
    friday = syllabus_view(schedule, _index(make_chunk, "lec2.pdf"), date(2026, 9, 18))[0]["items"]
    assert [i["id"] for i in monday] == [i["id"] for i in friday]


def test_outside_the_schedule_shows_nothing(tmp_path, make_chunk):
    schedule = _schedule(tmp_path)
    index = _index(make_chunk)
    assert syllabus_view(schedule, index, date(2026, 9, 6)) == []
    assert syllabus_view(schedule, index, date(2026, 10, 5)) == []  # after the last week
    assert syllabus_view(schedule, index, date(2026, 10, 4))[0]["week"] == 3


def test_missing_schedule_is_empty_not_a_warning(tmp_path):
    schedule = load_schedule(tmp_path / "nope.yaml")
    assert schedule.courses == {} and schedule.warnings == []


def test_broken_schedule_warns_and_is_ignored(tmp_path):
    schedule = _schedule(tmp_path, SCHEDULE.replace("starts: 2026-09-14", "starts: 2026-09-01"))
    assert schedule.courses == {}
    assert "date order" in schedule.warnings[0]
    assert "schedule.yaml ignored" in _schedule(tmp_path, "courses: [1]").warnings[0]


def test_packet_carries_syllabus_and_schedule_warnings(tmp_path, fixtures_dir):
    data = tmp_path / "data"
    (data / "C").mkdir(parents=True)
    shutil.copy(fixtures_dir / "sample_notes.md", data / "C" / "notes.md")
    courses = tmp_path / "courses.yaml"
    courses.write_text("courses:\n  - name: C\n    midterm_date: 2026-10-20\n")
    schedule = tmp_path / "schedule.yaml"
    schedule.write_text(
        "courses:\n  C:\n    - week: 1\n      starts: 2026-09-28\n"
        "      items:\n        - {title: Notes, files: [notes.md]}\n"
    )

    _, packet = run_reading_only(data, courses, tmp_path / "p.json", date(2026, 9, 28), schedule)
    assert packet["syllabus"][0]["items"] == [{"id": "c--w1--notes", "title": "Notes", "state": "in_drive"}]

    schedule.write_text("courses: nope")
    _, packet = run_reading_only(data, courses, tmp_path / "p2.json", date(2026, 9, 28), schedule)
    assert packet["syllabus"] == []
    assert any("schedule.yaml ignored" in w for w in packet["warnings"])
