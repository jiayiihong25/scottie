from datetime import date

import pytest

from graph.__main__ import _load_exam_dates, _load_exams


def _load(tmp_path, text):
    path = tmp_path / "courses.yaml"
    path.write_text(text)
    return _load_exam_dates(path)


def test_unquoted_yaml_date(tmp_path):
    text = "courses:\n  - name: A\n    midterm_date: 2026-10-15\n"
    assert _load(tmp_path, text) == {"A": date(2026, 10, 15)}


def test_quoted_iso_date(tmp_path):
    text = 'courses:\n  - name: A\n    midterm_date: "2026-10-15"\n'
    assert _load(tmp_path, text) == {"A": date(2026, 10, 15)}


def test_confirmed_midterm_beats_worst_case(tmp_path):
    text = (
        "courses:\n  - name: A\n    midterm_date: 2026-10-15\n"
        "    worst_case_date: 2026-10-30\n"
    )
    assert _load(tmp_path, text) == {"A": date(2026, 10, 15)}


def test_worst_case_used_when_midterm_unconfirmed(tmp_path):
    text = "courses:\n  - name: A\n    midterm_date: null\n    worst_case_date: 2026-10-30\n"
    assert _load(tmp_path, text) == {"A": date(2026, 10, 30)}


def test_course_with_no_dates_is_omitted(tmp_path):
    text = "courses:\n  - name: A\n  - name: B\n    midterm_date: 2026-10-15\n"
    assert _load(tmp_path, text) == {"B": date(2026, 10, 15)}


@pytest.mark.parametrize("bad", ['"Oct 15"', '"2026/10/15"', "12", "[2026, 10, 15]"])
def test_garbage_date_raises_naming_the_course(tmp_path, bad):
    text = f"courses:\n  - name: Econ\n    midterm_date: {bad}\n"
    with pytest.raises(ValueError, match="Econ"):
        _load(tmp_path, text)


def test_exams_list_midterms_and_finals_and_skip_missing(tmp_path):
    path = tmp_path / "courses.yaml"
    path.write_text(
        "courses:\n"
        "  - name: A\n    midterm_date: 2026-10-15\n    final_date: \"2026-12-11\"\n"
        "  - name: B\n    midterm_date: null\n    final_date: 2026-12-12\n"
    )
    assert _load_exams(path) == [
        {"course": "A", "name": "Midterm", "date": "2026-10-15"},
        {"course": "A", "name": "Final", "date": "2026-12-11"},
        {"course": "B", "name": "Final", "date": "2026-12-12"},
    ]
