import json
import shutil
from datetime import date

from graph.packet_only import READING_ONLY_WARNING, run_reading_only, write_packet

TODAY = date(2026, 9, 28)
COURSES = "courses:\n  - name: C\n    midterm_date: 2026-10-20\n    final_date: 2026-12-11\n"


def _setup(tmp_path, fixtures_dir):
    data = tmp_path / "data"
    (data / "C").mkdir(parents=True)
    shutil.copy(fixtures_dir / "sample_notes.md", data / "C" / "notes.md")
    courses = tmp_path / "courses.yaml"
    courses.write_text(COURSES)
    return data, courses, tmp_path / "pacing_state.json"


def test_first_day_is_new_reading_no_questions_or_deck(tmp_path, fixtures_dir):
    data, courses, pacing = _setup(tmp_path, fixtures_dir)

    state, packet = run_reading_only(data, courses, pacing, TODAY)

    assert packet["schema_version"] == 1
    assert packet["date"] == "2026-09-28"
    assert packet["reading"] and all(r["kind"] == "new" for r in packet["reading"])
    assert all(r["source_file"] == "notes.md" for r in packet["reading"])
    assert packet["questions"] == []
    assert packet["deck"] is None
    assert packet["warnings"][-1] == READING_ONLY_WARNING
    assert [e["name"] for e in packet["exams"]] == ["Midterm", "Final"]
    assert state["model_calls"] == []


def test_advances_pacing_so_reviews_come_due(tmp_path, fixtures_dir):
    data, courses, pacing = _setup(tmp_path, fixtures_dir)

    _, first = run_reading_only(data, courses, pacing, TODAY)
    saved = json.loads(pacing.read_text())
    assert len(saved) == len(first["reading"])

    # REVIEW_OFFSETS_DAYS starts at 1: yesterday's new chunks are due today.
    _, next_day = run_reading_only(data, courses, pacing, date(2026, 9, 29))
    assert sum(r["kind"] == "review" for r in next_day["reading"]) == len(first["reading"])


def test_write_packet_drops_stale_delivery_manifest(tmp_path):
    (tmp_path / "delivery.json").write_text("{}")

    path = write_packet({"schema_version": 1}, tmp_path)

    assert json.loads(path.read_text()) == {"schema_version": 1}
    assert not (tmp_path / "delivery.json").exists()
