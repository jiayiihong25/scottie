# Multi-agent orchestration design (LangGraph + OmniRoute)

Status: **design only, not yet implemented.** This document proposes the
graph structure, state schema, and model-routing approach for rebuilding
`pacing/` and `generate/` (and re-wrapping the already-built `ingest/`) as
a LangGraph pipeline that calls models through a self-hosted OmniRoute
gateway. Nothing here changes the existing `ingest/` code — see
"What stays deterministic" below.

## Why LangGraph here

`ingest/` today is a straight-line function pipeline (extract -> chunk ->
classify), which is exactly right for that stage per CLAUDE.md's
"deterministic and inspectable" convention. `pacing/` and `generate/` are
where actual judgment calls start (how hard is this chunk, what kind of
question tests it well, is a review overdue enough to bump priority) —
that's the part worth modeling as agents with explicit state, conditional
routing, and retries, rather than one big prompt or one big function.

## What stays deterministic (unchanged)

- `ingest/extractors/*` — PDF/slide/notes extraction
- `ingest/chunk.py` — chunking, chunk-id derivation
- `ingest/classify.py` — the conceptual/memorization keyword heuristic

These get wrapped as a single **tool call**, not rebuilt as agents: a
graph node calls `ingest.build_index()` exactly as it exists today. No
LLM involvement, no non-determinism, same test suite still applies.
Rethinking classification as LLM judgment is explicitly out of scope
(see prior conversation — deterministic-first per CLAUDE.md).

## Graph structure

```
                         ┌─────────────────┐
                         │   ingest_node    │  (calls ingest.build_index(),
                         │  (deterministic) │   no LLM — see above)
                         └────────┬─────────┘
                                  │ ContentIndex
                                  ▼
                         ┌─────────────────┐
                         │  pacing_agent    │  decides: new-today vs.
                         │                  │  due-for-review, per chunk
                         └────────┬─────────┘
                                  │ today's assigned chunks
                                  ▼
                         ┌─────────────────┐
                    ┌────┤  content_router  ├────┐
                    │    └──────────────────┘    │
                    ▼             ▼               ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │ concept_agent│ │  card_agent  │ │ (future: more │
          │ (conceptual  │ │ (memorization│ │  specialized   │
          │  chunks →    │ │  chunks →    │ │  content-type   │
          │  questions)  │ │  Anki cards) │ │  agents)        │
          └──────┬───────┘ └──────┬───────┘ └────────┬────────┘
                  └────────────────┼───────────────────┘
                                  ▼
                         ┌─────────────────┐
                         │  packet_writer   │  assembles reading list +
                         │  (deterministic) │  questions + .apkg via genanki
                         └────────┬─────────┘
                                  ▼
                          output/ (morning packet + .apkg)
```

`content_router` is a **conditional edge**, not an agent — it inspects
each assigned chunk's `content_type` (already set by the deterministic
`ingest/classify.py`) and routes it to `concept_agent` or `card_agent`.
On a day where every due chunk happens to be conceptual, `card_agent`
simply never fires. That is correct LangGraph behavior, not a bug — see
"Partial participation" below for the one thing this requires of state
design.

Per-content-type ingest agents (a separate PDF agent / slides agent /
notes agent) are **not** included above: extraction is deterministic
and format-specific already inside `ingest/extractors/`, so there's no
judgment call there to hand to a model. If a real need for
format-specific *agent* behavior shows up later (e.g. "summarize slide
speaker notes differently than PDF body text"), that's a rider on
`ingest_node`'s output. Splitting it out now would add router nodes with
nothing but deterministic code behind them — the case flagged in the
last question I asked you.

## State schema

LangGraph threads one shared state object through every node. Keep it
as a `TypedDict` (or a Pydantic model, if you want field validation) so
every node's input/output contract is visible in one place:

```python
class PipelineState(TypedDict):
    # set by ingest_node
    content_index: ContentIndex          # from ingest.models
    ingest_errors: list[str]

    # set by pacing_agent
    exam_dates: dict[str, date]          # course -> next exam date
    assigned_chunks: list[Chunk]         # today's new + due-for-review
    pacing_notes: list[str]              # why each chunk was picked (debuggability)

    # set by concept_agent / card_agent — both optional, may be empty lists
    concept_questions: list[ConceptQuestion]
    anki_cards: list[AnkiCardDraft]

    # set by packet_writer
    packet_path: Path | None
    apkg_path: Path | None

    # cross-cutting
    errors: list[str]                    # any node can append; packet_writer
                                          # checks this before declaring success
    model_calls: list[ModelCallLog]      # for cost tracking, see below
```

### Partial participation

Because `content_router` may skip `card_agent` or `concept_agent`
entirely on a given day, **every field a node might not populate must
default to an empty list/`None`, and every downstream node must treat
"empty" as a normal case, not an error.** `packet_writer` in particular
must not assume both lists are non-empty — a concept-only day producing
zero Anki cards is valid, not a failure. This is the one concrete
consequence of the finer-grained-agents question from earlier: skipped
nodes are fine as long as the state schema and downstream reads are
written to expect it from day one.

## OmniRoute integration

OmniRoute exposes an OpenAI-compatible endpoint locally (e.g.
`http://localhost:20128/v1/chat/completions`), resolves `model` fields
against configured provider aliases, and has its own **combo** config
for fallback/cost-aware routing server-side. That means the pipeline
does not need to reimplement cost routing — it needs to:

1. **Point every agent at the same base URL**, via one shared client
   construction (e.g. `ChatOpenAI(base_url="http://localhost:20128/v1",
   api_key=..., model=<alias>)` if using `langchain-openai`, since
   OmniRoute is OpenAI-compatible and LangGraph nodes typically wrap a
   LangChain chat model).

2. **Pick a model *alias* per task, not a hard-coded provider/model.**
   A small config file (`config/models.yaml`) maps task type to the
   OmniRoute alias to request:

   ```yaml
   # config/models.yaml — aliases must exist in OmniRoute's own
   # /api/models/alias config; this file only says which alias each
   # task type asks for.
   pacing_agent: cheap-fast       # simple scheduling logic, low stakes
   concept_agent: mid             # needs to write a decent question
   card_agent: cheap-fast         # flashcards are short, mechanical
   ```

   Changing which physical model an alias points to (e.g. swapping
   which provider backs `mid`) happens in OmniRoute's own dashboard/API,
   not in this repo — that's the whole point of routing through a
   gateway instead of hardcoding `gpt-4o` or similar in code.

3. **Wrap every model call in one helper**, so retries, error handling,
   and cost logging live in exactly one place:

   ```python
   def call_model(task_type: str, messages: list, **kwargs) -> ModelResponse:
       alias = MODEL_CONFIG[task_type]
       response = client.chat.completions.create(model=alias, messages=messages, **kwargs)
       state["model_calls"].append(ModelCallLog(task_type, alias, response.usage, ...))
       return response
   ```

   Every agent node calls `call_model(...)`, never the OpenAI client
   directly. This is what makes it possible to swap OmniRoute for
   something else later, or add a circuit-breaker/retry policy, without
   touching agent logic.

4. **Fail loudly per CLAUDE.md.** If OmniRoute is unreachable (e.g. the
   local gateway isn't running that morning), `call_model` should raise
   rather than silently degrade — same "no human present to fix a bad
   run" principle already applied to `ingest/`.

## Proposed file layout

```
graph/
  state.py          # PipelineState TypedDict + sub-dataclasses
  nodes/
    ingest_node.py   # thin wrapper around ingest.build_index()
    pacing_agent.py
    content_router.py
    concept_agent.py
    card_agent.py
    packet_writer.py
  models.py          # call_model() wrapper + MODEL_CONFIG loading
  build.py           # assembles the StateGraph, defines edges
config/
  models.yaml         # task type -> OmniRoute alias
```

## Decisions (locked in)

Everything below was an open question in the first draft of this doc;
resolved in conversation and now the basis for implementation.

- **Hosting**: OmniRoute deployed to Railway (Hobby plan, ~$5/month —
  the one recurring cost of this whole project). Self-hosted, always-on,
  reachable by a cloud Claude Code Routine.
- **Model cost**: OmniRoute configured with free-tier providers
  (Pollinations, OpenCode Free, Cloudflare AI, etc.) as the default
  aliases; a paid provider, if ever added, is fallback-only. Target
  steady-state model cost: $0/month.
- **Auth**: `OMNIROUTE_BASE_URL` and `OMNIROUTE_API_KEY` come from
  `.env` locally and from the Claude Code environment's own env vars
  when running inside a Routine — never hardcoded, never committed
  (see `.env.example` once added).
- **Course material storage**: Google Drive (already connected as an
  MCP tool in this environment). `data/` stops being "whatever's on
  your laptop" and becomes "synced from a Drive folder" — the
  ingest step needs a small adapter to pull files from Drive into the
  session's working directory before `ingest.build_index()` runs, since
  a Routine's container starts empty each morning.
- **Trigger**: a cron-scheduled Claude Code Routine, `create_new_session_on_fire`,
  timed to finish before you wake up.
- **Output #1 — the morning packet**: a single HTML page, generated by
  `packet_writer` and published as a **private Claude Artifact**,
  republished to the same URL every morning. Signed in via your
  claude.ai account already — no separate auth system, no extra
  hosting. Can optionally grow a "past packets" history view later
  using the Artifact's own small database capability, not a new service.
- **Output #2 — the Anki deck**: the generated `.apkg` can't live in a
  web page, so it's pushed to you directly as a file each morning
  (`SendUserFile`, proactive) alongside the Artifact link. You still
  import it into Anki yourself — no AnkiConnect/live-instance
  dependency, consistent with the original decision in `CLAUDE.md`.
- **Explicitly out of scope for cost reasons**: a standalone web app
  with its own login/server/database. The Artifact approach was chosen
  specifically to avoid that additional recurring cost and complexity.

## Per-course packet reminders

Each instructor posts material on their own schedule, and that cadence
is data, not code — it lives per-course in `docs/courses/<course>.md`
(e.g. `docs/courses/philosophy-1230.md`'s "Upload reminders" section),
not hardcoded into `graph/`. `packet_writer` should read each active
course's reminder entries and, on the matching day, surface a short
"upload X to Drive today" line at the top of the morning packet
alongside the reading list — separate from the concept
questions/Anki cards, since it's an action item for the user, not
generated content. This keeps the reminder text itself editable
without touching pipeline code: adding/adjusting a course's upload
cadence is a doc edit, not a `graph/` change.

## Remaining open items before implementation starts

1. Exact Drive folder structure/permissions for course material (mirror
   the existing `data/<course>/<topic>/<file>` convention, just rooted
   in Drive instead of local disk).
2. Your actual OmniRoute URL + API key, and which aliases you've set up
   (once the Railway deploy is done).
3. Preferred send time for the daily Routine (needs a concrete
   hour/timezone to convert to a UTC cron expression).
