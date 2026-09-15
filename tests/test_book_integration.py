from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from polish_tutor.app import PolishTutorApp, StudyScreen
from polish_tutor.course import CourseCatalog
from polish_tutor.db import Profile
from polish_tutor.engine import (
    DoneItem,
    FormIntroductionItem,
    IntroductionItem,
    ReviewItem,
    WaitingItem,
    form_exposures,
)
from polish_tutor.models import SelfForm
from polish_tutor.notes import LessonNotesScreen


@pytest.fixture(scope="session")
def catalog() -> CourseCatalog:
    return CourseCatalog.load_bundled()


def test_old_progress_is_retained_but_not_scheduled(database, catalog, clock) -> None:
    legacy = CourseCatalog.load_path(
        Path(__file__).parent / "fixtures" / "legacy_course_v1.yaml"
    )
    database.sync_course(legacy, clock.now())
    profile = Profile(SelfForm.FEMININE)
    database.save_profile(profile, clock.now())
    with database.transaction() as connection:
        connection.execute(
            "UPDATE card_progress SET introduced_at = ?, clean_cloze_count = 2 "
            "WHERE objective_id = 'lex.tak'",
            (clock.now().isoformat(),),
        )
    database.sync_course(catalog, clock.now())
    old = database.progress_for("lex.tak")
    assert old.introduced and old.ready and not old.active
    assert database.get_profile() == profile
    assert len(database.all_progress()) == 634
    assert not any(item.introduced for item in database.all_progress())
    assert not database.introduced_concepts(catalog)
    database.sync_course(catalog, clock.now())
    assert len(database.all_progress()) == 634
    assert len(database.all_progress(active_only=False)) == 754


def test_book_progression_does_not_test_unknown_forms(engine, database, clock) -> None:
    introductions = 0
    new_forms = 0
    for _ in range(15000):
        item = engine.next_item()
        if isinstance(item, IntroductionItem):
            introductions += 1
            engine.submit(item.objective.model.polish.text)
        elif isinstance(item, FormIntroductionItem):
            new_forms += 1
            assert not form_exposures(item.answer).issubset(engine._known_forms())
            engine.submit(item.answer.text)
        elif isinstance(item, ReviewItem):
            assert any(
                form_exposures(answer).issubset(engine._known_forms()) for answer in item.answers
            )
            engine.submit(item.canonical.text)
        else:
            assert isinstance(item, (WaitingItem, DoneItem))
            if all(progress.introduced for progress in database.all_progress()):
                break
            due = database.next_due()
            assert due is not None
            clock.advance(max(due - clock.now(), timedelta(seconds=1)))
            continue
        clock.advance(timedelta(seconds=1))
    else:
        raise AssertionError("textbook progression stalled")
    assert introductions == 634
    assert new_forms > 0


async def test_lesson_notes_return_to_same_answer_and_mark_review_assisted(
    catalog, database, engine, clock
) -> None:
    app = PolishTutorApp(catalog=catalog, database=database, engine=engine, clock=clock)
    async with app.run_test(size=(80, 24)) as pilot:
        assert isinstance(app.screen, StudyScreen)
        first = app.screen.item
        assert isinstance(first, IntroductionItem)
        engine.submit(first.objective.model.polish.text)
        clock.advance(timedelta(seconds=20))
        app.screen.show_next()
        assert isinstance(app.screen.item, ReviewItem)
        original = app.screen.item
        app.screen.query_one("#answer").value = "partial"
        await pilot.press("f2")
        assert isinstance(app.screen, LessonNotesScreen)
        assert engine.voluntary_hint
        await pilot.press("escape")
        assert isinstance(app.screen, StudyScreen)
        assert app.screen.item is original
        assert app.screen.query_one("#answer").value == "partial"
