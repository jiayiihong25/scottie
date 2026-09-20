# 04 — Don't discard the whole packet over one bad source file

**Size:** S · **Status:** not started

## Problem

Two deliberate designs collide.

`ingest/` collects per-file extraction errors and keeps going — a scanned
PDF it can't read shouldn't stop the other twelve files from being indexed.
`ingest_node` faithfully copies those into the shared error list:

```python
# graph/nodes/ingest_node.py:19-21
state["ingest_errors"] = list(index.errors)
if index.errors:
    state["errors"].extend(index.errors)
```

`packet_writer` then refuses to write anything if `state["errors"]` is
non-empty (`graph/nodes/packet_writer.py:41-46`), on fail-loudly grounds.

Net effect: **one unreadable PDF sitting in the Drive folder means no packet
at all, every morning, indefinitely** — and the run still pays for every
concept and card model call first, because the check happens at the last
node.

Both halves are individually right. The bug is that per-file extraction
warnings and genuine pipeline failures are being carried in the same list.

## What done looks like

Distinguish the two:

- **Per-file extraction warnings** — a source file couldn't be read, but the
  rest of the index is sound. The run should continue and the packet should
  render them as a visible banner ("couldn't read lecture-04.pdf"), so the
  user notices without losing the day's study material. Silently swallowing
  them is not acceptable either — the user needs to know a file is missing
  from their prep.
- **Fatal errors** — Drive unreachable, no content index at all, a model
  call failed. These should stop the run *before* the agent nodes fire, so
  a doomed run doesn't spend model calls on output that gets thrown away.

Concretely: keep `ingest_errors` out of `state["errors"]`, add the banner to
`_render_packet_html`, and move the fatal-error gate earlier in the graph.

## Open question

Is there a threshold where extraction warnings *should* be fatal? If 9 of 10
files fail to parse, a packet built from the remaining one is misleading —
it looks like a normal light day. A proportion-based rule ("more than half
the files failed") may be worth it, or may be over-engineering for a
single-user project. Start with the banner.

## Files

- `graph/nodes/ingest_node.py:19-21`
- `graph/nodes/packet_writer.py:41-46`, `:62-89`
- `graph/state.py:44-64` — `ingest_errors` vs `errors`
- `ingest/pipeline.py` — the collect-and-continue design being honored
