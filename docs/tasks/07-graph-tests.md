# 07 — Test coverage for graph/

**Size:** M · **Status:** done — all five targets covered (`call_model` was already tested in task 06). Not covered: a full `run_pipeline` run with a stubbed `call_model`; `requirements-dev.txt` already pulls in `requirements.txt` + pytest, and the README documents the install.

## Problem

`graph/` has **zero tests**. Nothing under `tests/` references it. The whole
package landed in one commit as a proof of concept and has never been run
end to end.

The cost of that is already measurable: the date-parsing crash and the
unloaded `.env` (both fixed), plus the chunk-ordering bug (task 05) and the
`None`-returning `call_model` (task 06) are all things a basic unit test
would have caught before they were committed.

`ingest/` sets the right precedent — four test files against
`tests/fixtures/`. `graph/` should meet the same bar.

## What done looks like

Highest-value targets, in order:

1. **`pacing_agent`** — the most logic-dense and least observable code in the
   repo, and per `CLAUDE.md` "the part most worth getting right." It's
   deterministic, so it's cheaply testable. Simulate multi-day runs against
   a temp `pacing_state.json`: does a chunk seen on day 1 come back for
   review on the right day? Does a course with no exam date get skipped with
   a note? Does a multi-file course come out in teaching order (this one
   fails today — task 05)?
2. **`call_model` with a stub client** — without this, no agent node is
   testable without a live OmniRoute. This is the unlock for everything else.
3. **`card_agent._parse_card`** — pure parsing, pure function, easy win.
   Include malformed model output; that's the case that matters unattended.
4. **`packet_writer` on empty-list days** — the partial-participation rule
   (a concept-only day, a card-only day, a nothing-due day) is currently
   honored, and a test keeps it that way.
5. **`__main__._load_exam_dates`** — quoted dates, unquoted dates, the
   worst-case fallback, missing dates, garbage. The recent crash lived here.

## Note

`langgraph` and `pytest` aren't installed in every environment this repo
gets checked out into — confirm `requirements-dev.txt` is sufficient to run
the suite from a clean clone, and that a contributor can tell how.

## Files

- New: `tests/test_pacing_agent.py`, `tests/test_packet_writer.py`,
  `tests/test_card_agent.py`, `tests/test_models.py`, `tests/test_main.py`
- `tests/fixtures/` — existing fixtures to extend
