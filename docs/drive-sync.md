# Drive sync (Routine-orchestrated)

Decided per `docs/tasks/01-drive-sync.md`: the daily Claude Code Routine
pulls and pushes Drive state via the Drive MCP tool, *before* and *after*
invoking `python -m graph`. `graph/` and `ingest/` stay Python-only, no
Drive dependency or service-account credentials in the codebase.

This means the sync step lives in the Routine's prompt (see
`routine/daily_prompt.md`), not in this repo's Python. Local dev runs
(`python -m graph`) still expect a hand-populated `data/` — that's
unchanged and gitignored, same as today.

## Drive folder layout

Mirrors the local convention, rooted at a single Drive folder (call it
`scottie-data/`) instead of local `data/`:

```
scottie-data/
  courses.yaml
  pacing_state.json
  <course>/
    <topic>/
      <source file>
```

## What the Routine does, in order

1. **Pull.** Before running the pipeline, list and download everything
   under `scottie-data/` into the local `data/` (course material,
   `courses.yaml`, `pacing_state.json`), preserving the
   `<course>/<topic>/<file>` layout.
2. **Fail loud if the pull didn't actually produce a usable `data/`.**
   Don't proceed into `python -m graph` if:
   - Drive is unreachable or the `scottie-data/` folder doesn't exist.
   - `courses.yaml` didn't come down.
   - No course subdirectories came down (now enforced in code too —
     `ingest.pipeline.build_index` raises `IngestError` on a
     course-dir-less `data_root`, so an empty/partial pull can't
     silently produce a "nothing due today" packet).
3. **Run the pipeline.** `python -m graph --data-root data --courses
   data/courses.yaml --pacing-state data/pacing_state.json --out output`.
4. **Push back only on success.** If and only if step 3 exits 0 and
   produces both `output/packet.html` and the `.apkg`, upload the
   updated `data/pacing_state.json` back to
   `scottie-data/pacing_state.json`, overwriting the previous version.
   A crash mid-run must never advance pacing state without a packet
   having actually been delivered — that's the whole point of gating
   the write-back on success.
5. **Deliver.** Publish the packet as the private Artifact and send the
   `.apkg` per `docs/orchestration-design.md`'s output-delivery section
   (task 02).

## Idempotency

Steps 1–2 are a full re-pull every run (simpler than incremental sync;
revisit if the course folder gets big enough to be slow). Step 4's
write-back is a plain overwrite of one file, so triggering the Routine
twice in a day is safe: the second run pulls whatever the first run
pushed and picks up from there — no partial merge logic needed.

## Open

- Exact Drive folder ID / sharing setup for `scottie-data/` — needs to
  be created and shared with the account the Routine runs as.
