# Polish Typing Tutor

An offline terminal application for learning Polish through recall and typing,
with short learning steps and FSRS scheduling.

## Current course: Teach Yourself Polish, lessons 1–7

The bundled course now follows **M. Corbridge-Patkaniowska, Teach Yourself Polish**
(Roy Publishers, New York), using the supplied scan's printed pages **7–31** and
answer-key pages **217–219**. Lesson 8 and later lessons are not included.

There are **146 vocabulary concepts, 634 learning objectives, and 2,240 practice
variants** across seven lessons. These are tutor counts, not a claim that the book
contains 2,240 distinct questions: vocabulary recall, clozes, and full production
reuse the same source material.

The course includes source-derived lesson notes, vocabulary and inflection tables,
examples, numbered translation exercises, questions and guided answers, formal
address, singular/plural transformations, and imperatives. Press **F2** during study
to read the current lesson's notes and selected reading-aloud drills. The application
does not evaluate pronunciation or provide recorded audio.

Polish-to-English readings are explicitly labelled **reversed reading practice**:
the tutor supplies an editorial English cue and asks for the book's Polish text.
Published key answers are distinguished from derived responses and editorial
alternatives. Source references appear with the exercises. See
[the source and adaptation notes](docs/course_source.md).

## Install and run

Python 3.12 or newer is required.

```powershell
python -m pip install -e ".[dev]"
polish-tutor
```

Run `polish-tutor --setup` to change the self-reference preference without deleting
progress. The preference is retained for later material; these lessons do not
practice first-person past-tense gender contrasts.

On the first launch with this course, old corpus cards become inactive, not deleted.
The new `ty.` identifiers start fresh and do not inherit mastery from unrelated old
cards. Existing history and profile preferences remain in the local database. Its
location is shown by `polish-tutor --data-path`. No manual reset is required.

## Study controls

- `Enter`: submit or continue. `Tab`: hint. `Ctrl+R`: reveal and copy correction.
- `F2`: lesson notes; `Esc` or `F2` returns to the same item. Consulting notes during
  a review counts as a hint. Long textbook items can be scrolled.
- `Esc`: pause. `Ctrl+Q`: save and quit. From pause, `R` opens the progress reset;
  history is deleted only after typing `DELETE` exactly.

Due reviews always take priority. There is no daily limit. Every objective starts
with a visible copy model and two cloze recalls. An unfamiliar productive form is
shown as `NEW FORM` before it is graded. Mature translation variants remain gated
until their words are ready. Reviews rotate through eligible source contexts.

Polish diacritics and the taught word order matter. Capitalization, surrounding
whitespace, and final punctuation are ignored. This is exact-target practice, not
an unrestricted translation evaluator: only the explicitly listed alternatives
are accepted. The original internal punctuation is retained.

## Corpus maintenance and tests

The compact, attributed source is `src/polish_tutor/data/teach_yourself.py`
and its seven adjacent `lesson_*.py` files.
`src/polish_tutor/book.py` compiles it deterministically without network access,
OCR, or generated content at runtime. Each Polish token must match the explicit
vocabulary/form inventory. The obsolete hand-written corpus generator is replaced.

```powershell
python scripts/build_course.py
python scripts/build_course.py --output course.yaml --notes lesson-guide.md
python -m pytest
```

`tests/test_course.py` checks the actual bundled book. The existing engine/UI tests
use a frozen legacy corpus under `tests/fixtures/` so their established examples
remain stable. That fixture is not bundled with the application. Additional book
integration tests cover progression, retained old history, and the notes screen.

The software's license does not confer rights to the source book. Book-derived
content retains its attribution and is not represented as original MIT-licensed
text; the supplied PDF itself is not distributed in this repository.
