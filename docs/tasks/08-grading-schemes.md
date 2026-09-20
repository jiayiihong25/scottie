# 08 — Grading-scheme awareness

**Size:** M · **Status:** designed, not started · **Decide open items first**

## Problem

Commit `81be30f` added a detailed design for this
(`docs/orchestration-design.md`, "Grading-scheme awareness"). **None of it
is implemented.** `config/` contains only `models.yaml`, there is no
`grading_scheme_loader.py`, and `graph/state.py:44-64` has no
`grading_schemes` field.

This matters more than its position in the queue suggests. The design doc
puts it plainly: the goal of this project isn't optimal spaced review, it's
**highest grade for lowest effort**. `pacing_agent` currently sees only
`exam_dates` plus the content index, so it will schedule review for material
already bought back by a drop rule or alt-credit — spending the user's
mornings on work that cannot change their grade. That's the opposite of the
point.

It sits after the critical path because an end-to-end daily run that
schedules slightly too much is still useful; one that never delivers isn't.

## What done looks like

Per the design doc:

- `config/grading_schemes.yaml` — hand-edited, **not** ingested from Drive
  or parsed from syllabus PDFs. The doc is emphatic about this: syllabi are
  irregular, and an LLM silently misreading "best 8 of 10" costs a real
  grade. Manual first, per `CLAUDE.md`'s start-simple convention.
- A `GradingScheme` dataclass covering drop/threshold rules ("best 8 of
  10"), alternate/substitute credit (research credit, participation), and
  already-banked progress.
- `grading_scheme_loader` node + a `grading_schemes` state field, defaulting
  to empty — a course with no scheme configured must behave exactly as it
  does today, not fail.
- `pacing_agent` consumes it and stays deterministic. This is rule
  arithmetic over a config file; there is no place for LLM judgment here,
  and `CLAUDE.md` forbids it explicitly.

## Open items — resolve before coding

Carried from the design doc, still undecided:

1. Should `remaining_load_bearing == 0` **exclude** chunks outright or just
   **deprioritize** them against exam-driven review? Excluding is the
   stronger effort saving, but it trusts the banked-progress math against
   things like a late grade change. Deprioritising is the safer default.
2. Is alt-credit coverage tracked at topic/unit granularity (as sketched),
   or does it need chunk-level mapping for courses where a research credit
   covers only part of a unit?
3. Update cadence for `completed` — manual edit after each submission, or a
   prompt in the morning packet asking "did you submit assignment N?" The
   doc calls the latter a v2 feedback loop; don't build it now.

Question 1 is the one that changes the data model. Decide it first.

## Files

- New: `config/grading_schemes.yaml`, `graph/nodes/grading_scheme_loader.py`
- `graph/state.py` — `grading_schemes` field
- `graph/nodes/pacing_agent.py` — consumes the scheme
- `graph/build.py` — wire the loader in
- `docs/orchestration-design.md` — the full spec
