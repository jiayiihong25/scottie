"""python -m drive_sync pull|push [--cache-only] [--data-root data]

push --cache-only writes back just the generation cache. The Routine runs
it after a failed run, so model output already paid for isn't regenerated
tomorrow; it never touches pacing_state.json.

push --snapshot-only writes back just daybook's last good snapshot
(daybook_snapshot.json), so tomorrow's page can carry over a section whose
source didn't deliver. Also never touches pacing_state.json.

Needs DRIVE_FOLDER_ID and GOOGLE_SERVICE_ACCOUNT_JSON (env vars or .env).
Exits nonzero with a clear message on any failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .client import GoogleDriveClient
from .sync import CACHE_FILES, SNAPSHOT_FILES, STATE_FILES, print_warnings, pull, push


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["pull", "push"])
    parser.add_argument("--data-root", default="data", type=Path)
    parser.add_argument(
        "--cache-only", action="store_true",
        help="push only the generation cache (safe after a failed run)",
    )
    parser.add_argument(
        "--snapshot-only", action="store_true",
        help="push only daybook's snapshot (safe whether or not scottie succeeded)",
    )
    args = parser.parse_args()
    if args.cache_only and args.snapshot_only:
        parser.error("--cache-only and --snapshot-only are separate pushes; use one")

    load_dotenv()
    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    if not folder_id:
        print("DRIVE_FOLDER_ID must be set (env var or .env)", file=sys.stderr)
        return 2

    try:
        client = GoogleDriveClient.from_env()
        if args.command == "pull":
            print_warnings(pull(client, folder_id, args.data_root))
            print(f"Pulled Drive folder into {args.data_root}")
        else:
            names = SNAPSHOT_FILES if args.snapshot_only else CACHE_FILES if args.cache_only else STATE_FILES
            push(client, folder_id, args.data_root, names)
            print(f"Pushed {', '.join(names)} back to Drive")
    except Exception as exc:  # one loud line for the Routine to report
        print(f"drive_sync {args.command} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
