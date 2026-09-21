# 03 — Daily Claude Code Routine

**Size:** S · **Depends on:** 01, 02 · **Status:** prompt drafted in
`routine/daily-prompt.md`; Routine itself not yet created (needs the Drive
service account env vars, see the prompt file)

## Problem

There is no Routine, no prompt file, and no scheduling artifact anywhere in
the repo. Without one there is no "daily" in this daily pipeline — every run
is a manual `python -m graph`. `docs/orchestration-design.md` still lists
this as an open item.

This is last on the critical path on purpose: a Routine that fires against
a pipeline which can't read Drive (01) and can't deliver output (02) just
produces a failure notification every morning.

## What done looks like

- A cron-scheduled Routine that fires once each morning and starts a fresh
  session (the container is ephemeral by design).
- A checked-in prompt file — the Routine prompt is real project logic and
  shouldn't live only in a web UI where it can't be diffed or reviewed.
- `OMNIROUTE_BASE_URL` and `OMNIROUTE_API_KEY` supplied as environment
  variables on the environment, never in the prompt text. `graph/models.py`
  reads real env vars in preference to `.env`, so this works as-is.
- A failed run is visible. An unattended pipeline that fails silently is
  worse than one that doesn't run — the user needs to find out at breakfast,
  not at the exam.

## Open questions

- **What time, and in what timezone?** Needs a concrete local hour converted
  to a UTC cron expression. "Morning packet" implies before the user starts
  working; pick the hour deliberately.
- How much does the Routine prompt do versus the Python entry point? If
  Drive sync and Artifact publishing land in the prompt (see 01 and 02),
  the prompt becomes substantial and needs its own care. If they land in
  Python, the prompt is nearly `python -m graph` and this task is trivial.
  **Resolve 01's access-mechanism question first.**
- What happens on a missed or failed day — skip, or catch up on the next
  run? Catching up interacts with pacing state: two days of new material in
  one packet may be better than silently dropping a day.

## Files

- New: a Routine prompt file (`routine/` or `docs/`)
- `docs/orchestration-design.md` — open-items section
