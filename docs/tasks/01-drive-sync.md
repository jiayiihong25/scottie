# 01 — Google Drive sync for course material and pacing state

**Size:** M · **Blocks:** every unattended run · **Status:** `drive_sync/` built and
tested against a fake Drive; not yet run against the real folder (needs the
service account key and the one-time Drive setup in `routine/daily-prompt.md`)

## Problem

`graph/nodes/ingest_node.py:17` calls `build_index(data_root)` against a
local path. A Routine container starts empty, so `data/` doesn't exist and
`ingest/pipeline.py` raises `IngestError("data root ... does not exist")`.
The run dies at node 1, every morning. `CLAUDE.md` already calls this out:
"a Routine's container starts empty each morning, so ingest needs to pull
from Drive first."

Three things live under `data/` and all of them vanish with the container:

- course material (PDFs, slides, notes) — the ingest input
- `data/courses.yaml` — exam dates, read by `graph/__main__.py:38`
- `data/pacing_state.json` — **the pipeline's only persistent memory**

The third is the one that turns this from an inconvenience into a
correctness bug. If `pacing_state.json` resets daily, every chunk looks new
forever, nothing is ever recorded as seen, and the spaced-review passes
never fire. The pipeline would silently produce a first-pass-only packet
every day and look like it was working.

## What done looks like

- A `drive_sync` step that runs before `ingest_node` and populates the local
  `data_root` from Drive: course material, `courses.yaml`, and
  `pacing_state.json`.
- A matching write-back that pushes the updated `pacing_state.json` to Drive
  **after** a successful run — and does not write it back on a failed run,
  so a crash can't advance pacing without a packet having been delivered.
- Fails loudly if Drive is unreachable or the course folder is missing,
  rather than proceeding with an empty `data_root` (which would otherwise
  produce a cheerful "nothing due today" packet — the exact silent-failure
  mode `CLAUDE.md` forbids).
- Deterministic, no LLM calls. Same category as `ingest/`.

## Decision

**Access mechanism: Python, via a Google service account** (`drive_sync/`,
run as `python -m drive_sync pull|push` around `python -m graph`). An earlier
plan had the Routine prompt use the Drive MCP connector; it was dropped
because the connector returns file bytes as base64 through the model's
context (millions of tokens a day for the PDFs) and cannot overwrite file
contents. `graph/` and `ingest/` still read only local `data/`. Full design:
`docs/drive-sync.md`.

Sync is a full re-pull every morning (the container is empty anyway, so a
changed-files cache would buy nothing). Write-back updates the existing
`pacing_state.json` and `artifact_url.txt` in place, so a same-day
double-trigger is safe with no merge logic.

Landed: `drive_sync/` with tests against a fake Drive, plus the empty-
`data_root` fail-loud guard in `ingest/pipeline.py`. Not yet done: a live
pull against the real folder, and wiring the env vars into the Routine (task
03's `create_trigger` call).

## Files

- `drive_sync/` — pull/push and the Google client
- `graph/nodes/ingest_node.py` — where the local-path assumption sits
- `graph/nodes/pacing_agent.py` — reads/writes the pacing state
- `ingest/pipeline.py` — empty-`data_root` guard
- `docs/drive-sync.md` — full sync design
- `routine/daily-prompt.md` — the Routine prompt that calls it
- `docs/orchestration-design.md` — "Course material storage" decision
