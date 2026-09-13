"""Smoke test: confirm OmniRoute is reachable and an alias resolves.

Not part of the pipeline itself — this is a one-off manual check to run
after (re)deploying or reconfiguring OmniRoute, before trusting graph/ to
call it for real. Loads credentials from .env, same as the real pipeline
will, so a pass here means graph/models.py's call_model() has a working
target to hit.

Usage:
    python scripts/test_omniroute.py [alias]

    alias defaults to "cheap-fast" if not given.
"""

from __future__ import annotations

import sys

import requests
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = os.environ.get("OMNIROUTE_BASE_URL")
API_KEY = os.environ.get("OMNIROUTE_API_KEY")


def main() -> int:
    alias = sys.argv[1] if len(sys.argv) > 1 else "cheap-fast"

    missing = [name for name, val in [("OMNIROUTE_BASE_URL", BASE_URL), ("OMNIROUTE_API_KEY", API_KEY)] if not val]
    if missing:
        print(f"Missing from .env: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in the real values.", file=sys.stderr)
        return 1

    url = f"{BASE_URL.rstrip('/')}/chat/completions"
    print(f"POST {url}")
    print(f"model (alias): {alias!r}\n")

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": alias,
                "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
                "stream": False,
            },
            timeout=60,  # generous: serverless/sleep-on-idle means a cold start on first hit
        )
    except requests.exceptions.RequestException as exc:
        print(f"FAILED: could not reach OmniRoute: {exc}", file=sys.stderr)
        print(
            "If this is the first request in a while, the Railway service may still be "
            "waking from sleep-on-idle — wait ~15-30s and retry before assuming it's broken.",
            file=sys.stderr,
        )
        return 1

    print(f"HTTP {response.status_code}")

    if response.status_code != 200:
        print(f"FAILED: unexpected status\n{response.text}", file=sys.stderr)
        return 1

    try:
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as exc:
        print(f"FAILED: unexpected response shape ({exc})\n{response.text}", file=sys.stderr)
        return 1

    print(f"Model replied: {reply!r}")
    print("\nOK — OmniRoute is reachable and the alias resolves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
