from __future__ import annotations

import unicodedata

import pytest

from polish_tutor.grading import (
    MatchKind,
    build_hint,
    compare_answer,
    fastest_quintile_threshold,
    normalize_answer,
    normalized_speed,
)
from polish_tutor.models import AcceptedAnswer


def accepted(text: str) -> AcceptedAnswer:
    return AcceptedAnswer(text=text, token_concepts=())


def test_normalization_ignores_presentation_but_not_diacritics() -> None:
    assert normalize_answer("  MAM   CZAS?! ") == "mam czas"
    decomposed = unicodedata.normalize("NFD", "chcę")
    assert normalize_answer(decomposed) == "chcę"
    assert normalize_answer("moge") != normalize_answer("mogę")


def test_exact_and_near_miss_classification() -> None:
    target = accepted("Mogę być tutaj.")
    assert compare_answer("mogę być tutaj", (target,)).kind is MatchKind.EXACT
    assert compare_answer("moge być tutaj", (target,)).kind is MatchKind.NEAR_MISS
    assert compare_answer("mogę tutaj być", (target,)).kind is MatchKind.WORD_ORDER
    assert compare_answer("mogę być", (target,)).kind is MatchKind.WORD_COUNT


def test_closest_accepted_alternative_drives_feedback() -> None:
    answers = (accepted("Wczoraj byłem w pracy."), accepted("Wczoraj byłam w pracy."))
    result = compare_answer("Wczoraj bylam w pracy", answers)
    assert result.kind is MatchKind.NEAR_MISS
    assert result.expected.text == "Wczoraj byłam w pracy."
    assert "word 2" in build_hint(result, "Use the selected form.").casefold()


def test_speed_only_unlocks_easy_after_twenty_samples() -> None:
    assert fastest_quintile_threshold([100.0] * 19) == float("-inf")
    threshold = fastest_quintile_threshold([float(value) for value in range(100, 300, 10)])
    assert threshold == 130.0
    assert normalized_speed(800, "Mam czas") == pytest.approx(800 / 7)
