# Creative coursework assist (DH2120) — design

Status: **design only, not yet implemented.**

## Scope and the integrity boundary

This is a second, separate module from the exam-prep pipeline — same
repo, same Drive/OmniRoute infrastructure, different purpose: help with
the *repetitive* parts of a creative course's weekly workflow, not
produce the creative deliverable itself.

This project's own history already flagged the risk here: an earlier,
broader idea ("an AI system to autonomously complete assignments with a
human review gate") was deliberately set aside because producing
submittable coursework crosses into academic integrity territory
*regardless of review*. What's being built now is narrower than that,
and grounded in DH2120's actual syllabus rather than a general rule:

> "You will interact with AI for a portion of the Weekly Creative
> Sprints (Augmented Brainstorming) to generate, challenge, or diversify
> ideas. You may use any generative AI tool you prefer... You are not
> required to pay for a subscription."

DH2120 explicitly designs AI assistance into one named step of the
assignment. That step is in scope to automate. The rest of the
assignment is not, per your own split (confirmed below) — this module
does not touch it.

## DH2120's actual weekly structure (from the syllabus)

Every week has a **Weekly Creative Sprint** (worth 60% of the course:
6% × best 10 of 11, +10% collaboration) with five components, due
Thursdays 8am (Collaboration) / Fridays 11:59pm (Review):

| Step | Word count | Automate? |
|---|---|---|
| Preparation | 100-120 words | **No** — personal reflection, stays yours |
| Augmented Brainstorming | 3-5 Q&A | **Yes** — syllabus-sanctioned AI step |
| Design/Creation | 100-150 words | **No** — the actual creative work |
| Collaboration | (in-tutorial) | N/A — happens in person |
| Review | 100-120 words | **No** — personal reflective peer review |

Plus, separately from the five graded steps: you want a **synopsis of
the week's assigned reading/reference material** before doing your own
work, so you understand the context going in. This is study/prep, never
submitted anywhere — same category as the exam-prep pipeline's reading
summaries, not a graded-work concern at all.

## What this module produces, weekly

1. **`reading_synopsis`** — a short summary of that week's assigned
   material, pulled from the DH2120 course schedule (e.g. "Week 3:
   Twyla Tharp — Dancing, Habit and Discipline") and whatever's been
   ingested for that topic. Informational only.
2. **`brainstorm_draft`** — a first-pass set of 3-5 questions and
   answers for that week's Augmented Brainstorming step. **This is a
   draft, not a submission.** The syllabus's own framing is that *you*
   interact with AI to generate/challenge/diversify ideas — the
   expectation is genuine engagement, not a pasted-in AI transcript. The
   tool's job is to save you the "stare at a blank page" cost of
   starting that interaction, not to finish it for you. Output should
   read as a starting point you edit into your own voice/ideas before
   it goes anywhere near a submission.

Everything else — Preparation, Design/Creation, Collaboration, Review —
this module does not touch, generate a draft for, or otherwise get
near. That's deliberate, not an oversight to fix later.

## Architecture

Reuses existing infrastructure rather than building a parallel system:

- **Input**: DH2120's Drive folder (already exists) — add the week's
  reading/reference material there same as any other course; reuses
  `ingest/extractors/*` unchanged to pull text out of it.
- **Model calls**: same `call_model()` wrapper and OmniRoute gateway as
  `graph/`. New aliases in `config/models.yaml` for this module's two
  tasks (probably `mid` for both — brainstorming needs real ideation
  quality, and a bad synopsis defeats its own purpose).
- **No LangGraph needed here.** Two independent generation tasks, no
  multi-step state to thread, no conditional routing — this is
  correctly a couple of plain functions, not a graph. Don't build
  orchestration machinery this doesn't need (same "keep it simple"
  principle CLAUDE.md already states for `pacing_agent`).
- **Cadence**: weekly, not daily — DH2120's cycle is Thursday/Friday
  deadlines, so this has its own weekly-scheduled Routine, separate from
  the exam-prep pipeline's daily one. **Fires Tuesday morning** — the
  week's content posts Monday morning, so Tuesday is the earliest point
  the reading/reference material is actually available to synthesize
  from, and it still leaves Tuesday through Thursday 8am to work with
  the brainstorm draft rather than getting it the night before it's due.
- **Delivery**: same private-Artifact pattern as the exam-prep morning
  packet — one page, republished weekly to the same URL, opens already
  signed in on your phone/laptop. No separate file push needed here
  (unlike the exam-prep pipeline's `.apkg`) since both outputs are just
  text, not a format an Artifact can't hold.

## Proposed file layout

```
creative_assist/
  __init__.py
  synopsis.py       # generate_reading_synopsis(week) -> str
  brainstorm.py      # generate_brainstorm_draft(week) -> list[QA]
  courses/
    dh2120.yaml       # week -> topic/person mapping, pulled from the
                       # syllabus's course schedule table
```

## Decisions (locked in)

1. **Delivery format**: private Claude Artifact, same pattern as the
   exam-prep morning packet (see above).
2. **Trigger timing**: weekly, **Tuesday morning** — after Monday's
   content posts, well ahead of the Thursday 8am deadline. Exact hour
   still needs a concrete timezone to convert to a UTC cron expression,
   same open item as the exam-prep pipeline's daily send time.
3. **Scope stays strictly DH2120.** Not extended to other courses. If
   that changes later, re-run the same syllabus-policy check done here
   before adding any course — no default assumption carries over.

## Remaining open item

- Exact send hour + timezone for the Tuesday Routine (mirrors the
  exam-prep pipeline's still-open daily send-time question).
