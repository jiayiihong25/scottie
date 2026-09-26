# Drive sync (Python, service account)

Decided per `docs/tasks/01-drive-sync.md`. The Routine runs
`python -m drive_sync pull` before the pipeline and `python -m drive_sync push`
after a successful delivery. The pipeline (`graph/`, `ingest/`) still reads only
local `data/`; the Drive dependency lives in `drive_sync/`.

Why not the Drive MCP connector: it returns file bytes as base64 through the
model's context, so a daily sync of the PDFs would cost millions of tokens, and
it cannot overwrite a file's contents (only rename or move it). A service
account downloads and updates files directly.

## Drive folder layout

Rooted at the "JiaYi Courses" folder (`DRIVE_FOLDER_ID`):

```
JiaYi Courses/
  courses.yaml
  pacing_state.json      (edited in place by push)
  artifact_url.txt       (edited in place by push)
  generated.json         (edited in place by push; generation cache)
  <course>/<topic>/<source file>
  <course>/<source file>            (topic defaults to "general")
  _anything/                        (folders starting with "_" are skipped)
```

Only `.pdf`, `.pptx/.ppt`, `.txt`, `.md` are downloaded; other files are
reported as warnings. The root `README` is ignored.

## Order of operations

1. **pull** — download `courses.yaml`, the state files (absent only on the first
   run) and every course file into `data/`. Fails (nonzero exit) if Drive is
   unreachable, `courses.yaml` is missing, or no course material comes down, so
   an empty pull can't become a cheerful "nothing due today" packet.
2. **run** — `python -m graph`; require `output/delivery.json`.
3. **deliver** — publish the Artifact, send the `.apkg` (see the design doc's
   delivery boundary).
4. **push** — only after delivery succeeded, write `pacing_state.json`,
   `artifact_url.txt` and `generated.json` back. A crash before this leaves
   pacing state untouched, so pacing can never advance without a delivered
   packet.
   After a failed run, `push --cache-only` writes back just `generated.json`.
   The cache is keyed by chunk text and never advances pacing, so saving it
   is always safe, and requests already spent on free-tier quota aren't
   wasted.

## Setup (one time)

- Service account with the Drive API enabled; its key supplied as
  `GOOGLE_SERVICE_ACCOUNT_JSON` (Routine) or `GOOGLE_SERVICE_ACCOUNT_FILE`
  (local `.env`). Never committed.
- Share the folder with the service account's email as **Editor**.
- Create `pacing_state.json` and `generated.json` (each containing `{}`) and an
  empty `artifact_url.txt`
  in the folder by hand: a service account can edit files you own but cannot
  create new ones in a personal Drive, so `push` is update-only.

## Idempotency

Pull is a full re-pull. Push overwrites one file's contents, so triggering the
Routine twice in a day is safe: the second run pulls what the first pushed.
