from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from fsrs import Rating

from polish_tutor.engine import (
    DoneItem,
    FormIntroductionItem,
    IntroductionItem,
    ReviewItem,
    SubmissionStatus,
    WaitingItem,
    answer_concepts,
    form_exposures,
)
from polish_tutor.models import PromptKind


FIRST_OBJECTIVE = "l01.read_translate"
SECOND_OBJECTIVE = "l01.into_english"


def introduce_first(engine) -> None:
    item = engine.next_item()
    assert isinstance(item, IntroductionItem)
    assert item.objective.id == FIRST_OBJECTIVE
    result = engine.submit(item.objective.model.polish.text)
    assert result.status is SubmissionStatus.COMPLETE


def test_intro_then_seconds_review(engine, clock) -> None:
    introduce_first(engine)
    next_item = engine.next_item()
    assert isinstance(next_item, IntroductionItem)
    assert next_item.objective.id == SECOND_OBJECTIVE

    clock.advance(timedelta(seconds=20))
    review = engine.next_item()
    assert isinstance(review, ReviewItem)
    assert review.objective.id == FIRST_OBJECTIVE
    assert review.variant.id == f"{FIRST_OBJECTIVE}.c1"
    result = engine.submit(review.canonical.text)
    assert result.rating is Rating.Good
    assert result.next_due == clock.now() + timedelta(minutes=2)


def test_two_clean_clozes_unlock_source_exercise_rotation(engine, database, clock) -> None:
    introduce_first(engine)
    clock.advance(timedelta(seconds=20))
    first = engine.next_item()
    assert isinstance(first, ReviewItem)
    assert first.variant.kind is PromptKind.CLOZE
    engine.submit(first.canonical.text)

    clock.advance(timedelta(minutes=2))
    second = engine.next_item()
    assert isinstance(second, ReviewItem)
    assert second.variant.id == f"{FIRST_OBJECTIVE}.c2"
    engine.submit(second.canonical.text)
    assert database.progress_for(FIRST_OBJECTIVE).clean_cloze_count == 2

    clock.advance(timedelta(minutes=15))
    mature = engine.next_item()
    assert isinstance(mature, ReviewItem)
    assert mature.variant.kind is PromptKind.TRANSLATION


def test_second_failure_reveals_and_requires_copy(engine, clock) -> None:
    introduce_first(engine)
    clock.advance(timedelta(seconds=20))
    review = engine.next_item()
    assert isinstance(review, ReviewItem)
    canonical = review.canonical.text

    assert engine.submit("wrong").status is SubmissionStatus.RETRY
    revealed = engine.submit("still wrong")
    assert revealed.status is SubmissionStatus.REVEAL
    assert revealed.canonical == canonical
    assert engine.submit("not it").status is SubmissionStatus.REVEAL
    completed = engine.submit(canonical)
    assert completed.rating is Rating.Again


def test_no_daily_limit_keeps_introducing_book_exercise_sets(engine) -> None:
    introduced_ids = []
    for _ in range(10):
        item = engine.next_item()
        assert isinstance(item, IntroductionItem)
        introduced_ids.append(item.objective.id)
        engine.submit(item.objective.model.polish.text)

    assert introduced_ids[:4] == [
        "l01.read_translate",
        "l01.into_english",
        "l01.into_polish",
        "l02.into_english",
    ]
    assert "l03.into_polish" in introduced_ids


def test_mature_rotation_uses_the_least_recent_source_item(
    engine, database, catalog, clock, monkeypatch
) -> None:
    class PredictableRandom:
        @staticmethod
        def random() -> float:
            return 0.0

        @staticmethod
        def choice(items):
            return items[0]

    objective = catalog.objectives[FIRST_OBJECTIVE]
    progress = replace(database.progress_for(objective.id), clean_cloze_count=2)
    history = {
        f"{FIRST_OBJECTIVE}.t01": (1, clock.now() - timedelta(days=1)),
        f"{FIRST_OBJECTIVE}.t02": (1, clock.now() - timedelta(days=4)),
        f"{FIRST_OBJECTIVE}.t03": (1, clock.now() - timedelta(days=3)),
        f"{FIRST_OBJECTIVE}.t04": (1, clock.now() - timedelta(days=2)),
        f"{FIRST_OBJECTIVE}.t05": (1, clock.now() - timedelta(hours=20)),
        f"{FIRST_OBJECTIVE}.t06": (1, clock.now() - timedelta(hours=19)),
        f"{FIRST_OBJECTIVE}.t07": (1, clock.now() - timedelta(hours=18)),
        f"{FIRST_OBJECTIVE}.t08": (1, clock.now() - timedelta(hours=17)),
    }
    monkeypatch.setattr(database, "variant_history", lambda _objective_id: history)
    engine.rng = PredictableRandom()

    variant = engine._choose_variant(objective, progress)

    assert variant.id == f"{FIRST_OBJECTIVE}.t02"


def test_fast_clean_answer_can_become_easy_after_calibration(engine, database, clock) -> None:
    introduce_first(engine)
    with database.transaction() as connection:
        connection.executemany(
            """
            INSERT INTO review_log(
                objective_id, variant_id, rating, answer_class, attempt_count,
                first_try, hint_used, duration_ms, normalized_ms_per_char,
                reviewed_at, fsrs_log_json
            ) VALUES ('sample', 'sample', 3, 'exact', 1, 1, 0, 1000, 500.0, ?, '{}')
            """,
            [(clock.now().isoformat(),)] * 20,
        )
    clock.advance(timedelta(seconds=20))
    review = engine.next_item()
    assert isinstance(review, ReviewItem)
    clock.advance(timedelta(milliseconds=100))
    result = engine.submit(review.canonical.text)
    assert result.rating is Rating.Easy


def test_literal_source_tokens_do_not_create_fake_forms_or_dependencies(catalog) -> None:
    objective = catalog.objectives[FIRST_OBJECTIVE]
    assert form_exposures(objective.model.polish) == frozenset()
    for variant in objective.variants:
        for answer in variant.answers:
            assert answer_concepts(answer) == frozenset()
            assert form_exposures(answer) == frozenset()


def test_literal_corpus_does_not_trigger_new_form_copy_screen(engine, clock) -> None:
    introduce_first(engine)
    clock.advance(timedelta(seconds=20))
    item = engine.next_item()
    assert isinstance(item, ReviewItem)
    assert not isinstance(item, FormIntroductionItem)


def test_full_book_scope_progression_never_tests_a_pseudo_form(engine, database, clock) -> None:
    form_introductions = 0

    for _ in range(1_500):
        item = engine.next_item()
        if isinstance(item, IntroductionItem):
            clock.advance(timedelta(seconds=4))
            engine.submit(item.objective.model.polish.text)
        elif isinstance(item, FormIntroductionItem):
            form_introductions += 1
            clock.advance(timedelta(seconds=4))
            engine.submit(item.answer.text)
        elif isinstance(item, ReviewItem):
            clock.advance(timedelta(seconds=4))
            engine.submit(item.canonical.text)
        else:
            assert isinstance(item, (WaitingItem, DoneItem))
            assert all(progress.introduced for progress in database.all_progress())
            break
    else:
        raise AssertionError("the complete Lessons 1–7 progression stalled")

    assert form_introductions == 0
