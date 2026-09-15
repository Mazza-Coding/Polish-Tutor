from __future__ import annotations

import copy
from collections import Counter

import pytest
import yaml

from polish_tutor.book import book_items, build_course, rows
from polish_tutor.course import CourseCatalog, CourseValidationError, polish_tokens
from polish_tutor.data import teach_yourself as source
from polish_tutor.models import Course, ObjectiveKind, PromptKind, SelfForm


@pytest.fixture(scope="session")
def catalog() -> CourseCatalog:
    """This module tests the actual bundled book, not the legacy engine fixture."""
    return CourseCatalog.load_bundled()


def test_release_counts_and_order(catalog: CourseCatalog) -> None:
    assert catalog.course.version == 2
    assert [unit.id for unit in catalog.course.units] == [f"ty.l{i:02}" for i in range(1, 8)]
    assert len(catalog.concepts) == 146
    assert len(catalog.objectives) == 634
    assert sum(len(obj.variants) for obj in catalog.course.objectives) == 2240
    assert Counter(obj.unit_id for obj in catalog.course.objectives) == {
        "ty.l01": 79, "ty.l02": 95, "ty.l03": 93, "ty.l04": 79,
        "ty.l05": 96, "ty.l06": 66, "ty.l07": 126,
    }


@pytest.mark.parametrize("number", range(1, 8))
def test_every_lesson_has_material_and_exercises(catalog: CourseCatalog, number: int) -> None:
    lesson = source.LESSONS[number - 1]
    unit = catalog.units[f"ty.l{number:02}"]
    assert lesson["title"] in unit.title
    assert all(note in unit.notes for note in lesson["notes"])
    assert lesson["speech"] in unit.notes
    assert list(rows(lesson["vocabulary"], 4))
    assert any(item.lesson == number and item.section == "reading" for item in book_items())
    section = "plural" if number == 6 else "translation"
    assert any(item.lesson == number and item.section == section for item in book_items())


def test_source_scope_and_answer_key_locations() -> None:
    assert source.SOURCE["printed_pages"] == [7, 31]
    assert source.SOURCE["pdf_pages"] == [15, 39]
    assert source.SOURCE["key_printed_pages"] == [217, 219]
    assert source.SOURCE["key_pdf_pages"] == [225, 227]
    assert {item.lesson for item in book_items()} == set(range(1, 8))
    assert all(7 <= item.page <= 31 for item in book_items())


def test_complete_numbered_translation_coverage() -> None:
    expected = {
        1: {str(i) for i in range(1, 9)},
        2: {str(i) for i in range(1, 15)},
        3: {f"1.{form}" for form in ("ty", "wy", "pan", "pani", "panowie", "panie", "panstwo")}
           | {str(i) for i in range(2, 14)},
        4: {str(i) for i in range(1, 11)},
        5: {str(i) for i in range(1, 8)} | {"8a", "8b"} | {str(i) for i in range(9, 14)},
        7: {str(i) for i in range(1, 18)},
    }
    for number, references in expected.items():
        assert {item.reference for item in book_items()
                if item.lesson == number and item.section == "translation"} == references


def test_formal_address_responses_and_both_genitives_are_present() -> None:
    counts = Counter(item.section for item in book_items())
    assert counts == {
        "reading": 136, "examples": 124, "translation": 82, "present": 48,
        "table": 44, "response": 15, "imperative": 15, "declension": 11,
        "address": 7, "plural": 6,
    }
    for item in book_items():
        if item.section == "declension":
            assert ";" in item.polish[0]
            assert "derived from Lesson 4" in item.provenance


@pytest.mark.parametrize(("identifier", "polish"), [
    ("ty.l01.translation.p9.5", "Mam czworo dzieci."),
    ("ty.l02.translation.p12.12", "Panie zamykają okna."),
    ("ty.l03.translation.p16.1.panstwo", "Czyje zadanie państwo czytają?"),
    ("ty.l04.translation.p19.1", "Nie znamy tego nowego pisma."),
    ("ty.l05.translation.p22.8b", "Kto śpiewa? My śpiewamy."),
    ("ty.l06.plural.p26.4", "Nie otwieramy pudełek."),
    ("ty.l07.translation.p30.1", "Nie biorę tych czterech jaj."),
    ("ty.l07.translation.p30.17", "On siada przy oknie."),
])
def test_published_key_answers(catalog: CourseCatalog, identifier: str, polish: str) -> None:
    objective = catalog.objectives[identifier]
    assert objective.model.polish.text == polish
    assert objective.translation_variants[0].answers[0].text == polish


def test_key_optional_czy_and_documented_person_discrepancy(catalog: CourseCatalog) -> None:
    optional = catalog.objectives["ty.l07.translation.p30.6"].translation_variants[0]
    assert [answer.text for answer in optional.answers] == [
        "Czy nie masz moich szkieł?", "Nie masz moich szkieł?",
    ]
    plural = catalog.objectives["ty.l06.plural.p26.6"].translation_variants[0]
    assert [answer.text for answer in plural.answers] == ["Szukamy piór.", "Szukają piór."]
    assert "not a quotation from the key" in plural.context


def test_every_book_item_becomes_a_source_attributed_objective(catalog: CourseCatalog) -> None:
    for item in book_items():
        objective = catalog.objectives[item.id]
        assert objective.model.polish.text == item.polish[0]
        variant = objective.translation_variants[0]
        assert variant.prompt == item.english
        assert [answer.text for answer in variant.answers] == list(item.polish)
        assert f"p. {item.page}" in variant.context
        if item.section == "reading":
            assert "editorial English cue" in variant.context
        if item.section == "response":
            assert "not all possible answers" in variant.context


def test_token_alignment_and_cloze_reconstruction(catalog: CourseCatalog) -> None:
    for objective in catalog.course.objectives:
        mappings = [objective.model.polish]
        for variant in objective.variants:
            mappings.extend(variant.answers)
            if variant.kind is PromptKind.CLOZE:
                assert len(polish_tokens(variant.prompt)) == len(variant.prompt_token_concepts)
                assert variant.prompt.count("____") == 1
                assert variant.prompt.replace("____", variant.answers[0].text) == objective.model.polish.text
        for mapping in mappings:
            assert len(polish_tokens(mapping.text)) == len(mapping.token_concepts)
            assert set(mapping.token_concepts).issubset(set(catalog.concepts) | {"@name"})


def test_new_namespace_does_not_reuse_old_progress_identifiers(catalog: CourseCatalog) -> None:
    assert all(identifier.startswith("ty.") for identifier in catalog.concepts)
    assert all(identifier.startswith("ty.") for identifier in catalog.objectives)
    assert "lex.tak" not in catalog.objectives
    assert "tak" not in catalog.concepts


def test_objectives_can_all_be_introduced_without_a_dependency_deadlock(catalog: CourseCatalog) -> None:
    introduced: set[str] = set()
    for objective in catalog.objectives_in_order:
        assert set(objective.requires_seen).issubset(introduced), objective.id
        if objective.concept_id:
            introduced.add(objective.concept_id)
    assert introduced == set(catalog.concepts)


def test_no_polish_answer_imports_vocabulary_from_a_later_lesson(catalog: CourseCatalog) -> None:
    for objective in catalog.course.objectives:
        order = catalog.units[objective.unit_id].order
        for variant in objective.variants:
            for answer in variant.answers:
                for identifier in answer.token_concepts:
                    if identifier != "@name":
                        assert catalog.units[catalog.concepts[identifier].unit_id].order <= order


def test_every_objective_has_two_initial_recalls_and_a_mature_variant(catalog: CourseCatalog) -> None:
    for objective in catalog.course.objectives:
        assert len(objective.cloze_variants) == 2
        assert objective.translation_variants
        for variant in objective.variants:
            for self_form in SelfForm:
                assert variant.answers_for(self_form)


def test_one_lexical_objective_per_concept(catalog: CourseCatalog) -> None:
    lexical = [obj for obj in catalog.course.objectives if obj.kind is ObjectiveKind.LEXICAL]
    assert len(lexical) == len(catalog.concepts)
    assert {obj.concept_id for obj in lexical} == set(catalog.concepts)


def test_rebuilding_is_deterministic_and_yaml_roundtrips(catalog: CourseCatalog, tmp_path) -> None:
    assert build_course() == build_course()
    assert Course.model_validate(build_course()) == catalog.course
    path = tmp_path / "export.yaml"
    path.write_text(yaml.safe_dump(build_course(), allow_unicode=True), encoding="utf-8")
    assert CourseCatalog.load_path(path).course == catalog.course
    assert CourseCatalog.load_bundled().content_hash == catalog.content_hash


def test_unmapped_source_words_are_rejected(monkeypatch) -> None:
    lessons = copy.deepcopy(source.LESSONS)
    lessons[0]["reading"] += "\n9|unknown|Unknown word.|Nieznanywyraz.\n"
    monkeypatch.setattr("polish_tutor.book.LESSONS", lessons)
    with pytest.raises(ValueError, match="unmapped source form"):
        build_course()


def test_undeclared_dependencies_raise_validation_errors_not_key_errors() -> None:
    raw = build_course()
    raw["objectives"][0]["requires_seen"] = ["ty.missing"]
    with pytest.raises(CourseValidationError, match="unknown dependency"):
        CourseCatalog._from_bytes(yaml.safe_dump(raw).encode(), strict_counts=True)


def test_missing_initial_recall_is_rejected() -> None:
    raw = build_course()
    raw["objectives"][0]["variants"].pop(0)
    with pytest.raises(CourseValidationError, match="expected 2 cloze"):
        CourseCatalog._from_bytes(yaml.safe_dump(raw).encode(), strict_counts=True)


@pytest.mark.parametrize("bad", ["one|two", "one||three|four", ""])
def test_bad_source_rows_are_not_silently_repaired(bad: str) -> None:
    if bad:
        with pytest.raises(ValueError, match="source row"):
            list(rows(bad, 4))
    else:
        assert list(rows(bad, 4)) == []
