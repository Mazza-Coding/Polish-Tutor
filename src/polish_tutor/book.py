"""Compile the attributed, compact textbook source into the tutor's course schema.

No network, OCR, morphological guesser, or LLM is used at runtime. Every Polish
form must belong to the source's explicit inventory. Readings become labelled
reverse recall; transformations retain their original Polish input in the cue.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from polish_tutor.data.teach_yourself import (
    EDITORIAL_NOTES,
    IMPERATIVE,
    LESSONS,
    PRESENT,
    PROPER_NAMES,
    SOURCE,
    TABLES,
)

_WORD = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+(?:-[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)?")
SECTIONS = ("examples", "reading", "translation", "address", "response", "plural", "declension")


def rows(table: str, columns: int) -> Iterator[tuple[str, ...]]:
    for line_number, line in enumerate(table.splitlines(), 1):
        if not line.strip():
            continue
        fields = tuple(field.strip() for field in line.split("|"))
        if len(fields) != columns or any(not field for field in fields):
            raise ValueError(f"invalid {columns}-column source row {line_number}: {line!r}")
        yield fields


def slug(value: str) -> str:
    value = unicodedata.normalize("NFD", value.replace("ł", "l").replace("Ł", "L"))
    return "".join(c for c in value.casefold() if c.isascii() and (c.isalnum() or c in "-."))


@dataclass(frozen=True)
class BookItem:
    lesson: int
    page: int
    section: str
    reference: str
    english: str
    polish: tuple[str, ...]

    @property
    def id(self) -> str:
        return f"ty.l{self.lesson:02}.{self.section}.p{self.page}.{self.reference}"

    @property
    def provenance(self) -> str:
        location = (f"Lesson {self.lesson}, p. {self.page} (PDF {self.page + 8}), "
                    f"{self.section} {self.reference}")
        if self.section == "reading":
            detail = "Reversed Polish reading; editorial English cue."
        elif self.section == "translation":
            detail = "Polish answer: printed key, pp. 217–219."
        elif self.section == "response":
            detail = "Guided response from key pp. 217–218; examples, not all possible answers."
        elif self.section == "plural":
            detail = "Plural transformation; printed key p. 218."
        elif self.section == "declension":
            detail = "Singular: derived from Lesson 4. Plural: printed key p. 218."
        elif self.section == "address":
            detail = "Formal-address exercise; responses formed from Lesson 2's tables."
        else:
            detail = "Book example/table; cue labels adapted for typing."
        note = EDITORIAL_NOTES.get((self.lesson, self.section, self.reference))
        return f"{location}. {detail}" + (f" {note}" if note else "")


def book_items() -> tuple[BookItem, ...]:
    items: list[BookItem] = []
    for lesson in LESSONS:
        number = lesson["number"]
        for section in SECTIONS:
            for page, reference, english, polish in rows(lesson.get(section, ""), 4):
                items.append(BookItem(number, int(page), section, reference, english,
                                      tuple(part.strip() for part in polish.split(";;"))))
    persons = ("ja", "ty", "on/ona/ono", "my", "wy", "oni/one")
    for lesson, page, verb, forms in rows(PRESENT, 4):
        parts = forms.split()
        if len(parts) != 6:
            raise ValueError(f"expected six present forms for {verb}")
        for person, form in zip(persons, parts, strict=True):
            items.append(BookItem(int(lesson), int(page), "present",
                                  f"{slug(verb)}.{slug(person)}",
                                  f"Present tense of {verb}: {person} (type the verb only).",
                                  (form,)))
    for page, verb, forms in rows(IMPERATIVE, 3):
        parts = forms.split()
        if len(parts) != 3:
            raise ValueError(f"expected three imperative forms for {verb}")
        for index, (person, form) in enumerate(zip(
            ("familiar singular", "let us", "familiar plural"), parts, strict=True
        ), 1):
            items.append(BookItem(7, int(page), "imperative", f"{slug(verb)}.{index}",
                                  f"Imperative of {verb}: {person} (type the verb only).", (form,)))
    for lesson, page, reference, english, polish in rows(TABLES, 5):
        items.append(BookItem(int(lesson), int(page), "table", reference, english,
                              tuple(part.strip() for part in polish.split(";;"))))
    identifiers = [item.id for item in items]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate book exercise identifiers")
    for item in items:
        lesson = LESSONS[item.lesson - 1]
        if not lesson["pages"][0] <= item.page <= lesson["pages"][1]:
            raise ValueError(f"{item.id}: page lies outside its lesson")
        if not item.english or not all(item.polish):
            raise ValueError(f"{item.id}: empty cue or answer")
    return tuple(items)


def build_course() -> dict[str, Any]:
    if [lesson["number"] for lesson in LESSONS] != list(range(1, 8)):
        raise ValueError("the bundled source must contain exactly lessons 1–7 in order")
    course: dict[str, Any] = {
        "version": 2,
        "title": "Teach Yourself Polish — Corbridge-Patkaniowska — Lessons 1–7",
        "proper_names": list(PROPER_NAMES),
        "units": [], "concepts": [], "objectives": [],
    }
    forms: dict[str, str] = {}
    first_lesson: dict[str, int] = {}
    by_unit: dict[int, list[dict[str, Any]]] = {}
    for lesson in LESSONS:
        number = lesson["number"]
        unit = f"ty.l{number:02}"
        course["units"].append({
            "id": unit, "order": number, "title": f"Lesson {number}: {lesson['title']}",
            "notes": [
                f"{SOURCE['title']} — {SOURCE['author']}. Printed pp. "
                f"{lesson['pages'][0]}–{lesson['pages'][1]} (PDF pages +8).",
                *lesson["notes"], lesson["speech"], SOURCE["adaptation"],
            ],
        })
        by_unit[number] = []
        for lemma, pos, gloss, inventory in rows(lesson["vocabulary"], 4):
            identifier = f"ty.{slug(lemma)}"
            if identifier in first_lesson:
                raise ValueError(f"duplicate vocabulary item {lemma}")
            first_lesson[identifier] = number
            concept = {"id": identifier, "order": len(course["concepts"]) + 1,
                       "lemma": lemma, "gloss": gloss, "part_of_speech": pos, "unit_id": unit}
            course["concepts"].append(concept)
            by_unit[number].append(concept)
            for form in (lemma, *inventory.split()):
                key = unicodedata.normalize("NFC", form).casefold()
                if key in forms and forms[key] != identifier:
                    raise ValueError(f"ambiguous explicit form {form}")
                forms[key] = identifier
    proper_names = {name.casefold() for name in PROPER_NAMES}

    def mapping(text: str) -> dict[str, Any]:
        tokens = [m.group() for m in _WORD.finditer(text)]
        if not tokens:
            raise ValueError(f"empty Polish text {text!r}")
        concepts = []
        for token in tokens:
            key = unicodedata.normalize("NFC", token).casefold()
            if key in proper_names:
                concepts.append("@name")
            elif key in forms:
                concepts.append(forms[key])
            else:
                raise ValueError(f"unmapped source form {token!r} in {text!r}")
        return {"text": text, "token_concepts": concepts}

    items = book_items()
    item_maps = {item.id: [mapping(answer) for answer in item.polish] for item in items}
    for item in items:
        for answer in item_maps[item.id]:
            for concept in answer["token_concepts"]:
                if concept != "@name" and first_lesson[concept] > item.lesson:
                    raise ValueError(f"{item.id}: uses {concept} before its source lesson")

    def add_objective(objective: dict[str, Any]) -> None:
        objective["order"] = len(course["objectives"]) + 1
        course["objectives"].append(objective)

    def cloze(identifier: str, text: str, index: int, context: str, hint: str) -> dict[str, Any]:
        matches = list(_WORD.finditer(text))
        target = matches[index]
        prompt = text[:target.start()] + "____" + text[target.end():]
        aligned = mapping(text)["token_concepts"]
        token_index = index % len(matches)
        return {"id": identifier, "kind": "cloze", "prompt": prompt,
                "prompt_token_concepts": aligned[:token_index] + aligned[token_index + 1:],
                "context": context, "hint": hint, "answers": [mapping(target.group())]}

    for lesson in LESSONS:
        number = lesson["number"]
        unit = f"ty.l{number:02}"
        unit_items = [item for item in items if item.lesson == number]
        for concept in by_unit[number]:
            identifier = f"ty.lex.{slug(concept['lemma'])}"
            model = mapping(concept["lemma"])
            context = f"Lesson {number} vocabulary: {concept['gloss']}. Recall the taught form."
            hint = f"The book's vocabulary form begins {concept['lemma'][0]}…"
            variants = [cloze(f"{identifier}.c{i}", concept["lemma"], 0, context, hint)
                        for i in (1, 2)]
            # Two spaced initial recalls are intentional. Do not invent four
            # textbook contexts for a word which has fewer attested contexts.
            variants.append({"id": f"{identifier}.t1", "kind": "translation",
                             "prompt": concept["gloss"], "context": context,
                             "hint": hint, "answers": [model]})
            seen = {(concept["gloss"], concept["lemma"].casefold())}
            for item in unit_items:
                answers = item_maps[item.id]
                # Every alternative on a lexical card must exercise that lexeme.
                if not all(concept["id"] in answer["token_concepts"] for answer in answers):
                    continue
                signature = (item.english, answers[0]["text"].casefold())
                if signature in seen:
                    continue
                seen.add(signature)
                variants.append({"id": f"{identifier}.t{len(variants) - 1}",
                                 "kind": "translation", "prompt": item.english,
                                 "context": item.provenance, "hint": hint, "answers": answers})
                if len(variants) == 6:
                    break
            add_objective({"id": identifier, "unit_id": unit, "kind": "lexical",
                           "concept_id": concept["id"], "requires_seen": [], "unlock_ready": [],
                           "model": {"english": context, "polish": model}, "variants": variants})
        for index, item in enumerate(unit_items):
            answers = item_maps[item.id]
            dependencies = sorted({c for answer in answers for c in answer["token_concepts"]
                                   if c != "@name"})
            hint = lesson["notes"][index % len(lesson["notes"])]
            context = f"{item.english}\n{item.provenance}"
            variants = [
                cloze(f"{item.id}.c1", item.polish[0], -1, context, hint),
                cloze(f"{item.id}.c2", item.polish[0], 0, context, hint),
                {"id": f"{item.id}.t1", "kind": "translation", "prompt": item.english,
                 "context": item.provenance, "hint": hint, "answers": answers},
            ]
            add_objective({"id": item.id, "unit_id": unit, "kind": "synthesis",
                           "requires_seen": dependencies, "unlock_ready": dependencies,
                           "model": {"english": context, "polish": answers[0]}, "variants": variants})
    return course
