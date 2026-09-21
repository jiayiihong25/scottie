# exam-prep-pipeline

Personal study-automation system. Generates a daily 3-hour morning learning
block — reading assignments, concept-check questions, and Anki flashcards —
paced against upcoming exam dates, using course material (PDFs, slides,
notes) as the source content.

## Status

`ingest/` is built and tested. `graph/` (the LangGraph pipeline: pacing,
concept and card generation, packet writing) is implemented as a proof of
concept and covered by a few unit tests, but has not been run end to end
against real course material or a live OmniRoute gateway. Drive sync and the
daily Routine are still outstanding — see `docs/tasks/` for the work list and
`CLAUDE.md` for the architecture.

## Structure

```
ingest/     # extracts + normalizes PDFs, slides, notes into a common
            # content index (topic, source, page/slide range, text, type)
graph/      # LangGraph pipeline: ingest -> pacing -> concept/card agents
            # -> packet_writer. Run with `python -m graph`.
config/     # models.yaml: task type -> OmniRoute model alias
routine/    # the daily Claude Code Routine prompt (when present)
docs/       # design doc (orchestration-design.md) and task specs (tasks/)
output/     # generated morning packets + .apkg files (gitignored — personal)
data/       # content index + course material (gitignored — personal)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt        # to run the pipeline
pip install -r requirements-dev.txt    # to also run the test suite
```

## Ingestion

Course material goes under `data/<course>/<topic>/<file>` (a topic
subfolder is optional — files directly under a course directory are
tagged topic `general`). Supported formats: `.pdf`, `.pptx`/`.ppt`,
`.txt`, `.md`.

```bash
python -m ingest                       # data/ -> data/content_index.json
python -m ingest --data-root data --out data/content_index.json
```

Each source file is split into pages/slides/sections, grouped into
~500-word chunks (never splitting a single page/slide/section, never
mixing two source files), and tagged `conceptual` or `memorization` by a
deterministic keyword heuristic (see `ingest/classify.py`). A chunk's id
is derived from its file path and unit range, not its content, so pacing
state (what's due for review) survives a wording fix to the source file.

Extraction failures for one file (unsupported format, empty/scanned PDF,
malformed deck) are collected in the index's `errors` list rather than
aborting the run; `python -m ingest` still exits nonzero if any file
failed, per the "fail loudly" rule in `CLAUDE.md`.

Run the test suite (uses synthetic sample material committed under
`tests/fixtures/`, not real course content):

```bash
pytest
```

## Running the pipeline

```bash
python -m graph                        # needs OMNIROUTE_BASE_URL / OMNIROUTE_API_KEY
```

Reads `data/courses.yaml` for exam dates and writes the morning packet and
`.apkg` under `output/`. Model credentials come from the environment or a
local `.env` (never committed).

## Eventual deployment

Once the pipeline runs cleanly end-to-end locally, it gets packaged as a
Claude Code Routine (prompt + this repo + a cron schedule) so the morning
generation step runs on its own, unattended.
