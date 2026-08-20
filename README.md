# Polish Typing Tutor

An offline terminal application for learning Polish through recall and typing. It
uses short learning steps followed by FSRS scheduling, Polish cloze prompts, and
English-to-Polish sentence production. It contains no multiple-choice drills or
grammar lectures.

The tutor tracks exact productive forms as well as lexemes. When a context needs
an inflection the learner has not typed before, it first appears as a `NEW FORM`
copy model and is recalled 20 seconds later; an unseen form is never graded as
prior knowledge.

The hand-authored core contains 100 lexemes and 20 synthesis objectives across
680 exercises. Every lexeme rotates through two initial clozes and four distinct
translation contexts. Mature reviews prefer the least-seen, least-recent context,
and a context stays unavailable until every word it uses is ready.

## Install and run

Python 3.12 or newer is required.

```powershell
python -m pip install -e ".[dev]"
polish-tutor
```

Run `polish-tutor --setup` to change the first-person grammatical form without
losing progress. Progress is stored locally in the platform data directory shown
by `polish-tutor --data-path`.

There is no daily card or new-objective limit. Due reviews always take priority;
when the due queue is empty, the tutor immediately introduces the next eligible
objective. Temporarily locked synthesis objectives do not block other eligible
material; synthesis production remains gated until its vocabulary is ready.

## Study keys

- `Enter`: submit an answer or continue
- `Tab`: request a hint
- `Ctrl+R`: reveal the answer and enter copy correction
- `Esc`: pause
- `Ctrl+Q`: save and quit

From the pause screen, press `R` to open the progress reset. The tutor deletes
study history only after `DELETE` is typed exactly; the self-reference preference
is kept.

Polish diacritics are required. Capitalization, surrounding whitespace, and final
punctuation are ignored.
