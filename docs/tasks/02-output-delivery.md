# 02 — Output delivery: Artifact publish and .apkg push

**Size:** M · **Blocks:** every unattended run · **Status:** not started

## Problem

`packet_writer` writes `output/morning_packet.html` and
`output/morning_deck.apkg` to local disk
(`graph/nodes/packet_writer.py:48-55`) and stops there.

Both specified delivery mechanisms have no code at all:

- the morning packet as a **private Claude Artifact, republished to the same
  URL daily** (so the link is stable and bookmarkable)
- the `.apkg` **pushed as a file** alongside it, since a web page can't hold
  an Anki deck

In a Routine container, `output/` is destroyed when the session ends. As it
stands the pipeline can complete successfully and produce nothing the user
ever sees. This is the single biggest gap between "the code exists" and
"the thing works."

## What done looks like

- The packet HTML is published as a private Artifact, to the **same URL**
  every day. That means the artifact URL has to be persisted somewhere
  durable (alongside `pacing_state.json` — see task 01) and reused, not
  re-created.
- The `.apkg` is delivered as a file the user can open on their phone.
- Delivery failure is loud. A packet generated but not delivered is a failed
  run, not a successful one.
- Nothing is delivered on a run that errored earlier — see task 04 for how
  errors should gate output.

## Open questions

- **Where does publishing happen?** Same fork as task 01: the Artifact tool
  belongs to the Claude Code session, not to the Python process. Most likely
  `packet_writer` keeps writing files and the Routine prompt publishes them.
  If so, `packet_writer`'s contract is "produce these two paths" and the
  Routine owns delivery — worth stating explicitly in the design doc so the
  boundary doesn't drift.
- The packet HTML at `packet_writer.py:80-89` is bare-bones — unstyled, no
  date heading, no per-course grouping. Worth a design pass once it's
  actually being read every morning, but not a blocker.
- Should the deck be one cumulative `.apkg` or one per day? Cumulative risks
  re-importing duplicates; daily means many small files. The stable
  model/deck IDs at `packet_writer.py:20-21` suggest cumulative was intended.

## Files

- `graph/nodes/packet_writer.py`
- `docs/orchestration-design.md` — "Output delivery" section
