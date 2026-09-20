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
- **Delivery boundary (decided in task 02)**: the Artifact and
  `SendUserFile` tools belong to the Claude Code session, not the Python
  process. So `packet_writer` only *produces files*: on success it writes
  `output/morning_packet.html`, optionally `output/morning_deck.apkg`, and
  `output/delivery.json` (`{"date", "packet", "apkg"}`, `apkg` null on a
  no-card day). The Routine prompt owns delivery: it reads the manifest,
  republishes the packet to the stored Artifact URL, and sends the deck.
  On any error `packet_writer` raises and deletes a stale manifest — **no
  `delivery.json` means nothing is delivered**, and the Routine must treat
  its absence as a failed run. The Artifact URL is persisted next to
  `pacing_state.json` (task 01 syncs both); the first run creates the
  Artifact and records the URL, later runs update by URL.
- **Deck cadence**: one deck per day containing only that day's cards,
  reusing the fixed model/deck IDs so Anki merges rather than duplicates.
  Not cumulative — re-importing old notes buys nothing.
- **Explicitly out of scope for cost reasons**: a standalone web app
  with its own login/server/database. The Artifact approach was chosen
  specifically to avoid that additional recurring cost and complexity.

## Grading-scheme awareness (effort optimization)

The stated goal of this project isn't "review everything spaced-out
optimally" — it's highest grade for lowest effort. As currently
specified, `pacing_agent` only sees `exam_dates` + the content index, so
it has no way to know that, e.g., a course only requires 8 of 10
assignments for full marks, or offers a research-credit option that
substitutes for a chunk of the syllabus. Without that, the pipeline will
happily schedule review for material that's already "bought back" by
slack elsewhere in the grading scheme — the opposite of the goal.

### What a grading scheme actually is

Syllabus-level structure, not lecture content:

- **Drop/threshold rules**: "best 8 of 10 assignments," "top 5 of 6
  quizzes," lowest-N-dropped patterns.
- **Alternate/substitute credit**: research credit, optional
  participation marks, or other paths that award full-weight credit
  without doing the "default" assigned work.
- **Already-banked progress**: how many of the above the user has
  already completed or locked in this term — this determines whether a
  given remaining assignment is still load-bearing or now optional.

This is structural per-course metadata, not something `ingest/`'s
chunker should touch — a syllabus isn't a study-content source, and this
data changes rarely (once per term, plus manual updates as credit gets
banked), unlike lecture chunks which change per file dropped in Drive.

### Where it lives

A new small deterministic module, **not** a `graph/` agent — same
"deterministic where possible" convention CLAUDE.md sets for
`pacing_agent` itself:

```
config/
  grading_schemes.yaml   # course -> rules + banked progress, hand-maintained
graph/
  nodes/
    grading_scheme_loader.py  # thin loader, validates the YAML into
                               # GradingScheme objects, no LLM call
```

`config/grading_schemes.yaml` sketch:

```yaml
DH:
  assignments:
    total: 10
    required_for_full_marks: 8
    completed: 6          # update by hand as you submit / bank credit
    remaining_load_bearing: 2   # derived, or hand-set — see below
  alt_credit:
    - name: research_credit
      covers: [unit_4, unit_7]   # topic/unit ids this substitutes for
      status: confirmed          # confirmed | pending | not_pursuing
OtherCourse:
  assignments:
    total: 6
    required_for_full_marks: 6
    completed: 3
  alt_credit: []
```

`required_for_full_marks - completed` (clamped at 0) gives
`remaining_load_bearing`: once that hits 0, no further assignment in
that course is worth pipeline attention regardless of due dates. Keep
this arithmetic in the loader, not hand-maintained, so it can't drift
out of sync with `completed`.

### State schema addition

```python
@dataclass
class GradingScheme:
    course: str
    assignments_total: int
    required_for_full_marks: int
    assignments_completed: int
    alt_credit: list[AltCredit]   # each: name, covers: list[topic/unit id], status

    @property
    def remaining_load_bearing(self) -> int:
        return max(0, self.required_for_full_marks - self.assignments_completed)


class PipelineState(TypedDict):
    ...
    # set by grading_scheme_loader
    grading_schemes: dict[str, GradingScheme]   # course -> scheme, may be {}
    ...
```

Same "partial participation" rule as the rest of the schema: a course
with no entry in `grading_schemes.yaml` just means an empty/absent
`GradingScheme` for it, and `pacing_agent` treats that as "no slack
known — pace normally," not an error.

### How `pacing_agent` uses it

Two effects, both before spaced-repetition logic runs:

1. **Skip chunks covered by confirmed alt-credit.** If a chunk's
   `topic`/unit is listed under an `alt_credit` entry with
   `status: confirmed`, `pacing_agent` excludes it from
   `assigned_chunks` outright and logs why in `pacing_notes` (e.g.
   `"DH unit_4 skipped — covered by research_credit"`). `pending` status
   does *not* skip — only confirmed slack is safe to bank on.
2. **Deprioritize, don't necessarily skip, when `remaining_load_bearing`
   is 0.** If a course has already banked full marks on the
   assignment/quiz component the scheme tracks, chunks tied to that
   component drop in priority (or are excluded, if you want strict
   effort-min behavior) even if nothing has explicitly marked them as
   alt-credited — the "why review something that's mathematically
   already worth zero" case.

This stays deterministic rule application (lookup + arithmetic), so no
`call_model()` involvement and no change to the "keep pacing simple and
debuggable" convention — same as the rest of `pacing_agent`.

### Maintenance model

`grading_schemes.yaml` is hand-edited, not ingested from Drive or
parsed from the syllabus PDF automatically. Syllabi are irregular
documents and getting "8 of 10, best-of, alt-credit" parsing right via
an LLM risks silently misreading a real grading rule — worse than doing
nothing, since a wrong skip costs a grade. Auto-parsing as a *suggestion*
you manually confirm into the YAML is a reasonable future add-on, but
starts here as manual, matching CLAUDE.md's "start simple before
sophistication" convention.

### Open items

1. Whether `remaining_load_bearing == 0` should **exclude** chunks
   outright or just **deprioritize** them relative to exam-driven
   review — depends how strictly you want to trust the banked-progress
   math against, e.g., a late grade change.
2. Whether alt-credit coverage is tracked at `topic`/unit granularity
   (as sketched) or needs finer chunk-level mapping for courses where a
   research credit only covers part of a unit.
3. Update cadence for `completed` — manual edit after each submission,
   or a lightweight prompt from the morning packet itself asking "did
   you submit assignment N yesterday?" (adds a v2 feedback loop, not
   needed for v1).

## Remaining open items before implementation starts

1. Exact Drive folder structure/permissions for course material (mirror
   the existing `data/<course>/<topic>/<file>` convention, just rooted
   in Drive instead of local disk).
2. Your actual OmniRoute URL + API key, and which aliases you've set up
   (once the Railway deploy is done).
3. ~~Preferred send time for the daily Routine.~~ Decided: 6:00 AM
   America/Toronto (cron `0 10 * * *` in daylight time, `0 11 * * *` after
   2026-11-01). The Routine prompt lives in `routine/daily-prompt.md`.
4. **Drive access mechanism (task 01's fork): decided — the Routine prompt
   pulls from and pushes to Drive via the Drive MCP connector**, and the
   Python pipeline stays dependency-free and reads only local `data/`. Local
   runs therefore need `data/` populated by hand. Task 01 is now about the
   prompt's sync steps and the Drive folder layout, not Python code.
