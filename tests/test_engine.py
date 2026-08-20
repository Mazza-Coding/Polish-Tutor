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
    form_exposures,
)
from polish_tutor.models import PromptKind


def introduce_first(engine) -> None:
    item = engine.next_item()
    assert isinstance(item, IntroductionItem)
    result = engine.submit(item.objective.model.polish.text)
    assert result.status is SubmissionStatus.COMPLETE


def test_intro_then_seconds_review(engine, clock) -> None:
    introduce_first(engine)
    next_item = engine.next_item()
    assert isinstance(next_item, IntroductionItem)
    assert next_item.objective.id == "lex.nie"

    clock.advance(timedelta(seconds=20))
    review = engine.next_item()
    assert isinstance(review, ReviewItem)
    assert review.objective.id == "lex.tak"
    assert review.variant.id == "lex.tak.c1"
    result = engine.submit(review.canonical.text)
    assert result.rating is Rating.Good
    assert result.next_due == clock.now() + timedelta(minutes=2)


def test_two_clean_clozes_make_concept_ready_and_unlock_translation(
    engine, database, clock
) -> None:
    introduce_first(engine)
    clock.advance(timedelta(seconds=20))
    first = engine.next_item()
    assert isinstance(first, ReviewItem)
    engine.submit(first.canonical.text)
    clock.advance(timedelta(minutes=2))
    second = engine.next_item()
    assert isinstance(second, ReviewItem)
    assert second.variant.id == "lex.tak.c2"
    engine.submit(second.canonical.text)
    assert "tak" in database.ready_concepts(engine.catalog)

    clock.advance(timedelta(minutes=15))
    mature = engine.next_item()
    assert isinstance(mature, ReviewItem)
    assert mature.variant.kind is PromptKind.TRANSLATION


def test_near_miss_is_hard_after_correction(engine, clock) -> None:
    introduce_first(engine)
    clock.advance(timedelta(seconds=20))
    review = engine.next_item()
    assert isinstance(review, ReviewItem)
    retry = engine.submit("Tąk")
    assert retry.status is SubmissionStatus.RETRY
    completed = engine.submit("Tak")
    assert completed.rating is Rating.Hard


def test_second_failure_reveals_and_requires_copy(engine, clock) -> None:
    introduce_first(engine)
    clock.advance(timedelta(seconds=20))
    review = engine.next_item()
    assert isinstance(review, ReviewItem)
    assert engine.submit("Nie").status is SubmissionStatus.RETRY
    revealed = engine.submit("Może")
    assert revealed.status is SubmissionStatus.REVEAL
    assert revealed.canonical == "Tak"
    still_wrong = engine.submit("takkk")
    assert still_wrong.status is SubmissionStatus.REVEAL
    completed = engine.submit("Tak")
    assert completed.rating is Rating.Again


def test_no_daily_limit_keeps_introducing_synthesis_and_lexical_material(engine) -> None:
    introduced_ids = []
    for _ in range(25):
        item = engine.next_item()
        assert isinstance(item, IntroductionItem)
        introduced_ids.append(item.objective.id)
        engine.submit(item.objective.model.polish.text)

    assert introduced_ids[9] == "lex.moc"
    assert introduced_ids[10].startswith("syn.u01.1")
    assert introduced_ids[11].startswith("syn.u01.2")
    assert introduced_ids[12] == "lex.on"


def test_early_synthesis_stays_on_cloze_until_translation_words_are_ready(
    engine, database, catalog
) -> None:
    objective = catalog.objectives["syn.u01.1.modal_negation"]
    progress = replace(database.progress_for(objective.id), clean_cloze_count=2)

    variant = engine._choose_variant(objective, progress)

    assert variant.kind is PromptKind.CLOZE


def test_mature_rotation_uses_the_least_recent_context(
    engine, database, catalog, clock, monkeypatch
) -> None:
    class PredictableRandom:
        @staticmethod
        def random() -> float:
            return 0.0

        @staticmethod
        def choice(items):
            return items[0]

    objective = catalog.objectives["lex.tak"]
    progress = replace(database.progress_for(objective.id), clean_cloze_count=2)
    history = {
        "lex.tak.t1": (1, clock.now() - timedelta(days=1)),
        "lex.tak.t2": (1, clock.now() - timedelta(days=4)),
        "lex.tak.t3": (1, clock.now() - timedelta(days=3)),
        "lex.tak.t4": (1, clock.now() - timedelta(days=2)),
    }
    monkeypatch.setattr(database, "ready_concepts", lambda _catalog: frozenset(catalog.concepts))
    monkeypatch.setattr(database, "variant_history", lambda _objective_id: history)
    engine.rng = PredictableRandom()

    variant = engine._choose_variant(objective, progress)

    assert variant.id == "lex.tak.t2"


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


def test_unseen_inflection_is_taught_before_it_is_tested(engine, database, catalog, clock) -> None:
    objective = catalog.objectives["lex.byc"]
    progress = database.progress_for(objective.id)
    card = engine.scheduler.new_card(progress.id, clock.now())
    database.introduce(
        objective.id,
        card,
        clock.now(),
        exposures=form_exposures(objective.model.polish),
    )

    clock.advance(timedelta(seconds=20))
    first_cloze = engine.next_item()
    assert isinstance(first_cloze, ReviewItem)
    assert first_cloze.variant.id == "lex.byc.c1"
    assert engine.submit("jest").rating is Rating.Good

    clock.advance(timedelta(minutes=2))
    new_form = engine.next_item()
    assert isinstance(new_form, FormIntroductionItem)
    assert new_form.variant.id == "lex.byc.c2"
    assert new_form.answer.text == "jestem"
    assert engine.submit("jestm").status is SubmissionStatus.RETRY

    introduced = engine.submit("jestem")
    assert introduced.status is SubmissionStatus.COMPLETE
    assert introduced.next_due == clock.now() + timedelta(seconds=20)
    assert ("byc", "jestem") in database.known_forms()
    assert database.progress_for(objective.id).clean_cloze_count == 1
    assert database.progress_for(objective.id).pending_variant_id == "lex.byc.c2"

    clock.advance(timedelta(seconds=20))
    recall = engine.next_item()
    assert isinstance(recall, ReviewItem)
    assert recall.variant.id == "lex.byc.c2"
    assert engine.submit("jestem").rating is Rating.Good
    updated = database.progress_for(objective.id)
    assert updated.clean_cloze_count == 2
    assert updated.pending_variant_id is None


def test_full_course_progression_never_tests_an_unseen_form(engine, database, clock) -> None:
    form_introductions = 0

    for _ in range(2_000):
        item = engine.next_item()
        if isinstance(item, IntroductionItem):
            clock.advance(timedelta(seconds=4))
            engine.submit(item.objective.model.polish.text)
        elif isinstance(item, FormIntroductionItem):
            form_introductions += 1
            assert not form_exposures(item.answer).issubset(engine._known_forms())
            clock.advance(timedelta(seconds=4))
            result = engine.submit(item.answer.text)
            assert result.next_due is not None
        elif isinstance(item, ReviewItem):
            known = engine._known_forms()
            assert any(form_exposures(answer).issubset(known) for answer in item.answers)
            clock.advance(timedelta(seconds=4))
            engine.submit(item.canonical.text)
        else:
            assert isinstance(item, (WaitingItem, DoneItem))
            assert all(progress.introduced for progress in database.all_progress())
            break
    else:
        raise AssertionError("the complete course progression stalled")

    assert form_introductions > 0
