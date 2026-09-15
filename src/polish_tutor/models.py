from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PartOfSpeech(StrEnum):
    VERB = "verb"
    NOUN = "noun"
    ADJECTIVE = "adjective"
    PRONOUN = "pronoun"
    ADVERB = "adverb"
    PREPOSITION = "preposition"
    PARTICLE = "particle"
    NUMERAL = "numeral"


class PromptKind(StrEnum):
    CLOZE = "cloze"
    TRANSLATION = "translation"


class ObjectiveKind(StrEnum):
    LEXICAL = "lexical"
    SYNTHESIS = "synthesis"


class SelfForm(StrEnum):
    MASCULINE = "masculine"
    FEMININE = "feminine"


class Unit(FrozenModel):
    id: str
    order: int = Field(ge=1)
    title: str
    notes: tuple[str, ...] = ()


class Concept(FrozenModel):
    id: str
    order: int = Field(ge=1)
    lemma: str
    gloss: str
    part_of_speech: PartOfSpeech
    unit_id: str


class TokenConceptMap(FrozenModel):
    text: str
    token_concepts: tuple[str, ...] = ()


class ModelSentence(FrozenModel):
    english: str
    polish: TokenConceptMap


class AcceptedAnswer(TokenConceptMap):
    when_self_form: Literal["any", "masculine", "feminine"] = "any"

    def applies_to(self, self_form: SelfForm) -> bool:
        return self.when_self_form == "any" or self.when_self_form == self_form.value


class Variant(FrozenModel):
    id: str
    kind: PromptKind
    prompt: str
    prompt_token_concepts: tuple[str, ...] = ()
    context: str | None = None
    hint: str
    answers: tuple[AcceptedAnswer, ...]

    @model_validator(mode="after")
    def require_answers(self) -> Variant:
        if not self.answers:
            raise ValueError("a variant must have at least one accepted answer")
        return self

    def answers_for(self, self_form: SelfForm) -> tuple[AcceptedAnswer, ...]:
        return tuple(answer for answer in self.answers if answer.applies_to(self_form))


class Objective(FrozenModel):
    id: str
    order: int = Field(ge=1)
    unit_id: str
    kind: ObjectiveKind
    concept_id: str | None = None
    requires_seen: tuple[str, ...] = ()
    unlock_ready: tuple[str, ...] = ()
    model: ModelSentence
    variants: tuple[Variant, ...]

    @model_validator(mode="after")
    def concept_matches_kind(self) -> Objective:
        if self.kind is ObjectiveKind.LEXICAL and self.concept_id is None:
            raise ValueError("lexical objectives require concept_id")
        if self.kind is ObjectiveKind.SYNTHESIS and self.concept_id is not None:
            raise ValueError("synthesis objectives cannot introduce a concept")
        return self

    @property
    def cloze_variants(self) -> tuple[Variant, ...]:
        return tuple(variant for variant in self.variants if variant.kind is PromptKind.CLOZE)

    @property
    def translation_variants(self) -> tuple[Variant, ...]:
        return tuple(variant for variant in self.variants if variant.kind is PromptKind.TRANSLATION)


class Course(FrozenModel):
    version: int = Field(ge=1)
    title: str
    proper_names: tuple[str, ...]
    units: tuple[Unit, ...]
    concepts: tuple[Concept, ...]
    objectives: tuple[Objective, ...]
