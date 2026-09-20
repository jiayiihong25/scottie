# 09 — Reconcile stale docs with the built code

**Size:** XS · **Status:** done — README and design-doc header updated; chose to document
the chain as the intended design (no conditional edge).

## Problem

Someone reading this repo cold gets the wrong model of it, in three places.

**1. `README.md:8-25`** describes `pacing/` and `generate/` as the plan and
as unbuilt. Both were superseded by the LangGraph `graph/` package and
neither directory exists. `CLAUDE.md` is already correct on this; the README
was never updated.

**2. `docs/orchestration-design.md:3`** still reads "Status: design only,
not yet implemented." `graph/` was implemented in commit `9f4dcae`. The
header should say what's actually true: implemented as a proof of concept,
untested, not yet running end to end — and link to `docs/tasks/` for what's
outstanding.

**3. `content_router` — code and doc disagree.** The doc specifies a
LangGraph **conditional edge** (`docs/orchestration-design.md:66-73`). The
implementation is a plain helper, `split_by_content_type`
(`graph/nodes/content_router.py:14`), with `concept → card → packet` wired
as an unconditional chain (`graph/build.py:45-48`).

The observable behavior is spec-compliant — an agent with nothing of its
type due produces an empty list, which is the documented normal case — and
`build.py:3-9` documents the deviation honestly. So this is low functional
risk. But the doc and the code now describe different architectures, and
one of them should change. **Either is defensible; pick one deliberately
rather than leaving both.** The simpler chain is arguably the better answer
given `CLAUDE.md`'s preference for debuggable-before-sophisticated.

## What done looks like

- README describes `graph/`, `ingest/`, and the real current state.
- Design doc header is accurate and points at `docs/tasks/`.
- `content_router`: either implement the conditional edge, or update the doc
  to describe the chain as the intended design and say why.

## Files

- `README.md:8-25`
- `docs/orchestration-design.md:3`, `:66-73`
- `graph/nodes/content_router.py:14`, `graph/build.py:3-9,45-48`
