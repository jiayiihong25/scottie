# Daily morning-packet Routine prompt

This file is the source of truth for the Routine prompt. Paste its body (below
the line) into the Routine; edit here, not in the web UI, so changes are
reviewed. Schedule and environment settings are at the bottom.


---

You are running the daily exam-prep pipeline for the `scottie` repo. No human
is present. If any step fails, **stop, do not continue, and report the failure
loudly** (see "Failure" below). Never deliver a partial or stale result.

## 1. Sync from Drive

Working directory is an empty checkout of the repo. Install dependencies and
pull the Drive folder into `data/` (Python does the download; do not fetch
files through the Drive connector — PDFs would flow through your context):

```
pip install -r requirements.txt
python -m drive_sync pull
```

This fills `data/` with course material, `courses.yaml`, and (after the first
run) `pacing_state.json`, `artifact_url.txt` and `generated.json` (the
generation cache: questions and cards already paid for). It exits nonzero if Drive is
unreachable, `courses.yaml` is missing, or no course material is found. That
is a failure: do not run the pipeline against an empty `data/`. Warnings on
stderr (e.g. a skipped unsupported file) are not failures, but mention them
in the final message.

## 2. Install and run

```
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
3. Only after both steps succeed, run `python -m drive_sync push` to write
   the updated `data/pacing_state.json`, `data/artifact_url.txt` and
   `data/generated.json` back to Drive. Pacing state must never advance unless the packet was delivered.
   A push failure is a failure: the next run would re-issue today's chunks.

## Failure

On any failure: do not upload `pacing_state.json` and do not publish anything.
If `data/generated.json` exists, run `python -m drive_sync push --cache-only`
so the model output this run already paid for isn't regenerated tomorrow. It
never touches pacing state. If that push fails too, mention it but keep going.
Then send the user a proactive message that starts with "Morning packet FAILED",
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
- **Environment variables:** `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`,
  `DRIVE_FOLDER_ID` (the "JiaYi Courses" folder id), and
  `GOOGLE_SERVICE_ACCOUNT_JSON` (the service account key, pasted as one value).
- **Connectors:** none required. The Drive connector is deliberately not used.
- **One-time Drive setup:** share the folder with the service account's email
  as Editor, and create empty `pacing_state.json` and `generated.json` (each
  containing `{}`) and `artifact_url.txt` in the folder. A service account can edit files you own
  but cannot create new ones in a personal Drive, so `push` needs these to
  exist.
