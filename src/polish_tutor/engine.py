from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from fsrs import Rating

from polish_tutor.course import CourseCatalog, polish_tokens
from polish_tutor.db import CardProgress, Database, Profile
from polish_tutor.grading import (
    Comparison,
    MatchKind,
    build_hint,
    compare_answer,
    fastest_quintile_threshold,
    normalized_speed,
)
from polish_tutor.models import (
    AcceptedAnswer,
    Objective,
    PromptKind,
    TokenConceptMap,
    Variant,
)
from polish_tutor.scheduling import Clock, SchedulingService, format_interval

WAIT_WINDOW = timedelta(seconds=30)


class ItemKind(StrEnum):
    INTRODUCTION = "introduction"
    FORM_INTRODUCTION = "form_introduction"
    REVIEW = "review"
    WAITING = "waiting"
    DONE = "done"


@dataclass(frozen=True)
class IntroductionItem:
    kind: ItemKind
    objective: Objective


@dataclass(frozen=True)
class FormIntroductionItem:
    kind: ItemKind
    objective: Objective
    progress: CardProgress
    variant: Variant
    answer: AcceptedAnswer


@dataclass(frozen=True)
class ReviewItem:
    kind: ItemKind
    objective: Objective
    progress: CardProgress
    variant: Variant
    answers: tuple[AcceptedAnswer, ...]

    @property
    def canonical(self) -> AcceptedAnswer:
        return self.answers[0]


@dataclass(frozen=True)
class WaitingItem:
    kind: ItemKind
    due: datetime
    seconds: int


@dataclass(frozen=True)
class DoneItem:
    kind: ItemKind
    next_due: datetime | None


StudyItem = IntroductionItem | FormIntroductionItem | ReviewItem | WaitingItem | DoneItem


class SubmissionStatus(StrEnum):
    RETRY = "retry"
    REVEAL = "reveal"
    COMPLETE = "complete"


@dataclass(frozen=True)
class SubmissionResult:
    status: SubmissionStatus
    message: str
    canonical: str | None = None
    rating: Rating | None = None
    next_due: datetime | None = None


@dataclass(frozen=True)
class StudyStatus:
    due_now: int
    introduced_concepts: int
    ready_concepts: int
    total_concepts: int


class StudyEngine:
    def __init__(
        self,
        *,
        catalog: CourseCatalog,
        database: Database,
        scheduler: SchedulingService,
        clock: Clock,
        rng: random.Random | None = None,
    ) -> None:
        self.catalog = catalog
        self.database = database
        self.scheduler = scheduler
        self.clock = clock
        self.rng = rng or random.Random()
        self.current: IntroductionItem | FormIntroductionItem | ReviewItem | None = None
        self.started_at: datetime | None = None
        self.wrong_attempts = 0
        self.voluntary_hint = False
        self.revealed = False
        self.first_mismatch: Comparison | None = None

    @property
    def profile(self) -> Profile:
        profile = self.database.get_profile()
        if profile is None:
            raise RuntimeError("onboarding must be completed before studying")
        return profile

    def status(self) -> StudyStatus:
        now = self.clock.now()
        introduced = self.database.introduced_concepts(self.catalog)
        ready = self.database.ready_concepts(self.catalog)
        return StudyStatus(
            due_now=len(self.database.due_progress(now)),
            introduced_concepts=len(introduced),
            ready_concepts=len(ready),
            total_concepts=len(self.catalog.course.concepts),
        )

    def next_item(self) -> StudyItem:
        self._reset_attempt()
        now = self.clock.now()
        due = self.database.due_progress(now)
        if due:
            progress = due[0]
            objective = self.catalog.objectives[progress.objective_id]
            variant = self._choose_variant(objective, progress)
            answers = self._eligible_answers(variant)
            known = self._known_forms()
            known_answers = tuple(
                answer for answer in answers if form_exposures(answer).issubset(known)
            )
            if known_answers:
                unknown_answers = tuple(answer for answer in answers if answer not in known_answers)
                item: FormIntroductionItem | ReviewItem = ReviewItem(
                    ItemKind.REVIEW,
                    objective,
                    progress,
                    variant,
                    known_answers + unknown_answers,
                )
            else:
                item = FormIntroductionItem(
                    ItemKind.FORM_INTRODUCTION,
                    objective,
                    progress,
                    variant,
                    answers[0],
                )
            self.current = item
            self.started_at = now
            return item

        objective = self._next_new_objective()
        if objective is not None:
            item = IntroductionItem(ItemKind.INTRODUCTION, objective)
            self.current = item
            self.started_at = now
            return item

        next_due = self.database.next_due()
        if next_due is not None and next_due <= now + WAIT_WINDOW:
            seconds = max(0, round((next_due - now).total_seconds()))
            return WaitingItem(ItemKind.WAITING, next_due, seconds)
        return DoneItem(ItemKind.DONE, next_due)

    def _next_new_objective(self) -> Objective | None:
        progress = {item.objective_id: item for item in self.database.all_progress()}
        introduced = self.database.introduced_concepts(self.catalog)
        for objective in self.catalog.objectives_in_order:
            if progress[objective.id].introduced:
                continue
            if set(objective.requires_seen).issubset(introduced):
                return objective
        return None

    def _choose_variant(self, objective: Objective, progress: CardProgress) -> Variant:
        if progress.pending_variant_id:
            return next(
                variant
                for variant in objective.variants
                if variant.id == progress.pending_variant_id
            )
        if progress.clean_cloze_count < 2:
            return objective.cloze_variants[progress.clean_cloze_count]

        ready = self.database.ready_concepts(self.catalog)
        translations = tuple(
            variant
            for variant in objective.translation_variants
            if any(
                answer_concepts(answer).issubset(ready)
                for answer in variant.answers_for(self.profile.self_form)
            )
        )
        if translations and self.rng.random() < 0.7:
            pool = translations
        else:
            pool = objective.cloze_variants

        history = self.database.variant_history(objective.id)
        minimum = min(history.get(item.id, (0, None))[0] for item in pool)
        least_seen = [item for item in pool if history.get(item.id, (0, None))[0] == minimum]
        if any(history.get(item.id, (0, None))[1] is None for item in least_seen):
            least_recent = [
                item for item in least_seen if history.get(item.id, (0, None))[1] is None
            ]
        else:
            oldest = min(history[item.id][1] for item in least_seen)
            least_recent = [item for item in least_seen if history[item.id][1] == oldest]
        least_recent.sort(key=lambda item: item.id)
        return self.rng.choice(least_recent)

    def _eligible_answers(self, variant: Variant) -> tuple[AcceptedAnswer, ...]:
        answers = variant.answers_for(self.profile.self_form)
        if variant.kind is PromptKind.TRANSLATION:
            ready = self.database.ready_concepts(self.catalog)
            answers = tuple(answer for answer in answers if answer_concepts(answer).issubset(ready))
        if not answers:
            raise RuntimeError(f"variant {variant.id} has no eligible accepted answer")
        return answers

    def submit(self, submitted: str) -> SubmissionResult:
        if self.current is None or self.started_at is None:
            raise RuntimeError("there is no active study item")
        if isinstance(self.current, IntroductionItem):
            return self._submit_introduction(submitted)
        if isinstance(self.current, FormIntroductionItem):
            return self._submit_form_introduction(submitted)
        return self._submit_review(submitted)

    def _submit_introduction(self, submitted: str) -> SubmissionResult:
        assert isinstance(self.current, IntroductionItem)
        model = self.current.objective.model
        expected = AcceptedAnswer(
            text=model.polish.text,
            token_concepts=model.polish.token_concepts,
        )
        comparison = compare_answer(submitted, (expected,))
        if not comparison.exact:
            return SubmissionResult(
                SubmissionStatus.RETRY,
                "Copy the visible Polish sentence exactly; diacritics matter.",
            )
        now = self.clock.now()
        progress = self.database.progress_for(self.current.objective.id)
        card = self.scheduler.new_card(progress.id, now)
        self.database.introduce(
            self.current.objective.id,
            card,
            now,
            exposures=form_exposures(model.polish),
        )
        self.current = None
        return SubmissionResult(
            SubmissionStatus.COMPLETE,
            f"Introduced — first recall in {format_interval(card.due - now)}.",
            canonical=model.polish.text,
            next_due=card.due,
        )

    def _submit_form_introduction(self, submitted: str) -> SubmissionResult:
        assert isinstance(self.current, FormIntroductionItem)
        comparison = compare_answer(submitted, (self.current.answer,))
        if not comparison.exact:
            return SubmissionResult(
                SubmissionStatus.RETRY,
                "Copy the visible Polish form exactly; diacritics matter.",
            )
        assert self.current.progress.card is not None
        now = self.clock.now()
        card = self.scheduler.defer_for_form_recall(self.current.progress.card, now)
        self.database.record_form_introduction(
            objective_id=self.current.objective.id,
            variant_id=self.current.variant.id,
            card=card,
            exposures=form_exposures(self.current.answer),
            introduced_at=now,
        )
        canonical = self.current.answer.text
        self.current = None
        return SubmissionResult(
            SubmissionStatus.COMPLETE,
            f"New form introduced — recall in {format_interval(card.due - now)}.",
            canonical=canonical,
            next_due=card.due,
        )

    def _submit_review(self, submitted: str) -> SubmissionResult:
        assert isinstance(self.current, ReviewItem)
        comparison = compare_answer(submitted, self.current.answers)
        if comparison.exact:
            if self.revealed:
                rating = Rating.Again
            elif self.wrong_attempts:
                rating = (
                    Rating.Hard
                    if self.first_mismatch and self.first_mismatch.near_miss
                    else Rating.Again
                )
            elif self.voluntary_hint:
                rating = Rating.Hard
            else:
                rating = self._clean_rating(comparison.expected.text)
            return self._finish_review(rating, comparison)

        if self.revealed:
            return SubmissionResult(
                SubmissionStatus.REVEAL,
                "The answer is still visible. Type it exactly to continue.",
                canonical=self.current.canonical.text,
            )

        self.wrong_attempts += 1
        if self.first_mismatch is None:
            self.first_mismatch = comparison
        if self.wrong_attempts == 1:
            return SubmissionResult(
                SubmissionStatus.RETRY,
                build_hint(comparison, self.current.variant.hint),
            )

        self.revealed = True
        return SubmissionResult(
            SubmissionStatus.REVEAL,
            "Here is the target. Type it exactly once to continue.",
            canonical=self.current.canonical.text,
        )

    def _clean_rating(self, expected: str) -> Rating:
        assert self.started_at is not None
        duration_ms = max(0, round((self.clock.now() - self.started_at).total_seconds() * 1000))
        speed = normalized_speed(duration_ms, expected)
        threshold = fastest_quintile_threshold(self.database.clean_speed_samples())
        return Rating.Easy if speed <= threshold else Rating.Good

    def _finish_review(self, rating: Rating, comparison: Comparison) -> SubmissionResult:
        assert isinstance(self.current, ReviewItem)
        assert self.current.progress.card is not None
        assert self.started_at is not None
        now = self.clock.now()
        duration_ms = max(0, round((now - self.started_at).total_seconds() * 1000))
        card, log = self.scheduler.review(
            self.current.progress.card,
            rating,
            now,
            duration_ms,
        )
        first_try = self.wrong_attempts == 0
        hint_used = self.voluntary_hint or self.wrong_attempts > 0 or self.revealed
        clean_cloze = (
            self.current.variant.kind is PromptKind.CLOZE
            and first_try
            and not hint_used
            and rating in (Rating.Good, Rating.Easy)
        )
        answer_class = (
            self.first_mismatch.kind.value if self.first_mismatch else MatchKind.EXACT.value
        )
        self.database.record_review(
            objective_id=self.current.objective.id,
            variant_id=self.current.variant.id,
            card=card,
            review_log=log,
            rating=rating,
            answer_class=answer_class,
            attempt_count=self.wrong_attempts + 1,
            first_try=first_try,
            hint_used=hint_used,
            duration_ms=duration_ms,
            normalized_ms_per_char=normalized_speed(duration_ms, comparison.expected.text),
            reviewed_at=now,
            clean_cloze_increment=clean_cloze,
            exposures=form_exposures(comparison.expected),
        )
        canonical = comparison.expected.text
        interval = format_interval(card.due - now)
        self.current = None
        return SubmissionResult(
            SubmissionStatus.COMPLETE,
            f"{rating.name} — next review in {interval}.",
            canonical=canonical,
            rating=rating,
            next_due=card.due,
        )

    def request_hint(self) -> SubmissionResult | None:
        if not isinstance(self.current, ReviewItem) or self.revealed:
            return None
        self.voluntary_hint = True
        return SubmissionResult(
            SubmissionStatus.RETRY,
            self.current.variant.hint,
        )

    def reveal(self) -> SubmissionResult | None:
        if not isinstance(self.current, ReviewItem):
            return None
        self.revealed = True
        return SubmissionResult(
            SubmissionStatus.REVEAL,
            "Type the revealed answer exactly once to continue.",
            canonical=self.current.canonical.text,
        )

    def _reset_attempt(self) -> None:
        self.current = None
        self.started_at = None
        self.wrong_attempts = 0
        self.voluntary_hint = False
        self.revealed = False
        self.first_mismatch = None

    def _known_forms(self) -> set[tuple[str, str]]:
        known = self.database.known_forms()
        progress = {item.objective_id: item for item in self.database.all_progress()}
        for objective in self.catalog.objectives_in_order:
            if progress[objective.id].introduced:
                known.update(form_exposures(objective.model.polish))
        return known


def form_exposures(mapping: TokenConceptMap) -> frozenset[tuple[str, str]]:
    """Return normalized concept/form pairs that have been productively shown."""
    return frozenset(
        (concept_id, unicodedata.normalize("NFC", token).casefold())
        for token, concept_id in zip(
            polish_tokens(mapping.text), mapping.token_concepts, strict=True
        )
        if not concept_id.startswith("@")
    )


def answer_concepts(mapping: TokenConceptMap) -> frozenset[str]:
    return frozenset(
        concept_id for concept_id in mapping.token_concepts if not concept_id.startswith("@")
    )
