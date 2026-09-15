from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import yaml
from pydantic import ValidationError

from polish_tutor.models import (
    Course,
    Objective,
    ObjectiveKind,
    PartOfSpeech,
    PromptKind,
    SelfForm,
    TokenConceptMap,
)

_POLISH_TOKEN = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+(?:-[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)?")
EXPECTED_POS_COUNTS = {
    PartOfSpeech.VERB: 30,
    PartOfSpeech.NOUN: 20,
    PartOfSpeech.ADJECTIVE: 8,
    PartOfSpeech.PRONOUN: 10,
    PartOfSpeech.ADVERB: 12,
    PartOfSpeech.PREPOSITION: 8,
    PartOfSpeech.PARTICLE: 12,
}


class CourseValidationError(ValueError):
    pass


def polish_tokens(value: str) -> tuple[str, ...]:
    return tuple(_POLISH_TOKEN.findall(value))


class CourseCatalog:
    def __init__(self, course: Course, source_bytes: bytes, *, strict_counts: bool = True) -> None:
        self.course = course
        self.content_hash = hashlib.sha256(source_bytes).hexdigest()
        self.concepts = {concept.id: concept for concept in course.concepts}
        self.objectives = {objective.id: objective for objective in course.objectives}
        self.units = {unit.id: unit for unit in course.units}
        self.objectives_in_order = tuple(sorted(course.objectives, key=lambda item: item.order))
        self.concept_objective = {
            objective.concept_id: objective
            for objective in course.objectives
            if objective.concept_id is not None
        }
        self.validate(strict_counts=strict_counts)

    @classmethod
    def load_bundled(cls) -> CourseCatalog:
        from polish_tutor.book import build_course

        raw = build_course()
        source = json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return cls(Course.model_validate(raw), source, strict_counts=True)

    @classmethod
    def load_path(cls, path: Path, *, strict_counts: bool = True) -> CourseCatalog:
        return cls._from_bytes(path.read_bytes(), strict_counts=strict_counts)

    @classmethod
    def _from_bytes(cls, source: bytes, *, strict_counts: bool) -> CourseCatalog:
        try:
            raw = yaml.safe_load(source)
            course = Course.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as error:
            raise CourseValidationError(f"invalid course structure: {error}") from error
        return cls(course, source, strict_counts=strict_counts)

    def validate(self, *, strict_counts: bool) -> None:
        errors: list[str] = []
        self._check_unique(errors, "unit", [unit.id for unit in self.course.units])
        self._check_unique(errors, "concept", [concept.id for concept in self.course.concepts])
        self._check_unique(errors, "objective", [item.id for item in self.course.objectives])
        variant_ids = [
            variant.id for objective in self.course.objectives for variant in objective.variants
        ]
        self._check_unique(errors, "variant", variant_ids)
        self._check_unique(errors, "unit order", [str(unit.order) for unit in self.course.units])
        self._check_unique(
            errors, "concept order", [str(item.order) for item in self.course.concepts]
        )
        self._check_unique(
            errors, "objective order", [str(item.order) for item in self.course.objectives]
        )

        unit_ids = set(self.units)
        concept_ids = set(self.concepts)
        proper_names = {name.casefold() for name in self.course.proper_names}
        lexical_by_concept: Counter[str] = Counter()

        for concept in self.course.concepts:
            if concept.unit_id not in unit_ids:
                errors.append(f"concept {concept.id}: unknown unit {concept.unit_id}")

        for objective in self.course.objectives:
            if objective.unit_id not in unit_ids:
                errors.append(f"objective {objective.id}: unknown unit {objective.unit_id}")
            if objective.concept_id is not None:
                lexical_by_concept[objective.concept_id] += 1
                if objective.concept_id not in concept_ids:
                    errors.append(
                        f"objective {objective.id}: unknown target concept {objective.concept_id}"
                    )
            for dependency in (*objective.requires_seen, *objective.unlock_ready):
                if dependency not in concept_ids:
                    errors.append(f"objective {objective.id}: unknown dependency {dependency}")
            if not set(objective.unlock_ready).issubset(set(objective.requires_seen)):
                errors.append(f"objective {objective.id}: unlock_ready must be in requires_seen")

            self._validate_text_map(
                errors,
                f"objective {objective.id} model",
                objective.model.polish,
                concept_ids,
                proper_names,
            )
            available = set(objective.requires_seen)
            if objective.concept_id:
                available.add(objective.concept_id)
                if objective.concept_id not in objective.model.polish.token_concepts:
                    errors.append(
                        f"objective {objective.id}: model does not contain target concept"
                    )
            model_used = set(objective.model.polish.token_concepts) - {"@name"}
            if not model_used.issubset(available):
                missing = sorted(model_used - available)
                errors.append(f"objective {objective.id}: undeclared model concepts {missing}")

            for variant in objective.variants:
                if variant.kind is PromptKind.CLOZE:
                    prompt_map = TokenConceptMap(
                        text=variant.prompt,
                        token_concepts=variant.prompt_token_concepts,
                    )
                    self._validate_text_map(
                        errors,
                        f"variant {variant.id} prompt",
                        prompt_map,
                        concept_ids,
                        proper_names,
                    )
                    used = set(variant.prompt_token_concepts) - {"@name"}
                    if not used.issubset(available):
                        errors.append(
                            f"variant {variant.id}: undeclared prompt concepts "
                            f"{sorted(used - available)}"
                        )
                elif variant.prompt_token_concepts:
                    errors.append(f"variant {variant.id}: English prompt has Polish token map")

                for answer in variant.answers:
                    self._validate_text_map(
                        errors,
                        f"variant {variant.id} answer",
                        answer,
                        concept_ids,
                        proper_names,
                    )
                    used = set(answer.token_concepts) - {"@name"}
                    mature_translation = (
                        objective.kind is ObjectiveKind.LEXICAL
                        and variant.kind is PromptKind.TRANSLATION
                    )
                    if not mature_translation and not used.issubset(available):
                        errors.append(
                            f"variant {variant.id}: undeclared answer concepts "
                            f"{sorted(used - available)}"
                        )
                    if objective.concept_id and objective.concept_id not in used:
                        errors.append(f"variant {variant.id}: answer does not exercise target")
                for self_form in SelfForm:
                    if not variant.answers_for(self_form):
                        errors.append(
                            f"variant {variant.id}: no answer for {self_form.value} self form"
                        )

            cloze_count = len(objective.cloze_variants)
            translation_count = len(objective.translation_variants)
            if self.course.version >= 2:
                # The engine needs two initial recalls. Textbook context counts
                # are variable; duplicating content to fill a quota is not useful.
                if cloze_count != 2 or translation_count < 1:
                    errors.append(
                        f"objective {objective.id}: expected 2 cloze and at least 1 translation variant"
                    )
            else:
                expected = (2, 4) if objective.kind is ObjectiveKind.LEXICAL else (2, 2)
                if (cloze_count, translation_count) != expected:
                    errors.append(
                        f"objective {objective.id}: expected {expected[0]} cloze and "
                        f"{expected[1]} translation variants"
                    )

        missing_lexical = sorted(
            concept_id for concept_id in concept_ids if lexical_by_concept[concept_id] != 1
        )
        if missing_lexical:
            errors.append(f"concepts without exactly one lexical objective: {missing_lexical}")

        self._validate_dependency_order(errors)
        if strict_counts:
            self._validate_release_counts(errors)
        if errors:
            raise CourseValidationError("\n".join(errors))

    def _validate_release_counts(self, errors: list[str]) -> None:
        if self.course.version == 2:
            expected_units = [f"ty.l{number:02}" for number in range(1, 8)]
            actual_units = [unit.id for unit in sorted(self.course.units, key=lambda x: x.order)]
            if actual_units != expected_units:
                errors.append("expected Teach Yourself lessons 1–7 in order")
            if not all(unit.notes for unit in self.course.units):
                errors.append("each textbook lesson must include its source notes")
            return
        if len(self.course.units) != 10:
            errors.append(f"expected 10 units, found {len(self.course.units)}")
        if len(self.course.concepts) != 100:
            errors.append(f"expected 100 concepts, found {len(self.course.concepts)}")
        if len(self.course.objectives) != 120:
            errors.append(f"expected 120 objectives, found {len(self.course.objectives)}")
        variant_count = sum(len(objective.variants) for objective in self.course.objectives)
        if variant_count != 680:
            errors.append(f"expected 680 variants, found {variant_count}")
        actual_pos = Counter(concept.part_of_speech for concept in self.course.concepts)
        if actual_pos != Counter(EXPECTED_POS_COUNTS):
            errors.append(
                f"part-of-speech counts differ: expected {EXPECTED_POS_COUNTS}, "
                f"found {dict(actual_pos)}"
            )
        for unit in self.course.units:
            concepts = [item for item in self.course.concepts if item.unit_id == unit.id]
            syntheses = [
                item
                for item in self.course.objectives
                if item.unit_id == unit.id and item.kind is ObjectiveKind.SYNTHESIS
            ]
            if len(concepts) != 10 or len(syntheses) != 2:
                errors.append(
                    f"unit {unit.id}: expected 10 concepts and 2 syntheses, "
                    f"found {len(concepts)} and {len(syntheses)}"
                )

    def _validate_dependency_order(self, errors: list[str]) -> None:
        concept_order = {concept.id: concept.order for concept in self.course.concepts}
        for objective in self.course.objectives:
            if not objective.concept_id or objective.concept_id not in concept_order:
                continue
            target_order = concept_order[objective.concept_id]
            late = [
                dependency
                for dependency in objective.requires_seen
                if dependency in concept_order and concept_order[dependency] >= target_order
            ]
            if late:
                errors.append(
                    f"objective {objective.id}: dependencies are not previously introduced {late}"
                )

    @staticmethod
    def _check_unique(errors: list[str], label: str, values: list[str]) -> None:
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        if duplicates:
            errors.append(f"duplicate {label} IDs: {duplicates}")

    @staticmethod
    def _validate_text_map(
        errors: list[str],
        label: str,
        mapping: TokenConceptMap,
        concept_ids: set[str],
        proper_names: set[str],
    ) -> None:
        tokens = polish_tokens(mapping.text)
        if len(tokens) != len(mapping.token_concepts):
            errors.append(
                f"{label}: {len(tokens)} Polish tokens but "
                f"{len(mapping.token_concepts)} token mappings ({mapping.text!r})"
            )
            return
        for token, concept_id in zip(tokens, mapping.token_concepts, strict=True):
            if concept_id == "@name":
                if token.casefold() not in proper_names:
                    errors.append(f"{label}: {token!r} is not an allowed proper name")
            elif concept_id not in concept_ids:
                errors.append(f"{label}: token {token!r} maps to unknown {concept_id!r}")

    def objective_for_concept(self, concept_id: str) -> Objective:
        return self.concept_objective[concept_id]
