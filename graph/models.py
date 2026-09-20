"""call_model() — the single chokepoint every agent node uses to reach
OmniRoute. Never construct an OpenAI client directly in a node; see
docs/orchestration-design.md ("OmniRoute integration").
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

from .state import ModelCallLog, PipelineState

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


def _load_model_config() -> dict[str, str]:
    return yaml.safe_load(_CONFIG_PATH.read_text())


MODEL_CONFIG = _load_model_config()

# The OpenAI SDK retries connection errors, timeouts, 408/409/429 and 5xx with
# exponential backoff, and does not retry other 4xx (an auth error fails the
# same way every time). Free-tier providers rate-limit, so allow a few tries;
# the timeout is per attempt, so a hung request can't stall the Routine.
_MAX_RETRIES = 4
_TIMEOUT_SECONDS = 120.0

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    # Local runs keep credentials in .env; a Routine container supplies them
    # as real env vars, which take precedence (load_dotenv never overrides).
    load_dotenv()

    base_url = os.environ.get("OMNIROUTE_BASE_URL")
    api_key = os.environ.get("OMNIROUTE_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError(
            "OMNIROUTE_BASE_URL and OMNIROUTE_API_KEY must both be set "
            "(env vars or .env) — no fallback, per CLAUDE.md 'fail loudly'."
        )
    _client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        max_retries=_MAX_RETRIES,
        timeout=_TIMEOUT_SECONDS,
    )
    return _client


def call_model(
    task_type: str,
    messages: list[dict],
    state: PipelineState,
    **kwargs,
) -> str:
    """Send a chat completion through OmniRoute and log the call.

    Returns a non-empty string or raises — an unreachable gateway or an
    empty completion must stop the run, not silently produce an
    empty/malformed morning packet. Nodes never need to defend against None.
    """
    alias = MODEL_CONFIG.get(task_type)
    if alias is None:
        raise ValueError(f"no OmniRoute alias configured for task_type {task_type!r}")

    client = _get_client()
    response = client.chat.completions.create(model=alias, messages=messages, **kwargs)

    usage = response.usage
    state["model_calls"].append(
        ModelCallLog(
            task_type=task_type,
            alias=alias,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
    )

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError(
            f"call_model: empty completion for task_type {task_type!r} "
            f"(alias {alias!r}) — likely a refusal or provider hiccup"
        )
    return content
