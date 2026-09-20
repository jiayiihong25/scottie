# 01 — Google Drive sync for course material and pacing state

**Size:** M · **Blocks:** every unattended run · **Status:** in progress

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

**Access mechanism: Routine prompt pulls/pushes via MCP**, not a Drive
client inside `graph/`/`ingest/`. Keeps Python dependency-free; the
Routine's prompt (draft: `routine/daily_prompt.md`) does the pull before
`python -m graph` and the write-back after. Local dev runs still expect a
hand-populated `data/`, unchanged from today. Full design:
`docs/drive-sync.md`.

Sync is a full re-pull every morning (course material is small; revisit
if this gets slow). Write-back is a plain overwrite of
`pacing_state.json`, which makes a same-day double-trigger safe with no
merge logic needed — see "Idempotency" in `docs/drive-sync.md`.

Landed so far: the empty-`data_root` fail-loud guard in
`ingest/pipeline.py` (raises `IngestError` when a pull produced no course
subdirectories, so a botched sync can't silently look like "nothing due
today"), and the Drive folder layout + Routine prompt draft. Not yet
landed: actually wiring the pull/push MCP calls into a real Routine
(that's task 03's `create_trigger` call).

## Open questions

- Exact Drive folder ID / sharing setup for `scottie-data/` — needs to be
  created and shared with the account the Routine runs as.

## Files

- `graph/nodes/ingest_node.py` — where the local-path assumption sits
- `graph/__main__.py` — `--data-root`, `--courses`, `--pacing-state` flags
- `graph/nodes/pacing_agent.py` — reads/writes the pacing state
- `ingest/pipeline.py` — empty-`data_root` guard
- `docs/drive-sync.md` — full sync design
- `routine/daily_prompt.md` — draft Routine prompt implementing it
- `docs/orchestration-design.md` — "Course material storage" decision
