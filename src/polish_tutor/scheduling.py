from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fsrs import Card, Rating, ReviewLog, Scheduler

LEARNING_STEPS = (
    timedelta(seconds=20),
    timedelta(minutes=2),
    timedelta(minutes=15),
    timedelta(hours=2),
    timedelta(hours=12),
)
RELEARNING_STEPS = (
    timedelta(seconds=30),
    timedelta(minutes=5),
    timedelta(hours=1),
)
FORM_RECALL_DELAY = timedelta(seconds=20)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class SchedulingService:
    def __init__(self, *, enable_fuzzing: bool = True) -> None:
        self.scheduler = Scheduler(
            desired_retention=0.9,
            learning_steps=LEARNING_STEPS,
            relearning_steps=RELEARNING_STEPS,
            maximum_interval=3650,
            enable_fuzzing=enable_fuzzing,
        )

    def new_card(self, card_id: int, now: datetime) -> Card:
        self._require_utc(now)
        return Card(card_id=card_id, due=now + LEARNING_STEPS[0])

    def review(
        self,
        card: Card,
        rating: Rating,
        now: datetime,
        duration_ms: int,
    ) -> tuple[Card, ReviewLog]:
        self._require_utc(now)
        return self.scheduler.review_card(
            card,
            rating,
            review_datetime=now,
            review_duration=max(0, duration_ms),
        )

    def defer_for_form_recall(self, card: Card, now: datetime) -> Card:
        """Keep FSRS state intact while placing a just-taught form 20 seconds ahead."""
        self._require_utc(now)
        deferred = Card.from_json(card.to_json())
        deferred.due = now + FORM_RECALL_DELAY
        return deferred

    @staticmethod
    def _require_utc(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("scheduler datetimes must be timezone-aware UTC")


def format_interval(delta: timedelta) -> str:
    seconds = max(0, round(delta.total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = round(minutes / 60)
    if hours < 48:
        return f"{hours}h"
    days = round(hours / 24)
    if days < 60:
        return f"{days}d"
    months = round(days / 30.44)
    if months < 24:
        return f"{months}mo"
    years = round(days / 365.25, 1)
    return f"{years:g}y"
