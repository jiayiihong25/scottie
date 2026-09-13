"""CLI: python -m ingest [--data-root data] [--out data/content_index.json]

Fails loudly (nonzero exit, errors printed to stderr) on any extraction
failure, per CLAUDE.md's unattended-cron requirement — better a stopped
run than a silently thin morning packet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import build_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingest")
    parser.add_argument(
        "--data-root", type=Path, default=Path("data"),
        help="directory of course material, laid out as <course>/<topic>/<file> (default: data)",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("data/content_index.json"),
        help="where to write the content index (default: data/content_index.json)",
    )
    parser.add_argument(
        "--target-words", type=int, default=500,
        help="approximate word count per chunk (default: 500)",
    )
    args = parser.parse_args(argv)

    index = build_index(args.data_root, target_words=args.target_words)
    index.write(args.out)

    print(f"ingested {len(index.chunks)} chunk(s) across {len(index.courses)} course(s)")
    print(f"wrote index to {args.out}")

    if index.errors:
        print(f"\n{len(index.errors)} file(s) failed to ingest:", file=sys.stderr)
        for err in index.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
