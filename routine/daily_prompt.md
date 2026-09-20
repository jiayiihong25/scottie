# Daily Routine prompt (draft)

Prompt body for the cron-scheduled `create_new_session_on_fire` Routine
described in `docs/orchestration-design.md`. See `docs/drive-sync.md` for
the design this implements. Not yet wired up to an actual `create_trigger`
call — task 03 (`docs/tasks/03-daily-routine.md`) owns that.

---

You are running the daily scottie exam-prep pipeline. This container
starts empty — do all of the following, in order, and stop with a clear
error message (don't send a packet) if any numbered step fails.

1. **Pull from Drive.** Using the Drive MCP tool, download everything
   under the `scottie-data/` folder into `data/` in this working
   directory, preserving its folder structure exactly
   (`courses.yaml`, `pacing_state.json`, and `<course>/<topic>/<file>`
   for course material). If the `scottie-data/` folder can't be found,
   or the download fails, stop here and report the failure — do not
   continue with a partial or empty `data/`.

2. **Sanity-check the pull.** Confirm `data/courses.yaml` exists and
   `data/` has at least one course subdirectory. (The pipeline itself
   also enforces the course-subdirectory check and will raise
   `IngestError` if this is empty, but catching it here gives a
   clearer failure message before spending time on the run.)

3. **Run the pipeline.**
   ```
   python -m graph --data-root data --courses data/courses.yaml \
     --pacing-state data/pacing_state.json --out output
   ```
   If this exits non-zero, stop and report the error — do not push
   anything back to Drive and do not attempt delivery.

4. **Push pacing state back to Drive.** Only after step 3 succeeds and
   both `output/packet.html` and the `.apkg` file exist: upload the
   updated `data/pacing_state.json`, overwriting
   `scottie-data/pacing_state.json`.

5. **Deliver the packet and deck.** Publish `output/packet.html` as the
   private Claude Artifact (republish to the same URL as previous
   mornings, don't create a new one each day) and send the `.apkg` file
   proactively.

If any step fails, do not perform later steps, and make sure the failure
is visible (this runs unattended — a silent partial run is the failure
mode to avoid).
