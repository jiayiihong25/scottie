# 01 — Google Drive sync for course material and pacing state

**Size:** M · **Blocks:** every unattended run · **Status:** not started

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

## Open questions

- **Access mechanism.** Drive is connected as an MCP tool, which is
  available to the Claude Code session but not to a plain
  `python -m graph` process. Either the Routine prompt does the pull via
  MCP before invoking the pipeline (keeps Python dependency-free, makes
  local runs differ from Routine runs), or the pipeline uses a Drive
  service-account client directly (uniform, but adds credentials and a
  dependency). **Decide this first — it determines where the code lives.**
- Sync the whole course folder every morning, or only changed files? Full
  sync is simpler and course material is small; revisit if it gets slow.
- Where does `pacing_state.json` live in Drive, and what happens if a run
  is triggered twice in one day — is the write-back idempotent?

## Files

- `graph/nodes/ingest_node.py` — where the local-path assumption sits
- `graph/__main__.py` — `--data-root`, `--courses`, `--pacing-state` flags
- `graph/nodes/pacing_agent.py` — reads/writes the pacing state
- `docs/orchestration-design.md` — "Course material" section
