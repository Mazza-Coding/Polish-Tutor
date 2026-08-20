from __future__ import annotations

import re
import runpy
from collections import Counter
from pathlib import Path

import yaml

from polish_tutor.course import EXPECTED_POS_COUNTS, CourseCatalog, polish_tokens
from polish_tutor.models import (
    ObjectiveKind,
    PartOfSpeech,
    PromptKind,
    SelfForm,
    TokenConceptMap,
)


def all_polish_mappings(catalog: CourseCatalog):
    for objective in catalog.course.objectives:
        yield objective.model.polish
        for variant in objective.variants:
            if variant.kind is PromptKind.CLOZE:
                yield TokenConceptMap(
                    text=variant.prompt,
                    token_concepts=variant.prompt_token_concepts,
                )
            yield from variant.answers


def english_polish_pairs(catalog: CourseCatalog):
    for objective in catalog.course.objectives:
        yield objective.id, objective.model.english, objective.model.polish
        for variant in objective.translation_variants:
            for answer in variant.answers:
                yield variant.id, variant.prompt, answer


def test_release_course_has_exact_promised_counts(catalog: CourseCatalog) -> None:
    assert len(catalog.course.units) == 10
    assert len(catalog.course.concepts) == 100
    assert len(catalog.course.objectives) == 120
    assert sum(len(objective.variants) for objective in catalog.course.objectives) == 680
    assert Counter(item.part_of_speech for item in catalog.course.concepts) == Counter(
        EXPECTED_POS_COUNTS
    )


def test_every_polish_token_has_an_aligned_concept(catalog: CourseCatalog) -> None:
    for objective in catalog.course.objectives:
        assert len(polish_tokens(objective.model.polish.text)) == len(
            objective.model.polish.token_concepts
        )
        for variant in objective.variants:
            if variant.kind is PromptKind.CLOZE:
                assert len(polish_tokens(variant.prompt)) == len(variant.prompt_token_concepts)
            for answer in variant.answers:
                assert len(polish_tokens(answer.text)) == len(answer.token_concepts)


def test_lexical_and_synthesis_shape(catalog: CourseCatalog) -> None:
    lexical = [
        objective
        for objective in catalog.course.objectives
        if objective.kind is ObjectiveKind.LEXICAL
    ]
    synthesis = [
        objective
        for objective in catalog.course.objectives
        if objective.kind is ObjectiveKind.SYNTHESIS
    ]
    assert len(lexical) == 100
    assert len(synthesis) == 20
    assert all(len(item.cloze_variants) == 2 for item in catalog.course.objectives)
    assert all(len(item.translation_variants) == 4 for item in lexical)
    assert all(len(item.translation_variants) == 2 for item in synthesis)


def test_each_lexeme_has_distinct_translation_contexts(catalog: CourseCatalog) -> None:
    for objective in catalog.course.objectives:
        if objective.kind is not ObjectiveKind.LEXICAL:
            continue
        prompts = {
            " ".join(variant.prompt.casefold().split())
            for variant in objective.translation_variants
        }
        answer_sets = {
            tuple(sorted(" ".join(answer.text.casefold().split()) for answer in variant.answers))
            for variant in objective.translation_variants
        }
        assert len(prompts) == 4, objective.id
        assert len(answer_sets) == 4, objective.id


def test_inflectable_lexemes_use_multiple_surface_forms(catalog: CourseCatalog) -> None:
    inflectable = {
        PartOfSpeech.VERB,
        PartOfSpeech.NOUN,
        PartOfSpeech.ADJECTIVE,
        PartOfSpeech.PRONOUN,
    }
    for objective in catalog.course.objectives:
        if objective.kind is not ObjectiveKind.LEXICAL or objective.concept_id is None:
            continue
        concept = catalog.concepts[objective.concept_id]
        if concept.part_of_speech not in inflectable:
            continue
        forms = {
            token.casefold()
            for mapping in (
                objective.model.polish,
                *(answer for variant in objective.variants for answer in variant.answers),
            )
            for token, concept_id in zip(
                polish_tokens(mapping.text), mapping.token_concepts, strict=True
            )
            if concept_id == objective.concept_id
        }
        assert len(forms) >= 2, (objective.id, forms)


def test_demonstratives_before_nouns_map_to_ten(catalog: CourseCatalog) -> None:
    demonstratives = {"ten", "ta", "to", "te", "tego", "tej", "tę", "tym"}
    for mapping in all_polish_mappings(catalog):
        tokens = polish_tokens(mapping.text)
        for index, token in enumerate(tokens[:-1]):
            next_concept = catalog.concepts.get(mapping.token_concepts[index + 1])
            if (
                token.casefold() in demonstratives
                and next_concept is not None
                and next_concept.part_of_speech is PartOfSpeech.NOUN
            ):
                assert mapping.token_concepts[index] == "ten", mapping.text


def test_chciec_examples_use_the_authored_object_forms(catalog: CourseCatalog) -> None:
    assert catalog.objectives["lex.chciec"].model.polish.text == "Chcę tego."
    assert catalog.objectives["lex.woda"].model.polish.text == "Chcę wody."
    assert catalog.objectives["lex.rzecz"].translation_variants[0].answers[0].text == (
        "Chcę tej rzeczy."
    )
    assert catalog.objectives["lex.cos"].cloze_variants[1].answers[0].text == "czegoś"


def test_motion_translations_identify_the_mode(catalog: CourseCatalog) -> None:
    cues = {
        "isc": ("walk", "on foot"),
        "pojsc": ("head", "on foot"),
        "jechac": ("vehicle",),
    }
    for label, english, polish in english_polish_pairs(catalog):
        used = set(polish.token_concepts)
        for concept_id, expected_cues in cues.items():
            if concept_id in used:
                assert any(cue in english.casefold() for cue in expected_cues), (
                    label,
                    english,
                    polish.text,
                )


def test_hints_do_not_explain_grammar_with_labels(catalog: CourseCatalog) -> None:
    theory_terms = re.compile(
        r"\b(?:nominative|accusative|genitive|dative|instrumental|locative|vocative|"
        r"case|declension|conjugation|paradigm|masculine|feminine|neuter|"
        r"perfective|imperfective|verb|noun|adjective|pronoun|first-person|"
        r"second-person|third-person|plural|singular|infinitive|subject|object|"
        r"past|present|future|modal|clause|preposition|agreement|negation|form|"
        r"bounded|ongoing)\b",
        re.IGNORECASE,
    )
    for objective in catalog.course.objectives:
        for variant in objective.variants:
            assert not theory_terms.search(variant.hint), (variant.id, variant.hint)


def test_mature_contexts_do_not_delay_initial_learning(catalog: CourseCatalog) -> None:
    assert catalog.objectives["lex.tak"].requires_seen == ()
    assert catalog.objectives["lex.nie"].requires_seen == ()
    assert any(
        "wiedziec" in answer.token_concepts
        for variant in catalog.objectives["lex.tak"].translation_variants
        for answer in variant.answers
    )


def test_gender_dependent_answers_select_only_requested_form(catalog: CourseCatalog) -> None:
    variant = catalog.objectives["lex.wczoraj"].translation_variants[0]
    masculine = variant.answers_for(SelfForm.MASCULINE)
    feminine = variant.answers_for(SelfForm.FEMININE)
    assert [answer.text for answer in masculine] == ["Wczoraj byłem w pracy."]
    assert [answer.text for answer in feminine] == ["Wczoraj byłam w pracy."]


def test_no_greetings_or_tourist_scripts(catalog: CourseCatalog) -> None:
    all_text = " ".join(
        [concept.lemma for concept in catalog.course.concepts]
        + [objective.model.polish.text for objective in catalog.course.objectives]
    ).casefold()
    assert "dzień dobry" not in all_text
    assert "do widzenia" not in all_text
    assert "przepraszam" not in all_text


def test_czlowiek_and_osoba_are_contrasted_or_both_accepted(
    catalog: CourseCatalog,
) -> None:
    person_concepts = {"czlowiek", "osoba"}
    cues = {
        "czlowiek": ("human being", "people", "man"),
        "osoba": ("individual",),
    }

    for objective in catalog.course.objectives:
        for variant in objective.variants:
            answer_concept_sets = [
                set(answer.token_concepts) & person_concepts for answer in variant.answers
            ]
            used = set().union(*answer_concept_sets)
            if not used:
                continue

            visible_english = " ".join(
                part for part in (variant.context, variant.prompt) if part
            ).casefold()
            if variant.kind is PromptKind.TRANSLATION and used == person_concepts:
                assert {"czlowiek"} in answer_concept_sets
                assert {"osoba"} in answer_concept_sets
                assert "both learned words" in visible_english
                continue

            assert len(used) == 1
            concept_id = next(iter(used))
            assert any(cue in visible_english for cue in cues[concept_id]), variant.id

    contrast = catalog.objectives["syn.u02.2.people_and_things"]
    assert contrast.model.english == ("A human being can be good. This individual is here.")
    assert contrast.model.polish.text == "Człowiek może być dobry. Ta osoba jest tutaj."


def test_bundled_yaml_matches_authored_source() -> None:
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "scripts" / "build_course.py"))
    generated = namespace["build"]()
    bundled = yaml.safe_load(
        (root / "src" / "polish_tutor" / "data" / "course_v1.yaml").read_text(encoding="utf-8")
    )
    assert bundled == generated
