# Philosophy 1230 — course syllabus context

Course-specific facts for ingest/pacing. Not code — reference data for
building the content index and pacing decisions for this course.

## Schedule

- Runs weekly. New lesson (chapter) posted every Wednesday.
- Chapter 1: posted last Wednesday.
- Chapter 2: posted this Wednesday.
- Each lesson includes two practice exercises, due the following
  Wednesday at 4:00 PM (i.e. one week after posting).

## Materials

- Textbook: free ebook format.
- Some readings are marked **optional**: not tested, but useful for
  understanding. Treat these as lower priority than required readings
  when pacing — they should not compete with tested content for a
  given day's review slot, but can be surfaced as supplementary.

## Lesson plan / material access window

- The course is structured as one lesson per week, numbered
  sequentially (Lesson 1, Lesson 2, ...).
- Lesson 1 has already been given (last Wednesday). Lesson 2 is
  posted starting tomorrow (this Wednesday).
- **Access is currently limited through Lesson 7** — module
  textbook PDFs for Lessons 1–7 will be uploaded to Drive as they
  become available. Material beyond Lesson 7 is not yet accessible.
- **Known future update needed:** once Lesson 7 is reached, this doc
  (and Drive access) will need to be refreshed with the next batch of
  lessons — this is a standing TODO, not a one-time task. Flag this in
  the packet as a reminder once pacing approaches Lesson 7, per
  "Per-course packet reminders" in `docs/orchestration-design.md`.

## Upload reminders

- Lectures post every Wednesday. **Every Thursday morning**, upload the
  incoming week's Wednesday lecture material to Drive (source for
  `ingest/`).
- This should surface in the morning packet as a standing Thursday
  reminder — see "Per-course packet reminders" in
  `docs/orchestration-design.md` for how `packet_writer` is meant to
  pick this up once built.

## Uploaded to Drive so far

- All "C" module lessons (critical-thinking companion site content,
  e.g. C01, C02, ...) — uploaded, labeled `C0X`.
- All "A" module lessons — uploaded, labeled `A0X`.

## Known gap: Module A practice exercises

- Module A has a good number of practice exercises that have **not**
  been uploaded or reviewed yet.
- Flag this during pacing/review: don't assume Module A's exercise
  set is complete just because the lesson content is in Drive.
  Someone (the user) still needs to go through and add/review those
  exercises. Surface this as an open action item in the packet until
  resolved — same mechanism as other per-course reminders, see
  "Per-course packet reminders" in `docs/orchestration-design.md`.

## Chapter 1 (week 1, last Wednesday)

- Source PDF: `lau-chap1.pdf` (not committed — belongs in `data/`,
  per the ingest pipeline; course material lives in Drive, not the repo).
- Companion site: https://philosophy.hku.hk/think/critical/
- Required readings: C01, C02, C03, C05, C06 (includes reading the
  Cognitive Reflection Test answers).
- Optional readings: C04, C07, C08, C09.
