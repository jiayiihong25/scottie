# exam-prep-pipeline

Personal study-automation system. Generates a daily 3-hour morning learning
block — reading assignments, concept-check questions, and Anki flashcards —
paced against upcoming exam dates, using course material (PDFs, slides,
notes) as the source content.

## Status

`ingest/` is built and tested. `pacing/`, `generate/`, and the daily cron
entry point are not yet started — see `CLAUDE.md` for the architecture
this is converging on.

## Structure

```
ingest/     # extracts + normalizes PDFs, slides, notes into a common
            # content index (topic, source, page/slide range, text, type)
pacing/     # (not yet built) scheduling engine — maps exam dates + content
            # volume into a day-by-day plan, tracks what's due for review
generate/   # (not yet built) daily generation logic — pulls today's
            # content, produces concept-check questions and Anki cards
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

## Eventual deployment

Once the pipeline runs cleanly end-to-end locally, it gets packaged as a
Claude Code Routine (prompt + this repo + a cron schedule) so the morning
generation step runs on its own, unattended.
