# Task specs

One file per outstanding piece of work, each sized to become its own PR.
Written after a gap analysis of the built code against
`docs/orchestration-design.md` and `CLAUDE.md` (2026-09-20).

Each file states: what's wrong today (with file:line evidence), what done
looks like, and the open questions that need a decision before coding.

## Critical path — nothing runs unattended until these land

| # | Task | Size |
|---|------|------|
| 01 | [Google Drive sync for course material + pacing state](01-drive-sync.md) | M |
| 02 | [Output delivery: Artifact publish + .apkg push](02-output-delivery.md) | M |
| 03 | [Daily Claude Code Routine](03-daily-routine.md) | S |

## Correctness

| # | Task | Size |
|---|------|------|
| 04 | [Don't discard the packet over one bad source file](04-error-gating.md) | S |
| 05 | [Fix cross-file chunk ordering](05-chunk-ordering.md) | S |
| 06 | [Harden call_model: empty completions, retries, timeout](06-call-model-hardening.md) | S |
| 07 | [Test coverage for graph/](07-graph-tests.md) | M |

## Features

| # | Task | Size |
|---|------|------|
| 08 | [Grading-scheme awareness](08-grading-schemes.md) | M |

## Housekeeping

| # | Task | Size |
|---|------|------|
| 09 | [Reconcile stale docs with the built code](09-doc-reconciliation.md) | XS |

Already fixed (see the PR this directory was added in): the `python -m graph`
date-parsing crash and `.env` never being loaded.
