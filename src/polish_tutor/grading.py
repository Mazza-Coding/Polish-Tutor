from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from math import inf

from polish_tutor.models import AcceptedAnswer

_FINAL_PUNCTUATION = re.compile(r"[.!?…,:;]+$")
_WHITESPACE = re.compile(r"\s+")


def normalize_answer(value: str) -> str:
    """Normalize presentation details while preserving Polish spelling and word order."""
    value = unicodedata.normalize("NFC", value).strip().casefold()
    value = _WHITESPACE.sub(" ", value)
    value = _FINAL_PUNCTUATION.sub("", value).rstrip()
    return value


class MatchKind(StrEnum):
    EXACT = "exact"
    NEAR_MISS = "near_miss"
    WORD_COUNT = "word_count"
    WORD_ORDER = "word_order"
    MISMATCH = "mismatch"


@dataclass(frozen=True)
class Comparison:
    kind: MatchKind
    expected: AcceptedAnswer
    normalized_submitted: str
    distance: int
    differing_word: int | None = None

    @property
    def exact(self) -> bool:
        return self.kind is MatchKind.EXACT

    @property
    def near_miss(self) -> bool:
        return self.kind is MatchKind.NEAR_MISS


def _damerau_levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    rows = len(left) + 1
    cols = len(right) + 1
    matrix = [[0] * cols for _ in range(rows)]
    for row in range(rows):
        matrix[row][0] = row
    for col in range(cols):
        matrix[0][col] = col
    for row in range(1, rows):
        for col in range(1, cols):
            cost = 0 if left[row - 1] == right[col - 1] else 1
            matrix[row][col] = min(
                matrix[row - 1][col] + 1,
                matrix[row][col - 1] + 1,
                matrix[row - 1][col - 1] + cost,
            )
            if (
                row > 1
                and col > 1
                and left[row - 1] == right[col - 2]
                and left[row - 2] == right[col - 1]
            ):
                matrix[row][col] = min(matrix[row][col], matrix[row - 2][col - 2] + cost)
    return matrix[-1][-1]


def _first_differing_word(submitted: str, expected: str) -> int | None:
    submitted_words = submitted.split()
    expected_words = expected.split()
    for index, (actual, wanted) in enumerate(zip(submitted_words, expected_words, strict=False)):
        if actual != wanted:
            return index
    return None


def compare_answer(submitted: str, answers: Iterable[AcceptedAnswer]) -> Comparison:
    normalized = normalize_answer(submitted)
    candidates = tuple(answers)
    if not candidates:
        raise ValueError("cannot grade without accepted answers")

    ranked: list[tuple[int, AcceptedAnswer, str]] = []
    for answer in candidates:
        expected = normalize_answer(answer.text)
        distance = _damerau_levenshtein(normalized, expected)
        ranked.append((distance, answer, expected))
    distance, answer, expected = min(ranked, key=lambda item: item[0])

    if distance == 0:
        kind = MatchKind.EXACT
    elif distance == 1:
        kind = MatchKind.NEAR_MISS
    else:
        submitted_words = normalized.split()
        expected_words = expected.split()
        if len(submitted_words) != len(expected_words):
            kind = MatchKind.WORD_COUNT
        elif sorted(submitted_words) == sorted(expected_words):
            kind = MatchKind.WORD_ORDER
        else:
            kind = MatchKind.MISMATCH
    return Comparison(
        kind=kind,
        expected=answer,
        normalized_submitted=normalized,
        distance=distance,
        differing_word=_first_differing_word(normalized, expected),
    )


def _masked_word(word: str) -> str:
    stripped = word.strip(".,!?…:;")
    if not stripped:
        return "•"
    if len(stripped) == 1:
        return stripped
    return stripped[0] + "•" * (len(stripped) - 1)


def build_hint(comparison: Comparison, authored_hint: str) -> str:
    expected = normalize_answer(comparison.expected.text)
    if comparison.kind is MatchKind.NEAR_MISS:
        word_number = (comparison.differing_word or 0) + 1
        target_word = expected.split()[word_number - 1]
        return f"Check spelling or the ending of word {word_number}: {_masked_word(target_word)}"
    if comparison.kind is MatchKind.WORD_COUNT:
        actual_count = len(comparison.normalized_submitted.split())
        expected_count = len(expected.split())
        if actual_count + 1 == expected_count:
            return "One word is missing."
        if actual_count == expected_count + 1:
            return "There is one extra word."
        return f"Check the number of words; the answer has {expected_count}."
    if comparison.kind is MatchKind.WORD_ORDER:
        return "The words are right, but their order is not."
    if comparison.differing_word is not None:
        word_number = comparison.differing_word + 1
        target_word = expected.split()[comparison.differing_word]
        return f"{authored_hint} Word {word_number} begins {_masked_word(target_word)}"
    return authored_hint


def normalized_speed(duration_ms: int, expected: str) -> float:
    characters = sum(1 for char in normalize_answer(expected) if not char.isspace())
    return duration_ms / max(1, characters)


def fastest_quintile_threshold(samples: Iterable[float]) -> float:
    values = sorted(samples)
    if len(values) < 20:
        return -inf
    index = max(0, int((len(values) - 1) * 0.2))
    return values[index]
