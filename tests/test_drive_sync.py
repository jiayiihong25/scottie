from pathlib import Path

import pytest

from drive_sync.sync import FOLDER_MIME, DriveItem, DriveSyncError, pull, push


class FakeDrive:
    """tree: folder_id -> list[DriveItem]; blobs: file_id -> bytes."""

    def __init__(self, tree, blobs):
        self.tree, self.blobs, self.updated = tree, blobs, {}

    def list_children(self, folder_id):
        return self.tree.get(folder_id, [])

    def download(self, file_id, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.blobs[file_id])

    def update_content(self, file_id, src: Path):
        self.updated[file_id] = src.read_bytes()


def _f(id, name, mime="text/plain"):
    return DriveItem(id, name, mime)


def _d(id, name):
    return DriveItem(id, name, FOLDER_MIME)


def _drive(root_extra=()):
    tree = {
        "root": [
            _f("y", "courses.yaml"),
            _d("c1", "PHIL"),
            _d("intake", "_syllabi_intake"),
            _f("readme", "README"),
            *root_extra,
        ],
        "c1": [_f("a", "lec1.pdf", "application/pdf"), _d("t1", "week 2"), _f("z", "notes.docx", "x")],
        "t1": [_f("b", "lec2.txt")],
        "intake": [_f("s", "syllabus.pdf", "application/pdf")],
    }
    blobs = {k: k.encode() for k in ("y", "a", "b", "s", "sp", "au")}
    return FakeDrive(tree, blobs)


def test_pull_lays_out_course_topic_file_and_skips_underscore_folders(tmp_path):
    warnings = pull(_drive(), "root", tmp_path)

    assert (tmp_path / "courses.yaml").exists()
    assert (tmp_path / "PHIL" / "lec1.pdf").exists()
    assert (tmp_path / "PHIL" / "week 2" / "lec2.txt").exists()
    assert not (tmp_path / "_syllabi_intake").exists()
    assert not (tmp_path / "README").exists()
    assert any("notes.docx" in w for w in warnings)  # unsupported type is reported


def test_pull_downloads_state_files_when_present(tmp_path):
    drive = _drive([_f("sp", "pacing_state.json"), _f("au", "artifact_url.txt")])
    pull(drive, "root", tmp_path)
    assert (tmp_path / "pacing_state.json").read_bytes() == b"sp"
    assert (tmp_path / "artifact_url.txt").read_bytes() == b"au"


def test_missing_courses_yaml_is_fatal(tmp_path):
    drive = FakeDrive({"root": [_d("c1", "PHIL")], "c1": [_f("a", "x.pdf")]}, {"a": b"a"})
    with pytest.raises(DriveSyncError, match="courses.yaml"):
        pull(drive, "root", tmp_path)


def test_no_course_material_is_fatal(tmp_path):
    drive = FakeDrive({"root": [_f("y", "courses.yaml")]}, {"y": b"y"})
    with pytest.raises(DriveSyncError, match="no course material"):
        pull(drive, "root", tmp_path)


def test_slash_in_drive_name_cannot_escape_data_root(tmp_path):
    drive = FakeDrive(
        {"root": [_f("y", "courses.yaml"), _d("c", "C")], "c": [_f("a", "../../evil.txt")]},
        {"y": b"y", "a": b"a"},
    )
    pull(drive, "root", tmp_path / "data")
    assert not (tmp_path / "evil.txt").exists()
    assert (tmp_path / "data" / "C" / ".._.._evil.txt").exists()


def test_duplicate_names_are_both_kept(tmp_path):
    drive = FakeDrive(
        {"root": [_f("y", "courses.yaml"), _d("c", "C")],
         "c": [_f("aaaaaa1", "a.txt"), _f("bbbbbb2", "a.txt")]},
        {"y": b"y", "aaaaaa1": b"1", "bbbbbb2": b"2"},
    )
    pull(drive, "root", tmp_path)
    assert sorted(p.name for p in (tmp_path / "C").iterdir()) == ["a (bbbbbb).txt", "a.txt"]


def test_push_updates_existing_state_files_only(tmp_path):
    (tmp_path / "pacing_state.json").write_text("{}")
    drive = _drive([_f("sp", "pacing_state.json"), _f("au", "artifact_url.txt")])

    push(drive, "root", tmp_path)

    assert drive.updated == {"sp": b"{}"}  # artifact_url.txt absent locally -> untouched


def test_push_without_drive_placeholder_fails_loudly(tmp_path):
    (tmp_path / "pacing_state.json").write_text("{}")
    with pytest.raises(DriveSyncError, match="placeholder"):
        push(_drive(), "root", tmp_path)
