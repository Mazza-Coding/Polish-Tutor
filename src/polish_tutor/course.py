from __future__ import annotations

import hashlib
import re
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from polish_tutor.models import (
    Course,
    Objective,
    ObjectiveKind,
    PromptKind,
    SelfForm,
    TokenConceptMap,
)

_POLISH_TOKEN = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+(?:-[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)?")
_PSEUDO_CONCEPTS = {"@name", "@literal"}
_COMPACT_FORMAT = "teach-yourself-exercises"
EXPECTED_BUNDLED_UNIT_COUNT = 7
EXPECTED_BUNDLED_OBJECTIVE_COUNT = 17
EXPECTED_BUNDLED_VARIANT_COUNT = 251


class CourseValidationError(ValueError):
    pass


def polish_tokens(value: str) -> tuple[str, ...]:
    return tuple(_POLISH_TOKEN.findall(value))


def _literal_map(text: str) -> list[str]:
    return ["@literal"] * len(polish_tokens(text))


def _make_cloze(polish: str, position: float) -> tuple[str, str]:
    matches = list(_POLISH_TOKEN.finditer(polish))
    if not matches:
        raise ValueError(f"no Polish token in {polish!r}")
    index = min(len(matches) - 1, round((len(matches) - 1) * position))
    match = matches[index]
    answer = match.group(0)
    prompt = polish[: match.start()] + "____" + polish[match.end() :]
    return prompt, answer


def expand_compact_course(raw: dict[str, Any]) -> dict[str, Any]:
    """Expand the readable Teach Yourself corpus into the runtime Course schema."""
    if raw.get("format") != _COMPACT_FORMAT:
        return raw

    units: list[dict[str, Any]] = []
    objectives: list[dict[str, Any]] = []
    objective_order = 1

    for lesson in raw["lessons"]:
        units.append(
            {
                "id": lesson["id"],
                "order": lesson["order"],
                "title": lesson["title"],
                "source_pages": lesson["source_pages"],
                "material": lesson["material"],
            }
        )
        for exercise_set in lesson["sets"]:
            objective_id = f"{lesson['id']}.{exercise_set['slug']}"
            items = exercise_set["items"]
            if not items:
                raise ValueError(f"exercise set {objective_id} has no items")
            model_english = items[0]["prompt"]
            model_polish = items[0]["answers"][0]
            variants: list[dict[str, Any]] = []

            cloze_sources = [items[0], items[min(1, len(items) - 1)]]
            for cloze_number, item in enumerate(cloze_sources, start=1):
                polish = item["answers"][0]
                prompt, missing = _make_cloze(
                    polish, 0.33 if cloze_number == 1 else 0.67
                )
                variants.append(
                    {
                        "id": f"{objective_id}.c{cloze_number}",
                        "kind": "cloze",
                        "prompt": prompt,
                        "prompt_token_concepts": _literal_map(prompt),
                        "context": item["prompt"],
                        "hint": (
                            "Restore the omitted word from "
                            f"{exercise_set['label']} ({exercise_set['page']})."
                        ),
                        "answers": [
                            {
                                "text": missing,
                                "token_concepts": _literal_map(missing),
                                "when_self_form": "any",
                            }
                        ],
                    }
                )

            for index, item in enumerate(items, start=1):
                variants.append(
                    {
                        "id": f"{objective_id}.t{index:02d}",
                        "kind": "translation",
                        "prompt": item["prompt"],
                        "prompt_token_concepts": [],
                        "context": f"{exercise_set['label']} · {exercise_set['page']}",
                        "hint": "Use the wording and patterns introduced in this lesson.",
                        "answers": [
                            {
                                "text": answer,
                                "token_concepts": _literal_map(answer),
                                "when_self_form": "any",
                            }
                            for answer in item["answers"]
                        ],
                    }
                )

            objectives.append(
                {
                    "id": objective_id,
                    "order": objective_order,
                    "unit_id": lesson["id"],
                    "kind": "exercise",
                    "concept_id": None,
                    "requires_seen": [],
                    "unlock_ready": [],
                    "model": {
                        "english": model_english,
                        "polish": {
                            "text": model_polish,
                            "token_concepts": _literal_map(model_polish),
                        },
                    },
                    "variants": variants,
                }
            )
            objective_order += 1

    return {
        "version": raw["version"],
        "title": raw["title"],
        "proper_names": [],
        "units": units,
        "concepts": [],
        "objectives": objectives,
    }


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
        root = files("polish_tutor.data")
        resource = root.joinpath("course_v1.yaml")
        return cls._from_bytes(
            resource.read_bytes(),
            strict_counts=True,
            lesson_reader=lambda name: root.joinpath(name).read_bytes(),
        )

    @classmethod
    def load_path(cls, path: Path, *, strict_counts: bool = True) -> CourseCatalog:
        return cls._from_bytes(
            path.read_bytes(),
            strict_counts=strict_counts,
            lesson_reader=lambda name: (path.parent / name).read_bytes(),
        )

    @classmethod
    def _from_bytes(
        cls,
        source: bytes,
        *,
        strict_counts: bool,
        lesson_reader=None,
    ) -> CourseCatalog:
        hash_source = source
        try:
            raw = yaml.safe_load(source)
            if not isinstance(raw, dict):
                raise ValueError("course root must be a mapping")
            lesson_files = raw.get("lesson_files")
            if lesson_files is not None:
                if lesson_reader is None:
                    raise ValueError("lesson_files require a source directory")
                if not isinstance(lesson_files, list) or not lesson_files:
                    raise ValueError("lesson_files must be a non-empty list")
                lessons = []
                lesson_sources = []
                for name in lesson_files:
                    if not isinstance(name, str):
                        raise ValueError("lesson file names must be strings")
                    lesson_source = lesson_reader(name)
                    lesson = yaml.safe_load(lesson_source)
                    if not isinstance(lesson, dict):
                        raise ValueError(f"lesson file {name!r} must contain a mapping")
                    lessons.append(lesson)
                    lesson_sources.append(lesson_source)
                raw = dict(raw)
                raw.pop("lesson_files")
                raw["lessons"] = lessons
                hash_source = source + b"\n" + b"\n".join(lesson_sources)
            expanded = expand_compact_course(raw)
            course = Course.model_validate(expanded)
        except (yaml.YAMLError, ValidationError, KeyError, TypeError, ValueError, OSError) as error:
            raise CourseValidationError(f"invalid course structure: {error}") from error
        return cls(course, hash_source, strict_counts=strict_counts)

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
            model_used = set(objective.model.polish.token_concepts) - _PSEUDO_CONCEPTS
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
                    used = set(variant.prompt_token_concepts) - _PSEUDO_CONCEPTS
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
                    used = set(answer.token_concepts) - _PSEUDO_CONCEPTS
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
            if objective.kind is ObjectiveKind.LEXICAL:
                expected = (2, 4)
                if (cloze_count, translation_count) != expected:
                    errors.append(
                        f"objective {objective.id}: expected {expected[0]} cloze and "
                        f"{expected[1]} translation variants"
                    )
            elif objective.kind is ObjectiveKind.SYNTHESIS:
                expected = (2, 2)
                if (cloze_count, translation_count) != expected:
                    errors.append(
                        f"objective {objective.id}: expected {expected[0]} cloze and "
                        f"{expected[1]} translation variants"
                    )
            else:
                if cloze_count != 2:
                    errors.append(
                        f"objective {objective.id}: expected 2 cloze variants, "
                        f"found {cloze_count}"
                    )
                if translation_count < 1:
                    errors.append(
                        f"objective {objective.id}: expected at least one translation variant"
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
        if len(self.course.units) != EXPECTED_BUNDLED_UNIT_COUNT:
            errors.append(
                f"expected {EXPECTED_BUNDLED_UNIT_COUNT} lessons, found {len(self.course.units)}"
            )
        if len(self.course.objectives) != EXPECTED_BUNDLED_OBJECTIVE_COUNT:
            errors.append(
                f"expected {EXPECTED_BUNDLED_OBJECTIVE_COUNT} exercise sets, "
                f"found {len(self.course.objectives)}"
            )
        variant_count = sum(len(objective.variants) for objective in self.course.objectives)
        if variant_count != EXPECTED_BUNDLED_VARIANT_COUNT:
            errors.append(
                f"expected {EXPECTED_BUNDLED_VARIANT_COUNT} variants, found {variant_count}"
            )
        if self.course.concepts:
            errors.append(
                "the bundled Teach Yourself corpus should not contain legacy lexeme concepts"
            )
        for unit in self.course.units:
            if not unit.source_pages:
                errors.append(f"unit {unit.id}: missing source_pages")
            if not unit.material:
                errors.append(f"unit {unit.id}: missing lesson material")

    def _validate_dependency_order(self, errors: list[str]) -> None:
        concept_order = {concept.id: concept.order for concept in self.course.concepts}
        for objective in self.course.objectives:
            if not objective.concept_id:
                continue
            target_order = concept_order[objective.concept_id]
            late = [
                dependency
                for dependency in objective.requires_seen
                if concept_order[dependency] >= target_order
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
            if concept_id == "@literal":
                continue
            if concept_id == "@name":
                if token.casefold() not in proper_names:
                    errors.append(f"{label}: {token!r} is not an allowed proper name")
            elif concept_id.startswith("@"):
                errors.append(f"{label}: unsupported pseudo-concept {concept_id!r}")
            elif concept_id not in concept_ids:
                errors.append(f"{label}: token {token!r} maps to unknown {concept_id!r}")

    def objective_for_concept(self, concept_id: str) -> Objective:
        return self.concept_objective[concept_id]
