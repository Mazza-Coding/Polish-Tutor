# Polish Typing Tutor

An offline terminal application for learning Polish through recall and typing. It
uses short learning steps followed by FSRS scheduling, Polish cloze prompts, and
English-to-Polish production. There are no multiple-choice drills.

## Course corpus

The bundled course now follows M. Corbridge-Patkaniowska's *Teach Yourself
Polish*. This release contains Lessons 1–7: lesson notes and vocabulary, the
printed translation exercises, the Lesson 2 formal-address drill, and the Lesson
6 plural/genitive exercises. The source page range is stored with every lesson so
that the terminal corpus can be checked against the book.

The book's Polish exercise text is transcribed into the corpus. The uploaded scan
does not include Part II (the answer key), so canonical Polish answers for the
English-to-Polish exercises are reconstructed from the grammar, examples, and
vocabulary in Lessons 1–7. Where the lesson explicitly permits several address
forms or wording variants, the tutor accepts multiple answers. Lesson 3 also asks
for open-ended answers to its Polish questions; those questions remain in the
recall material rather than being forced into one arbitrary canonical response.

The current bundle contains 7 lessons, 17 exercise sets, and 251 prompt variants.
The corpus is authored as a small `course_v1.yaml` manifest plus one readable YAML file per
lesson in `src/polish_tutor/data/`. `scripts/build_course.py` expands those sources into the
runtime schema for inspection and validation.

Progress is synchronized by objective ID. When upgrading from the previous Core
100 corpus, old cards are retained in the SQLite database but become inactive;
the Teach Yourself exercise sets start as new material.

## Study behaviour

Every exercise set begins with a visible Polish model. The first two recalls are
cloze prompts; later reviews rotate through the source exercise items. Due reviews
always take priority, and there is no daily new-objective limit. Polish diacritics
are required. Capitalization, surrounding whitespace, and final punctuation are
ignored.

The tutor tracks exact productive forms for concept-based courses. The Teach
Yourself corpus uses literal source-text mappings, so a word from a printed
exercise is not incorrectly treated as a new lexeme or unseen inflection.

## Install and run

Python 3.12 or newer is required.

```powershell
python -m pip install -e ".[dev]"
polish-tutor
```

Run `polish-tutor --setup` to change the first-person grammatical form without
losing progress. Progress is stored locally in the platform data directory shown
by `polish-tutor --data-path`.

## Study keys

- `Enter`: submit an answer or continue
- `Tab`: request a hint
- `Ctrl+R`: reveal the answer and enter copy correction
- `Esc`: pause
- `Ctrl+Q`: save and quit

From the pause screen, press `R` to open the progress reset. The tutor deletes
study history only after `DELETE` is typed exactly; the self-reference preference
is kept.
