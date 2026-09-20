"""python -m drive_sync pull|push [--data-root data]

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
from .sync import print_warnings, pull, push


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["pull", "push"])
    parser.add_argument("--data-root", default="data", type=Path)
    args = parser.parse_args()

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
            push(client, folder_id, args.data_root)
            print("Pushed state back to Drive")
    except Exception as exc:  # one loud line for the Routine to report
        print(f"drive_sync {args.command} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
