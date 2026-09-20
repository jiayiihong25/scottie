# 05 — Fix cross-file chunk ordering in pacing_agent

**Size:** S · **Status:** not started

## Problem

`graph/nodes/pacing_agent.py:85` sorts a course's chunks by `chunk.order`.
But `order` is assigned **per document** and resets to 0 for each file
(`ingest/chunk.py:30,63,66`).

So for a course with three lecture decks, sorting by `order` alone gives:

```
deck-A chunk 0, deck-B chunk 0, deck-C chunk 0,
deck-A chunk 1, deck-B chunk 1, deck-C chunk 1, ...
```

New material is assigned in scrambled cross-file order. The reading list
jumps between lecture decks mid-sequence, and — worse — the "first pass"
through a course stops following the order the material was taught in,
which is the whole premise of the pacing algorithm.

This is invisible in a single-file course, which is probably why it survived
the PHILOSOP1230 proof of concept.

## What done looks like

- Sort by a course-level key: `(source_file, order)` at minimum.
- `source_file` alphabetical is a proxy for teaching order, and a decent one
  if files are named `lecture-01.pdf`, `lecture-02.pdf`. It is **not**
  reliable in general — `week10` sorts before `week2`. Consider natural sort,
  or an explicit ordering hint in `courses.yaml`.
- A test with a multi-file course that would fail on the current code. See
  task 07.

## Open question

Is filename ordering good enough, or does `courses.yaml` need an explicit
file sequence per course? Explicit is more reliable and more work to
maintain. Given this is a single-user project with a handful of courses,
natural-sorted filenames plus a consistent naming convention is probably
the right trade — but check what the real Drive folder actually looks like
before deciding.

## Files

- `graph/nodes/pacing_agent.py:85`
- `ingest/chunk.py:30,63,66` — where `order` is assigned per document
