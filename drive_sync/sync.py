"""pull / push logic against a small DriveClient interface, so it can be
tested without Google. The real client is in client.py.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ingest import extractors

FOLDER_MIME = "application/vnd.google-apps.folder"

# Files the pipeline reads/writes at the Drive folder root.
COURSES_FILE = "courses.yaml"
# generated.json is the generation cache (graph/cache.py). Unlike pacing
# state it's safe to push after a failed run, see push(names=CACHE_FILES).
CACHE_FILES = ("generated.json",)
STATE_FILES = ("pacing_state.json", "artifact_url.txt", *CACHE_FILES)
_ROOT_FILES = (COURSES_FILE, *STATE_FILES)


class DriveSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class DriveItem:
    id: str
    name: str
    mime_type: str

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME


class DriveClient(Protocol):
    def list_children(self, folder_id: str) -> list[DriveItem]: ...
    def download(self, file_id: str, dest: Path) -> None: ...
    def update_content(self, file_id: str, src: Path) -> None: ...


def _safe_name(name: str) -> str:
    # Drive allows "/" in names; never let one become a path separator.
    cleaned = name.replace("/", "_").replace("\\", "_").strip()
    return "_" if cleaned in ("", ".", "..") else cleaned


def _unique(path: Path, file_id: str) -> Path:
    # Drive permits two files with the same name in one folder.
    if not path.exists():
        return path
    return path.with_name(f"{path.stem} ({file_id[:6]}){path.suffix}")


def pull(client: DriveClient, folder_id: str, data_root: Path) -> list[str]:
    """Download the course folder into data_root. Returns warnings.

    Raises DriveSyncError if the folder has no courses.yaml or no course
    material — proceeding on an empty data/ would yield a cheerful
    "nothing due today" packet, the silent failure CLAUDE.md forbids.
    """
    data_root = Path(data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    supported = extractors.supported_extensions()

    root_items = client.list_children(folder_id)
    by_name = {i.name: i for i in root_items if not i.is_folder}

    if COURSES_FILE not in by_name:
        raise DriveSyncError(f"{COURSES_FILE} not found in Drive folder {folder_id}")
    for name in _ROOT_FILES:
        item = by_name.get(name)
        if item is not None:
            client.download(item.id, data_root / name)

    files_downloaded = 0
    for folder in sorted((i for i in root_items if i.is_folder), key=lambda i: i.name):
        if folder.name.startswith("_"):
            continue  # e.g. _syllabi_intake: not a course, ingest would treat it as one
        files_downloaded += _pull_folder(
            client, folder.id, data_root / _safe_name(folder.name), supported, warnings
        )

    if files_downloaded == 0:
        raise DriveSyncError(f"no course material found under Drive folder {folder_id}")
    return warnings


def _pull_folder(
    client: DriveClient,
    folder_id: str,
    dest_dir: Path,
    supported: set[str],
    warnings: list[str],
) -> int:
    count = 0
    for item in client.list_children(folder_id):
        target = dest_dir / _safe_name(item.name)
        if item.is_folder:
            count += _pull_folder(client, item.id, target, supported, warnings)
        elif target.suffix.lower() in supported:
            dest_dir.mkdir(parents=True, exist_ok=True)
            client.download(item.id, _unique(target, item.id))
            count += 1
        else:
            warnings.append(f"skipped {target} — unsupported type ({item.mime_type})")
    return count


def push(
    client: DriveClient,
    folder_id: str,
    data_root: Path,
    names: tuple[str, ...] = STATE_FILES,
) -> None:
    """Write state files (or just `names`) back to their existing Drive copies.

    Update-only on purpose: a service account has no storage quota of its
    own, so it can edit files you created but cannot create new ones in a
    personal My Drive. The placeholders must already exist.
    """
    data_root = Path(data_root)
    by_name = {i.name: i for i in client.list_children(folder_id) if not i.is_folder}
    for name in names:
        src = data_root / name
        if not src.exists():
            continue
        item = by_name.get(name)
        if item is None:
            raise DriveSyncError(
                f"{name} does not exist in Drive folder {folder_id}; create an "
                "empty placeholder there first (the service account can edit "
                "files but not create them)"
            )
        client.update_content(item.id, src)


def print_warnings(warnings: list[str]) -> None:
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
