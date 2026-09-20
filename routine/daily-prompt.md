# Daily morning-packet Routine prompt

This file is the source of truth for the Routine prompt. Paste its body (below
the line) into the Routine; edit here, not in the web UI, so changes are
reviewed. Schedule and environment settings are at the bottom.

Placeholders in `<ANGLE_BRACKETS>` must be filled in before the Routine is
created (Drive folder names, and the Artifact URL after the first run).

---

You are running the daily exam-prep pipeline for the `scottie` repo. No human
is present. If any step fails, **stop, do not continue, and report the failure
loudly** (see "Failure" below). Never deliver a partial or stale result.

## 1. Sync from Drive

Working directory is an empty checkout of the repo. Using the Google Drive
connector, download the Drive folder `<DRIVE_COURSE_FOLDER>` into `data/`,
preserving its `course/topic/file` layout. It must contain:

- course material (PDFs, slides, notes)
- `courses.yaml`
- `pacing_state.json` (absent only on the very first run — that is the one
  case where you may continue without it)
- `artifact_url.txt` (absent only on the very first run)

If the folder is missing, Drive is unreachable, or `courses.yaml` is absent,
this is a failure. Do not run the pipeline against an empty `data/`.

## 2. Install and run

```
pip install -r requirements.txt
python -m graph
```

`OMNIROUTE_BASE_URL` and `OMNIROUTE_API_KEY` are already set as environment
variables. Never print or write them anywhere. A non-zero exit is a failure.

## 3. Check the manifest

`output/delivery.json` must exist. If it does not, the run failed — that is
the pipeline's signal that nothing may be delivered. Read it: it names the
packet file and the deck file (or `null` on a day with no cards).

## 4. Deliver

1. Publish `output/<packet>` as a **private** Artifact. If `data/artifact_url.txt`
   exists, update that URL in place; otherwise create the Artifact and write
   its URL to `data/artifact_url.txt`. The link must stay the same every day.
2. If the manifest's `apkg` is not null, send `output/<apkg>` to the user as a
   file with `SendUserFile` (status `proactive`, display `attach`), with the
   Artifact link in the caption. If it is null, say there is no deck today.
3. Only after both steps succeed: upload the updated `data/pacing_state.json`
   and `data/artifact_url.txt` back to `<DRIVE_COURSE_FOLDER>`, overwriting the
   old copies. Pacing state must never advance unless the packet was delivered.

## Failure

On any failure: do not upload `pacing_state.json`, do not publish anything,
and send the user a proactive message that starts with "Morning packet FAILED",
names the step that failed, and includes the error output (with secrets
removed). A visible failure at breakfast is the requirement.

## Missed days

If a day is missed, do nothing special: the next run computes pacing from
`pacing_state.json` and the current date, so it resumes from wherever state
left off. Do not try to backfill.

---

## Schedule and environment (configure in the Routine, not in the prompt)

- **Fires:** 6:00 AM America/Toronto daily, fresh session each time.
  Cron is UTC-only: `0 10 * * *` while daylight time is in effect
  (through 2026-11-01), then `0 11 * * *`. Update the cron when the clocks
  change, or the packet arrives an hour early/late.
- **Environment variables:** `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`.
- **Connectors:** Google Drive.
