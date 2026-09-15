# Source and adaptation record

## Source

M. Corbridge-Patkaniowska, *Teach Yourself Polish*, Roy Publishers, New York.
The supplied scan's title pages do not state a publication year; none is inferred.
The actual PDF contains 284 scanned pages, although the conversation preview
indexes only its first 150. Printed page numbers are PDF page numbers minus eight.
The PDF is not included in the repository.

| Lesson | Book heading | Printed pages |
| --- | --- | --- |
| 1 | Neuter nouns; qualifying pronoun and adjective | 7–10 |
| 2 | First conjugation; personal pronoun; formal address; na | 10–13 |
| 3 | Questions and interrogatives | 13–17 |
| 4 | Neuter nouns; functions of the genitive | 17–20 |
| 5 | Second conjugation | 21–23 |
| 6 | Neuter nouns; vowel interchanges; kie, gie | 23–27 |
| 7 | Adjectives and pronouns; cardinal numbers; imperative | 27–31 |

Lesson 7 stops before Lesson 8 on printed page 31. The answers used here come from
printed key pages 217–219 (PDF pages 225–227). The unnumbered pronunciation chapter
is not imported as an additional unit. Lesson-specific speech practice is retained
as selected reading-aloud material, not as machine-graded audio.

## What is source text and what is adapted

The course preserves the book's lesson order, terminology (including its numbered
conjugations), neuter-first presentation, and period vocabulary. Notes are concise
source-derived summaries rather than a facsimile of the grammar prose. Vocabulary
headwords use the form first introduced by the book, which need not be a modern
dictionary citation form. Form inventories include the forms needed by these
lessons' exercises and key, not hypothetical later-course paradigms.

The compact data contains 488 book-based items: 136 reading segments, 124 examples,
82 translation tasks, 48 present-tense table prompts, 44 other table prompts,
15 guided responses, 15 imperative prompts, 11 declension tasks, seven formal-address
responses, and six plural transformations. Some multi-sentence exercises are split
into labelled subitems. Seven address variants expand Lesson 3's first translation.
Alongside 146 vocabulary objectives these compile to 634 objectives and 2,240
practice variants. Initial and mature recalls reuse source material intentionally.

`reading` items reverse the book's Polish-to-English direction to suit a Polish
production tutor. Their English cues are editorial translations, not quotations
from an English answer key. Polish answers are the source reading text.
`translation` items use the published Polish key, including formal-address choices.
`response` items give guided key examples, not an exhaustive set of valid answers.
The prompts for table and transformation practice are adapted instructional cues.

Lesson 2's formal-address responses are derived from its tables. Lesson 6's
singular genitives are derived from Lesson 4: the key supplies only the plural
answers. These distinctions are included in the on-screen source context.
Clozes and vocabulary cards are tutor adaptations, not additional printed exercises.

## Explicit source discrepancies

- Lesson 2 prints `Pani ma moje pudełko.` beside an English translation containing
  “new box”; the Polish has no `nowe`. The cue follows the Polish, and the discrepancy
  is recorded in the item's context.
- Lesson 3's translation 3 key is punctuated as a statement although the prompt is a
  question. Its wording and printed punctuation are retained; final punctuation is
  not graded.
- Lesson 5 repeats exercise number 8 in both the exercise and key. The butter
  dialogue and singing question are separate `8a` and `8b` entries; subsequent
  printed numbering is not silently shifted.
- Lesson 6's plural exercise has `Szuka pióra.` but the key gives `Szukamy piór.`.
  The key remains canonical; `Szukają piór.` is an explicitly labelled derived
  alternative preserving the source's third person.

No attempt has been made to replace historical wording with a different modern
course. All editorial additions are supporting cues, summaries, or labelled
answers tied to the supplied lesson material. The source guide can be regenerated
with `python scripts/build_course.py --notes lesson-guide.md`.

## Scheduling and saved history

New concept, objective, and variant identifiers are namespaced `ty.`. The existing
course synchronizer marks removed cards inactive and adds new cards, retaining
old progress and the profile. It does not migrate mastery between unrelated courses.
Exact productive forms are still introduced before testing. Full translation cards
remain gated by vocabulary readiness; lexical introductions have no circular
sentence dependencies. Lesson notes during a graded review count as assistance.

## Validation

The corpus tests check source scope, exercise coverage, key samples, alternatives,
all Polish token mappings, dependency order, stable IDs, deterministic generation,
YAML round-tripping, and malformed-source failures. Legacy engine/UI tests keep a
frozen test-only corpus. Separate integration tests exercise the new book's engine
progression, SQLite synchronization, and notes-screen behavior.

Local validation during preparation: 34 corpus tests passed and Python compilation
succeeded. The full FSRS/Textual suite could not run in the preparation environment
because those dependencies were unavailable; run `python -m pip install -e ".[dev]"`
and `python -m pytest` in a normal development environment before merging.

Software licensing and book-content rights are separate. The book-derived material
is attributed, not claimed as original software-licensed content.
