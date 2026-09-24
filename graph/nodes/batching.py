"""One model request per batch of chunks, not one per chunk.

Free-tier providers cap requests per day, not tokens, so the cheapest
request is a big one: consecutive chunks from the same source file go
into one prompt and come back as a JSON object keyed by chunk_id. Shared
by concept_agent and card_agent; each supplies its own instructions and
the fields it expects back per chunk.

Parsing is strict. A missing chunk_id, a missing or blank field, or
anything that isn't a JSON object raises, per CLAUDE.md's fail-loudly
rule. A half-filled batch must not turn into blank questions or cards.
"""

from __future__ import annotations

import json

from ingest.models import Chunk

from ..models import call_model, config_setting
from ..state import PipelineState


def batch_max_words() -> int:
    return int(config_setting("batch_max_words"))


def make_batches(chunks: list[Chunk], max_words: int) -> list[list[Chunk]]:
    """Group by source file (first-seen order), then cut each file's
    run into batches of at most max_words. A chunk bigger than max_words
    gets a batch to itself; chunks are never split.
    """
    by_file: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        # Files in first-seen order; a file's chunks stay together even if
        # pacing interleaved them (new chunks first, then reviews).
        by_file.setdefault(chunk.source_file, []).append(chunk)

    batches: list[list[Chunk]] = []
    for file_chunks in by_file.values():
        batch: list[Chunk] = []
        words = 0
        for chunk in file_chunks:
            if batch and words + chunk.word_count > max_words:
                batches.append(batch)
                batch, words = [], 0
            batch.append(chunk)
            words += chunk.word_count
        if batch:
            batches.append(batch)
    return batches


_ENVELOPE = """{instructions}

The excerpts below come from one source file of the course {course}. Write \
one result per excerpt, based only on that excerpt.

Reply with a single JSON object and nothing else, no preamble and no code \
fence, in exactly this shape, with every chunk_id below as a key:
{{"items": {{"<chunk_id>": {shape}}}}}

{excerpts}"""


def _format_prompt(instructions: str, fields: tuple[str, ...], batch: list[Chunk]) -> str:
    shape = "{" + ", ".join(f'"{f}": "..."' for f in fields) + "}"
    excerpts = "\n\n".join(
        f"### chunk_id: {c.chunk_id} ({c.unit_range})\n{c.text}" for c in batch
    )
    return _ENVELOPE.format(
        instructions=instructions, course=batch[0].course, shape=shape, excerpts=excerpts
    )


def generate_batch(
    task_type: str,
    instructions: str,
    fields: tuple[str, ...],
    batch: list[Chunk],
    state: PipelineState,
) -> dict[str, dict[str, str]]:
    """One call_model request for the batch. Returns {chunk_id: {field: text}}."""
    prompt = _format_prompt(instructions, fields, batch)
    raw = call_model(task_type, [{"role": "user", "content": prompt}], state)
    return parse_batch(raw, [c.chunk_id for c in batch], fields, task_type)


def parse_batch(
    raw: str, chunk_ids: list[str], fields: tuple[str, ...], task_type: str
) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{task_type} got unparseable model output (not JSON): {raw!r}") from exc

    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, dict):
        raise ValueError(f"{task_type} got unparseable model output (no 'items' object): {raw!r}")

    results: dict[str, dict[str, str]] = {}
    for chunk_id in chunk_ids:
        item = items.get(chunk_id)
        if not isinstance(item, dict):
            raise ValueError(f"{task_type} got unparseable model output: no item for {chunk_id!r}")
        values = {}
        for f in fields:
            value = item.get(f)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{task_type} got unparseable model output: {chunk_id!r} has no {f!r}"
                )
            values[f] = value.strip()
        results[chunk_id] = values
    return results


def _strip_code_fence(raw: str) -> str:
    """Models often wrap JSON in ```json ... ``` even when told not to.

    Not using response_format=json_object: the fallback providers in the
    OmniRoute combos don't all accept it, and a 400 there would fail the run.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()
