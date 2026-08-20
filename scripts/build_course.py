"""Build the bundled YAML from the compact, hand-authored course source.

Every Polish token is annotated with its concept ID in this source. The generated
YAML keeps the visible text and the aligned token map as separate fields, which is
what the runtime validator consumes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TOKEN = r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+(?:-[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)?"
ANNOTATED = re.compile(rf"({TOKEN})\{{([^{{}}]+)\}}")
VISIBLE = re.compile(TOKEN)


def mapped(source: str) -> dict[str, Any]:
    concepts: list[str] = []

    def replace(match: re.Match[str]) -> str:
        concepts.append(match.group(2))
        return match.group(1)

    text = ANNOTATED.sub(replace, source)
    if "{" in text or "}" in text:
        raise ValueError(f"malformed annotation: {source}")
    tokens = VISIBLE.findall(text)
    if len(tokens) != len(concepts):
        raise ValueError(f"every Polish token must be annotated: {source} -> {tokens}/{concepts}")
    return {"text": text, "token_concepts": concepts}


def answer(source: str, when: str = "any") -> dict[str, Any]:
    value = mapped(source)
    value["when_self_form"] = when
    return value


def model(english: str, polish: str) -> dict[str, Any]:
    return {"english": english, "polish": mapped(polish)}


THEORY_FREE_HINTS = {
    "A general feminine noun for a thing.": "The ordinary word for a thing.",
    "Contrast the masculine and feminine descriptions.": (
        "Use a different ending with problem and odpowiedź."
    ),
    "Join the two masculine alternatives.": "Use nowy before both alternatives.",
    "Match a feminine person.": "Use the form that fits Anna.",
    "Match a masculine person.": "Use the form that fits Marek.",
    "Match both descriptions to the neuter noun.": ("Use the same -e ending on both descriptions."),
    "Match the adjective to the feminine noun.": "Make the describing word fit the noun.",
    "Match the adjective to the feminine object.": "Use the -ą ending before rzecz.",
    "Match the adjective to the masculine noun.": "Make the describing word fit the noun.",
    "Match the adjective to the masculine time noun.": ("Make the describing word fit dzień."),
    "Match the adjective to the neuter noun.": "Use the -e ending with this noun.",
    "Match the demonstrative and adjective to the neuter noun.": (
        "Use to and an -e ending with miejsce."
    ),
    "Match the description to the feminine noun.": "Make the description fit the noun.",
    "Match the description to the masculine noun.": "Make the description fit the noun.",
    "Match the feminine noun.": "Use the form that fits this noun.",
    "Match the masculine noun.": "Use the form that fits this noun.",
    "Match the masculine object.": "Use the form that fits the following word.",
    "Match the neuter adjective.": "Use the description ending in -e.",
    "Match the neuter noun.": "Use the form that fits this noun.",
    "Match ‘this’ to a masculine noun.": "Use the form of ‘this’ that fits człowiek.",
    "Match ‘this’ to a neuter noun.": "Use the form of ‘this’ that fits dziecko.",
    "Match ‘this’ to the feminine object.": "Use tę before osobę.",
    "Put yesterday before the feminine completed past form.": (
        "Put yesterday before the form that says Anna did it once."
    ),
    "The feminine noun keeps its form here.": "Use the dictionary form here.",
    "The feminine singular pronoun.": "The word used for ‘she’.",
    "The masculine noun for a day.": "The ordinary word for a day.",
    "The masculine noun for a year.": "The ordinary word for a year.",
    "The masculine noun for home or house.": "The ordinary word for home or house.",
    "The masculine noun keeps its base form.": "Use the dictionary form here.",
    "The masculine object keeps its base form.": "Use the dictionary form here.",
    "The masculine singular pronoun.": "The word used for ‘he’.",
    "The neuter noun for a child.": "The ordinary word for a child.",
    "The neuter noun for a place.": "The ordinary word for a place.",
    "The neuter noun for life.": "The ordinary word for life.",
    "The neuter noun keeps its base form.": "Use the dictionary form here.",
    "The neuter object keeps its base form.": "Use the dictionary form here.",
    "Use osoba for the individual and genitive forms after ‘want’.": (
        "Use osoba; the last two words have the shape t__ r_____."
    ),
    "Use the feminine completed past form before the statement's content.": (
        "Use the form that says Anna said it once."
    ),
    "Use the feminine completed past form.": "Use the form that says Anna did it once.",
    "Use the feminine object form.": "Use the short form that means ‘her’ here.",
    "Use the feminine object forms.": "Use the forms that fit tę osobę.",
    "Use the feminine pronoun explicitly.": "Begin with ona.",
    "Use the masculine form after ‘he’.": "Use the form that follows on.",
    "Use the neuter description.": "Use the description ending in -e.",
    "Use the neuter noun.": "Use the word for child.",
    "Use the plural verb before the masculine object.": ("Begin with Widzimy, then use duży dom."),
}


THEORY_TERMS = re.compile(
    r"\b(?:nominative|accusative|genitive|dative|instrumental|locative|vocative|"
    r"case|declension|conjugation|paradigm|masculine|feminine|neuter|perfective|"
    r"imperfective|verb|noun|adjective|pronoun|first-person|second-person|"
    r"third-person|plural|singular|infinitive|subject|object|past|present|future|"
    r"modal|clause|preposition|agreement|negation|form|bounded|ongoing)\b",
    re.IGNORECASE,
)


def _masked_answer_shape(text: str) -> str:
    def mask(match: re.Match[str]) -> str:
        word = match.group(0)
        return word[0] + "•" * (len(word) - 1)

    return VISIBLE.sub(mask, text)


def learner_hint(hint: str, answers: list[dict[str, Any]]) -> str:
    hint = THEORY_FREE_HINTS.get(hint, hint)
    if not THEORY_TERMS.search(hint):
        return hint
    shapes = tuple(dict.fromkeys(_masked_answer_shape(item["text"]) for item in answers))
    return f"Answer shape: {' / '.join(shapes)}"


def cloze(
    prompt: str,
    context: str,
    accepted: str | list[tuple[str, str]],
    hint: str,
) -> dict[str, Any]:
    prompt_map = mapped(prompt)
    answers = (
        [answer(accepted)]
        if isinstance(accepted, str)
        else [answer(text, when) for text, when in accepted]
    )
    return {
        "kind": "cloze",
        "prompt": prompt_map["text"],
        "prompt_token_concepts": prompt_map["token_concepts"],
        "context": context,
        "hint": learner_hint(hint, answers),
        "answers": answers,
    }


def translation(
    prompt: str,
    accepted: str | list[tuple[str, str]],
    hint: str,
    *,
    context: str | None = None,
) -> dict[str, Any]:
    answers = (
        [answer(accepted)]
        if isinstance(accepted, str)
        else [answer(text, when) for text, when in accepted]
    )
    return {
        "kind": "translation",
        "prompt": prompt,
        "prompt_token_concepts": [],
        "context": context,
        "hint": learner_hint(hint, answers),
        "answers": answers,
    }


@dataclass
class Lexeme:
    id: str
    lemma: str
    gloss: str
    pos: str
    unit: int
    model: dict[str, Any]
    variants: list[dict[str, Any]]


@dataclass
class Synthesis:
    id: str
    unit: int
    model: dict[str, Any]
    variants: list[dict[str, Any]]


LEXEMES: list[Lexeme] = []
SYNTHESES: list[Synthesis] = []


def L(
    concept_id: str,
    lemma: str,
    gloss: str,
    pos: str,
    unit: int,
    introduction: dict[str, Any],
    first_cloze: dict[str, Any],
    second_cloze: dict[str, Any],
    production: dict[str, Any],
) -> None:
    LEXEMES.append(
        Lexeme(
            concept_id,
            lemma,
            gloss,
            pos,
            unit,
            introduction,
            [first_cloze, second_cloze, production],
        )
    )


def R(concept_id: str, *review_variants: dict[str, Any]) -> None:
    """Add mature translation contexts without changing the initial learning steps."""
    if len(review_variants) != 3:
        raise ValueError(f"{concept_id}: expected exactly three mature review variants")
    item = next((lexeme for lexeme in LEXEMES if lexeme.id == concept_id), None)
    if item is None:
        raise ValueError(f"unknown review concept: {concept_id}")
    if any(variant["kind"] != "translation" for variant in review_variants):
        raise ValueError(f"{concept_id}: mature review variants must be translations")
    item.variants.extend(review_variants)


def S(
    synthesis_id: str,
    unit: int,
    introduction: dict[str, Any],
    first_cloze: dict[str, Any],
    second_cloze: dict[str, Any],
    first_production: dict[str, Any],
    second_production: dict[str, Any],
) -> None:
    SYNTHESES.append(
        Synthesis(
            synthesis_id,
            unit,
            introduction,
            [first_cloze, second_cloze, first_production, second_production],
        )
    )


# Unit 1 — intentions and ability. The first items deliberately bootstrap with
# compact utterances; from "być" onward every example is a natural sentence.
L(
    "tak",
    "tak",
    "yes; so",
    "particle",
    1,
    model("Yes.", "Tak{tak}."),
    cloze("____.", "Give an affirmative answer.", "Tak{tak}", "An affirmative answer."),
    cloze(
        "Tak{tak} ____.", "Confirm emphatically: yes, yes.", "tak{tak}", "Repeat the confirmation."
    ),
    translation("Yes.", "Tak{tak}.", "A short affirmative answer."),
)
L(
    "nie",
    "nie",
    "not; no",
    "particle",
    1,
    model("No.", "Nie{nie}."),
    cloze("____.", "Give a negative answer.", "Nie{nie}", "A short negative answer."),
    cloze(
        "Nie{nie}, ____.",
        "Reject a repeated suggestion: no, no.",
        "nie{nie}",
        "Repeat the refusal.",
    ),
    translation("No.", "Nie{nie}.", "A short negative answer."),
)
L(
    "to",
    "to",
    "this; it; that",
    "pronoun",
    1,
    model("This?", "To{to}?"),
    cloze("____?", "Point at one thing and ask about it.", "To{to}", "A short pointing word."),
    cloze(
        "Tak{tak}, ____.",
        "Confirm which one: yes, this one.",
        "to{to}",
        "Name the selected thing after the confirmation.",
    ),
    translation("This?", "To{to}?", "Point at a nearby thing."),
)
L(
    "ja",
    "ja",
    "I; me",
    "pronoun",
    1,
    model("It's me.", "To{to} ja{ja}."),
    cloze("To{to} ____.", "Identify yourself.", "ja{ja}", "The stressed word for ‘I’."),
    cloze("____? Tak{tak}.", "Ask ‘Me?’ and confirm.", "Ja{ja}", "The speaker points to themself."),
    translation("It's me.", "To{to} ja{ja}.", "Identify yourself, with natural Polish word order."),
)
L(
    "ty",
    "ty",
    "you (singular)",
    "pronoun",
    1,
    model("It's you.", "To{to} ty{ty}."),
    cloze(
        "To{to} ____.",
        "Identify the person you are speaking to.",
        "ty{ty}",
        "Informal singular ‘you’.",
    ),
    cloze("____? Nie{nie} ja{ja}?", "Ask: you, not me?", "Ty{ty}", "Address one person directly."),
    translation("You?", "Ty{ty}?", "Address one person informally."),
)
L(
    "byc",
    "być",
    "to be",
    "verb",
    1,
    model("This is Anna.", "To{to} jest{byc} Anna{@name}."),
    cloze("To{to} ____ Anna{@name}.", "This is Anna.", "jest{byc}", "Link the thing to Anna."),
    cloze(
        "Ja{ja} ____.",
        "Contrast yourself with someone else: I am.",
        "jestem{byc}",
        "Use the first-person present form.",
    ),
    translation("I am Anna.", "Jestem{byc} Anną{@name}.", "Identify yourself as Anna."),
)
L(
    "tutaj",
    "tutaj",
    "here",
    "adverb",
    1,
    model("Anna is here.", "Anna{@name} jest{byc} tutaj{tutaj}."),
    cloze(
        "Anna{@name} jest{byc} ____.",
        "Anna is here.",
        "tutaj{tutaj}",
        "The place close to the speaker.",
    ),
    cloze("Ja{ja} jestem{byc} ____.", "I am here.", "tutaj{tutaj}", "Say where you are now."),
    translation("I am here.", "Jestem{byc} tutaj{tutaj}.", "Omit the unnecessary subject pronoun."),
)
L(
    "miec",
    "mieć",
    "to have",
    "verb",
    1,
    model("I have it.", "Mam{miec} to{to}."),
    cloze("____ to{to}.", "I have it.", "Mam{miec}", "Use the first-person present form."),
    cloze("Ty{ty} ____ to{to}.", "You have it.", "masz{miec}", "Address one person."),
    translation("You have it.", "Masz{miec} to{to}.", "The subject pronoun is unnecessary."),
)
L(
    "chciec",
    "chcieć",
    "to want",
    "verb",
    1,
    model("I want it.", "Chcę{chciec} tego{to}."),
    cloze("____ tego{to}.", "I want it.", "Chcę{chciec}", "Use the first-person form."),
    cloze("____ tego{to}.", "You want it.", "Chcesz{chciec}", "Address one person."),
    translation("We want it.", "Chcemy{chciec} tego{to}.", "Use the plural verb form."),
)
L(
    "moc",
    "móc",
    "can; to be able",
    "verb",
    1,
    model("I can be here.", "Mogę{moc} być{byc} tutaj{tutaj}."),
    cloze(
        "____ być{byc} tutaj{tutaj}.", "I can be here.", "Mogę{moc}", "Use the first-person form."
    ),
    cloze(
        "____ to{to} mieć{miec}.",
        "You can have it.",
        "Możesz{moc}",
        "Address one person.",
    ),
    translation(
        "I can't be here.",
        "Nie{nie} mogę{moc} być{byc} tutaj{tutaj}.",
        "Put negation directly before the modal verb.",
    ),
)

# Unit 2 — people, things, and agreement.
L(
    "on",
    "on",
    "he; it (masculine)",
    "pronoun",
    2,
    model("He is here.", "On{on} jest{byc} tutaj{tutaj}."),
    cloze(
        "____ jest{byc} tutaj{tutaj}.", "He is here.", "On{on}", "The masculine singular pronoun."
    ),
    cloze("To{to} ____.", "That's him.", "on{on}", "Identify a man already mentioned."),
    translation(
        "He is here.",
        "On{on} jest{byc} tutaj{tutaj}.",
        "Keep the pronoun for contrast or emphasis.",
    ),
)
L(
    "ona",
    "ona",
    "she; it (feminine)",
    "pronoun",
    2,
    model("She is here.", "Ona{ona} jest{byc} tutaj{tutaj}."),
    cloze(
        "____ jest{byc} tutaj{tutaj}.", "She is here.", "Ona{ona}", "The feminine singular pronoun."
    ),
    cloze("To{to} ____.", "That's her.", "ona{ona}", "Identify a woman already mentioned."),
    translation("She has it.", "Ona{ona} ma{miec} to{to}.", "Use the feminine pronoun explicitly."),
)
L(
    "my",
    "my",
    "we",
    "pronoun",
    2,
    model("We—not the others—are here.", "My{my} jesteśmy{byc} tutaj{tutaj}."),
    cloze(
        "____ jesteśmy{byc} tutaj{tutaj}.",
        "We are here.",
        "My{my}",
        "The first-person plural pronoun.",
    ),
    cloze("To{to} ____.", "That's us.", "my{my}", "Identify your group."),
    translation(
        "We are the ones who have it.",
        "My{my} mamy{miec} to{to}.",
        "Emphasize who has it.",
    ),
)
L(
    "czlowiek",
    "człowiek",
    "human being; person in general",
    "noun",
    2,
    model("This is a human being.", "To{to} jest{byc} człowiek{czlowiek}."),
    cloze(
        "To{to} jest{byc} ____.",
        "This is a human being — humanity is the point.",
        "człowiek{czlowiek}",
        "Use the word for a human being, not a neutral reference to an individual.",
    ),
    cloze(
        "____ jest{byc} tutaj{tutaj}.",
        "A human being is here — the person is viewed simply as human.",
        "Człowiek{czlowiek}",
        "Use the word for a human being or people in general.",
    ),
    translation(
        "I am a human being.",
        "Jestem{byc} człowiekiem{czlowiek}.",
        "Choose the word that presents someone as a human being.",
    ),
)
L(
    "osoba",
    "osoba",
    "individual; particular person",
    "noun",
    2,
    model(
        "This individual is here.",
        "Ta{ten} osoba{osoba} jest{byc} tutaj{tutaj}.",
    ),
    cloze(
        "Ta{ten} ____ jest{byc} tutaj{tutaj}.",
        "This individual is here — a neutral reference to one person.",
        "osoba{osoba}",
        "Use the neutral word for an identified or particular individual.",
    ),
    cloze(
        "Ta{ten} ____ ma{miec} to{to}.",
        "This individual has it.",
        "osoba{osoba}",
        "Refer neutrally to a particular individual.",
    ),
    translation(
        "That's the individual.",
        "To{to} jest{byc} ta{ten} osoba{osoba}.",
        "Use the neutral reference word in a specific identification.",
    ),
)
L(
    "dziecko",
    "dziecko",
    "child",
    "noun",
    2,
    model("This is a child.", "To{to} jest{byc} dziecko{dziecko}."),
    cloze(
        "To{to} jest{byc} ____.",
        "This is a child.",
        "dziecko{dziecko}",
        "The neuter noun for a child.",
    ),
    cloze(
        "____ jest{byc} tutaj{tutaj}.",
        "The child is here.",
        "Dziecko{dziecko}",
        "Use the neuter noun.",
    ),
    translation(
        "The child is here.",
        "Dziecko{dziecko} jest{byc} tutaj{tutaj}.",
        "State where the child is.",
    ),
)
L(
    "rzecz",
    "rzecz",
    "thing; matter",
    "noun",
    2,
    model("This is a thing.", "To{to} jest{byc} rzecz{rzecz}."),
    cloze(
        "To{to} jest{byc} ____.",
        "This is a thing.",
        "rzecz{rzecz}",
        "A general feminine noun for a thing.",
    ),
    cloze(
        "Mam{miec} tę{ten} ____.",
        "I have this thing.",
        "rzecz{rzecz}",
        "The noun keeps its form here.",
    ),
    translation(
        "I want this thing.",
        "Chcę{chciec} tej{ten} rzeczy{rzecz}.",
        "Both words take the form required after ‘want’.",
    ),
)
L(
    "ten",
    "ten",
    "this; that",
    "pronoun",
    2,
    model(
        "This human being is here. This child is here.",
        "Ten{ten} człowiek{czlowiek} jest{byc} tutaj{tutaj}. To{ten} dziecko{dziecko} jest{byc} tutaj{tutaj}.",
    ),
    cloze(
        "____ człowiek{czlowiek} jest{byc} tutaj{tutaj}.",
        "This human being is here.",
        "Ten{ten}",
        "Match ‘this’ to a masculine noun.",
    ),
    cloze(
        "____ dziecko{dziecko} jest{byc} tutaj{tutaj}.",
        "This child is here.",
        "To{ten}",
        "Match ‘this’ to a neuter noun.",
    ),
    translation(
        "This person is here.",
        [
            ("Ten{ten} człowiek{czlowiek} jest{byc} tutaj{tutaj}.", "any"),
            ("Ta{ten} osoba{osoba} jest{byc} tutaj{tutaj}.", "any"),
        ],
        "Either learned person noun works; make ‘this’ agree with the noun you choose.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
)
L(
    "dobry",
    "dobry",
    "good",
    "adjective",
    2,
    model(
        "Marek is good. Anna is good.",
        "Marek{@name} jest{byc} dobry{dobry}. Anna{@name} jest{byc} dobra{dobry}.",
    ),
    cloze(
        "Marek{@name} jest{byc} ____.",
        "Marek is good.",
        "dobry{dobry}",
        "Match a masculine person.",
    ),
    cloze(
        "Anna{@name} jest{byc} ____.",
        "Anna is good.",
        "dobra{dobry}",
        "Match a feminine person.",
    ),
    translation(
        "This is a good thing.",
        "To{to} jest{byc} dobra{dobry} rzecz{rzecz}.",
        "Match the adjective to the feminine noun.",
    ),
)
L(
    "duzy",
    "duży",
    "big; large",
    "adjective",
    2,
    model("This is a big thing.", "To{to} jest{byc} duża{duzy} rzecz{rzecz}."),
    cloze(
        "To{to} jest{byc} ____ rzecz{rzecz}.",
        "This is a big thing.",
        "duża{duzy}",
        "Match the feminine noun.",
    ),
    cloze(
        "To{to} jest{byc} ____ dziecko{dziecko}.",
        "This is a big child.",
        "duże{duzy}",
        "Match the neuter noun.",
    ),
    translation(
        "He is big.",
        "On{on} jest{byc} duży{duzy}.",
        "Use the masculine form after ‘he’.",
    ),
)

# Unit 3 — needs, questions, and absence.
L(
    "czas",
    "czas",
    "time",
    "noun",
    3,
    model("I have time.", "Mam{miec} czas{czas}."),
    cloze(
        "Mam{miec} ____.", "I have time.", "czas{czas}", "The direct object keeps its base form."
    ),
    cloze(
        "Nie{nie} mam{miec} ____.",
        "I do not have time.",
        "czasu{czas}",
        "Negation changes the form of the object.",
    ),
    translation(
        "I don't have time.", "Nie{nie} mam{miec} czasu{czas}.", "Place negation before the verb."
    ),
)
L(
    "pieniadze",
    "pieniądze",
    "money",
    "noun",
    3,
    model("I have money.", "Mam{miec} pieniądze{pieniadze}."),
    cloze(
        "Mam{miec} ____.",
        "I have money.",
        "pieniądze{pieniadze}",
        "Use the common plural-form noun.",
    ),
    cloze(
        "Nie{nie} mam{miec} ____.",
        "I have no money.",
        "pieniędzy{pieniadze}",
        "Negation changes this plural form.",
    ),
    translation(
        "We have money.", "Mamy{miec} pieniądze{pieniadze}.", "Use the first-person plural verb."
    ),
)
L(
    "pomoc",
    "pomoc",
    "help",
    "noun",
    3,
    model("I want help.", "Chcę{chciec} pomocy{pomoc}."),
    cloze(
        "Chcę{chciec} ____.",
        "I want some help.",
        "pomocy{pomoc}",
        "Use the natural form after wanting some help.",
    ),
    cloze(
        "Ta{ten} ____ jest{byc} dobra{dobry}.",
        "This help is good.",
        "pomoc{pomoc}",
        "Use the base form as the subject.",
    ),
    translation(
        "I have no help.",
        "Nie{nie} mam{miec} pomocy{pomoc}.",
        "Negation changes the object form.",
    ),
)
L(
    "musiec",
    "musieć",
    "must; to have to",
    "verb",
    3,
    model("I have to be here.", "Muszę{musiec} być{byc} tutaj{tutaj}."),
    cloze(
        "____ być{byc} tutaj{tutaj}.",
        "I have to be here.",
        "Muszę{musiec}",
        "Use the first-person form.",
    ),
    cloze(
        "____ to{to} mieć{miec}.",
        "You have to have it.",
        "Musisz{musiec}",
        "Address one person.",
    ),
    translation(
        "We have to be here.",
        "Musimy{musiec} być{byc} tutaj{tutaj}.",
        "Use the first-person plural modal.",
    ),
)
L(
    "potrzebowac",
    "potrzebować",
    "to need",
    "verb",
    3,
    model("I need time.", "Potrzebuję{potrzebowac} czasu{czas}."),
    cloze(
        "____ czasu{czas}.", "I need time.", "Potrzebuję{potrzebowac}", "Use the first-person form."
    ),
    cloze(
        "____ pomocy{pomoc}.",
        "You need help.",
        "Potrzebujesz{potrzebowac}",
        "Address one person.",
    ),
    translation(
        "We need money.",
        "Potrzebujemy{potrzebowac} pieniędzy{pieniadze}.",
        "Use the plural verb and the required noun form.",
    ),
)
L(
    "cos",
    "coś",
    "something",
    "pronoun",
    3,
    model("I have something.", "Mam{miec} coś{cos}."),
    cloze("Mam{miec} ____.", "I have something.", "coś{cos}", "An unspecified thing."),
    cloze(
        "Chcę{chciec} ____.",
        "I want something.",
        "czegoś{cos}",
        "Use the form required after ‘want’.",
    ),
    translation(
        "I need something.",
        "Potrzebuję{potrzebowac} czegoś{cos}.",
        "The form changes after ‘need’.",
    ),
)
L(
    "kto",
    "kto",
    "who",
    "pronoun",
    3,
    model("Who is this?", "Kto{kto} to{to} jest{byc}?"),
    cloze("____ to{to} jest{byc}?", "Who is this?", "Kto{kto}", "Ask about a person."),
    cloze(
        "____ jest{byc} tutaj{tutaj}?", "Who is here?", "Kto{kto}", "Ask which person is present."
    ),
    translation(
        "Who has time?", "Kto{kto} ma{miec} czas{czas}?", "Ask about the person with time."
    ),
)
L(
    "co",
    "co",
    "what",
    "pronoun",
    3,
    model("What is this?", "Co{co} to{to} jest{byc}?"),
    cloze("____ to{to} jest{byc}?", "What is this?", "Co{co}", "Ask about a thing."),
    cloze("____ masz{miec}?", "What do you have?", "Co{co}", "Ask for the object."),
    translation(
        "What do you want?",
        "Czego{co} chcesz{chciec}?",
        "Use the question-word form required by ‘want’.",
    ),
)
L(
    "bez",
    "bez",
    "without",
    "preposition",
    3,
    model("I am here without Anna.", "Jestem{byc} tutaj{tutaj} bez{bez} Anny{@name}."),
    cloze(
        "Jestem{byc} tutaj{tutaj} ____ Anny{@name}.",
        "I am here without Anna.",
        "bez{bez}",
        "Mark absence before the person.",
    ),
    cloze(
        "Nie{nie} mogę{moc} być{byc} ____ pomocy{pomoc}.",
        "I cannot be without help.",
        "bez{bez}",
        "Mark what is absent.",
    ),
    translation(
        "Marek is here without Anna.",
        "Marek{@name} jest{byc} tutaj{tutaj} bez{bez} Anny{@name}.",
        "Put the absent companion after the preposition.",
    ),
)
L(
    "dla",
    "dla",
    "for",
    "preposition",
    3,
    model("This is for Anna.", "To{to} jest{byc} dla{dla} Anny{@name}."),
    cloze(
        "To{to} jest{byc} ____ Anny{@name}.",
        "This is for Anna.",
        "dla{dla}",
        "Mark the intended recipient.",
    ),
    cloze(
        "Mam{miec} czas{czas} ____ ciebie{ty}.",
        "I have time for you.",
        "dla{dla}",
        "Mark who receives the time.",
    ),
    translation(
        "This is help for you.",
        "To{to} jest{byc} pomoc{pomoc} dla{dla} ciebie{ty}.",
        "Name the help, then its intended recipient.",
    ),
)

# Unit 4 — home, work, location, and high-yield prepositions.
L(
    "dom",
    "dom",
    "home; house",
    "noun",
    4,
    model("This is a house.", "To{to} jest{byc} dom{dom}."),
    cloze(
        "To{to} jest{byc} ____.",
        "This is a house.",
        "dom{dom}",
        "The masculine noun for home or house.",
    ),
    cloze("Mam{miec} ____.", "I have a house.", "dom{dom}", "The object keeps its base form."),
    translation(
        "This is a big house.",
        "To{to} jest{byc} duży{duzy} dom{dom}.",
        "Match the adjective to the masculine noun.",
    ),
)
L(
    "praca",
    "praca",
    "work; job",
    "noun",
    4,
    model("I have a job.", "Mam{miec} pracę{praca}."),
    cloze("Mam{miec} ____.", "I have a job.", "pracę{praca}", "Use the direct-object form."),
    cloze(
        "Chcę{chciec} ____.",
        "I want a job.",
        "pracy{praca}",
        "Use the form required after ‘want’.",
    ),
    translation(
        "I need a job.", "Potrzebuję{potrzebowac} pracy{praca}.", "The noun changes after ‘need’."
    ),
)
L(
    "miejsce",
    "miejsce",
    "place; room",
    "noun",
    4,
    model("This is a good place.", "To{to} jest{byc} dobre{dobry} miejsce{miejsce}."),
    cloze(
        "To{to} jest{byc} dobre{dobry} ____.",
        "This is a good place.",
        "miejsce{miejsce}",
        "The neuter noun for a place.",
    ),
    cloze(
        "Mam{miec} ____.",
        "I have room/a place.",
        "miejsce{miejsce}",
        "Use the base form as the object.",
    ),
    translation(
        "I need a place.",
        "Potrzebuję{potrzebowac} miejsca{miejsce}.",
        "The noun changes after ‘need’.",
    ),
)
L(
    "w",
    "w",
    "in; at",
    "preposition",
    4,
    model("I am at home.", "Jestem{byc} w{w} domu{dom}."),
    cloze("Jestem{byc} ____ domu{dom}.", "I am at home.", "w{w}", "Use the location preposition."),
    cloze(
        "Anna{@name} jest{byc} ____ pracy{praca}.",
        "Anna is at work.",
        "w{w}",
        "Use the same location preposition.",
    ),
    translation(
        "We are at home.",
        "Jesteśmy{byc} w{w} domu{dom}.",
        "Use the plural verb and the home-location form.",
    ),
)
L(
    "na",
    "na",
    "on; for",
    "preposition",
    4,
    model("I have time for work.", "Mam{miec} czas{czas} na{na} pracę{praca}."),
    cloze(
        "Mam{miec} czas{czas} ____ pracę{praca}.",
        "I have time for work.",
        "na{na}",
        "Mark what the time is allocated to.",
    ),
    cloze(
        "Mam{miec} pieniądze{pieniadze} ____ dom{dom}.",
        "I have money for a house.",
        "na{na}",
        "Mark the intended purchase.",
    ),
    translation(
        "I need time for work.",
        "Potrzebuję{potrzebowac} czasu{czas} na{na} pracę{praca}.",
        "Combine ‘need time’ with its purpose.",
    ),
)
L(
    "do",
    "do",
    "to; into; for",
    "preposition",
    4,
    model("This is for work.", "To{to} jest{byc} do{do} pracy{praca}."),
    cloze(
        "To{to} jest{byc} ____ pracy{praca}.",
        "This is intended for work.",
        "do{do}",
        "Mark the destination or purpose.",
    ),
    cloze(
        "Mam{miec} tę{ten} rzecz{rzecz} ____ pracy{praca}.",
        "I have this thing for work.",
        "do{do}",
        "Mark what it is intended for.",
    ),
    translation(
        "I need this for work.",
        "Potrzebuję{potrzebowac} tego{to} do{do} pracy{praca}.",
        "Use the required forms after ‘need’ and ‘for’.",
    ),
)
L(
    "z",
    "z",
    "with; from",
    "preposition",
    4,
    model("I am with Anna.", "Jestem{byc} z{z} Anną{@name}."),
    cloze("Jestem{byc} ____ Anną{@name}.", "I am with Anna.", "z{z}", "Mark accompaniment."),
    cloze(
        "Mam{miec} coś{cos} ____ pracy{praca}.",
        "I have something from work.",
        "z{z}",
        "Mark the source.",
    ),
    translation(
        "I want to be with you.",
        "Chcę{chciec} być{byc} z{z} tobą{ty}.",
        "Use the form of ‘you’ required after ‘with’.",
    ),
)
L(
    "o",
    "o",
    "about",
    "preposition",
    6,
    model("I am talking about work.", "Mówię{mowic} o{o} pracy{praca}."),
    cloze(
        "Mówię{mowic} ____ pracy{praca}.",
        "I am talking about work.",
        "o{o}",
        "Introduce the topic.",
    ),
    cloze(
        "Marek{@name} mówi{mowic} ____ domu{dom}.",
        "Marek is talking about home.",
        "o{o}",
        "Put the topic after the verb.",
    ),
    translation(
        "We are talking about this person.",
        [
            ("Mówimy{mowic} o{o} tej{ten} osobie{osoba}.", "any"),
            ("Mówimy{mowic} o{o} tym{ten} człowieku{czlowiek}.", "any"),
        ],
        "Either person noun works; use its matching forms after the topic preposition.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
)
L(
    "gdzie",
    "gdzie",
    "where",
    "adverb",
    4,
    model("Where is Anna?", "Gdzie{gdzie} jest{byc} Anna{@name}?"),
    cloze("____ jest{byc} Anna{@name}?", "Where is Anna?", "Gdzie{gdzie}", "Ask about a location."),
    cloze(
        "____ jest{byc} dom{dom}?",
        "Where is the house?",
        "Gdzie{gdzie}",
        "Ask for the house’s location.",
    ),
    translation("Where are we?", "Gdzie{gdzie} jesteśmy{byc}?", "Use the verb form for ‘we’."),
)
L(
    "tam",
    "tam",
    "there",
    "adverb",
    4,
    model("Anna is there.", "Anna{@name} jest{byc} tam{tam}."),
    cloze(
        "Anna{@name} jest{byc} ____.",
        "Anna is there.",
        "tam{tam}",
        "A place away from the speaker.",
    ),
    cloze(
        "Nie{nie} jestem{byc} ____.", "I am not there.", "tam{tam}", "Name the distant location."
    ),
    translation("We are there.", "Jesteśmy{byc} tam{tam}.", "Use the plural form of ‘be’."),
)

# Unit 5 — movement and immediate plans.
L(
    "isc",
    "iść",
    "to go (on foot)",
    "verb",
    5,
    model("I am going home on foot.", "Idę{isc} do{do} domu{dom}."),
    cloze(
        "____ do{do} domu{dom}.",
        "I am going home on foot.",
        "Idę{isc}",
        "Use the first-person motion form.",
    ),
    cloze(
        "Anna{@name} ____ do{do} pracy{praca}.",
        "Anna is walking to work.",
        "idzie{isc}",
        "Use the third-person form.",
    ),
    translation(
        "We are walking home.",
        "Idziemy{isc} do{do} domu{dom}.",
        "Use the first-person plural motion form.",
    ),
)
L(
    "pojsc",
    "pójść",
    "to go (completed/intended trip)",
    "verb",
    5,
    model(
        "I want to head home.",
        "Chcę{chciec} pójść{pojsc} do{do} domu{dom}.",
    ),
    cloze(
        "Chcę{chciec} ____ do{do} domu{dom}.",
        "I want to head home.",
        "pójść{pojsc}",
        "Use the bounded form after ‘want’.",
    ),
    cloze(
        "Możesz{moc} ____ do{do} pracy{praca}.",
        "You can head to work.",
        "pójść{pojsc}",
        "Use the infinitive after the modal.",
    ),
    translation(
        "I have to head there.",
        "Muszę{musiec} tam{tam} pójść{pojsc}.",
        "Put the destination before the final infinitive.",
    ),
)
L(
    "jechac",
    "jechać",
    "to go by vehicle",
    "verb",
    5,
    model("I am going to work by vehicle.", "Jadę{jechac} do{do} pracy{praca}."),
    cloze(
        "____ do{do} pracy{praca}.",
        "I am going to work by vehicle.",
        "Jadę{jechac}",
        "Use the first-person vehicle-motion form.",
    ),
    cloze(
        "Anna{@name} ____ do{do} domu{dom}.",
        "Anna is going home by vehicle.",
        "jedzie{jechac}",
        "Use the third-person form.",
    ),
    translation(
        "We are going there by vehicle.",
        "Jedziemy{jechac} tam{tam}.",
        "Use the first-person plural form.",
    ),
)
L(
    "wracac",
    "wracać",
    "to return",
    "verb",
    5,
    model("I am returning home.", "Wracam{wracac} do{do} domu{dom}."),
    cloze(
        "____ do{do} domu{dom}.",
        "I am returning home.",
        "Wracam{wracac}",
        "Use the first-person form.",
    ),
    cloze(
        "Anna{@name} ____ z{z} pracy{praca}.",
        "Anna is returning from work.",
        "wraca{wracac}",
        "Use the third-person form.",
    ),
    translation(
        "We are returning home.",
        "Wracamy{wracac} do{do} domu{dom}.",
        "Use the first-person plural form.",
    ),
)
L(
    "dzis",
    "dziś",
    "today",
    "adverb",
    5,
    model("Today I am at home.", "Dziś{dzis} jestem{byc} w{w} domu{dom}."),
    cloze(
        "____ jestem{byc} w{w} domu{dom}.", "Today I am at home.", "Dziś{dzis}", "The current day."
    ),
    cloze(
        "____ idę{isc} do{do} pracy{praca}.",
        "Today I am walking to work.",
        "Dziś{dzis}",
        "Put the day first for emphasis.",
    ),
    translation(
        "Today we are here.", "Dziś{dzis} jesteśmy{byc} tutaj{tutaj}.", "Lead with the current day."
    ),
)
L(
    "jutro",
    "jutro",
    "tomorrow",
    "adverb",
    5,
    model("Tomorrow I am walking to work.", "Jutro{jutro} idę{isc} do{do} pracy{praca}."),
    cloze(
        "____ idę{isc} do{do} pracy{praca}.",
        "Tomorrow I am walking to work.",
        "Jutro{jutro}",
        "The day after today.",
    ),
    cloze(
        "Anna{@name} ____ wraca{wracac} do{do} domu{dom}.",
        "Anna returns home tomorrow.",
        "jutro{jutro}",
        "Place the future day after the subject.",
    ),
    translation(
        "Tomorrow I am walking home.",
        "Jutro{jutro} idę{isc} do{do} domu{dom}.",
        "Polish can use the present form for a planned trip.",
    ),
)
L(
    "teraz",
    "teraz",
    "now",
    "adverb",
    5,
    model("I am here now.", "Teraz{teraz} jestem{byc} tutaj{tutaj}."),
    cloze(
        "____ jestem{byc} tutaj{tutaj}.", "I am here now.", "Teraz{teraz}", "The present moment."
    ),
    cloze(
        "____ idę{isc} do{do} domu{dom}.",
        "I am going home now.",
        "Teraz{teraz}",
        "Emphasize that the action is immediate.",
    ),
    translation(
        "I need it now.",
        "Potrzebuję{potrzebowac} tego{to} teraz{teraz}.",
        "Place the time naturally at the end.",
    ),
)
L(
    "juz",
    "już",
    "already",
    "adverb",
    5,
    model("I am already at home.", "Już{juz} jestem{byc} w{w} domu{dom}."),
    cloze(
        "____ jestem{byc} w{w} domu{dom}.",
        "I am already at home.",
        "Już{juz}",
        "The change has happened by now.",
    ),
    cloze(
        "Anna{@name} ____ wraca{wracac}.",
        "Anna is already returning.",
        "już{juz}",
        "The action has begun sooner than expected.",
    ),
    translation(
        "We already have it.",
        "Już{juz} to{to} mamy{miec}.",
        "Put ‘already’ first, then the emphasized object.",
    ),
)
L(
    "jeszcze",
    "jeszcze",
    "still; yet; more",
    "adverb",
    5,
    model("I am still at work.", "Jeszcze{jeszcze} jestem{byc} w{w} pracy{praca}."),
    cloze(
        "____ jestem{byc} w{w} pracy{praca}.",
        "I am still at work.",
        "Jeszcze{jeszcze}",
        "The situation continues.",
    ),
    cloze(
        "Nie{nie} mam{miec} ____ czasu{czas}.",
        "I do not have time yet.",
        "jeszcze{jeszcze}",
        "In a negative sentence, the expected state has not happened yet.",
    ),
    translation(
        "Are you still here?",
        "Jeszcze{jeszcze} jesteś{byc} tutaj{tutaj}?",
        "Ask whether the situation continues.",
    ),
)
L(
    "czekac",
    "czekać",
    "to wait",
    "verb",
    5,
    model("I am waiting here.", "Czekam{czekac} tutaj{tutaj}."),
    cloze(
        "____ tutaj{tutaj}.", "I am waiting here.", "Czekam{czekac}", "Use the first-person form."
    ),
    cloze(
        "Anna{@name} ____ na{na} Marka{@name}.",
        "Anna is waiting for Marek.",
        "czeka{czekac}",
        "Use the third-person form.",
    ),
    translation(
        "We are waiting at home.",
        "Czekamy{czekac} w{w} domu{dom}.",
        "Use the first-person plural form.",
    ),
)

# Unit 6 — knowing, thinking, and communicating.
L(
    "wiedziec",
    "wiedzieć",
    "to know (a fact)",
    "verb",
    6,
    model("I know where Anna is.", "Wiem{wiedziec}, gdzie{gdzie} jest{byc} Anna{@name}."),
    cloze(
        "____, gdzie{gdzie} jest{byc} Anna{@name}.",
        "I know where Anna is.",
        "Wiem{wiedziec}",
        "Use the first-person fact-knowing form.",
    ),
    cloze(
        "____, gdzie{gdzie} jest{byc} dom{dom}.",
        "You know where the house is.",
        "Wiesz{wiedziec}",
        "Address one person.",
    ),
    translation(
        "I know where he is.",
        "Wiem{wiedziec}, gdzie{gdzie} on{on} jest{byc}.",
        "The subordinate clause keeps the pronoun before the verb.",
    ),
)
L(
    "znac",
    "znać",
    "to know; be familiar with",
    "verb",
    6,
    model("I know Anna.", "Znam{znac} Annę{@name}."),
    cloze(
        "____ Annę{@name}.",
        "I know Anna personally.",
        "Znam{znac}",
        "Use the first-person familiarity form.",
    ),
    cloze(
        "Marek{@name} ____ tę{ten} osobę{osoba}.",
        "Marek knows this particular individual.",
        "zna{znac}",
        "Use the third-person form.",
    ),
    translation(
        "We know this person.",
        [
            ("Znamy{znac} tę{ten} osobę{osoba}.", "any"),
            ("Znamy{znac} tego{ten} człowieka{czlowiek}.", "any"),
        ],
        "Either person noun works; use the matching object forms.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
)
L(
    "rozumiec",
    "rozumieć",
    "to understand",
    "verb",
    6,
    model("I understand it.", "Rozumiem{rozumiec} to{to}."),
    cloze("____ to{to}.", "I understand it.", "Rozumiem{rozumiec}", "Use the first-person form."),
    cloze(
        "____ to{to}.",
        "You understand it.",
        "Rozumiesz{rozumiec}",
        "Address one person.",
    ),
    translation(
        "We don't understand this.",
        "Nie{nie} rozumiemy{rozumiec} tego{to}.",
        "Negate the plural verb and change the object form.",
    ),
)
L(
    "myslec",
    "myśleć",
    "to think",
    "verb",
    6,
    model("I am thinking about work.", "Myślę{myslec} o{o} pracy{praca}."),
    cloze(
        "____ o{o} pracy{praca}.",
        "I am thinking about work.",
        "Myślę{myslec}",
        "Use the first-person form.",
    ),
    cloze(
        "Anna{@name} ____ o{o} domu{dom}.",
        "Anna is thinking about home.",
        "myśli{myslec}",
        "Use the third-person form.",
    ),
    translation(
        "We are thinking about it.",
        "Myślimy{myslec} o{o} tym{to}.",
        "Use the plural verb and the form required after ‘about’.",
    ),
)
L(
    "mowic",
    "mówić",
    "to speak; say",
    "verb",
    6,
    model("I am speaking to Anna.", "Mówię{mowic} do{do} Anny{@name}."),
    cloze(
        "____ do{do} Anny{@name}.",
        "I am speaking to Anna.",
        "Mówię{mowic}",
        "Use the first-person form.",
    ),
    cloze(
        "Marek{@name} ____ do{do} Anny{@name}.",
        "Marek is speaking to Anna.",
        "mówi{mowic}",
        "Use the third-person form.",
    ),
    translation(
        "We are speaking to Anna.",
        "Mówimy{mowic} do{do} Anny{@name}.",
        "Use the first-person plural form.",
    ),
)
L(
    "powiedziec",
    "powiedzieć",
    "to say; tell (completed)",
    "verb",
    6,
    model("I want to say something.", "Chcę{chciec} coś{cos} powiedzieć{powiedziec}."),
    cloze(
        "Chcę{chciec} coś{cos} ____.",
        "I want to say something.",
        "powiedzieć{powiedziec}",
        "Use the completed infinitive.",
    ),
    cloze(
        "Mogę{moc} to{to} teraz{teraz} ____.",
        "I can say it now as one complete statement.",
        "powiedzieć{powiedziec}",
        "Use the infinitive after the modal.",
    ),
    translation(
        "I have to say it now.",
        "Muszę{musiec} to{to} teraz{teraz} powiedzieć{powiedziec}.",
        "Place the object before the final infinitive.",
    ),
)
L(
    "pytac",
    "pytać",
    "to ask",
    "verb",
    6,
    model("I am asking about work.", "Pytam{pytac} o{o} pracę{praca}."),
    cloze(
        "____ o{o} pracę{praca}.",
        "I am asking about work.",
        "Pytam{pytac}",
        "Use the first-person form.",
    ),
    cloze(
        "Anna{@name} ____ o{o} Marka{@name}.",
        "Anna is asking about Marek.",
        "pyta{pytac}",
        "Use the third-person form.",
    ),
    translation(
        "We are asking about this person.",
        [
            ("Pytamy{pytac} o{o} tę{ten} osobę{osoba}.", "any"),
            ("Pytamy{pytac} o{o} tego{ten} człowieka{czlowiek}.", "any"),
        ],
        "Either person noun works; use the matching object forms.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
)
L(
    "odpowiadac",
    "odpowiadać",
    "to answer",
    "verb",
    6,
    model("I am answering.", "Odpowiadam{odpowiadac}."),
    cloze("____.", "I am answering.", "Odpowiadam{odpowiadac}", "Use the first-person form."),
    cloze(
        "Anna{@name} ____ Markowi{@name}.",
        "Anna is answering Marek.",
        "odpowiada{odpowiadac}",
        "Use the third-person form.",
    ),
    translation(
        "We have to keep answering.",
        "Musimy{musiec} odpowiadać{odpowiadac}.",
        "Use the infinitive after the plural modal.",
    ),
)
L(
    "ze",
    "że",
    "that (clause connector)",
    "particle",
    6,
    model(
        "I know that Anna is here.", "Wiem{wiedziec}, że{ze} Anna{@name} jest{byc} tutaj{tutaj}."
    ),
    cloze(
        "Wiem{wiedziec}, ____ Anna{@name} jest{byc} tutaj{tutaj}.",
        "I know that Anna is here.",
        "że{ze}",
        "Join a known fact to the main clause.",
    ),
    cloze(
        "Myślę{myslec}, ____ on{on} jest{byc} w{w} domu{dom}.",
        "I think that he is at home.",
        "że{ze}",
        "Join the thought to its content.",
    ),
    translation(
        "I know that you have it.",
        [
            ("Wiem{wiedziec}, że{ze} to{to} masz{miec}.", "any"),
            ("Wiem{wiedziec}, że{ze} masz{miec} to{to}.", "any"),
        ],
        "Connect the known fact; both natural object positions are accepted.",
    ),
)
L(
    "czy",
    "czy",
    "whether; question marker",
    "particle",
    4,
    model("Is Anna here?", "Czy{czy} Anna{@name} jest{byc} tutaj{tutaj}?"),
    cloze(
        "____ Anna{@name} jest{byc} tutaj{tutaj}?",
        "Is Anna here?",
        "Czy{czy}",
        "Open a yes/no question.",
    ),
    cloze(
        "____ Marek{@name} jest{byc} w{w} domu{dom}?",
        "Is Marek at home?",
        "Czy{czy}",
        "Open another yes/no question.",
    ),
    translation(
        "Is this place good?",
        "Czy{czy} to{ten} miejsce{miejsce} jest{byc} dobre{dobry}?",
        "Open the question before the thing being judged.",
    ),
)

# Unit 7 — work, routine, aspect, and time.
L(
    "pracowac",
    "pracować",
    "to work",
    "verb",
    7,
    model("I am working here.", "Pracuję{pracowac} tutaj{tutaj}."),
    cloze(
        "____ tutaj{tutaj}.",
        "I am working here.",
        "Pracuję{pracowac}",
        "Use the first-person form.",
    ),
    cloze(
        "Anna{@name} ____ w{w} domu{dom}.",
        "Anna works at home.",
        "pracuje{pracowac}",
        "Use the third-person form.",
    ),
    translation(
        "Today we are working here.",
        "Dziś{dzis} pracujemy{pracowac} tutaj{tutaj}.",
        "Use the plural verb after the time word.",
    ),
)
L(
    "robic",
    "robić",
    "to do; make",
    "verb",
    7,
    model("I am doing it.", "Robię{robic} to{to}."),
    cloze("____ to{to}.", "I am doing it.", "Robię{robic}", "Use the first-person ongoing form."),
    cloze("Co{co} ____?", "What are you doing?", "robisz{robic}", "Address one person."),
    translation("What are we doing?", "Co{co} robimy{robic}?", "Use the first-person plural form."),
)
L(
    "zrobic",
    "zrobić",
    "to do; make (completed)",
    "verb",
    7,
    model("I want to get it done.", "Chcę{chciec} to{to} zrobić{zrobic}."),
    cloze(
        "Muszę{musiec} to{to} ____.",
        "I have to get it done.",
        "zrobić{zrobic}",
        "Use the completed infinitive.",
    ),
    cloze(
        "Anna{@name} może{moc} to{to} ____.",
        "Anna can get it done.",
        "zrobić{zrobic}",
        "Use the infinitive after the modal.",
    ),
    translation(
        "We want to get it done.",
        "Chcemy{chciec} to{to} zrobić{zrobic}.",
        "Use the plural form of ‘want’ and the completed infinitive.",
    ),
)
L(
    "uczyc_sie",
    "uczyć się",
    "to learn; study",
    "verb",
    7,
    model("I am studying here.", "Uczę{uczyc_sie} się{uczyc_sie} tutaj{tutaj}."),
    cloze(
        "____ ____ tutaj{tutaj}.",
        "I am studying here.",
        "Uczę{uczyc_sie} się{uczyc_sie}",
        "The verb is completed by its short companion word.",
    ),
    cloze(
        "Anna{@name} ____ ____ w{w} domu{dom}.",
        "Anna studies at home.",
        "uczy{uczyc_sie} się{uczyc_sie}",
        "Use the third-person form and keep the companion word.",
    ),
    translation(
        "We are studying now.",
        "Uczymy{uczyc_sie} się{uczyc_sie} teraz{teraz}.",
        "Use the plural verb and keep its companion word.",
    ),
)
L(
    "pamietac",
    "pamiętać",
    "to remember",
    "verb",
    7,
    model("I remember it.", "Pamiętam{pamietac} to{to}."),
    cloze("____ to{to}.", "I remember it.", "Pamiętam{pamietac}", "Use the first-person form."),
    cloze(
        "____ Annę{@name}.",
        "You remember Anna.",
        "Pamiętasz{pamietac}",
        "Address one person.",
    ),
    translation(
        "We remember that Anna is here.",
        "Pamiętamy{pamietac}, że{ze} Anna{@name} jest{byc} tutaj{tutaj}.",
        "Use the plural form before the known fact.",
    ),
)
L(
    "dzien",
    "dzień",
    "day",
    "noun",
    7,
    model("This is a good day.", "To{to} jest{byc} dobry{dobry} dzień{dzien}."),
    cloze(
        "To{to} jest{byc} dobry{dobry} ____.",
        "This is a good day.",
        "dzień{dzien}",
        "The masculine noun for a day.",
    ),
    cloze(
        "Dziś{dzis} jest{byc} dobry{dobry} ____.",
        "Today is a good day.",
        "dzień{dzien}",
        "Name the unit of time.",
    ),
    translation(
        "Today is a good day.",
        "Dziś{dzis} jest{byc} dobry{dobry} dzień{dzien}.",
        "Lead with today and match the adjective.",
    ),
)
L(
    "rok",
    "rok",
    "year",
    "noun",
    7,
    model("This year is good.", "Ten{ten} rok{rok} jest{byc} dobry{dobry}."),
    cloze(
        "Ten{ten} ____ jest{byc} dobry{dobry}.",
        "This year is good.",
        "rok{rok}",
        "The masculine noun for a year.",
    ),
    cloze(
        "Jestem{byc} tutaj{tutaj} ____.",
        "I have been here for a year.",
        "rok{rok}",
        "A bare duration can follow the location.",
    ),
    translation(
        "I have been working here for a year.",
        "Pracuję{pracowac} tutaj{tutaj} rok{rok}.",
        "Use the present tense for an activity that is still continuing.",
    ),
)
L(
    "wczoraj",
    "wczoraj",
    "yesterday",
    "adverb",
    7,
    model("Anna worked yesterday.", "Anna{@name} pracowała{pracowac} wczoraj{wczoraj}."),
    cloze(
        "Anna{@name} pracowała{pracowac} ____.",
        "Anna worked yesterday.",
        "wczoraj{wczoraj}",
        "The day before today.",
    ),
    cloze(
        "Marek{@name} ____ wracał{wracac} do{do} domu{dom}.",
        "Marek was returning home yesterday.",
        "wczoraj{wczoraj}",
        "Place the past day after the subject.",
    ),
    translation(
        "Yesterday I was at work.",
        [
            ("Wczoraj{wczoraj} byłem{byc} w{w} pracy{praca}.", "masculine"),
            ("Wczoraj{wczoraj} byłam{byc} w{w} pracy{praca}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
)
L(
    "zawsze",
    "zawsze",
    "always",
    "adverb",
    7,
    model("I always remember.", "Zawsze{zawsze} pamiętam{pamietac}."),
    cloze(
        "____ pamiętam{pamietac}.",
        "I always remember.",
        "Zawsze{zawsze}",
        "The action happens every time.",
    ),
    cloze(
        "Anna{@name} ____ pracuje{pracowac} tutaj{tutaj}.",
        "Anna always works here.",
        "zawsze{zawsze}",
        "Put the frequency before the verb.",
    ),
    translation(
        "We always know where Anna is.",
        "Zawsze{zawsze} wiemy{wiedziec}, gdzie{gdzie} jest{byc} Anna{@name}.",
        "Put the frequency word before the complete known fact.",
    ),
)
L(
    "czesto",
    "często",
    "often",
    "adverb",
    7,
    model("I often work at home.", "Często{czesto} pracuję{pracowac} w{w} domu{dom}."),
    cloze(
        "____ pracuję{pracowac} w{w} domu{dom}.",
        "I often work at home.",
        "Często{czesto}",
        "The action happens many times.",
    ),
    cloze(
        "Anna{@name} ____ mówi{mowic} o{o} pracy{praca}.",
        "Anna often talks about work.",
        "często{czesto}",
        "Put the frequency before the verb.",
    ),
    translation(
        "We often walk home.",
        "Często{czesto} idziemy{isc} do{do} domu{dom}.",
        "Lead with the frequency word.",
    ),
)

# Unit 8 — giving, taking, and connected clauses.
L(
    "dac",
    "dać",
    "to give",
    "verb",
    8,
    model("I want to give it to Anna.", "Chcę{chciec} to{to} dać{dac} Annie{@name}."),
    cloze(
        "Chcę{chciec} to{to} ____ Annie{@name}.",
        "I want to give it to Anna.",
        "dać{dac}",
        "Use the completed infinitive.",
    ),
    cloze(
        "Marek{@name} może{moc} to{to} ____ Annie{@name}.",
        "Marek can give it to Anna.",
        "dać{dac}",
        "Use the infinitive after the modal.",
    ),
    translation(
        "I have to give it to you.",
        "Muszę{musiec} ci{ty} to{to} dać{dac}.",
        "Put the short recipient before the object.",
    ),
)
L(
    "brac",
    "brać",
    "to take",
    "verb",
    8,
    model("I am taking it.", "Biorę{brac} to{to}."),
    cloze("____ to{to}.", "I am taking it.", "Biorę{brac}", "Use the first-person ongoing form."),
    cloze(
        "Anna{@name} ____ tę{ten} rzecz{rzecz}.",
        "Anna is taking this thing.",
        "bierze{brac}",
        "Use the third-person form.",
    ),
    translation("We are taking it.", "Bierzemy{brac} to{to}.", "Use the first-person plural form."),
)
L(
    "wziac",
    "wziąć",
    "to take (completed)",
    "verb",
    8,
    model(
        "I have to take it home.",
        "Muszę{musiec} to{to} wziąć{wziac} do{do} domu{dom}.",
    ),
    cloze(
        "Muszę{musiec} to{to} ____ do{do} domu{dom}.",
        "I have to take it home.",
        "wziąć{wziac}",
        "Use the completed infinitive.",
    ),
    cloze(
        "Możesz{moc} ____ tę{ten} rzecz{rzecz} do{do} pracy{praca}.",
        "You can take this thing to work.",
        "wziąć{wziac}",
        "Use the infinitive after the modal.",
    ),
    translation(
        "We want to take this thing home.",
        "Chcemy{chciec} wziąć{wziac} tę{ten} rzecz{rzecz} do{do} domu{dom}.",
        "Use a destination to make this one bounded trip.",
    ),
)
L(
    "i",
    "i",
    "and",
    "particle",
    8,
    model("Anna and Marek are here.", "Anna{@name} i{i} Marek{@name} są{byc} tutaj{tutaj}."),
    cloze(
        "Anna{@name} ____ Marek{@name} są{byc} tutaj{tutaj}.",
        "Anna and Marek are here.",
        "i{i}",
        "Join both people.",
    ),
    cloze(
        "Mam{miec} czas{czas} ____ pieniądze{pieniadze}.",
        "I have time and money.",
        "i{i}",
        "Add the second thing.",
    ),
    translation(
        "We want time and money.",
        "Chcemy{chciec} czasu{czas} i{i} pieniędzy{pieniadze}.",
        "Use the natural forms after ‘want’.",
    ),
)
L(
    "ale",
    "ale",
    "but",
    "particle",
    8,
    model(
        "I want to walk, but I have to wait.",
        "Chcę{chciec} iść{isc}, ale{ale} muszę{musiec} czekać{czekac}.",
    ),
    cloze(
        "Chcę{chciec} iść{isc}, ____ muszę{musiec} czekać{czekac}.",
        "I want to walk, but I have to wait.",
        "ale{ale}",
        "Introduce the contrast.",
    ),
    cloze(
        "Anna{@name} jest{byc} tutaj{tutaj}, ____ Marek{@name} jest{byc} tam{tam}.",
        "Anna is here, but Marek is there.",
        "ale{ale}",
        "Contrast the two locations.",
    ),
    translation(
        "We have time, but we don't have money.",
        "Mamy{miec} czas{czas}, ale{ale} nie{nie} mamy{miec} pieniędzy{pieniadze}.",
        "Join an affirmative fact to a contrasting negative one.",
    ),
)
L(
    "albo",
    "albo",
    "or",
    "particle",
    8,
    model("Home or work?", "Dom{dom} albo{albo} praca{praca}?"),
    cloze("Dom{dom} ____ praca{praca}?", "Home or work?", "albo{albo}", "Offer two alternatives."),
    cloze(
        "Możemy{moc} iść{isc} ____ jechać{jechac}.",
        "We can walk or go by vehicle.",
        "albo{albo}",
        "Join alternative actions.",
    ),
    translation(
        "Today or tomorrow?",
        "Dziś{dzis} albo{albo} jutro{jutro}?",
        "Offer the two days as alternatives.",
    ),
)
L(
    "bo",
    "bo",
    "because",
    "particle",
    8,
    model(
        "I am returning because I have to work.",
        "Wracam{wracac}, bo{bo} muszę{musiec} pracować{pracowac}.",
    ),
    cloze(
        "Wracam{wracac}, ____ muszę{musiec} pracować{pracowac}.",
        "I am returning because I have to work.",
        "bo{bo}",
        "Introduce the reason.",
    ),
    cloze(
        "Czekam{czekac}, ____ Anna{@name} jeszcze{jeszcze} pracuje{pracowac}.",
        "I am waiting because Anna is still working.",
        "bo{bo}",
        "Connect the action to its reason.",
    ),
    translation(
        "I am at home because I am not working today.",
        "Jestem{byc} w{w} domu{dom}, bo{bo} dziś{dzis} nie{nie} pracuję{pracowac}.",
        "Put the reason after the main fact.",
    ),
)
L(
    "tez",
    "też",
    "also; too",
    "particle",
    8,
    model("Me too.", "Ja{ja} też{tez}."),
    cloze("Ja{ja} ____.", "Me too.", "też{tez}", "Add yourself to the same situation."),
    cloze(
        "Anna{@name} ____ jest{byc} tutaj{tutaj}.",
        "Anna is also here.",
        "też{tez}",
        "Add Anna to those already present.",
    ),
    translation(
        "We want it too.",
        "Też{tez} tego{to} chcemy{chciec}.",
        "Place ‘too’ first and use the form required by ‘want’.",
    ),
)
L(
    "tylko",
    "tylko",
    "only",
    "particle",
    8,
    model("Only me.", "Tylko{tylko} ja{ja}."),
    cloze("____ ja{ja}.", "Only me.", "Tylko{tylko}", "Exclude everyone else."),
    cloze(
        "Chcę{chciec} ____ tego{to}.",
        "I want only this.",
        "tylko{tylko}",
        "Restrict the choice to this thing.",
    ),
    translation(
        "Only Anna knows.",
        "Tylko{tylko} Anna{@name} wie{wiedziec}.",
        "Put the restriction before the person.",
    ),
)
L(
    "od",
    "od",
    "from; since",
    "preposition",
    8,
    model("This is from Marek.", "To{to} jest{byc} od{od} Marka{@name}."),
    cloze(
        "To{to} jest{byc} ____ Marka{@name}.",
        "This is from Marek.",
        "od{od}",
        "Mark the source person.",
    ),
    cloze(
        "Wracam{wracac} ____ Anny{@name}.",
        "I am returning from Anna's place.",
        "od{od}",
        "Mark the person whose place you are leaving.",
    ),
    translation(
        "I have this from you.",
        "Mam{miec} to{to} od{od} ciebie{ty}.",
        "Use the form of ‘you’ required after the source preposition.",
    ),
)

# Unit 9 — problems, questions, and finding solutions.
L(
    "problem",
    "problem",
    "problem",
    "noun",
    9,
    model("I have a problem.", "Mam{miec} problem{problem}."),
    cloze(
        "Mam{miec} ____.",
        "I have a problem.",
        "problem{problem}",
        "The masculine noun keeps its base form.",
    ),
    cloze(
        "To{to} jest{byc} duży{duzy} ____.",
        "This is a big problem.",
        "problem{problem}",
        "Name the difficulty.",
    ),
    translation(
        "We have a problem.", "Mamy{miec} problem{problem}.", "Use the plural form of ‘have’."
    ),
)
L(
    "pytanie",
    "pytanie",
    "question",
    "noun",
    9,
    model("I have a question.", "Mam{miec} pytanie{pytanie}."),
    cloze(
        "Mam{miec} ____.",
        "I have a question.",
        "pytanie{pytanie}",
        "The neuter noun keeps its base form.",
    ),
    cloze(
        "To{to} jest{byc} dobre{dobry} ____.",
        "This is a good question.",
        "pytanie{pytanie}",
        "Name what is being asked.",
    ),
    translation(
        "I have a question for you.",
        "Mam{miec} pytanie{pytanie} do{do} ciebie{ty}.",
        "Put the recipient after the question.",
    ),
)
L(
    "odpowiedz",
    "odpowiedź",
    "answer",
    "noun",
    9,
    model("I know the answer.", "Znam{znac} odpowiedź{odpowiedz}."),
    cloze(
        "Znam{znac} ____.",
        "I know the answer.",
        "odpowiedź{odpowiedz}",
        "The feminine noun keeps its form here.",
    ),
    cloze(
        "Mam{miec} ____.",
        "I have an answer.",
        "odpowiedź{odpowiedz}",
        "Use the base form as the direct object.",
    ),
    translation(
        "I don't know the answer.",
        "Nie{nie} znam{znac} odpowiedzi{odpowiedz}.",
        "Negation changes the object form.",
    ),
)
L(
    "sposob",
    "sposób",
    "way; method",
    "noun",
    9,
    model("I know a way.", "Znam{znac} sposób{sposob}."),
    cloze(
        "Znam{znac} ____.",
        "I know a way.",
        "sposób{sposob}",
        "The masculine object keeps its base form.",
    ),
    cloze(
        "To{to} jest{byc} dobry{dobry} ____.",
        "This is a good way.",
        "sposób{sposob}",
        "Name the method.",
    ),
    translation(
        "We need a way.",
        "Potrzebujemy{potrzebowac} sposobu{sposob}.",
        "The noun changes after ‘need’.",
    ),
)
L(
    "szukac",
    "szukać",
    "to look for",
    "verb",
    9,
    model("I am looking for the answer.", "Szukam{szukac} odpowiedzi{odpowiedz}."),
    cloze(
        "____ odpowiedzi{odpowiedz}.",
        "I am looking for the answer.",
        "Szukam{szukac}",
        "Use the first-person form.",
    ),
    cloze(
        "Anna{@name} ____ sposobu{sposob}.",
        "Anna is looking for a way.",
        "szuka{szukac}",
        "Use the third-person form.",
    ),
    translation(
        "We are looking for help.",
        "Szukamy{szukac} pomocy{pomoc}.",
        "Use the plural verb and the required noun form.",
    ),
)
L(
    "znalezc",
    "znaleźć",
    "to find",
    "verb",
    9,
    model("I want to find a way.", "Chcę{chciec} znaleźć{znalezc} sposób{sposob}."),
    cloze(
        "Chcę{chciec} ____ sposób{sposob}.",
        "I want to find a way.",
        "znaleźć{znalezc}",
        "Use the completed infinitive.",
    ),
    cloze(
        "Marek{@name} musi{musiec} ____ odpowiedź{odpowiedz}.",
        "Marek has to find the answer.",
        "znaleźć{znalezc}",
        "Use the infinitive after the modal.",
    ),
    translation(
        "We can find a good way.",
        "Możemy{moc} znaleźć{znalezc} dobry{dobry} sposób{sposob}.",
        "Use the plural modal before the completed infinitive.",
    ),
)
L(
    "widziec",
    "widzieć",
    "to see",
    "verb",
    9,
    model("I see the problem.", "Widzę{widziec} problem{problem}."),
    cloze(
        "____ problem{problem}.",
        "I see the problem.",
        "Widzę{widziec}",
        "Use the first-person form.",
    ),
    cloze(
        "Anna{@name} ____ dom{dom}.",
        "Anna sees the house.",
        "widzi{widziec}",
        "Use the third-person form.",
    ),
    translation(
        "We see this person.",
        [
            ("Widzimy{widziec} tę{ten} osobę{osoba}.", "any"),
            ("Widzimy{widziec} tego{ten} człowieka{czlowiek}.", "any"),
        ],
        "Either person noun works; use the matching object forms.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
)
L(
    "wazny",
    "ważny",
    "important",
    "adjective",
    9,
    model("This is an important question.", "To{to} jest{byc} ważne{wazny} pytanie{pytanie}."),
    cloze(
        "To{to} jest{byc} ____ pytanie{pytanie}.",
        "This is an important question.",
        "ważne{wazny}",
        "Match the neuter noun.",
    ),
    cloze(
        "Ten{ten} problem{problem} jest{byc} ____.",
        "This problem is important.",
        "ważny{wazny}",
        "Match the masculine noun.",
    ),
    translation(
        "This is important.", "To{to} jest{byc} ważne{wazny}.", "Use the neutral predicative form."
    ),
)
L(
    "latwy",
    "łatwy",
    "easy",
    "adjective",
    9,
    model("This is an easy question.", "To{to} jest{byc} łatwe{latwy} pytanie{pytanie}."),
    cloze(
        "To{to} jest{byc} ____ pytanie{pytanie}.",
        "This is an easy question.",
        "łatwe{latwy}",
        "Match the neuter noun.",
    ),
    cloze(
        "Ten{ten} sposób{sposob} jest{byc} ____.",
        "This way is easy.",
        "łatwy{latwy}",
        "Match the masculine noun.",
    ),
    translation(
        "This is easy.", "To{to} jest{byc} łatwe{latwy}.", "Use the neutral predicative form."
    ),
)
L(
    "trudny",
    "trudny",
    "difficult",
    "adjective",
    9,
    model("This is a difficult problem.", "To{to} jest{byc} trudny{trudny} problem{problem}."),
    cloze(
        "To{to} jest{byc} ____ problem{problem}.",
        "This is a difficult problem.",
        "trudny{trudny}",
        "Match the masculine noun.",
    ),
    cloze(
        "Ta{ten} praca{praca} jest{byc} ____.",
        "This work is difficult.",
        "trudna{trudny}",
        "Match the feminine noun.",
    ),
    translation(
        "This is difficult for me.",
        "To{to} jest{byc} dla{dla} mnie{ja} trudne{trudny}.",
        "Put the affected person before the final description.",
    ),
)

# Unit 10 — useful daily nouns, description, and conditional links.
L(
    "woda",
    "woda",
    "water",
    "noun",
    10,
    model("I want water.", "Chcę{chciec} wody{woda}."),
    cloze(
        "Chcę{chciec} ____.",
        "I want water.",
        "wody{woda}",
        "Use the form required after ‘want’.",
    ),
    cloze(
        "Potrzebuję{potrzebowac} ____.",
        "I need water.",
        "wody{woda}",
        "The noun changes after ‘need’.",
    ),
    translation(
        "We have water.", "Mamy{miec} wodę{woda}.", "Use the plural verb and direct-object form."
    ),
)
L(
    "jedzenie",
    "jedzenie",
    "food",
    "noun",
    10,
    model("I have food.", "Mam{miec} jedzenie{jedzenie}."),
    cloze(
        "Mam{miec} ____.",
        "I have food.",
        "jedzenie{jedzenie}",
        "The neuter object keeps its base form.",
    ),
    cloze(
        "Potrzebuję{potrzebowac} ____.",
        "I need food.",
        "jedzenia{jedzenie}",
        "The noun changes after ‘need’.",
    ),
    translation(
        "I want food and water.",
        "Chcę{chciec} jedzenia{jedzenie} i{i} wody{woda}.",
        "Use the natural forms for unspecified food and water.",
    ),
)
L(
    "telefon",
    "telefon",
    "telephone",
    "noun",
    10,
    model("I have a phone.", "Mam{miec} telefon{telefon}."),
    cloze(
        "Mam{miec} ____.",
        "I have a phone.",
        "telefon{telefon}",
        "The masculine object keeps its base form.",
    ),
    cloze(
        "Potrzebuję{potrzebowac} ____.",
        "I need a phone.",
        "telefonu{telefon}",
        "The noun changes after ‘need’.",
    ),
    translation(
        "I am looking for the phone.",
        "Szukam{szukac} telefonu{telefon}.",
        "The noun takes the form required after ‘look for’.",
    ),
)
L(
    "zycie",
    "życie",
    "life",
    "noun",
    10,
    model("Life is difficult.", "Życie{zycie} jest{byc} trudne{trudny}."),
    cloze(
        "____ jest{byc} trudne{trudny}.",
        "Life is difficult.",
        "Życie{zycie}",
        "The neuter noun for life.",
    ),
    cloze(
        "To{to} jest{byc} dobre{dobry} ____.",
        "This is a good life.",
        "życie{zycie}",
        "Match the neuter adjective.",
    ),
    translation(
        "I want a good life.",
        "Chcę{chciec} dobrego{dobry} życia{zycie}.",
        "Both words change after this use of ‘want’.",
    ),
)
L(
    "maly",
    "mały",
    "small; little",
    "adjective",
    10,
    model("This is a small problem.", "To{to} jest{byc} mały{maly} problem{problem}."),
    cloze(
        "To{to} jest{byc} ____ problem{problem}.",
        "This is a small problem.",
        "mały{maly}",
        "Match the masculine noun.",
    ),
    cloze(
        "To{to} jest{byc} ____ dziecko{dziecko}.",
        "This is a small child.",
        "małe{maly}",
        "Match the neuter noun.",
    ),
    translation(
        "This is a small house.",
        "To{to} jest{byc} mały{maly} dom{dom}.",
        "Match the masculine noun.",
    ),
)
L(
    "nowy",
    "nowy",
    "new",
    "adjective",
    10,
    model("I have a new phone.", "Mam{miec} nowy{nowy} telefon{telefon}."),
    cloze(
        "Mam{miec} ____ telefon{telefon}.",
        "I have a new phone.",
        "nowy{nowy}",
        "Match the masculine object.",
    ),
    cloze(
        "To{to} jest{byc} ____ miejsce{miejsce}.",
        "This is a new place.",
        "nowe{nowy}",
        "Match the neuter noun.",
    ),
    translation(
        "This is a new job.",
        "To{to} jest{byc} nowa{nowy} praca{praca}.",
        "Match the feminine noun.",
    ),
)
L(
    "zly",
    "zły",
    "bad",
    "adjective",
    10,
    model("This is a bad way.", "To{to} jest{byc} zły{zly} sposób{sposob}."),
    cloze(
        "To{to} jest{byc} ____ sposób{sposob}.",
        "This is a bad way.",
        "zły{zly}",
        "Match the masculine noun.",
    ),
    cloze(
        "To{to} jest{byc} ____ odpowiedź{odpowiedz}.",
        "This is a bad answer.",
        "zła{zly}",
        "Match the feminine noun.",
    ),
    translation(
        "This is a bad thing.",
        "To{to} jest{byc} zła{zly} rzecz{rzecz}.",
        "Match the feminine noun.",
    ),
)
L(
    "jesli",
    "jeśli",
    "if",
    "particle",
    10,
    model(
        "If I'm allowed, I'm walking there.",
        "Jeśli{jesli} mogę{moc}, idę{isc} tam{tam}.",
    ),
    cloze(
        "____ mogę{moc}, idę{isc} tam{tam}.",
        "If I'm allowed, I'm walking there.",
        "Jeśli{jesli}",
        "Introduce the condition.",
    ),
    cloze(
        "____ masz{miec} czas{czas}, możemy{moc} iść{isc}.",
        "If you have time, we can walk.",
        "Jeśli{jesli}",
        "Put the condition first.",
    ),
    translation(
        "If Anna is at home, I’m walking there now.",
        "Jeśli{jesli} Anna{@name} jest{byc} w{w} domu{dom}, idę{isc} tam{tam} teraz{teraz}.",
        "State the condition before the result.",
    ),
)
L(
    "wiec",
    "więc",
    "so; therefore",
    "particle",
    10,
    model("I have time, so I am walking.", "Mam{miec} czas{czas}, więc{wiec} idę{isc}."),
    cloze(
        "Mam{miec} czas{czas}, ____ idę{isc}.",
        "I have time, so I am walking.",
        "więc{wiec}",
        "Introduce the result.",
    ),
    cloze(
        "Anna{@name} pracuje{pracowac}, ____ czekam{czekac}.",
        "Anna is working, so I am waiting.",
        "więc{wiec}",
        "Connect the fact to its consequence.",
    ),
    translation(
        "We don't have time, so we are returning home.",
        "Nie{nie} mamy{miec} czasu{czas}, więc{wiec} wracamy{wracac} do{do} domu{dom}.",
        "Put the consequence after the comma.",
    ),
)
L(
    "bardzo",
    "bardzo",
    "very",
    "adverb",
    10,
    model("This is very important.", "To{to} jest{byc} bardzo{bardzo} ważne{wazny}."),
    cloze(
        "To{to} jest{byc} ____ ważne{wazny}.",
        "This is very important.",
        "bardzo{bardzo}",
        "Intensify the description.",
    ),
    cloze(
        "To{to} jest{byc} ____ duży{duzy} dom{dom}.",
        "This is a very big house.",
        "bardzo{bardzo}",
        "Place the intensifier before the adjective.",
    ),
    translation(
        "This is very difficult.",
        "To{to} jest{byc} bardzo{bardzo} trudne{trudny}.",
        "Put the intensifier directly before the description.",
    ),
)


# Mature review bank. These contexts unlock only when every concept in an
# accepted Polish answer is ready, so early cards gain variety as the learner's
# usable vocabulary grows without leaking unseen words.

# Unit 1 review contexts.
R(
    "tak",
    translation("Yes, I know.", "Tak{tak}, wiem{wiedziec}.", "Confirm, then state the fact."),
    translation("Yes, we can.", "Tak{tak}, możemy{moc}.", "Confirm the group's ability."),
    translation(
        "Yes, Anna is here.",
        "Tak{tak}, Anna{@name} jest{byc} tutaj{tutaj}.",
        "Confirm the complete statement.",
    ),
)
R(
    "nie",
    translation("I do not know.", "Nie{nie} wiem{wiedziec}.", "Negate the fact-knowing verb."),
    translation(
        "We do not have time.",
        "Nie{nie} mamy{miec} czasu{czas}.",
        "Put negation before the plural verb.",
    ),
    translation(
        "Anna is not here.",
        "Anna{@name} nie{nie} jest{byc} tutaj{tutaj}.",
        "Put negation directly before the verb.",
    ),
)
R(
    "to",
    translation("I know that.", "Wiem{wiedziec} to{to}.", "Put the known fact after the verb."),
    translation("We are doing this.", "Robimy{robic} to{to}.", "Use the plural ongoing verb."),
    translation(
        "I am thinking about it.",
        "Myślę{myslec} o{o} tym{to}.",
        "Use the form required after ‘about’.",
    ),
)
R(
    "ja",
    translation(
        "I am the one who is here, not Marek.",
        "To{to} ja{ja} jestem{byc} tutaj{tutaj}, nie{nie} Marek{@name}.",
        "Put the contrasting speaker immediately after to.",
    ),
    translation(
        "This is for me.",
        "To{to} jest{byc} dla{dla} mnie{ja}.",
        "Use the form of ‘me’ required after ‘for’.",
    ),
    translation(
        "Anna is with me.",
        "Anna{@name} jest{byc} ze{z} mną{ja}.",
        "Use the natural longer preposition before ‘me’.",
    ),
)
R(
    "ty",
    translation(
        "This is for you.",
        "To{to} jest{byc} dla{dla} ciebie{ty}.",
        "Use the form required after ‘for’.",
    ),
    translation(
        "I am with you.",
        "Jestem{byc} z{z} tobą{ty}.",
        "Use the form required after ‘with’.",
    ),
    translation(
        "I have to give it to you.",
        "Muszę{musiec} ci{ty} to{to} dać{dac}.",
        "Put the short recipient before the object.",
    ),
)
R(
    "byc",
    translation(
        "He is at work.",
        "On{on} jest{byc} w{w} pracy{praca}.",
        "Use the third-person present form.",
    ),
    translation(
        "We are at home.",
        "Jesteśmy{byc} w{w} domu{dom}.",
        "Use the first-person plural form.",
    ),
    translation(
        "Yesterday I was there.",
        [
            ("Wczoraj{wczoraj} byłem{byc} tam{tam}.", "masculine"),
            ("Wczoraj{wczoraj} byłam{byc} tam{tam}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "tutaj",
    translation(
        "Anna works here.",
        "Anna{@name} pracuje{pracowac} tutaj{tutaj}.",
        "Put the location after the verb.",
    ),
    translation(
        "We are waiting here.",
        "Czekamy{czekac} tutaj{tutaj}.",
        "Use the plural verb before the location.",
    ),
    translation(
        "Is Marek here?",
        "Czy{czy} Marek{@name} jest{byc} tutaj{tutaj}?",
        "Open the question, then name the location.",
    ),
)
R(
    "miec",
    translation("We have time.", "Mamy{miec} czas{czas}.", "Use the plural verb form."),
    translation(
        "Anna has a problem.",
        "Anna{@name} ma{miec} problem{problem}.",
        "Use the third-person verb form.",
    ),
    translation(
        "Yesterday I had time.",
        [
            ("Wczoraj{wczoraj} miałem{miec} czas{czas}.", "masculine"),
            ("Wczoraj{wczoraj} miałam{miec} czas{czas}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "chciec",
    translation(
        "Anna wants help.",
        "Anna{@name} chce{chciec} pomocy{pomoc}.",
        "Use the third-person verb and the required noun form.",
    ),
    translation(
        "Do you want water?",
        "Chcesz{chciec} wody{woda}?",
        "Use the second-person verb and the required noun form.",
    ),
    translation(
        "Yesterday I wanted to head home.",
        [
            (
                "Wczoraj{wczoraj} chciałem{chciec} pójść{pojsc} do{do} domu{dom}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} chciałam{chciec} pójść{pojsc} do{do} domu{dom}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "moc",
    translation("We can wait.", "Możemy{moc} czekać{czekac}.", "Use the plural modal form."),
    translation(
        "Anna can get it done.",
        "Anna{@name} może{moc} to{to} zrobić{zrobic}.",
        "Use the third-person modal before the completed action.",
    ),
    translation(
        "Yesterday I could not work.",
        [
            (
                "Wczoraj{wczoraj} nie{nie} mogłem{moc} pracować{pracowac}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} nie{nie} mogłam{moc} pracować{pracowac}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form after negation.",
    ),
)

# Unit 2 review contexts.
R(
    "on",
    translation("I know him.", "Znam{znac} go{on}.", "Use the short object form of ‘he’."),
    translation(
        "I am talking about him.",
        "Mówię{mowic} o{o} nim{on}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "I have to give it to him.",
        "Muszę{musiec} mu{on} to{to} dać{dac}.",
        "Put the short recipient before the object.",
    ),
)
R(
    "ona",
    translation("I know her.", "Znam{znac} ją{ona}.", "Use the feminine object form."),
    translation(
        "I am talking about her.",
        "Mówię{mowic} o{o} niej{ona}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "I have to give it to her.",
        "Muszę{musiec} jej{ona} to{to} dać{dac}.",
        "Put the short recipient before the object.",
    ),
)
R(
    "my",
    translation(
        "This is for us.",
        "To{to} jest{byc} dla{dla} nas{my}.",
        "Use the form required after ‘for’.",
    ),
    translation(
        "Anna is with us.",
        "Anna{@name} jest{byc} z{z} nami{my}.",
        "Use the form required after ‘with’.",
    ),
    translation(
        "Marek has to give it to us.",
        "Marek{@name} musi{musiec} nam{my} to{to} dać{dac}.",
        "Put the short recipient before the object.",
    ),
)
R(
    "czlowiek",
    translation(
        "People are here.",
        "Ludzie{czlowiek} są{byc} tutaj{tutaj}.",
        "Use the irregular plural for human beings in general.",
    ),
    translation(
        "We know this man.",
        "Znamy{znac} tego{ten} człowieka{czlowiek}.",
        "Use the animate object form.",
    ),
    translation(
        "We are talking about this man.",
        "Mówimy{mowic} o{o} tym{ten} człowieku{czlowiek}.",
        "Use the form required after ‘about’.",
    ),
)
R(
    "dziecko",
    translation(
        "I see the child.",
        "Widzę{widziec} dziecko{dziecko}.",
        "The neuter object keeps its base form.",
    ),
    translation(
        "I am talking about the child.",
        "Mówię{mowic} o{o} dziecku{dziecko}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "This is for the child.",
        "To{to} jest{byc} dla{dla} dziecka{dziecko}.",
        "Use the form required after ‘for’.",
    ),
)
R(
    "rzecz",
    translation(
        "I need this thing.",
        "Potrzebuję{potrzebowac} tej{ten} rzeczy{rzecz}.",
        "Use matching forms after ‘need’.",
    ),
    translation(
        "We are talking about this thing.",
        "Mówimy{mowic} o{o} tej{ten} rzeczy{rzecz}.",
        "Use matching forms after ‘about’.",
    ),
    translation(
        "I have to give this thing to Anna.",
        "Muszę{musiec} dać{dac} tę{ten} rzecz{rzecz} Annie{@name}.",
        "Keep the thing as the direct object and mark the recipient.",
    ),
)
R(
    "ten",
    translation(
        "I know this man.",
        "Znam{znac} tego{ten} człowieka{czlowiek}.",
        "Match ‘this’ to the animate object.",
    ),
    translation(
        "I see this individual.",
        "Widzę{widziec} tę{ten} osobę{osoba}.",
        "Match ‘this’ to the feminine object.",
    ),
    translation(
        "We are talking about this thing.",
        "Mówimy{mowic} o{o} tej{ten} rzeczy{rzecz}.",
        "Match ‘this’ to the form required after ‘about’.",
    ),
)
R(
    "osoba",
    translation(
        "I know this individual.",
        "Znam{znac} tę{ten} osobę{osoba}.",
        "Use the feminine object forms.",
    ),
    translation(
        "We are talking about this individual.",
        "Mówimy{mowic} o{o} tej{ten} osobie{osoba}.",
        "Use the forms required after ‘about’.",
    ),
    translation(
        "This is intended for this individual.",
        "To{to} jest{byc} dla{dla} tej{ten} osoby{osoba}.",
        "Use the forms required after ‘for’.",
    ),
)
R(
    "dobry",
    translation(
        "This is a good answer.",
        "To{to} jest{byc} dobra{dobry} odpowiedź{odpowiedz}.",
        "Match the adjective to the feminine noun.",
    ),
    translation(
        "This is good food.",
        "To{to} jest{byc} dobre{dobry} jedzenie{jedzenie}.",
        "Match the adjective to the neuter noun.",
    ),
    translation(
        "We need a good way.",
        "Potrzebujemy{potrzebowac} dobrego{dobry} sposobu{sposob}.",
        "Match both words after ‘need’.",
    ),
)
R(
    "duzy",
    translation(
        "This is a big problem.",
        "To{to} jest{byc} duży{duzy} problem{problem}.",
        "Match the adjective to the masculine noun.",
    ),
    translation(
        "I have a big question.",
        "Mam{miec} duże{duzy} pytanie{pytanie}.",
        "Match the adjective to the neuter noun.",
    ),
    translation(
        "We need a big house.",
        "Potrzebujemy{potrzebowac} dużego{duzy} domu{dom}.",
        "Match both words after ‘need’.",
    ),
)

# Unit 3 review contexts.
R(
    "czas",
    translation(
        "I need time.",
        "Potrzebuję{potrzebowac} czasu{czas}.",
        "Use the form required after ‘need’.",
    ),
    translation(
        "We are talking about time.",
        "Mówimy{mowic} o{o} czasie{czas}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "This is a difficult time.",
        "To{to} jest{byc} trudny{trudny} czas{czas}.",
        "Match the adjective to the masculine noun.",
    ),
)
R(
    "pieniadze",
    translation(
        "We need money.",
        "Potrzebujemy{potrzebowac} pieniędzy{pieniadze}.",
        "Use the form required after ‘need’.",
    ),
    translation(
        "I am thinking about money.",
        "Myślę{myslec} o{o} pieniądzach{pieniadze}.",
        "Use the plural form required after ‘about’.",
    ),
    translation(
        "This money is for Anna.",
        "Te{ten} pieniądze{pieniadze} są{byc} dla{dla} Anny{@name}.",
        "Match ‘this’ to the plural noun, then name the recipient.",
    ),
)
R(
    "pomoc",
    translation(
        "We need help.",
        "Potrzebujemy{potrzebowac} pomocy{pomoc}.",
        "Use the form required after ‘need’.",
    ),
    translation(
        "We are talking about help.",
        "Mówimy{mowic} o{o} pomocy{pomoc}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "With help, I can get it done.",
        "Z{z} pomocą{pomoc} mogę{moc} to{to} zrobić{zrobic}.",
        "Put the help phrase before what becomes possible.",
    ),
)
R(
    "musiec",
    translation(
        "Anna has to work.",
        "Anna{@name} musi{musiec} pracować{pracowac}.",
        "Use the third-person modal before the infinitive.",
    ),
    translation(
        "Do you have to head home?",
        "Musisz{musiec} pójść{pojsc} do{do} domu{dom}?",
        "Use the second-person modal before the bounded trip.",
    ),
    translation(
        "Yesterday I had to wait.",
        [
            (
                "Wczoraj{wczoraj} musiałem{musiec} czekać{czekac}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} musiałam{musiec} czekać{czekac}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "potrzebowac",
    translation(
        "Anna needs water.",
        "Anna{@name} potrzebuje{potrzebowac} wody{woda}.",
        "Use the third-person verb and the required noun form.",
    ),
    translation(
        "Do you need help?",
        "Potrzebujesz{potrzebowac} pomocy{pomoc}?",
        "Use the second-person verb and the required noun form.",
    ),
    translation(
        "Yesterday I needed time.",
        [
            (
                "Wczoraj{wczoraj} potrzebowałem{potrzebowac} czasu{czas}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} potrzebowałam{potrzebowac} czasu{czas}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "cos",
    translation("I know something.", "Wiem{wiedziec} coś{cos}.", "Use the base form after ‘know’."),
    translation(
        "We are thinking about something.",
        "Myślimy{myslec} o{o} czymś{cos}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "I need something for work.",
        "Potrzebuję{potrzebowac} czegoś{cos} do{do} pracy{praca}.",
        "Use the form required after ‘need’.",
    ),
)
R(
    "kto",
    translation("Who do you know?", "Kogo{kto} znasz{znac}?", "Ask about a known person."),
    translation(
        "Who are you talking about?",
        "O{o} kim{kto} mówisz{mowic}?",
        "Use the form required after ‘about’.",
    ),
    translation(
        "Who do you have to give it to?",
        "Komu{kto} musisz{musiec} to{to} dać{dac}?",
        "Begin with the recipient question.",
    ),
)
R(
    "co",
    translation(
        "What are you thinking about?",
        "O{o} czym{co} myślisz{myslec}?",
        "Use the form required after ‘about’.",
    ),
    translation(
        "What do you need?",
        "Czego{co} potrzebujesz{potrzebowac}?",
        "Use the form required by ‘need’.",
    ),
    translation("What are you doing?", "Co{co} robisz{robic}?", "Ask about the current action."),
)
R(
    "bez",
    translation(
        "I cannot head there without money.",
        "Nie{nie} mogę{moc} tam{tam} pójść{pojsc} bez{bez} pieniędzy{pieniadze}.",
        "Put the missing resource after the preposition.",
    ),
    translation(
        "We cannot be without water.",
        "Nie{nie} możemy{moc} być{byc} bez{bez} wody{woda}.",
        "Use the required form of the missing resource.",
    ),
    translation(
        "Anna works without help.",
        "Anna{@name} pracuje{pracowac} bez{bez} pomocy{pomoc}.",
        "Put the missing assistance after the verb.",
    ),
)
R(
    "dla",
    translation(
        "This water is for the child.",
        "Ta{ten} woda{woda} jest{byc} dla{dla} dziecka{dziecko}.",
        "Name the recipient after the preposition.",
    ),
    translation(
        "I work for Anna.",
        "Pracuję{pracowac} dla{dla} Anny{@name}.",
        "Put the person benefiting from the work last.",
    ),
    translation(
        "I have something for you.",
        "Mam{miec} coś{cos} dla{dla} ciebie{ty}.",
        "Use the form of ‘you’ required after ‘for’.",
    ),
)

# Unit 4 review contexts.
R(
    "dom",
    translation("I am at home.", "Jestem{byc} w{w} domu{dom}.", "Use the home-location form."),
    translation(
        "I am walking home.",
        "Idę{isc} do{do} domu{dom}.",
        "Use the form after the destination preposition.",
    ),
    translation(
        "We are looking for a house.",
        "Szukamy{szukac} domu{dom}.",
        "Use the form required by ‘look for’.",
    ),
)
R(
    "praca",
    translation(
        "Anna is at work.",
        "Anna{@name} jest{byc} w{w} pracy{praca}.",
        "Use the work-location form.",
    ),
    translation(
        "We are returning from work.",
        "Wracamy{wracac} z{z} pracy{praca}.",
        "Use the form after the source preposition.",
    ),
    translation(
        "Work is important.",
        "Praca{praca} jest{byc} ważna{wazny}.",
        "Use the base noun form as the subject.",
    ),
)
R(
    "miejsce",
    translation(
        "We are at this location.",
        "Jesteśmy{byc} w{w} tym{ten} miejscu{miejsce}.",
        "Use matching forms after the location preposition.",
    ),
    translation(
        "I do not have room.",
        "Nie{nie} mam{miec} miejsca{miejsce}.",
        "Negation changes the object form.",
    ),
    translation(
        "This place is important.",
        "To{ten} miejsce{miejsce} jest{byc} ważne{wazny}.",
        "Match the demonstrative and adjective to the neuter noun.",
    ),
)
R(
    "w",
    translation(
        "We are in a big house.",
        "Jesteśmy{byc} w{w} dużym{duzy} domu{dom}.",
        "Put matching location forms after the preposition.",
    ),
    translation(
        "I'm at work tomorrow.",
        "Jutro{jutro} jestem{byc} w{w} pracy{praca}.",
        "Place the location after the verb.",
    ),
    translation(
        "Anna is waiting at home.",
        "Anna{@name} czeka{czekac} w{w} domu{dom}.",
        "Put the waiting location last.",
    ),
)
R(
    "na",
    translation(
        "I am waiting for Anna.",
        "Czekam{czekac} na{na} Annę{@name}.",
        "Mark the person being awaited.",
    ),
    translation(
        "I need money for a new phone.",
        "Potrzebuję{potrzebowac} pieniędzy{pieniadze} na{na} nowy{nowy} telefon{telefon}.",
        "Mark what the money is intended to buy.",
    ),
    translation(
        "I have time for an answer.",
        "Mam{miec} czas{czas} na{na} odpowiedź{odpowiedz}.",
        "Mark what the available time is for.",
    ),
)
R(
    "do",
    translation("I am walking to work.", "Idę{isc} do{do} pracy{praca}.", "Mark the destination."),
    translation(
        "We are returning home.", "Wracamy{wracac} do{do} domu{dom}.", "Mark the destination."
    ),
    translation(
        "I have a question for Anna.",
        "Mam{miec} pytanie{pytanie} do{do} Anny{@name}.",
        "Mark the person the question is directed to.",
    ),
)
R(
    "z",
    translation("I am with Marek.", "Jestem{byc} z{z} Markiem{@name}.", "Mark the companion."),
    translation(
        "I am returning from work.",
        "Wracam{wracac} z{z} pracy{praca}.",
        "Mark the source location.",
    ),
    translation(
        "This is a problem with the phone.",
        "To{to} jest{byc} problem{problem} z{z} telefonem{telefon}.",
        "Put the affected thing after the preposition.",
    ),
)
R(
    "gdzie",
    translation(
        "Where do you work?",
        "Gdzie{gdzie} pracujesz{pracowac}?",
        "Begin with the location question.",
    ),
    translation(
        "Do you know where the phone is?",
        "Wiesz{wiedziec}, gdzie{gdzie} jest{byc} telefon{telefon}?",
        "Put the embedded location question after ‘know’.",
    ),
    translation(
        "Where are we going on foot?",
        "Gdzie{gdzie} idziemy{isc}?",
        "Ask for the destination of the current walk.",
    ),
)
R(
    "tam",
    translation(
        "I work there.", "Pracuję{pracowac} tam{tam}.", "Put the distant location after the verb."
    ),
    translation(
        "Tomorrow we are walking there.",
        "Jutro{jutro} idziemy{isc} tam{tam}.",
        "Put the destination after the motion verb.",
    ),
    translation(
        "Is Anna there?",
        "Czy{czy} Anna{@name} jest{byc} tam{tam}?",
        "End the question with the distant location.",
    ),
)
R(
    "czy",
    translation("Do you know?", "Czy{czy} wiesz{wiedziec}?", "Open the yes/no question."),
    translation(
        "Are we walking home?",
        "Czy{czy} idziemy{isc} do{do} domu{dom}?",
        "Open the question before the current motion.",
    ),
    translation(
        "Does Anna need help?",
        "Czy{czy} Anna{@name} potrzebuje{potrzebowac} pomocy{pomoc}?",
        "Open the question before the subject.",
    ),
)

# Unit 5 review contexts.
R(
    "isc",
    translation(
        "Where are you walking?",
        "Gdzie{gdzie} idziesz{isc}?",
        "Ask for the current walking destination.",
    ),
    translation(
        "Anna is walking to work now.",
        "Anna{@name} idzie{isc} teraz{teraz} do{do} pracy{praca}.",
        "Use the third-person current-motion form.",
    ),
    translation(
        "Yesterday I was walking home.",
        [
            ("Wczoraj{wczoraj} szedłem{isc} do{do} domu{dom}.", "masculine"),
            ("Wczoraj{wczoraj} szłam{isc} do{do} domu{dom}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "pojsc",
    translation(
        "We can head home.",
        "Możemy{moc} pójść{pojsc} do{do} domu{dom}.",
        "Use the bounded infinitive after the modal.",
    ),
    translation(
        "Anna wants to head to work tomorrow.",
        "Anna{@name} chce{chciec} jutro{jutro} pójść{pojsc} do{do} pracy{praca}.",
        "Put tomorrow before the bounded trip.",
    ),
    translation(
        "Yesterday I went there on foot.",
        [
            ("Wczoraj{wczoraj} poszedłem{pojsc} tam{tam}.", "masculine"),
            ("Wczoraj{wczoraj} poszłam{pojsc} tam{tam}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "jechac",
    translation(
        "Where are you going by vehicle?",
        "Gdzie{gdzie} jedziesz{jechac}?",
        "Ask for the vehicle journey's destination.",
    ),
    translation(
        "We are travelling home by vehicle now.",
        "Teraz{teraz} jedziemy{jechac} do{do} domu{dom}.",
        "Use the plural vehicle-motion form.",
    ),
    translation(
        "Yesterday I was travelling to work by vehicle.",
        [
            (
                "Wczoraj{wczoraj} jechałem{jechac} do{do} pracy{praca}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} jechałam{jechac} do{do} pracy{praca}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "wracac",
    translation(
        "We are returning from work.",
        "Wracamy{wracac} z{z} pracy{praca}.",
        "Use the plural returning form.",
    ),
    translation(
        "Anna is returning home tomorrow.",
        "Anna{@name} jutro{jutro} wraca{wracac} do{do} domu{dom}.",
        "Put tomorrow before the returning verb.",
    ),
    translation(
        "Yesterday I was returning with Marek.",
        [
            (
                "Wczoraj{wczoraj} wracałem{wracac} z{z} Markiem{@name}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} wracałam{wracac} z{z} Markiem{@name}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "dzis",
    translation(
        "Today I need help.",
        "Dziś{dzis} potrzebuję{potrzebowac} pomocy{pomoc}.",
        "Lead with today.",
    ),
    translation(
        "Is Anna working today?",
        "Czy{czy} Anna{@name} dziś{dzis} pracuje{pracowac}?",
        "Keep today near the verb.",
    ),
    translation(
        "We are walking home today.",
        "Dziś{dzis} idziemy{isc} do{do} domu{dom}.",
        "Lead with today before the current trip.",
    ),
)
R(
    "jutro",
    translation(
        "Tomorrow we are working at home.",
        "Jutro{jutro} pracujemy{pracowac} w{w} domu{dom}.",
        "Lead with tomorrow.",
    ),
    translation(
        "Is Marek walking to work tomorrow?",
        "Czy{czy} Marek{@name} jutro{jutro} idzie{isc} do{do} pracy{praca}?",
        "Keep tomorrow before the motion verb.",
    ),
    translation(
        "I have to get it done tomorrow.",
        "Jutro{jutro} muszę{musiec} to{to} zrobić{zrobic}.",
        "Lead with tomorrow before the obligation.",
    ),
)
R(
    "teraz",
    translation(
        "We are working now.", "Teraz{teraz} pracujemy{pracowac}.", "Lead with the current time."
    ),
    translation(
        "Anna is walking home now.",
        "Anna{@name} teraz{teraz} idzie{isc} do{do} domu{dom}.",
        "Put now before the current motion.",
    ),
    translation(
        "Do you understand now?",
        "Teraz{teraz} rozumiesz{rozumiec}?",
        "Lead with now to contrast the earlier situation.",
    ),
)
R(
    "juz",
    translation(
        "I already know.", "Już{juz} wiem{wiedziec}.", "Lead with the completed change of state."
    ),
    translation(
        "Anna has already done it.",
        "Anna{@name} już{juz} to{to} zrobiła{zrobic}.",
        "Put ‘already’ before the completed action.",
    ),
    translation(
        "We already have the answer.",
        "Już{juz} mamy{miec} odpowiedź{odpowiedz}.",
        "Lead with ‘already’.",
    ),
)
R(
    "jeszcze",
    translation(
        "I am still working.",
        "Jeszcze{jeszcze} pracuję{pracowac}.",
        "Lead with the continuing-state word.",
    ),
    translation(
        "We do not know yet.",
        "Jeszcze{jeszcze} nie{nie} wiemy{wiedziec}.",
        "Put ‘yet’ before negation.",
    ),
    translation(
        "Do you need more time?",
        "Potrzebujesz{potrzebowac} jeszcze{jeszcze} czasu{czas}?",
        "Put ‘more’ before the requested resource.",
    ),
)
R(
    "czekac",
    translation(
        "Who are you waiting for?",
        "Na{na} kogo{kto} czekasz{czekac}?",
        "Begin with the person being awaited.",
    ),
    translation(
        "We are still waiting for the answer.",
        "Jeszcze{jeszcze} czekamy{czekac} na{na} odpowiedź{odpowiedz}.",
        "Keep the continuing action before what is awaited.",
    ),
    translation(
        "Yesterday I waited at home.",
        [
            ("Wczoraj{wczoraj} czekałem{czekac} w{w} domu{dom}.", "masculine"),
            ("Wczoraj{wczoraj} czekałam{czekac} w{w} domu{dom}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
)

# Unit 6 review contexts.
R(
    "wiedziec",
    translation("Do you know?", "Wiesz{wiedziec}?", "Use the second-person fact-knowing form."),
    translation(
        "Anna knows that Marek is at home.",
        "Anna{@name} wie{wiedziec}, że{ze} Marek{@name} jest{byc} w{w} domu{dom}.",
        "Use the third-person form before the known fact.",
    ),
    translation(
        "Yesterday I knew where Anna was.",
        [
            (
                "Wczoraj{wczoraj} wiedziałem{wiedziec}, gdzie{gdzie} była{byc} Anna{@name}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} wiedziałam{wiedziec}, gdzie{gdzie} była{byc} Anna{@name}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form before the past fact.",
    ),
)
R(
    "znac",
    translation(
        "Do you know Anna?", "Znasz{znac} Annę{@name}?", "Use the familiarity verb for a person."
    ),
    translation(
        "Marek knows the answer.",
        "Marek{@name} zna{znac} odpowiedź{odpowiedz}.",
        "Use the third-person familiarity form.",
    ),
    translation(
        "Yesterday I was not familiar with this place.",
        [
            (
                "Wczoraj{wczoraj} nie{nie} znałem{znac} tego{ten} miejsca{miejsce}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} nie{nie} znałam{znac} tego{ten} miejsca{miejsce}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form and matching negative object forms.",
    ),
)
R(
    "rozumiec",
    translation(
        "Do you understand the question?",
        "Rozumiesz{rozumiec} pytanie{pytanie}?",
        "Use the second-person verb before the object.",
    ),
    translation(
        "Anna understands the answer.",
        "Anna{@name} rozumie{rozumiec} odpowiedź{odpowiedz}.",
        "Use the third-person verb before the object.",
    ),
    translation(
        "Yesterday I did not understand it.",
        [
            (
                "Wczoraj{wczoraj} nie{nie} rozumiałem{rozumiec} tego{to}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} nie{nie} rozumiałam{rozumiec} tego{to}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form after negation.",
    ),
)
R(
    "myslec",
    translation(
        "What are you thinking about?",
        "O{o} czym{co} myślisz{myslec}?",
        "Begin with the topic question.",
    ),
    translation(
        "Anna thinks that the question is important.",
        "Anna{@name} myśli{myslec}, że{ze} pytanie{pytanie} jest{byc} ważne{wazny}.",
        "Put the thought before its content.",
    ),
    translation(
        "Yesterday I was thinking about work.",
        [
            (
                "Wczoraj{wczoraj} myślałem{myslec} o{o} pracy{praca}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} myślałam{myslec} o{o} pracy{praca}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "mowic",
    translation("What are you saying?", "Co{co} mówisz{mowic}?", "Ask about the current speech."),
    translation(
        "We are talking about the problem.",
        "Mówimy{mowic} o{o} problemie{problem}.",
        "Use the plural verb and the topic form.",
    ),
    translation(
        "Yesterday I was speaking to Anna.",
        [
            (
                "Wczoraj{wczoraj} mówiłem{mowic} do{do} Anny{@name}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} mówiłam{mowic} do{do} Anny{@name}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "powiedziec",
    translation(
        "Can you tell me that?",
        "Możesz{moc} mi{ja} to{to} powiedzieć{powiedziec}?",
        "Put the short recipient before what is said.",
    ),
    translation(
        "Anna said that she has a problem.",
        "Anna{@name} powiedziała{powiedziec}, że{ze} ma{miec} problem{problem}.",
        "Use the feminine completed past form before the statement's content.",
    ),
    translation(
        "Yesterday I said it.",
        [
            ("Wczoraj{wczoraj} powiedziałem{powiedziec} to{to}.", "masculine"),
            ("Wczoraj{wczoraj} powiedziałam{powiedziec} to{to}.", "feminine"),
        ],
        "Use your selected past self-reference form for one completed statement.",
    ),
)
R(
    "pytac",
    translation(
        "What are you asking about?", "O{o} co{co} pytasz{pytac}?", "Begin with the topic question."
    ),
    translation(
        "Marek is asking Anna about work.",
        "Marek{@name} pyta{pytac} Annę{@name} o{o} pracę{praca}.",
        "Put the person asked before the topic.",
    ),
    translation(
        "Yesterday I was asking about the answer.",
        [
            (
                "Wczoraj{wczoraj} pytałem{pytac} o{o} odpowiedź{odpowiedz}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} pytałam{pytac} o{o} odpowiedź{odpowiedz}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "odpowiadac",
    translation(
        "I am answering the question.",
        "Odpowiadam{odpowiadac} na{na} pytanie{pytanie}.",
        "Put the question after the response verb.",
    ),
    translation(
        "Anna is answering the question.",
        "Anna{@name} odpowiada{odpowiadac} na{na} pytanie{pytanie}.",
        "Use the third-person response form.",
    ),
    translation(
        "Yesterday I was answering Marek.",
        [
            (
                "Wczoraj{wczoraj} odpowiadałem{odpowiadac} Markowi{@name}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} odpowiadałam{odpowiadac} Markowi{@name}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form and mark the recipient.",
    ),
)
R(
    "o",
    translation(
        "I am thinking about home.",
        "Myślę{myslec} o{o} domu{dom}.",
        "Introduce the topic after the thinking verb.",
    ),
    translation(
        "I have a question about work.",
        "Mam{miec} pytanie{pytanie} o{o} pracę{praca}.",
        "Put the question's topic last.",
    ),
    translation(
        "We are talking about the answer.",
        "Mówimy{mowic} o{o} odpowiedzi{odpowiedz}.",
        "Use the answer form required after ‘about’.",
    ),
)
R(
    "ze",
    translation(
        "Anna says that Marek is here.",
        "Anna{@name} mówi{mowic}, że{ze} Marek{@name} jest{byc} tutaj{tutaj}.",
        "Join the statement to its content.",
    ),
    translation(
        "We think that this is important.",
        "Myślimy{myslec}, że{ze} to{to} jest{byc} ważne{wazny}.",
        "Join the thought to its content.",
    ),
    translation(
        "Do you know that Anna is at home?",
        "Czy{czy} wiesz{wiedziec}, że{ze} Anna{@name} jest{byc} w{w} domu{dom}?",
        "Keep the clause connector inside the question.",
    ),
)

# Unit 7 review contexts.
R(
    "pracowac",
    translation(
        "Where do you work?", "Gdzie{gdzie} pracujesz{pracowac}?", "Ask for the work location."
    ),
    translation(
        "We work at home.", "Pracujemy{pracowac} w{w} domu{dom}.", "Use the plural present form."
    ),
    translation(
        "Yesterday I worked at home.",
        [
            (
                "Wczoraj{wczoraj} pracowałem{pracowac} w{w} domu{dom}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} pracowałam{pracowac} w{w} domu{dom}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "robic",
    translation(
        "Anna is doing something.",
        "Anna{@name} robi{robic} coś{cos}.",
        "Use the third-person ongoing form.",
    ),
    translation(
        "We often do this.",
        "Często{czesto} to{to} robimy{robic}.",
        "Put the object before the plural ongoing verb.",
    ),
    translation(
        "Yesterday I was doing it.",
        [
            ("Wczoraj{wczoraj} robiłem{robic} to{to}.", "masculine"),
            ("Wczoraj{wczoraj} robiłam{robic} to{to}.", "feminine"),
        ],
        "Use your selected past self-reference form for an ongoing action.",
    ),
)
R(
    "zrobic",
    translation(
        "Can you get it done?",
        "Możesz{moc} to{to} zrobić{zrobic}?",
        "Use the completed infinitive after the modal.",
    ),
    translation(
        "Anna got it done yesterday.",
        "Anna{@name} zrobiła{zrobic} to{to} wczoraj{wczoraj}.",
        "Use the feminine completed past form.",
    ),
    translation(
        "Yesterday I got it done.",
        [
            ("Wczoraj{wczoraj} zrobiłem{zrobic} to{to}.", "masculine"),
            ("Wczoraj{wczoraj} zrobiłam{zrobic} to{to}.", "feminine"),
        ],
        "Use your selected past self-reference form for a completed result.",
    ),
)
R(
    "uczyc_sie",
    translation(
        "What are you learning?",
        "Czego{co} się{uczyc_sie} uczysz{uczyc_sie}?",
        "Begin with the thing being learned and keep the companion word.",
    ),
    translation(
        "Anna is learning something new.",
        "Anna{@name} uczy{uczyc_sie} się{uczyc_sie} czegoś{cos} nowego{nowy}.",
        "Keep both parts of the verb before the thing learned.",
    ),
    translation(
        "Yesterday I studied at home.",
        [
            (
                "Wczoraj{wczoraj} uczyłem{uczyc_sie} się{uczyc_sie} w{w} domu{dom}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} uczyłam{uczyc_sie} się{uczyc_sie} w{w} domu{dom}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form and keep the companion word.",
    ),
)
R(
    "pamietac",
    translation("Do you remember?", "Pamiętasz{pamietac}?", "Use the second-person form."),
    translation(
        "Anna remembers the question.",
        "Anna{@name} pamięta{pamietac} pytanie{pytanie}.",
        "Use the third-person form before the object.",
    ),
    translation(
        "We always remember.",
        "Zawsze{zawsze} pamiętamy{pamietac}.",
        "Put the frequency word before the plural verb.",
    ),
)
R(
    "dzien",
    translation(
        "This is an important day.",
        "To{to} jest{byc} ważny{wazny} dzień{dzien}.",
        "Match the adjective to the masculine time noun.",
    ),
    translation(
        "I need a day.",
        "Potrzebuję{potrzebowac} dnia{dzien}.",
        "Use the form required after ‘need’.",
    ),
    translation(
        "This day is difficult.",
        "Ten{ten} dzień{dzien} jest{byc} trudny{trudny}.",
        "Use the base form as the subject.",
    ),
)
R(
    "rok",
    translation(
        "I need a year.",
        "Potrzebuję{potrzebowac} roku{rok}.",
        "Use the form required after ‘need’.",
    ),
    translation(
        "This year is important.",
        "Ten{ten} rok{rok} jest{byc} ważny{wazny}.",
        "Use the base form as the subject.",
    ),
    translation(
        "This year I am working at home.",
        "W{w} tym{ten} roku{rok} pracuję{pracowac} w{w} domu{dom}.",
        "Use matching forms after ‘in’.",
    ),
)
R(
    "wczoraj",
    translation(
        "Anna was studying at home yesterday.",
        "Anna{@name} wczoraj{wczoraj} uczyła{uczyc_sie} się{uczyc_sie} w{w} domu{dom}.",
        "Keep yesterday before the past activity.",
    ),
    translation(
        "Did Anna work yesterday?",
        "Czy{czy} Anna{@name} pracowała{pracowac} wczoraj{wczoraj}?",
        "Put yesterday at the end of the question.",
    ),
    translation(
        "Yesterday I was answering the question.",
        [
            (
                "Wczoraj{wczoraj} odpowiadałem{odpowiadac} na{na} pytanie{pytanie}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} odpowiadałam{odpowiadac} na{na} pytanie{pytanie}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "zawsze",
    translation(
        "Anna always knows the answer.",
        "Anna{@name} zawsze{zawsze} zna{znac} odpowiedź{odpowiedz}.",
        "Put the frequency word before the verb.",
    ),
    translation(
        "Are you always here?",
        "Czy{czy} zawsze{zawsze} jesteś{byc} tutaj{tutaj}?",
        "Put the frequency word before the verb.",
    ),
    translation(
        "We always wait for Anna.",
        "Zawsze{zawsze} czekamy{czekac} na{na} Annę{@name}.",
        "Lead with the frequency word.",
    ),
)
R(
    "czesto",
    translation(
        "We often work at home.",
        "Często{czesto} pracujemy{pracowac} w{w} domu{dom}.",
        "Lead with the frequency word.",
    ),
    translation(
        "Does Anna often ask about it?",
        "Czy{czy} Anna{@name} często{czesto} o{o} to{to} pyta{pytac}?",
        "Keep the frequency before the topic phrase and verb.",
    ),
    translation(
        "I often think about life.",
        "Często{czesto} myślę{myslec} o{o} życiu{zycie}.",
        "Lead with the frequency word and use the topic form.",
    ),
)

# Unit 8 review contexts.
R(
    "dac",
    translation(
        "Can you give me water?",
        "Możesz{moc} mi{ja} dać{dac} wodę{woda}?",
        "Put the short recipient before the giving verb.",
    ),
    translation(
        "Anna will give Marek the answer tomorrow.",
        "Anna{@name} jutro{jutro} da{dac} Markowi{@name} odpowiedź{odpowiedz}.",
        "Use the completed future form before the recipient and object.",
    ),
    translation(
        "Yesterday I gave it to Anna.",
        [
            ("Wczoraj{wczoraj} dałem{dac} to{to} Annie{@name}.", "masculine"),
            ("Wczoraj{wczoraj} dałam{dac} to{to} Annie{@name}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "brac",
    translation(
        "What are you taking?", "Co{co} bierzesz{brac}?", "Ask about the current taking action."
    ),
    translation(
        "We often take water to work.",
        "Często{czesto} bierzemy{brac} wodę{woda} do{do} pracy{praca}.",
        "Use the ongoing plural form for a repeated action.",
    ),
    translation(
        "Yesterday I was taking it home.",
        [
            (
                "Wczoraj{wczoraj} brałem{brac} to{to} do{do} domu{dom}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} brałam{brac} to{to} do{do} domu{dom}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form for the ongoing action.",
    ),
)
R(
    "wziac",
    translation(
        "Can you take the phone home?",
        "Możesz{moc} wziąć{wziac} telefon{telefon} do{do} domu{dom}?",
        "Use the completed infinitive with a destination.",
    ),
    translation(
        "Anna took the water yesterday.",
        "Anna{@name} wczoraj{wczoraj} wzięła{wziac} wodę{woda}.",
        "Put yesterday before the feminine completed past form.",
    ),
    translation(
        "Yesterday I took it home.",
        [
            (
                "Wczoraj{wczoraj} wziąłem{wziac} to{to} do{do} domu{dom}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} wzięłam{wziac} to{to} do{do} domu{dom}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form for one completed action.",
    ),
)
R(
    "i",
    translation(
        "Anna works and studies.",
        "Anna{@name} pracuje{pracowac} i{i} uczy{uczyc_sie} się{uczyc_sie}.",
        "Join the two activities.",
    ),
    translation(
        "Home and work are important.",
        "Dom{dom} i{i} praca{praca} są{byc} ważne{wazny}.",
        "Join the two subjects before the plural verb.",
    ),
    translation(
        "Water and food are here.",
        "Woda{woda} i{i} jedzenie{jedzenie} są{byc} tutaj{tutaj}.",
        "Join the two subjects before the plural verb.",
    ),
)
R(
    "ale",
    translation(
        "I know, but I do not understand.",
        "Wiem{wiedziec}, ale{ale} nie{nie} rozumiem{rozumiec}.",
        "Connect the knowledge to the contrasting lack of understanding.",
    ),
    translation(
        "Anna wants to walk, but she has no time.",
        "Anna{@name} chce{chciec} iść{isc}, ale{ale} nie{nie} ma{miec} czasu{czas}.",
        "Put the contrasting problem after the connector.",
    ),
    translation(
        "The problem is difficult but important.",
        "Problem{problem} jest{byc} trudny{trudny}, ale{ale} ważny{wazny}.",
        "Join the two contrasting descriptions.",
    ),
)
R(
    "albo",
    translation(
        "Water or food?",
        "Woda{woda} albo{albo} jedzenie{jedzenie}?",
        "Offer the two things as alternatives.",
    ),
    translation(
        "We can wait here or head home.",
        "Możemy{moc} czekać{czekac} tutaj{tutaj} albo{albo} pójść{pojsc} do{do} domu{dom}.",
        "Join the two possible actions.",
    ),
    translation(
        "A new phone or a new house?",
        "Nowy{nowy} telefon{telefon} albo{albo} nowy{nowy} dom{dom}?",
        "Join the two masculine alternatives.",
    ),
)
R(
    "bo",
    translation(
        "I know because Anna said it.",
        "Wiem{wiedziec}, bo{bo} Anna{@name} to{to} powiedziała{powiedziec}.",
        "Put the reason after the known fact.",
    ),
    translation(
        "I am looking for the phone because I need it.",
        "Szukam{szukac} telefonu{telefon}, bo{bo} go{on} potrzebuję{potrzebowac}.",
        "Connect the search to its reason.",
    ),
    translation(
        "Anna is asking because she does not know the answer.",
        "Anna{@name} pyta{pytac}, bo{bo} nie{nie} zna{znac} odpowiedzi{odpowiedz}.",
        "Put the reason after the question action.",
    ),
)
R(
    "tez",
    translation(
        "Anna also works.", "Anna{@name} też{tez} pracuje{pracowac}.", "Put ‘also’ before the verb."
    ),
    translation(
        "I also need help.",
        "Też{tez} potrzebuję{potrzebowac} pomocy{pomoc}.",
        "Lead with ‘also’ before the need.",
    ),
    translation(
        "We are walking too.",
        "My{my} też{tez} idziemy{isc}.",
        "Keep the group pronoun because the group is being added.",
    ),
)
R(
    "tylko",
    translation(
        "I have only a day.",
        "Mam{miec} tylko{tylko} dzień{dzien}.",
        "Put the restriction before the available time.",
    ),
    translation(
        "We need only water.",
        "Potrzebujemy{potrzebowac} tylko{tylko} wody{woda}.",
        "Put the restriction before the needed thing.",
    ),
    translation(
        "Anna works only at home.",
        "Anna{@name} pracuje{pracowac} tylko{tylko} w{w} domu{dom}.",
        "Put the restriction before the location.",
    ),
)
R(
    "od",
    translation(
        "I have been working since yesterday.",
        "Pracuję{pracowac} od{od} wczoraj{wczoraj}.",
        "Use the present tense with the starting point.",
    ),
    translation(
        "I have been here for a year.",
        "Jestem{byc} tutaj{tutaj} od{od} roku{rok}.",
        "Use the present tense with the one-year starting span.",
    ),
    translation(
        "I have an answer from Anna.",
        "Mam{miec} odpowiedź{odpowiedz} od{od} Anny{@name}.",
        "Put the source person last.",
    ),
)

# Unit 9 review contexts.
R(
    "problem",
    translation(
        "I do not have a problem.",
        "Nie{nie} mam{miec} problemu{problem}.",
        "Negation changes the object form.",
    ),
    translation(
        "I am thinking about the problem.",
        "Myślę{myslec} o{o} problemie{problem}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "We are looking for a way because we have a problem.",
        "Szukamy{szukac} sposobu{sposob}, bo{bo} mamy{miec} problem{problem}.",
        "Put the problem in the reason clause.",
    ),
)
R(
    "pytanie",
    translation(
        "I am answering the question.",
        "Odpowiadam{odpowiadac} na{na} pytanie{pytanie}.",
        "Put the question after the response verb.",
    ),
    translation(
        "I am thinking about the question.",
        "Myślę{myslec} o{o} pytaniu{pytanie}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "I do not have a question.",
        "Nie{nie} mam{miec} pytania{pytanie}.",
        "Negation changes the object form.",
    ),
)
R(
    "odpowiedz",
    translation(
        "We are looking for the answer.",
        "Szukamy{szukac} odpowiedzi{odpowiedz}.",
        "Use the form required after ‘look for’.",
    ),
    translation(
        "We are talking about the answer.",
        "Mówimy{mowic} o{o} odpowiedzi{odpowiedz}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "I have to give Anna the answer.",
        "Muszę{musiec} dać{dac} Annie{@name} odpowiedź{odpowiedz}.",
        "Mark the recipient before the direct object.",
    ),
)
R(
    "sposob",
    translation(
        "We can do it this way.",
        "W{w} ten{ten} sposób{sposob} możemy{moc} to{to} zrobić{zrobic}.",
        "Lead with the manner phrase.",
    ),
    translation(
        "I am thinking about a way.",
        "Myślę{myslec} o{o} sposobie{sposob}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "I do not know a good way.",
        "Nie{nie} znam{znac} dobrego{dobry} sposobu{sposob}.",
        "Use the changed forms after the negative verb.",
    ),
)
R(
    "szukac",
    translation(
        "I am looking for the phone.",
        "Szukam{szukac} telefonu{telefon}.",
        "Use the form required after ‘look for’.",
    ),
    translation(
        "Anna is looking for a new job.",
        "Anna{@name} szuka{szukac} nowej{nowy} pracy{praca}.",
        "Match both words after the searching verb.",
    ),
    translation(
        "Yesterday I was looking for the answer.",
        [
            (
                "Wczoraj{wczoraj} szukałem{szukac} odpowiedzi{odpowiedz}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} szukałam{szukac} odpowiedzi{odpowiedz}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "znalezc",
    translation(
        "Can you find the phone?",
        "Możesz{moc} znaleźć{znalezc} telefon{telefon}?",
        "Use the completed finding infinitive.",
    ),
    translation(
        "Anna found the answer yesterday.",
        "Anna{@name} wczoraj{wczoraj} znalazła{znalezc} odpowiedź{odpowiedz}.",
        "Use the feminine completed past form.",
    ),
    translation(
        "Yesterday I found a way.",
        [
            (
                "Wczoraj{wczoraj} znalazłem{znalezc} sposób{sposob}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} znalazłam{znalezc} sposób{sposob}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form for the completed result.",
    ),
)
R(
    "widziec",
    translation(
        "Do you see Anna?",
        "Widzisz{widziec} Annę{@name}?",
        "Use the second-person verb before the object.",
    ),
    translation(
        "We see a big house.",
        "Widzimy{widziec} duży{duzy} dom{dom}.",
        "Use the plural verb before the masculine object.",
    ),
    translation(
        "Yesterday I saw the problem.",
        [
            (
                "Wczoraj{wczoraj} widziałem{widziec} problem{problem}.",
                "masculine",
            ),
            (
                "Wczoraj{wczoraj} widziałam{widziec} problem{problem}.",
                "feminine",
            ),
        ],
        "Use your selected past self-reference form.",
    ),
)
R(
    "wazny",
    translation(
        "This answer is important.",
        "Ta{ten} odpowiedź{odpowiedz} jest{byc} ważna{wazny}.",
        "Match the adjective to the feminine noun.",
    ),
    translation(
        "Life is very important.",
        "Życie{zycie} jest{byc} bardzo{bardzo} ważne{wazny}.",
        "Match the adjective to the neuter noun.",
    ),
    translation(
        "We are talking about an important problem.",
        "Mówimy{mowic} o{o} ważnym{wazny} problemie{problem}.",
        "Match both words after ‘about’.",
    ),
)
R(
    "latwy",
    translation(
        "This work is easy.",
        "Ta{ten} praca{praca} jest{byc} łatwa{latwy}.",
        "Match the adjective to the feminine noun.",
    ),
    translation(
        "Life is not easy.",
        "Życie{zycie} nie{nie} jest{byc} łatwe{latwy}.",
        "Match the adjective to the neuter noun.",
    ),
    translation(
        "We are looking for an easy way.",
        "Szukamy{szukac} łatwego{latwy} sposobu{sposob}.",
        "Match both words after ‘look for’.",
    ),
)
R(
    "trudny",
    translation(
        "This is a difficult question.",
        "To{to} jest{byc} trudne{trudny} pytanie{pytanie}.",
        "Match the adjective to the neuter noun.",
    ),
    translation(
        "This answer is difficult.",
        "Ta{ten} odpowiedź{odpowiedz} jest{byc} trudna{trudny}.",
        "Match the adjective to the feminine noun.",
    ),
    translation(
        "We are talking about a difficult problem.",
        "Mówimy{mowic} o{o} trudnym{trudny} problemie{problem}.",
        "Match both words after ‘about’.",
    ),
)

# Unit 10 review contexts.
R(
    "woda",
    translation(
        "I have to give you water.",
        "Muszę{musiec} ci{ty} dać{dac} wodę{woda}.",
        "Put the short recipient before the giving verb.",
    ),
    translation(
        "We do not have water.",
        "Nie{nie} mamy{miec} wody{woda}.",
        "Negation changes the object form.",
    ),
    translation(
        "We are talking about water.",
        "Mówimy{mowic} o{o} wodzie{woda}.",
        "Use the form required after ‘about’.",
    ),
)
R(
    "jedzenie",
    translation(
        "We do not have food.",
        "Nie{nie} mamy{miec} jedzenia{jedzenie}.",
        "Negation changes the object form.",
    ),
    translation(
        "I am thinking about food.",
        "Myślę{myslec} o{o} jedzeniu{jedzenie}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "I have to give the child food.",
        "Muszę{musiec} dać{dac} dziecku{dziecko} jedzenie{jedzenie}.",
        "Mark the recipient before the direct object.",
    ),
)
R(
    "telefon",
    translation(
        "I have a problem with the phone.",
        "Mam{miec} problem{problem} z{z} telefonem{telefon}.",
        "Use the form required after ‘with’.",
    ),
    translation(
        "I have to give Anna the phone.",
        "Muszę{musiec} dać{dac} Annie{@name} telefon{telefon}.",
        "Mark the recipient before the direct object.",
    ),
    translation(
        "I am thinking about a new phone.",
        "Myślę{myslec} o{o} nowym{nowy} telefonie{telefon}.",
        "Match both words after ‘about’.",
    ),
)
R(
    "zycie",
    translation(
        "I often think about life.",
        "Często{czesto} myślę{myslec} o{o} życiu{zycie}.",
        "Use the form required after ‘about’.",
    ),
    translation(
        "Life is very important.",
        "Życie{zycie} jest{byc} bardzo{bardzo} ważne{wazny}.",
        "Use the base noun form as the subject.",
    ),
    translation(
        "We are looking for a way to a good life.",
        "Szukamy{szukac} sposobu{sposob} na{na} dobre{dobry} życie{zycie}.",
        "Put the intended result after the way.",
    ),
)
R(
    "maly",
    translation(
        "This is a small question.",
        "To{to} jest{byc} małe{maly} pytanie{pytanie}.",
        "Match the adjective to the neuter noun.",
    ),
    translation(
        "I have a small thing.",
        "Mam{miec} małą{maly} rzecz{rzecz}.",
        "Match the adjective to the feminine object.",
    ),
    translation(
        "We are talking about a small problem.",
        "Mówimy{mowic} o{o} małym{maly} problemie{problem}.",
        "Match both words after ‘about’.",
    ),
)
R(
    "nowy",
    translation(
        "This is a new answer.",
        "To{to} jest{byc} nowa{nowy} odpowiedź{odpowiedz}.",
        "Match the adjective to the feminine noun.",
    ),
    translation(
        "We need a new place.",
        "Potrzebujemy{potrzebowac} nowego{nowy} miejsca{miejsce}.",
        "Match both words after ‘need’.",
    ),
    translation(
        "We are talking about a new phone.",
        "Mówimy{mowic} o{o} nowym{nowy} telefonie{telefon}.",
        "Match both words after ‘about’.",
    ),
)
R(
    "zly",
    translation(
        "This is a bad day.",
        "To{to} jest{byc} zły{zly} dzień{dzien}.",
        "Use the description that fits dzień.",
    ),
    translation(
        "This is bad food.",
        "To{to} jest{byc} złe{zly} jedzenie{jedzenie}.",
        "Match the adjective to the neuter noun.",
    ),
    translation(
        "We are talking about a bad answer.",
        "Mówimy{mowic} o{o} złej{zly} odpowiedzi{odpowiedz}.",
        "Match both words after ‘about’.",
    ),
)
R(
    "jesli",
    translation(
        "If we do not have time, we return home.",
        "Jeśli{jesli} nie{nie} mamy{miec} czasu{czas}, wracamy{wracac} do{do} domu{dom}.",
        "State the condition before its result.",
    ),
    translation(
        "If Anna knows the answer, she can say so.",
        "Jeśli{jesli} Anna{@name} zna{znac} odpowiedź{odpowiedz}, może{moc} to{to} powiedzieć{powiedziec}.",
        "State the condition before the available action.",
    ),
    translation(
        "I am here if you need help.",
        "Jestem{byc} tutaj{tutaj}, jeśli{jesli} potrzebujesz{potrzebowac} pomocy{pomoc}.",
        "Put the condition after the main reassurance.",
    ),
)
R(
    "wiec",
    translation(
        "I do not know the answer, so I am asking.",
        "Nie{nie} znam{znac} odpowiedzi{odpowiedz}, więc{wiec} pytam{pytac}.",
        "Put the resulting action after the connector.",
    ),
    translation(
        "I have a problem with the phone, so I am looking for help.",
        "Mam{miec} problem{problem} z{z} telefonem{telefon}, więc{wiec} szukam{szukac} pomocy{pomoc}.",
        "Put the response to the problem after the connector.",
    ),
    translation(
        "Anna is at home, so I am walking there.",
        "Anna{@name} jest{byc} w{w} domu{dom}, więc{wiec} idę{isc} tam{tam}.",
        "Put the resulting motion after the connector.",
    ),
)
R(
    "bardzo",
    translation(
        "This is a very good answer.",
        "To{to} jest{byc} bardzo{bardzo} dobra{dobry} odpowiedź{odpowiedz}.",
        "Put the intensifier before the adjective.",
    ),
    translation(
        "I really need help.",
        "Bardzo{bardzo} potrzebuję{potrzebowac} pomocy{pomoc}.",
        "Lead with the intensifier before the need.",
    ),
    translation(
        "We work at home very often.",
        "Bardzo{bardzo} często{czesto} pracujemy{pracowac} w{w} domu{dom}.",
        "Combine the intensifier with the frequency word.",
    ),
)

# Two synthesis objectives per unit combine only material already introduced.
S(
    "modal_negation",
    1,
    model("I cannot have it.", "Nie{nie} mogę{moc} tego{to} mieć{miec}."),
    cloze(
        "Nie{nie} ____ tego{to} mieć{miec}.",
        "I cannot have it.",
        "mogę{moc}",
        "Use the first-person modal after negation.",
    ),
    cloze(
        "Chcę{chciec} ____ tutaj{tutaj}.",
        "I want to be here.",
        "być{byc}",
        "Use the infinitive after ‘want’.",
    ),
    translation(
        "I don't want it.",
        "Nie{nie} chcę{chciec} tego{to}.",
        "Negate the verb and use the object form.",
    ),
    translation(
        "Can you be here?",
        "Możesz{moc} być{byc} tutaj{tutaj}?",
        "Begin with the second-person modal.",
    ),
)
S(
    "person_contrast",
    1,
    model("You can. I cannot.", "Ty{ty} możesz{moc}. Ja{ja} nie{nie} mogę{moc}."),
    cloze(
        "Ty{ty} _____. Ja{ja} nie{nie} mogę{moc}.",
        "You can. I cannot.",
        "możesz{moc}",
        "Match the first sentence to ‘you’.",
    ),
    cloze(
        "Ja{ja} jestem{byc} tutaj{tutaj}. Ty{ty} ____ tutaj{tutaj}.",
        "I am here. You are here.",
        "jesteś{byc}",
        "Match the second sentence to ‘you’.",
    ),
    translation(
        "I have it. You don't.",
        "Ja{ja} mam{miec} to{to}. Ty{ty} nie{nie} masz{miec}.",
        "Contrast the two people explicitly.",
    ),
    translation(
        "I want to be here.",
        "Chcę{chciec} być{byc} tutaj{tutaj}.",
        "Use two verbs without the subject pronoun.",
    ),
)
S(
    "agreement",
    2,
    model(
        "This person is good. This thing is big.",
        "Ten{ten} człowiek{czlowiek} jest{byc} dobry{dobry}. Ta{ten} rzecz{rzecz} jest{byc} duża{duzy}.",
    ),
    cloze(
        "Ten{ten} człowiek{czlowiek} jest{byc} ____.",
        "This person is good.",
        "dobry{dobry}",
        "Match the description to the masculine noun.",
    ),
    cloze(
        "Ta{ten} rzecz{rzecz} jest{byc} ____.",
        "This thing is big.",
        "duża{duzy}",
        "Match the description to the feminine noun.",
    ),
    translation(
        "This child is big.",
        "To{ten} dziecko{dziecko} jest{byc} duże{duzy}.",
        "Use the neuter description.",
    ),
    translation(
        "This is a good thing.",
        "To{to} jest{byc} dobra{dobry} rzecz{rzecz}.",
        "Match the description to the feminine noun.",
    ),
)
S(
    "people_and_things",
    2,
    model(
        "A human being can be good. This individual is here.",
        "Człowiek{czlowiek} może{moc} być{byc} dobry{dobry}. Ta{ten} osoba{osoba} jest{byc} tutaj{tutaj}.",
    ),
    cloze(
        "____ może{moc} być{byc} dobry{dobry}.",
        "A human being can be good — humanity is the point.",
        "Człowiek{czlowiek}",
        "Use the word for a human being or people in general.",
    ),
    cloze(
        "Ta{ten} ____ jest{byc} tutaj{tutaj}.",
        "This individual is here — a neutral reference to one person.",
        "osoba{osoba}",
        "Use the neutral word for an identified individual.",
    ),
    translation(
        "We are good people.",
        "Jesteśmy{byc} dobrymi{dobry} ludźmi{czlowiek}.",
        "Use the people form of człowiek and match the adjective to it.",
    ),
    translation(
        "This particular individual wants this thing.",
        "Ta{ten} osoba{osoba} chce{chciec} tej{ten} rzeczy{rzecz}.",
        "Use osoba for the individual and genitive forms after ‘want’.",
    ),
)
S(
    "need_and_absence",
    3,
    model(
        "I have no time. I have no money.",
        "Nie{nie} mam{miec} czasu{czas}. Nie{nie} mam{miec} pieniędzy{pieniadze}.",
    ),
    cloze(
        "Potrzebuję{potrzebowac} ____.",
        "I need help.",
        "pomocy{pomoc}",
        "Use the required form after ‘need’.",
    ),
    cloze(
        "Nie{nie} mam{miec} ____.",
        "I have no money.",
        "pieniędzy{pieniadze}",
        "Use the negative object form.",
    ),
    translation(
        "I need something for this person.",
        [
            (
                "Potrzebuję{potrzebowac} czegoś{cos} dla{dla} tej{ten} osoby{osoba}.",
                "any",
            ),
            (
                "Potrzebuję{potrzebowac} czegoś{cos} dla{dla} tego{ten} człowieka{czlowiek}.",
                "any",
            ),
        ],
        "Either person noun works; match its form after ‘for’.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
    translation(
        "I cannot be without help.",
        "Nie{nie} mogę{moc} być{byc} bez{bez} pomocy{pomoc}.",
        "Keep the modal pattern before the absence phrase.",
    ),
)
S(
    "need_questions",
    3,
    model("Who needs help?", "Kto{kto} potrzebuje{potrzebowac} pomocy{pomoc}?"),
    cloze(
        "____ potrzebuje{potrzebowac} pomocy{pomoc}?",
        "Who needs help?",
        "Kto{kto}",
        "Ask about a person.",
    ),
    cloze("Co{co} ____?", "What do you need?", "potrzebujesz{potrzebowac}", "Address one person."),
    translation(
        "What does this person need?",
        [
            ("Czego{co} potrzebuje{potrzebowac} ta{ten} osoba{osoba}?", "any"),
            ("Czego{co} potrzebuje{potrzebowac} ten{ten} człowiek{czlowiek}?", "any"),
        ],
        "Begin with the form of ‘what’ used by ‘need’; either person noun works.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
    translation(
        "Who has no time?",
        "Kto{kto} nie{nie} ma{miec} czasu{czas}?",
        "Ask about the person, then negate possession.",
    ),
)
S(
    "location_exchange",
    4,
    model("Where are you? I am at home.", "Gdzie{gdzie} jesteś{byc}? Jestem{byc} w{w} domu{dom}."),
    cloze(
        "Gdzie{gdzie} jesteś{byc}? Jestem{byc} ____ domu{dom}.",
        "Where are you? I am at home.",
        "w{w}",
        "Use the home-location preposition.",
    ),
    cloze(
        "Anna{@name} jest{byc} ____ pracy{praca}.",
        "Anna is at work.",
        "w{w}",
        "Use the location form.",
    ),
    translation(
        "Where is that place?",
        "Gdzie{gdzie} jest{byc} to{ten} miejsce{miejsce}?",
        "Ask for the location of the place.",
    ),
    translation(
        "I am there with Anna.",
        "Jestem{byc} tam{tam} z{z} Anną{@name}.",
        "Put the distant location before the companion phrase.",
    ),
)
S(
    "preposition_contrast",
    4,
    model(
        "This is from work. This is for work.",
        "To{to} jest{byc} z{z} pracy{praca}. To{to} jest{byc} do{do} pracy{praca}.",
    ),
    cloze(
        "To{to} jest{byc} ____ pracy{praca}.", "This comes from work.", "z{z}", "Mark the source."
    ),
    cloze(
        "To{to} jest{byc} ____ pracy{praca}.",
        "This is intended for work.",
        "do{do}",
        "Mark the purpose.",
    ),
    translation(
        "I need this for work.",
        "Potrzebuję{potrzebowac} tego{to} do{do} pracy{praca}.",
        "Use the purpose phrase after what is needed.",
    ),
    translation(
        "I am at work with Anna.",
        "Jestem{byc} w{w} pracy{praca} z{z} Anną{@name}.",
        "Combine location and companionship.",
    ),
)
S(
    "motion_choice",
    5,
    model(
        "I am walking home. Anna is travelling to work by vehicle.",
        "Idę{isc} do{do} domu{dom}. Anna{@name} jedzie{jechac} do{do} pracy{praca}.",
    ),
    cloze(
        "____ do{do} domu{dom}.",
        "I am walking home.",
        "Idę{isc}",
        "Choose the on-foot motion form.",
    ),
    cloze(
        "Anna{@name} ____ do{do} pracy{praca}.",
        "Anna is travelling to work by vehicle.",
        "jedzie{jechac}",
        "Choose the vehicle-motion form.",
    ),
    translation(
        "Today we are travelling home by vehicle.",
        "Dziś{dzis} jedziemy{jechac} do{do} domu{dom}.",
        "Use the plural vehicle-motion form.",
    ),
    translation(
        "Tomorrow we can head there on foot.",
        "Jutro{jutro} możemy{moc} tam{tam} pójść{pojsc}.",
        "Place the destination before the final infinitive.",
    ),
)
S(
    "short_time",
    5,
    model(
        "I am still waiting. Anna is already returning.",
        "Jeszcze{jeszcze} czekam{czekac}. Anna{@name} już{juz} wraca{wracac}.",
    ),
    cloze(
        "____ czekam{czekac}.", "I am still waiting.", "Jeszcze{jeszcze}", "The action continues."
    ),
    cloze(
        "Anna{@name} ____ wraca{wracac}.",
        "Anna is already returning.",
        "już{juz}",
        "The action has begun by now.",
    ),
    translation(
        "I am still waiting here.",
        "Jeszcze{jeszcze} czekam{czekac} tutaj{tutaj}.",
        "Lead with the continuing-state word.",
    ),
    translation(
        "Tomorrow I am walking home. Today I am still at work.",
        "Jutro{jutro} idę{isc} do{do} domu{dom}. Dziś{dzis} jeszcze{jeszcze} jestem{byc} w{w} pracy{praca}.",
        "Contrast the two days in separate sentences.",
    ),
)
S(
    "know_fact_person",
    6,
    model(
        "I know Anna. I know where she is.",
        "Znam{znac} Annę{@name}. Wiem{wiedziec}, gdzie{gdzie} ona{ona} jest{byc}.",
    ),
    cloze(
        "____ Annę{@name}.",
        "I know Anna personally.",
        "Znam{znac}",
        "Use familiarity rather than fact knowledge.",
    ),
    cloze(
        "____, gdzie{gdzie} ona{ona} jest{byc}.",
        "I know where she is.",
        "Wiem{wiedziec}",
        "Use fact knowledge.",
    ),
    translation(
        "I know this person. I don't know where this person is.",
        [
            (
                "Znam{znac} tego{ten} człowieka{czlowiek}. Nie{nie} wiem{wiedziec}, gdzie{gdzie} on{on} jest{byc}.",
                "any",
            ),
            (
                "Znam{znac} tę{ten} osobę{osoba}. Nie{nie} wiem{wiedziec}, gdzie{gdzie} ona{ona} jest{byc}.",
                "any",
            ),
        ],
        "Use different knowing verbs for a person and a fact; either person noun works.",
        context="Neutral context: both learned words for ‘person’ are natural.",
    ),
    translation(
        "Do you understand what I am saying?",
        "Rozumiesz{rozumiec}, co{co} mówię{mowic}?",
        "Put the content question after the main verb.",
    ),
)
S(
    "embedded_clause",
    6,
    model("I think that Anna knows.", "Myślę{myslec}, że{ze} Anna{@name} wie{wiedziec}."),
    cloze(
        "Myślę{myslec}, ____ Anna{@name} wie{wiedziec}.",
        "I think that Anna knows.",
        "że{ze}",
        "Introduce stated content.",
    ),
    cloze(
        "Nie{nie} wiem{wiedziec}, ____ Marek{@name} rozumie{rozumiec}.",
        "I don't know whether Marek understands.",
        "czy{czy}",
        "Introduce uncertainty.",
    ),
    translation(
        "I don't know whether Anna understands.",
        "Nie{nie} wiem{wiedziec}, czy{czy} Anna{@name} rozumie{rozumiec}.",
        "Join negated knowledge to an uncertain fact.",
    ),
    translation(
        "We say that Anna knows.",
        "Mówimy{mowic}, że{ze} Anna{@name} wie{wiedziec}.",
        "Put Anna's knowledge in the second clause.",
    ),
)
S(
    "doing_aspect",
    7,
    model(
        "I am doing it now. Tomorrow I want to get it done.",
        "Robię{robic} to{to} teraz{teraz}. Jutro{jutro} chcę{chciec} to{to} zrobić{zrobic}.",
    ),
    cloze(
        "____ to{to} teraz{teraz}.", "I am doing it now.", "Robię{robic}", "Use the ongoing form."
    ),
    cloze(
        "Jutro{jutro} chcę{chciec} to{to} ____.",
        "Tomorrow I want to get it done.",
        "zrobić{zrobic}",
        "Use the completed infinitive.",
    ),
    translation(
        "Yesterday I got it done.",
        [
            ("Wczoraj{wczoraj} zrobiłem{zrobic} to{to}.", "masculine"),
            ("Wczoraj{wczoraj} zrobiłam{zrobic} to{to}.", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
    translation(
        "Anna often does this.",
        "Anna{@name} często{czesto} to{to} robi{robic}.",
        "Put the object before the ongoing verb.",
    ),
)
S(
    "past_routine",
    7,
    model(
        "Anna worked yesterday. Marek worked yesterday.",
        "Anna{@name} pracowała{pracowac} wczoraj{wczoraj}. Marek{@name} pracował{pracowac} wczoraj{wczoraj}.",
    ),
    cloze(
        "Wczoraj{wczoraj} ____ w{w} domu{dom}.",
        "I worked at home yesterday.",
        [
            ("pracowałem{pracowac}", "masculine"),
            ("pracowałam{pracowac}", "feminine"),
        ],
        "Use your selected past self-reference form.",
    ),
    cloze(
        "Anna{@name} zawsze{zawsze} ____ to{to}.",
        "Anna always remembers it.",
        "pamięta{pamietac}",
        "Use the third-person routine form.",
    ),
    translation(
        "I was studying yesterday.",
        [
            ("Wczoraj{wczoraj} uczyłem{uczyc_sie} się{uczyc_sie}.", "masculine"),
            ("Wczoraj{wczoraj} uczyłam{uczyc_sie} się{uczyc_sie}.", "feminine"),
        ],
        "Use your selected past self-reference form and keep the companion word.",
    ),
    translation(
        "We have been working here for a year.",
        "Pracujemy{pracowac} tutaj{tutaj} rok{rok}.",
        "Use the present plural form with a bare duration.",
    ),
)
S(
    "connected_reason",
    8,
    model(
        "I want to walk, but I am waiting because Anna is working.",
        "Chcę{chciec} iść{isc}, ale{ale} czekam{czekac}, bo{bo} Anna{@name} pracuje{pracowac}.",
    ),
    cloze(
        "Chcę{chciec} iść{isc}, ____ czekam{czekac}.",
        "I want to go, but I am waiting.",
        "ale{ale}",
        "Introduce contrast.",
    ),
    cloze(
        "Czekam{czekac}, ____ Anna{@name} pracuje{pracowac}.",
        "I am waiting because Anna is working.",
        "bo{bo}",
        "Introduce the reason.",
    ),
    translation(
        "Anna and Marek are here, but only Anna is working.",
        "Anna{@name} i{i} Marek{@name} są{byc} tutaj{tutaj}, ale{ale} tylko{tylko} Anna{@name} pracuje{pracowac}.",
        "Join the people, then contrast who works.",
    ),
    translation(
        "We are returning home because we have to work tomorrow.",
        "Wracamy{wracac} do{do} domu{dom}, bo{bo} jutro{jutro} musimy{musiec} pracować{pracowac}.",
        "Place the reason after the main action.",
    ),
)
S(
    "give_or_take",
    8,
    model(
        "Anna wants to give Marek this thing.",
        "Anna{@name} chce{chciec} dać{dac} tę{ten} rzecz{rzecz} Markowi{@name}.",
    ),
    cloze(
        "Anna{@name} chce{chciec} ____ tę{ten} rzecz{rzecz} Markowi{@name}.",
        "Anna wants to give Marek this thing.",
        "dać{dac}",
        "Use the completed giving infinitive.",
    ),
    cloze(
        "Marek{@name} chce{chciec} ____ tę{ten} rzecz{rzecz} do{do} domu{dom}.",
        "Marek wants to take this thing home.",
        "wziąć{wziac}",
        "Use the completed taking infinitive.",
    ),
    translation(
        "We can give this thing to Anna or take it home.",
        "Możemy{moc} dać{dac} tę{ten} rzecz{rzecz} Annie{@name} albo{albo} wziąć{wziac} ją{ona} do{do} domu{dom}.",
        "Keep the same object across the two alternatives.",
    ),
    translation(
        "This is from you, but it is for Anna.",
        "To{to} jest{byc} od{od} ciebie{ty}, ale{ale} dla{dla} Anny{@name}.",
        "Contrast the source and recipient.",
    ),
)
S(
    "solve_problem",
    9,
    model(
        "I am looking for the answer because I have a problem.",
        "Szukam{szukac} odpowiedzi{odpowiedz}, bo{bo} mam{miec} problem{problem}.",
    ),
    cloze(
        "____ odpowiedzi{odpowiedz}, bo{bo} mam{miec} problem{problem}.",
        "I am looking for the answer because I have a problem.",
        "Szukam{szukac}",
        "Use the first-person searching form.",
    ),
    cloze(
        "Muszę{musiec} ____ dobry{dobry} sposób{sposob}.",
        "I have to find a good way.",
        "znaleźć{znalezc}",
        "Use the completed infinitive.",
    ),
    translation(
        "We need to find a good way.",
        "Musimy{musiec} znaleźć{znalezc} dobry{dobry} sposób{sposob}.",
        "Use the plural modal before the completed infinitive.",
    ),
    translation(
        "Do you see the problem?",
        "Czy{czy} widzisz{widziec} problem{problem}?",
        "Open the yes/no question, then use the second-person verb.",
    ),
)
S(
    "evaluate_answer",
    9,
    model(
        "This is an important question, but the answer is difficult.",
        "To{to} jest{byc} ważne{wazny} pytanie{pytanie}, ale{ale} odpowiedź{odpowiedz} jest{byc} trudna{trudny}.",
    ),
    cloze(
        "To{to} jest{byc} ____ pytanie{pytanie}.",
        "This is an important question.",
        "ważne{wazny}",
        "Match the neuter noun.",
    ),
    cloze(
        "Odpowiedź{odpowiedz} jest{byc} ____.",
        "The answer is difficult.",
        "trudna{trudny}",
        "Match the feminine noun.",
    ),
    translation(
        "The problem is difficult, but the answer is easy.",
        "Problem{problem} jest{byc} trudny{trudny}, ale{ale} odpowiedź{odpowiedz} jest{byc} łatwa{latwy}.",
        "Contrast the masculine and feminine descriptions.",
    ),
    translation(
        "This question is good and important.",
        "To{ten} pytanie{pytanie} jest{byc} dobre{dobry} i{i} ważne{wazny}.",
        "Match both descriptions to the neuter noun.",
    ),
)
S(
    "condition_result",
    10,
    model(
        "If I have time, I walk there. If not, I wait.",
        "Jeśli{jesli} mam{miec} czas{czas}, idę{isc} tam{tam}. Jeśli{jesli} nie{nie}, czekam{czekac}.",
    ),
    cloze(
        "____ mam{miec} czas{czas}, idę{isc} tam{tam}.",
        "If I have time, I go there.",
        "Jeśli{jesli}",
        "Introduce the condition.",
    ),
    cloze(
        "Nie{nie} mam{miec} czasu{czas}, ____ czekam{czekac}.",
        "I do not have time, so I wait.",
        "więc{wiec}",
        "Introduce the consequence.",
    ),
    translation(
        "If the problem is difficult, we look for a new way.",
        "Jeśli{jesli} problem{problem} jest{byc} trudny{trudny}, szukamy{szukac} nowego{nowy} sposobu{sposob}.",
        "State the condition before the plural response.",
    ),
    translation(
        "We have water and food, so we can wait.",
        "Mamy{miec} wodę{woda} i{i} jedzenie{jedzenie}, więc{wiec} możemy{moc} czekać{czekac}.",
        "Connect what is available to the result.",
    ),
)
S(
    "final_mix",
    10,
    model(
        "Life is difficult, but very important.",
        "Życie{zycie} jest{byc} trudne{trudny}, ale{ale} bardzo{bardzo} ważne{wazny}.",
    ),
    cloze(
        "Życie{zycie} jest{byc} trudne{trudny}, ale{ale} ____ ważne{wazny}.",
        "Life is difficult, but very important.",
        "bardzo{bardzo}",
        "Intensify the second description.",
    ),
    cloze(
        "Potrzebuję{potrzebowac} ____ telefonu{telefon}.",
        "I need a new phone.",
        "nowego{nowy}",
        "Match the form required after ‘need’.",
    ),
    translation(
        "I need a new phone, but I don't have money.",
        "Potrzebuję{potrzebowac} nowego{nowy} telefonu{telefon}, ale{ale} nie{nie} mam{miec} pieniędzy{pieniadze}.",
        "Contrast the need with the missing resource.",
    ),
    translation(
        "If this way is bad, we can find a new way.",
        "Jeśli{jesli} ten{ten} sposób{sposob} jest{byc} zły{zly}, możemy{moc} znaleźć{znalezc} nowy{nowy} sposób{sposob}.",
        "State the condition before the available solution.",
    ),
)


UNITS = [
    (1, "Intentions and ability"),
    (2, "People and possession"),
    (3, "Needs and negation"),
    (4, "Home, work, and location"),
    (5, "Movement and plans"),
    (6, "Knowledge and communication"),
    (7, "Time and routine"),
    (8, "Giving and relations"),
    (9, "Problems and completion"),
    (10, "Connected everyday Polish"),
]

UNIT_CONCEPT_ORDER = [
    ["tak", "nie", "to", "ja", "ty", "byc", "tutaj", "miec", "chciec", "moc"],
    ["on", "ona", "my", "czlowiek", "dziecko", "ten", "rzecz", "osoba", "dobry", "duzy"],
    ["czas", "pieniadze", "pomoc", "musiec", "potrzebowac", "cos", "kto", "co", "bez", "dla"],
    ["dom", "praca", "miejsce", "w", "na", "do", "z", "gdzie", "tam", "czy"],
    ["isc", "pojsc", "jechac", "wracac", "dzis", "jutro", "teraz", "juz", "jeszcze", "czekac"],
    [
        "wiedziec",
        "znac",
        "rozumiec",
        "mowic",
        "o",
        "myslec",
        "powiedziec",
        "pytac",
        "odpowiadac",
        "ze",
    ],
    [
        "pracowac",
        "robic",
        "zrobic",
        "uczyc_sie",
        "pamietac",
        "dzien",
        "rok",
        "wczoraj",
        "zawsze",
        "czesto",
    ],
    ["dac", "brac", "wziac", "i", "ale", "albo", "bo", "tez", "tylko", "od"],
    [
        "problem",
        "pytanie",
        "odpowiedz",
        "sposob",
        "szukac",
        "znalezc",
        "widziec",
        "wazny",
        "latwy",
        "trudny",
    ],
    ["woda", "jedzenie", "telefon", "zycie", "maly", "nowy", "zly", "jesli", "wiec", "bardzo"],
]


def all_maps(model_value: dict[str, Any], variants: list[dict[str, Any]]) -> list[str]:
    result = list(model_value["polish"]["token_concepts"])
    for variant in variants:
        result.extend(variant["prompt_token_concepts"])
        for accepted in variant["answers"]:
            result.extend(accepted["token_concepts"])
    return result


def learning_maps(model_value: dict[str, Any], variants: list[dict[str, Any]]) -> list[str]:
    """Concepts needed for the model and the two mandatory early cloze recalls."""
    return all_maps(
        model_value,
        [variant for variant in variants if variant["kind"] == "cloze"],
    )


def ordered_unique(values: list[str], order: dict[str, int]) -> list[str]:
    return sorted({value for value in values if value != "@name"}, key=order.__getitem__)


def build() -> dict[str, Any]:
    by_id = {item.id: item for item in LEXEMES}
    expected_ids = [concept_id for unit in UNIT_CONCEPT_ORDER for concept_id in unit]
    if set(by_id) != set(expected_ids) or len(LEXEMES) != 100:
        missing = sorted(set(expected_ids) - set(by_id))
        extra = sorted(set(by_id) - set(expected_ids))
        raise ValueError(f"lexeme inventory mismatch: missing={missing}, extra={extra}")
    ordered_lexemes = [by_id[concept_id] for concept_id in expected_ids]
    concept_order = {item.id: index for index, item in enumerate(ordered_lexemes, start=1)}

    concepts = [
        {
            "id": item.id,
            "order": concept_order[item.id],
            "lemma": item.lemma,
            "gloss": item.gloss,
            "part_of_speech": item.pos,
            "unit_id": f"u{item.unit:02d}",
        }
        for item in ordered_lexemes
    ]

    synth_by_unit: dict[int, list[Synthesis]] = {unit: [] for unit, _ in UNITS}
    for synthesis in SYNTHESES:
        synth_by_unit[synthesis.unit].append(synthesis)
    if any(len(items) != 2 for items in synth_by_unit.values()):
        raise ValueError("each unit must contain exactly two synthesis objectives")

    objectives: list[dict[str, Any]] = []
    objective_order = 0
    seen: set[str] = set()
    for unit_number, concept_ids in enumerate(UNIT_CONCEPT_ORDER, start=1):
        for concept_id in concept_ids:
            item = by_id[concept_id]
            used = learning_maps(item.model, item.variants)
            requirements = ordered_unique(
                [value for value in used if value != concept_id], concept_order
            )
            unavailable = set(requirements) - seen
            if unavailable:
                raise ValueError(f"{concept_id} uses later concepts: {sorted(unavailable)}")
            objective_order += 1
            variants: list[dict[str, Any]] = []
            kind_counts = {"cloze": 0, "translation": 0}
            for variant in item.variants:
                kind = variant["kind"]
                kind_counts[kind] += 1
                prefix = "c" if kind == "cloze" else "t"
                suffix = f"{prefix}{kind_counts[kind]}"
                variants.append({"id": f"lex.{concept_id}.{suffix}", **variant})
            objectives.append(
                {
                    "id": f"lex.{concept_id}",
                    "order": objective_order,
                    "unit_id": f"u{unit_number:02d}",
                    "kind": "lexical",
                    "concept_id": concept_id,
                    "requires_seen": requirements,
                    "unlock_ready": [],
                    "model": item.model,
                    "variants": variants,
                }
            )
            seen.add(concept_id)

        unit_concepts = set(concept_ids)
        for synthesis_index, item in enumerate(synth_by_unit[unit_number], start=1):
            used = all_maps(item.model, item.variants)
            if set(used) - {"@name"} - seen:
                raise ValueError(f"synthesis {item.id} uses unavailable concepts")
            requirements = ordered_unique(used + list(unit_concepts), concept_order)
            objective_order += 1
            variants = []
            suffixes = ("c1", "c2", "t1", "t2")
            for suffix, variant in zip(suffixes, item.variants, strict=True):
                variants.append(
                    {"id": f"syn.u{unit_number:02d}.{synthesis_index}.{suffix}", **variant}
                )
            objectives.append(
                {
                    "id": f"syn.u{unit_number:02d}.{synthesis_index}.{item.id}",
                    "order": objective_order,
                    "unit_id": f"u{unit_number:02d}",
                    "kind": "synthesis",
                    "concept_id": None,
                    "requires_seen": requirements,
                    "unlock_ready": requirements,
                    "model": item.model,
                    "variants": variants,
                }
            )

    return {
        "version": 3,
        "title": "Polish Typing Tutor — Core 100",
        "proper_names": [
            "Anna",
            "Anny",
            "Annę",
            "Annie",
            "Anną",
            "Marek",
            "Marka",
            "Markowi",
            "Markiem",
        ],
        "units": [
            {"id": f"u{number:02d}", "order": number, "title": title} for number, title in UNITS
        ],
        "concepts": concepts,
        "objectives": objectives,
    }


def main() -> None:
    output = (
        Path(__file__).resolve().parents[1] / "src" / "polish_tutor" / "data" / "course_v1.yaml"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(build(), allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
