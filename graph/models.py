"""Shared model-call wrapper — every agent node calls call_model(), never
a client directly."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

from graph.state import ModelCallLog

load_dotenv()

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


MODEL_CONFIG: dict = _load_config()


def _get_credentials() -> tuple[str, str]:
    base_url = os.environ.get("OMNIROUTE_BASE_URL")
    api_key = os.environ.get("OMNIROUTE_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError(
            "OMNIROUTE_BASE_URL and OMNIROUTE_API_KEY must be set in env"
        )
    return base_url, api_key


def call_model(
    content_type: str,
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> tuple[str, ModelCallLog]:
    """Call OmniRoute and return (response_text, log_entry).

    Raises on network errors or non-200 — fail loudly per CLAUDE.md.
    """
    alias = MODEL_CONFIG.get("generate_agent", {}).get(content_type, "auto")
    base_url, api_key = _get_credentials()

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": alias,
        "messages": messages,
        "stream": False,
        **kwargs,
    }

    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"OmniRoute returned HTTP {resp.status_code} for alias "
            f"{alias!r}: {resp.text}"
        )

    data = resp.json()
    choice = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    log = ModelCallLog(
        content_type=content_type,
        alias=alias,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )
    return choice, log
