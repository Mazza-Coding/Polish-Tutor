from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fsrs import Rating, State

from polish_tutor.scheduling import SchedulingService, format_interval


def test_learning_steps_move_from_seconds_to_days() -> None:
    scheduler = SchedulingService(enable_fuzzing=False)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    card = scheduler.new_card(1, now)
    assert card.due - now == timedelta(seconds=20)

    expected = [
        timedelta(minutes=2),
        timedelta(minutes=15),
        timedelta(hours=2),
        timedelta(hours=12),
        timedelta(days=2),
    ]
    now = card.due
    for interval in expected:
        card, _ = scheduler.review(card, Rating.Good, now, 1000)
        assert card.due - now == interval
        now = card.due
    assert card.state is State.Review


def test_mature_lapse_starts_with_seconds() -> None:
    scheduler = SchedulingService(enable_fuzzing=False)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    card = scheduler.new_card(1, now)
    for _ in range(5):
        now = card.due
        card, _ = scheduler.review(card, Rating.Good, now, 1000)
    assert card.state is State.Review
    now = card.due
    card, _ = scheduler.review(card, Rating.Again, now, 1000)
    assert card.state is State.Relearning
    assert card.due - now == timedelta(seconds=30)


def test_form_introduction_defers_without_mutating_fsrs_state() -> None:
    scheduler = SchedulingService(enable_fuzzing=False)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    card = scheduler.new_card(1, now)
    original_due = card.due

    taught_at = now + timedelta(minutes=2)
    deferred = scheduler.defer_for_form_recall(card, taught_at)

    assert card.due == original_due
    assert deferred.due == taught_at + timedelta(seconds=20)
    assert deferred.state == card.state
    assert deferred.step == card.step


def test_interval_labels() -> None:
    assert format_interval(timedelta(seconds=20)) == "20s"
    assert format_interval(timedelta(minutes=15)) == "15m"
    assert format_interval(timedelta(hours=12)) == "12h"
    assert format_interval(timedelta(days=14)) == "14d"
