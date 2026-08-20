from __future__ import annotations

import random
from datetime import timedelta

from fsrs import Rating

from polish_tutor.app import (
    PauseScreen,
    PolishTutorApp,
    ResetProgressScreen,
    SetupScreen,
    StudyScreen,
)
from polish_tutor.db import Profile
from polish_tutor.engine import StudyEngine, form_exposures
from polish_tutor.models import SelfForm
from polish_tutor.scheduling import SchedulingService


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


async def test_existing_profile_opens_study_and_submits_intro(catalog, database, clock) -> None:
    app = make_app(catalog, database, clock, profile=Profile(SelfForm.MASCULINE))
    async with app.run_test(size=(80, 24)) as pilot:
        assert isinstance(app.screen, StudyScreen)
        answer = app.screen.query_one("#answer")
        answer.value = "Tak."
        await pilot.press("enter")
        assert database.progress_for("lex.tak").introduced
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
    progress = database.progress_for("lex.tak")
    database.introduce("lex.tak", scheduler.new_card(progress.id, clock.now()), clock.now())
    clock.advance(timedelta(seconds=20))
    app = make_app(catalog, database, clock)
    async with app.run_test(size=(80, 24)) as pilot:
        assert isinstance(app.screen, StudyScreen)
        await pilot.press("tab")
        assert "affirmative" in str(app.screen.query_one("#feedback").render()).casefold()
        await pilot.press("ctrl+r")
        assert "Tak" in str(app.screen.query_one("#model").render())


async def test_unseen_inflection_uses_new_form_copy_screen(catalog, database, clock) -> None:
    objective = catalog.objectives["lex.byc"]
    scheduler = SchedulingService(enable_fuzzing=False)
    progress = database.progress_for(objective.id)
    card = scheduler.new_card(progress.id, clock.now())
    database.introduce(
        objective.id,
        card,
        clock.now(),
        exposures=form_exposures(objective.model.polish),
    )
    clock.advance(timedelta(seconds=20))
    card, log = scheduler.review(card, Rating.Good, clock.now(), 500)
    database.record_review(
        objective_id=objective.id,
        variant_id="lex.byc.c1",
        card=card,
        review_log=log,
        rating=Rating.Good,
        answer_class="exact",
        attempt_count=1,
        first_try=True,
        hint_used=False,
        duration_ms=500,
        normalized_ms_per_char=125.0,
        reviewed_at=clock.now(),
        clean_cloze_increment=True,
        exposures=(("byc", "jest"),),
    )
    clock.advance(timedelta(minutes=2))

    app = make_app(catalog, database, clock, profile=Profile(SelfForm.MASCULINE))
    async with app.run_test(size=(80, 24)) as pilot:
        assert isinstance(app.screen, StudyScreen)
        assert "NEW FORM" in str(app.screen.query_one("#phase").render())
        assert "jestem" in str(app.screen.query_one("#model").render())
        answer = app.screen.query_one("#answer")
        answer.value = "jestem"
        await pilot.press("enter")
        assert "recall in 20s" in str(app.screen.query_one("#feedback").render())


async def test_pause_menu_can_delete_progress_only_after_exact_confirmation(
    catalog, database, clock
) -> None:
    profile = Profile(SelfForm.FEMININE)
    scheduler = SchedulingService(enable_fuzzing=False)
    progress = database.progress_for("lex.tak")
    database.introduce(
        "lex.tak",
        scheduler.new_card(progress.id, clock.now()),
        clock.now(),
        exposures=(("tak", "tak"),),
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
        assert database.progress_for("lex.tak").introduced
        assert "Nothing was deleted" in str(app.screen.query_one("#reset-error").render())

        confirmation.value = "DELETE"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
        assert not database.progress_for("lex.tak").introduced
        assert database.get_profile() == profile
        assert "progress deleted" in str(app.screen.query_one("#feedback").render())
