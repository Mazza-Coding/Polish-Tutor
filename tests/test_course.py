from __future__ import annotations

import runpy
from pathlib import Path

import yaml

from polish_tutor.course import (
    EXPECTED_BUNDLED_OBJECTIVE_COUNT,
    EXPECTED_BUNDLED_UNIT_COUNT,
    EXPECTED_BUNDLED_VARIANT_COUNT,
    CourseCatalog,
    polish_tokens,
)
from polish_tutor.models import Course, ObjectiveKind, PromptKind, TokenConceptMap


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


def test_release_course_has_the_book_scope(catalog: CourseCatalog) -> None:
    assert catalog.course.title == "Teach Yourself Polish — Lessons 1–7"
    assert len(catalog.course.units) == EXPECTED_BUNDLED_UNIT_COUNT == 7
    assert len(catalog.course.objectives) == EXPECTED_BUNDLED_OBJECTIVE_COUNT == 17
    assert sum(len(item.variants) for item in catalog.course.objectives) == (
        EXPECTED_BUNDLED_VARIANT_COUNT == 251
    )
    assert catalog.course.concepts == ()


def test_every_polish_token_has_an_aligned_mapping(catalog: CourseCatalog) -> None:
    for mapping in all_polish_mappings(catalog):
        assert len(polish_tokens(mapping.text)) == len(mapping.token_concepts), mapping.text
        assert all(item in {"@literal", "@name"} for item in mapping.token_concepts)


def test_book_exercise_objectives_have_two_clozes_and_source_items(
    catalog: CourseCatalog,
) -> None:
    for objective in catalog.course.objectives:
        assert objective.kind is ObjectiveKind.EXERCISE
        assert len(objective.cloze_variants) == 2
        assert objective.translation_variants
        assert all(variant.context for variant in objective.translation_variants)


def test_each_lesson_keeps_source_pages_and_teaching_material(catalog: CourseCatalog) -> None:
    for number, unit in enumerate(catalog.course.units, start=1):
        assert unit.id == f"l{number:02d}"
        assert unit.source_pages
        assert unit.source_pages.startswith("book pp.")
        assert len(unit.material) >= 5


def test_anchor_exercises_from_lessons_one_to_seven_are_present(
    catalog: CourseCatalog,
) -> None:
    anchors = {
        "l01.into_english.t01": "To pole jest małe, tamto jest duże.",
        "l02.into_english.t01": "Zamykamy okna.",
        "l03.into_english.t01": "Które okno jest duże?",
        "l04.into_english.t01": (
            "Czyje zadanie jest najlepsze? Zadanie tego małego dziecka jest najlepsze."
        ),
        "l05.into_english.t01": "Co je to dziecko?",
        "l06.into_english.t01": "Mam jabłka. Nie mam jabłek. Mam dużo jabłek.",
        "l07.into_english.t01": "Nie otwieraj tych trzech okien.",
    }
    variants = {
        variant.id: variant
        for objective in catalog.course.objectives
        for variant in objective.variants
    }
    for variant_id, expected in anchors.items():
        assert variants[variant_id].answers[0].text == expected


def test_formal_address_exercises_accept_the_printed_range_of_you_forms(
    catalog: CourseCatalog,
) -> None:
    formal = catalog.objectives["l02.formal_address"].translation_variants[0]
    assert {answer.text for answer in formal.answers} == {
        "Pamiętasz.",
        "Pamiętacie.",
        "Pan pamięta.",
        "Pani pamięta.",
        "Panowie pamiętają.",
        "Panie pamiętają.",
        "Państwo pamiętają.",
    }

    whose = catalog.objectives["l03.into_polish"].translation_variants[0]
    assert len(whose.answers) == 7
    assert whose.answers[0].text == "Czyje zadanie czytasz?"
    assert whose.answers[-1].text == "Czyje zadanie państwo czytają?"


def test_lesson_six_keeps_both_numbered_exercises(catalog: CourseCatalog) -> None:
    plural = catalog.objectives["l06.plural_change"]
    assert len(plural.translation_variants) == 6
    assert plural.translation_variants[0].answers[0].text == "Nie zamykacie okien."

    genitive = catalog.objectives["l06.genitive_forms"]
    assert len(genitive.translation_variants) == 11
    assert genitive.translation_variants[0].answers[0].text == "pola, pól"
    assert genitive.translation_variants[-1].answers[0].text == "uczucia, uczuć"


def test_build_script_expands_the_bundled_compact_source(catalog: CourseCatalog) -> None:
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "scripts" / "build_course.py"))
    generated = Course.model_validate(namespace["build"]())
    assert generated == catalog.course

    bundled = yaml.safe_load(
        (root / "src" / "polish_tutor" / "data" / "course_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert bundled["format"] == "teach-yourself-exercises"
    assert len(bundled["lesson_files"]) == 7
