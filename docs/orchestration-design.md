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
                         │  (deterministic) │  due-for-review, per chunk
                         └────────┬─────────┘
                                  │ today's assigned chunks
                                  ▼
                         ┌─────────────────┐
                         │  generate_agent  │  per chunk, branches on
                         │                  │  content_type: writes a
                         │                  │  concept question OR an
                         │                  │  Anki card draft
                         └────────┬─────────┘
                                  ▼
                         ┌─────────────────┐
                         │  packet_writer   │  assembles reading list +
                         │  (deterministic) │  questions + .apkg via genanki
                         └────────┬─────────┘
                                  ▼
                          output/ (morning packet + .apkg)
```

**Revision (superseding an earlier 5-node draft):** `concept_agent` and
`card_agent` were originally separate nodes with a `content_router`
conditional edge between them. Merged into one `generate_agent` after
review — the two nodes differed only in prompt template and (optionally)
which OmniRoute alias to use per `content_type`; the actual code around
each (call `call_model()`, parse the response, handle the empty case)
was identical. Splitting them bought correctness nothing and duplicated
boilerplate. `content_router` as a standalone node/edge is gone too —
`generate_agent` just branches internally per-chunk on the `content_type`
field `ingest/classify.py` already set.

The two-node version's only real property was letting `concept_agent`
and `card_agent` run **in parallel** (as the only two nodes in the whole
graph with no dependency on each other). Rejected as not worth the
duplication: this pipeline makes a handful of model calls once a day,
unattended, with nobody waiting on the result live — the wall-clock
difference between running those calls concurrently vs. sequentially
inside one node is on the order of seconds, invisible against an
overnight run. Parallel nodes are worth it when a human is waiting on
latency; that's not this pipeline. If call volume ever grows enough to
matter, `generate_agent` can dispatch its own calls concurrently
(threads/`asyncio.gather` over the assigned chunks) without needing to
become two graph nodes again.

Per-content-type *ingest* agents (a separate PDF agent / slides agent /
notes agent) are **not** included above, for the same reason: extraction
is deterministic and format-specific already inside `ingest/extractors/`,
so there's no judgment call there to hand to a model.

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

    # set by generate_agent — both may be empty depending on which
    # content types were actually assigned today (see "Partial participation")
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

Because `generate_agent` may find zero chunks of one `content_type`
assigned on a given day (e.g. everything due today happens to be
conceptual), **`concept_questions` or `anki_cards` can legitimately come
back empty, and every downstream node must treat "empty" as a normal
case, not an error.** `packet_writer` in particular must not assume both
lists are non-empty — a concept-only day producing zero Anki cards is
valid, not a failure. This was originally framed around a node getting
skipped entirely (back when routing was a separate graph edge); the
principle is unchanged now that it's an internal branch in one node —
only the mechanism moved.

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
   # task type asks for. pacing_agent is deterministic (no model call)
   # and isn't listed; generate_agent looks up by content_type since
   # it's one node handling both.
   generate_agent:
     conceptual: mid           # needs to write a decent question
     memorization: cheap-fast  # flashcards are short, mechanical
   ```

   Changing which physical model an alias points to (e.g. swapping
   which provider backs `mid`) happens in OmniRoute's own dashboard/API,
   not in this repo — that's the whole point of routing through a
   gateway instead of hardcoding `gpt-4o` or similar in code.

3. **Wrap every model call in one helper**, so retries, error handling,
   and cost logging live in exactly one place:

   ```python
   def call_model(content_type: str, messages: list, **kwargs) -> ModelResponse:
       alias = MODEL_CONFIG["generate_agent"][content_type]
       response = client.chat.completions.create(model=alias, messages=messages, **kwargs)
       state["model_calls"].append(ModelCallLog(content_type, alias, response.usage, ...))
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
    ingest_node.py    # thin wrapper around ingest.build_index()
    pacing_agent.py
    generate_agent.py # branches per-chunk on content_type internally
    packet_writer.py
  models.py          # call_model() wrapper + MODEL_CONFIG loading
  build.py           # assembles the StateGraph, defines edges
config/
  models.yaml         # content_type -> OmniRoute alias, under generate_agent
```

## Decisions (locked in)

Everything below was an open question in the first draft of this doc;
resolved in conversation and now the basis for implementation.

- **Hosting**: OmniRoute deployed to Railway (Hobby plan, ~$5/month —
  the one recurring cost of this whole project), **with sleep-on-idle
  (Serverless mode) enabled** so it scales to zero between the daily
  Routine's requests instead of billing 24/7 uptime — keeps actual
  usage well under the $5 included credit. Self-hosted, reachable by a
  cloud Claude Code Routine. Trade-off: a cold-start delay on the first
  request after idle, a non-issue for an unattended morning run.
  Base URL is live: `https://omniroute-production-e33a.up.railway.app/api/v1`
  — note this instance uses `/api/v1`, not the generic `/v1` path shown
  in OmniRoute's own docs; verify against the dashboard if redeployed.
- **Model cost**: OmniRoute configured with free-tier providers
  (Pollinations, OpenCode Free, Cloudflare AI, etc.) as the default
  aliases; a paid provider, if ever added, is fallback-only. Target
  steady-state model cost: $0/month.
- **Auth**: `OMNIROUTE_BASE_URL` and `OMNIROUTE_API_KEY` come from
  `.env` locally (see `.env.example`) and from the Claude Code
  environment's own env vars when running inside a Routine — never
  hardcoded, never committed. Both set and **verified working**
  end-to-end (see open items for the alias gotcha found during
  verification).
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

## Drive structure — live

The Google Drive folder ("JiaYi Courses") is populated:

```
JiaYi Courses/
├── courses.yaml          # exam dates + final_cumulative per course
├── _syllabi_intake/      # drop zone for future syllabi (currently empty)
├── PHILOSOP1230/         # syllabus moved in as ordinary course material
├── DH2120/
├── POLSCI2191/
├── MOS2320/
└── PSYCH1002/
```

Syllabi are treated as ordinary ingestible material (dropped straight into
their course folder), not special config — per the earlier decision to
defer topic-weighting/syllabus-aware pacing to a v2, not build it into
`pacing_agent` now.

### `courses.yaml` schema addition: `final_cumulative`

Pulled directly from reading the actual syllabi — several state explicitly
whether the final exam is cumulative or only covers post-midterm material.
This is real input for `pacing_agent`, not just metadata:

- `final_cumulative: true` — every chunk in the course stays in the spaced-
  review rotation right up to the final, even ones covered weeks ago.
- `final_cumulative: false` — pre-midterm chunks can wind down their review
  cycle once the midterm passes; only post-midterm chunks need to be fresh
  for the final.
- `final_cumulative: null` — not stated in the syllabus; `pacing_agent`
  should default to treating it as cumulative (safer to over-review than
  have a chunk go stale that turns out to be tested).

Several exam dates in the current `courses.yaml` are explicitly marked
`PLACEHOLDER` (Registrar-scheduled finals not yet published, standard for
Western mid-September) — update the file once real dates are posted;
`pacing_agent` treats them as provisional targets until then.

## Remaining open items before implementation starts

1. ~~Exact Drive folder structure~~ — done, see above.
2. ~~OmniRoute reachability~~ — **verified working end-to-end**, via
   `scripts/test_omniroute.py auto` run from a real machine (the
   original "Default" Claude Code environment has a restricted egress
   allowlist that blocks Railway entirely — a separate "SCOTTIE"
   environment was created with broader network access; use that
   environment for the actual daily Routine). `model: "auto"` (lets
   OmniRoute pick a working free provider) returned `HTTP 200` and a
   real completion. **Gotcha found**: the named alias `cheap-fast`
   returned `HTTP 400` — "Unable to determine provider for model
   'cheap-fast'... ensure the model is added as a combo entry" — meaning
   named aliases from `config/models.yaml` are not actually usable yet
   until properly saved in OmniRoute's own dashboard (Aliases/Models
   section; exact save format isn't documented in OmniRoute's own
   wiki). Until aliases are confirmed working individually, `"auto"` is
   a safe fallback default for any model reference.
3. ~~Preferred send time for the daily Routine~~ — **8:30 AM Eastern**,
   both this pipeline and `creative_assist/`. Cron runs in fixed UTC, so
   this needs re-deriving whenever US Eastern's DST offset changes:
   - Now through Sun Nov 1, 2026 (EDT, UTC-4): **12:30 UTC**
   - From Nov 1, 2026 onward (EST, UTC-5): **13:30 UTC** — remember to
     update both Routines' cron expressions then, they will not
     auto-adjust.
4. Real final exam dates — deliberately deferred; Western doesn't
   publish these until partway through term. Revisit `courses.yaml`
   when they're out, no urgency now.
5. **Model-routing choice for `generate_agent`** — discussed but not
   yet decided: call OmniRoute (free-tier, now confirmed working, but
   real aliases still need dashboard setup), OmniRoute with your own
   Anthropic key added as a paid provider, or skip the HTTP call
   entirely and have the Routine's own Claude session reason directly
   (uses Claude Code plan usage, not a separate bill). These are
   mixable per-task, not an all-or-nothing pipeline choice — e.g.
   direct reasoning for concept questions, OmniRoute free-tier for Anki
   cards, is a legitimate combination. Still needs a final call before
   `call_model()`/`generate_agent` gets built.
