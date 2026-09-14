# Project context

Personal exam-prep automation. Not a product — single user, single owner.
Full design rationale and decision history: `docs/orchestration-design.md`
— read it before touching `graph/`, `pacing/`, or `generate/`.

## Architecture (current target — see docs/orchestration-design.md for how we got here)

Google Drive (course material) -> ingest/ (deterministic, built) ->
LangGraph pipeline (graph/, pacing + generation as agents, model calls
routed through a self-hosted OmniRoute gateway) -> two outputs:
a private Claude Artifact (the morning packet: reading list + concept
questions) and an .apkg Anki deck pushed as a file. Triggered daily by
a cron-scheduled Claude Code Routine.

- `ingest/`: turns PDFs, slides, and notes into a normalized index. Each
  chunk needs: course, topic/unit, source file, page or slide range, raw
  text, and a content-type tag (conceptual vs. memorization-based).
  **Built and tested — deterministic, no LLM calls.** Stays that way;
  it gets wrapped as a single node in `graph/`, not rebuilt as an agent.
- `graph/` (not yet built): LangGraph pipeline replacing the originally
  planned plain-function `pacing/` and `generate/`.
  - `pacing_agent`: given exam dates + the content index, decides what's
    new today vs. due for spaced review. Keep this deterministic and
    inspectable where possible — it's the part most worth getting right.
    Reads `courses.yaml`'s `final_cumulative` field per course: `true`
    keeps every chunk in review rotation until the final; `false` lets
    pre-midterm chunks wind down after the midterm passes; `null`
    (not stated in the syllabus) defaults to cumulative — safer to
    over-review than let something go stale that's actually tested.
  - `generate_agent`: one node, branches per-chunk on `content_type` —
    conceptual chunks get a concept-check question, memorization chunks
    get an Anki card draft, via model calls routed through OmniRoute
    (never call a model client directly — see `call_model()` in the
    design doc). Originally two separate nodes (`concept_agent` /
    `card_agent`) plus a `content_router` edge; merged since the only
    difference between them was prompt template and alias, not control
    flow — see the design doc's "Revision" note. A content type with
    nothing due today just produces an empty list — normal, not a bug;
    every state field either branch might not populate must default to
    empty, and downstream nodes must treat "empty" as a normal case.
  - `packet_writer`: deterministic, assembles the reading list +
    questions into the Artifact page and the cards into an `.apkg` via
    `genanki`.
- **OmniRoute**: self-hosted AI gateway (Railway, ~$5/mo — the one
  recurring cost of this project), OpenAI-compatible endpoint. Every
  model call goes through it via aliases (`config/models.yaml`), free-tier
  providers first, so steady-state model cost is $0. Credentials
  (`OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`) come from `.env`
  (or the Routine's environment env vars), never hardcoded/committed.
- **Course material**: lives in Google Drive (connected as an MCP tool),
  not just local disk — a Routine's container starts empty each
  morning, so ingest needs to pull from Drive first.
- **Output delivery**: the morning packet is a private Claude Artifact,
  republished to the same URL daily (signed in via claude.ai already —
  deliberately not a standalone web app with its own login/hosting,
  ruled out for cost/complexity). The `.apkg` is pushed as a file
  alongside it, since a web page can't hold an Anki deck.

## Conventions

- `data/` and `output/` are gitignored — they hold personal course
  material and generated study content, never commit them.
- Keep the pacing algorithm simple and debuggable before adding
  sophistication (e.g. start with a fixed first-pass + N-review-pass
  cadence before anything adaptive). This applies to `pacing_agent` too
  — don't reach for LLM judgment where a deterministic rule works.
- This runs unattended as a Claude Code Routine on a daily cron
  schedule — write generation logic assuming no human is present to fix
  a bad run, so fail loudly (clear error output, `call_model` raises on
  an unreachable OmniRoute) rather than silently producing an empty or
  malformed morning packet.
- Every agent node calls a single shared `call_model()` wrapper, never
  a model client directly — that's what keeps OmniRoute swappable and
  cost logging centralized.
