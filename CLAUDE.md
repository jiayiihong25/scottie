# Project context

Personal exam-prep automation. Not a product — single user, single owner.

## Architecture

Content store (ingest/) -> Pacing engine (pacing/) -> Daily routine (generate/)
-> Morning packet + Anki deck (output/), with performance feeding back into
the pacing engine.

- `ingest/`: turns PDFs, slides, and notes into a normalized index. Each
  chunk needs: course, topic/unit, source file, page or slide range, raw
  text, and a content-type tag (conceptual vs. memorization-based).
- `pacing/`: given exam dates and the content index, decides what's new
  today vs. what's due for spaced review. Keep this deterministic and
  inspectable — it's the part most worth getting right.
- `generate/`: for today's assigned chunks, produces (a) a reading list
  with page ranges, (b) concept-check questions, (c) Anki cards for
  memorization-tagged content, via `genanki`.
- `output/`: the generated artifacts. Gitignored — this is the user's
  actual coursework content, not something to version.

## Conventions

- `data/` and `output/` are gitignored — they hold personal course
  material and generated study content, never commit them.
- Keep the pacing algorithm simple and debuggable before adding
  sophistication (e.g. start with a fixed first-pass + N-review-pass
  cadence before anything adaptive).
- This eventually runs unattended as a Claude Code Routine on a daily
  cron schedule — write generation logic assuming no human is present
  to fix a bad run, so fail loudly (clear error output) rather than
  silently producing an empty or malformed morning packet.
