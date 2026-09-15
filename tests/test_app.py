from __future__ import annotations

import random
from datetime import timedelta

from polish_tutor.app import (
    PauseScreen,
    PolishTutorApp,
    ResetProgressScreen,
    SetupScreen,
    StudyScreen,
)
from polish_tutor.db import Profile
from polish_tutor.engine import StudyEngine
from polish_tutor.models import SelfForm
from polish_tutor.scheduling import SchedulingService


FIRST_OBJECTIVE = "l01.read_translate"


def make_app(catalog, database, clock, *, profile: Profile | None = None, setup: bool = False):
    if profile:
        database.save_profile(profile, clock.now())
    engine = StudyEngine(
        catalog=catalog,
        database=database,
        scheduler=SchedulingService(enable_fuzzing=False),
        clock=clock,
        rng=random.Random(1),
    )
    return PolishTutorApp(
        catalog=catalog,
        database=database,
        engine=engine,
        clock=clock,
        force_setup=setup,
    )


async def test_first_run_opens_setup(catalog, database, clock) -> None:
    app = make_app(catalog, database, clock)
    async with app.run_test(size=(80, 24)):
        assert isinstance(app.screen, SetupScreen)
        assert "Polish Typing Tutor" in str(app.screen.query_one("#setup-title").render())


async def test_existing_profile_opens_book_course_and_submits_intro(
    catalog, database, clock
) -> None:
    app = make_app(catalog, database, clock, profile=Profile(SelfForm.MASCULINE))
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, StudyScreen)
        assert "Lesson 1" in str(app.screen.query_one("#phase").render())
        assert "This is a pen" in str(app.screen.query_one("#context").render())
        assert "To jest pióro" in str(app.screen.query_one("#model").render())
        answer = app.screen.query_one("#answer")
        answer.value = "To jest pióro."
        await pilot.press("enter")
        assert database.progress_for(FIRST_OBJECTIVE).introduced
        assert "Introduced" in str(app.screen.query_one("#feedback").render())


async def test_setup_mode_preserves_existing_progress(catalog, database, clock) -> None:
    profile = Profile(SelfForm.MASCULINE)
    app = make_app(catalog, database, clock, profile=profile, setup=True)
    async with app.run_test(size=(100, 32)) as pilot:
        assert isinstance(app.screen, SetupScreen)
        app.screen.query_one("#feminine").value = True
        await pilot.click("#save-setup")
        await pilot.pause()
        assert database.get_profile() == Profile(SelfForm.FEMININE)
        assert isinstance(app.screen, StudyScreen)


async def test_review_hint_and_reveal_keys(catalog, database, clock) -> None:
    profile = Profile(SelfForm.MASCULINE)
    database.save_profile(profile, clock.now())
    scheduler = SchedulingService(enable_fuzzing=False)
    progress = database.progress_for(FIRST_OBJECTIVE)
    database.introduce(FIRST_OBJECTIVE, scheduler.new_card(progress.id, clock.now()), clock.now())
    clock.advance(timedelta(seconds=20))
    app = make_app(catalog, database, clock)
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, StudyScreen)
        await pilot.press("tab")
        assert "Restore the omitted word" in str(app.screen.query_one("#feedback").render())
        await pilot.press("ctrl+r")
        assert "jest" in str(app.screen.query_one("#model").render())


async def test_status_counts_exercise_sets_for_conceptless_book_corpus(
    catalog, database, clock
) -> None:
    app = make_app(catalog, database, clock, profile=Profile(SelfForm.MASCULINE))
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, StudyScreen)
        status = str(app.screen.query_one("#status").render())
        assert "Exercise sets 0/17" in status
        assert "Ready words" not in status


async def test_pause_menu_can_delete_progress_only_after_exact_confirmation(
    catalog, database, clock
) -> None:
    profile = Profile(SelfForm.FEMININE)
    scheduler = SchedulingService(enable_fuzzing=False)
    progress = database.progress_for(FIRST_OBJECTIVE)
    database.introduce(
        FIRST_OBJECTIVE,
        scheduler.new_card(progress.id, clock.now()),
        clock.now(),
    )
    app = make_app(catalog, database, clock, profile=profile)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("escape")
        assert isinstance(app.screen, PauseScreen)
        await pilot.press("r")
        assert isinstance(app.screen, ResetProgressScreen)

        confirmation = app.screen.query_one("#reset-confirmation")
        confirmation.value = "delete"
        await pilot.press("enter")
        assert isinstance(app.screen, ResetProgressScreen)
        assert database.progress_for(FIRST_OBJECTIVE).introduced
        assert "Nothing was deleted" in str(app.screen.query_one("#reset-error").render())

        confirmation.value = "DELETE"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
        assert not database.progress_for(FIRST_OBJECTIVE).introduced
        assert database.get_profile() == profile
        assert "progress deleted" in str(app.screen.query_one("#feedback").render())
