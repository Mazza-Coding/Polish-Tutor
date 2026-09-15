from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest
from fsrs import Rating

from polish_tutor.db import Database, Profile, ProgressDatabaseError
from polish_tutor.models import SelfForm
from polish_tutor.scheduling import SchedulingService


FIRST_OBJECTIVE = "l01.read_translate"
FIRST_CLOZE = f"{FIRST_OBJECTIVE}.c1"


def test_profile_update_preserves_progress(database, catalog, clock) -> None:
    database.save_profile(Profile(SelfForm.MASCULINE), clock.now())
    progress = database.progress_for(FIRST_OBJECTIVE)
    scheduler = SchedulingService(enable_fuzzing=False)
    card = scheduler.new_card(progress.id, clock.now())
    database.introduce(FIRST_OBJECTIVE, card, clock.now())

    database.save_profile(Profile(SelfForm.FEMININE), clock.now())
    assert database.get_profile() == Profile(SelfForm.FEMININE)
    assert database.progress_for(FIRST_OBJECTIVE).introduced


def test_database_round_trips_fsrs_card(tmp_path, catalog, clock) -> None:
    path = tmp_path / "resume.sqlite3"
    scheduler = SchedulingService(enable_fuzzing=False)
    with Database(path) as first:
        first.sync_course(catalog, clock.now())
        progress = first.progress_for(FIRST_OBJECTIVE)
        card = scheduler.new_card(progress.id, clock.now())
        first.introduce(FIRST_OBJECTIVE, card, clock.now())

    with Database(path) as reopened:
        loaded = reopened.progress_for(FIRST_OBJECTIVE)
        assert loaded.card is not None
        assert loaded.card.due == clock.now() + timedelta(seconds=20)
        assert reopened.next_due() == loaded.card.due
        assert reopened.known_forms() == set()


def test_review_write_is_atomic(database, catalog, clock) -> None:
    scheduler = SchedulingService(enable_fuzzing=False)
    progress = database.progress_for(FIRST_OBJECTIVE)
    card = scheduler.new_card(progress.id, clock.now())
    database.introduce(FIRST_OBJECTIVE, card, clock.now())
    clock.advance(timedelta(seconds=20))
    card, log = scheduler.review(card, Rating.Good, clock.now(), 500)
    database.record_review(
        objective_id=FIRST_OBJECTIVE,
        variant_id=FIRST_CLOZE,
        card=card,
        review_log=log,
        rating=Rating.Good,
        answer_class="exact",
        attempt_count=1,
        first_try=True,
        hint_used=False,
        duration_ms=500,
        normalized_ms_per_char=166.7,
        reviewed_at=clock.now(),
        clean_cloze_increment=True,
    )
    loaded = database.progress_for(FIRST_OBJECTIVE)
    assert loaded.clean_cloze_count == 1
    assert database.variant_history(FIRST_OBJECTIVE)[FIRST_CLOZE][0] == 1


def test_reset_progress_is_transactional_and_keeps_profile(database, catalog, clock) -> None:
    profile = Profile(SelfForm.FEMININE)
    database.save_profile(profile, clock.now())
    scheduler = SchedulingService(enable_fuzzing=False)
    progress = database.progress_for(FIRST_OBJECTIVE)
    card = scheduler.new_card(progress.id, clock.now())
    database.introduce(FIRST_OBJECTIVE, card, clock.now())
    clock.advance(timedelta(seconds=20))
    card, log = scheduler.review(card, Rating.Good, clock.now(), 500)
    database.record_review(
        objective_id=FIRST_OBJECTIVE,
        variant_id=FIRST_CLOZE,
        card=card,
        review_log=log,
        rating=Rating.Good,
        answer_class="exact",
        attempt_count=1,
        first_try=True,
        hint_used=False,
        duration_ms=500,
        normalized_ms_per_char=166.7,
        reviewed_at=clock.now(),
        clean_cloze_increment=True,
    )

    database.reset_progress()

    assert database.get_profile() == profile
    assert database.known_forms() == set()
    assert database.variant_history(FIRST_OBJECTIVE) == {}
    assert database.connection.execute("SELECT COUNT(*) FROM review_log").fetchone()[0] == 0
    assert all(
        progress.card is None
        and progress.due is None
        and progress.introduced_at is None
        and progress.clean_cloze_count == 0
        and progress.mature_review_count == 0
        and progress.pending_variant_id is None
        for progress in database.all_progress()
    )


def test_course_sync_deactivates_legacy_objectives_without_deleting_them(
    database, catalog, clock
) -> None:
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO card_progress(objective_id, active) VALUES ('lex.tak', 1)"
        )

    database.sync_course(catalog, clock.now())

    legacy = database.progress_for("lex.tak")
    assert not legacy.active
    assert database.progress_for(FIRST_OBJECTIVE).active


def test_corrupt_database_is_reported_without_replacement(tmp_path) -> None:
    path = tmp_path / "corrupt.sqlite3"
    original = b"not a sqlite database"
    path.write_bytes(original)
    with pytest.raises(ProgressDatabaseError, match="Progress database"):
        Database(path)
    assert path.read_bytes() == original


def test_version_one_database_migrates_without_losing_card_rows(tmp_path) -> None:
    path = tmp_path / "version-one.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE card_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                objective_id TEXT NOT NULL UNIQUE,
                fsrs_json TEXT,
                due_utc TEXT,
                introduced_at TEXT,
                clean_cloze_count INTEGER NOT NULL DEFAULT 0,
                mature_review_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO card_progress(objective_id) VALUES ('lex.tak');
            PRAGMA user_version = 1;
            """
        )

    with Database(path) as migrated:
        columns = {
            row["name"]
            for row in migrated.connection.execute("PRAGMA table_info(card_progress)").fetchall()
        }
        version = migrated.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3
        assert "pending_variant_id" in columns
        assert migrated.progress_for("lex.tak").objective_id == "lex.tak"
        assert migrated.known_forms() == set()


def test_version_two_profile_migration_removes_limit_and_keeps_self_form(tmp_path) -> None:
    path = tmp_path / "version-two.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE profile (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                self_form TEXT NOT NULL CHECK (
                    self_form IN ('masculine', 'feminine')
                ),
                daily_new_limit INTEGER NOT NULL CHECK (
                    daily_new_limit BETWEEN 1 AND 20
                ),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO profile(
                singleton, self_form, daily_new_limit, created_at, updated_at
            ) VALUES (
                1, 'feminine', 8, '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            );
            PRAGMA user_version = 2;
            """
        )

    with Database(path) as migrated:
        columns = {
            row["name"] for row in migrated.connection.execute("PRAGMA table_info(profile)").fetchall()
        }
        assert migrated.get_profile() == Profile(SelfForm.FEMININE)
        assert "daily_new_limit" not in columns
        assert migrated.connection.execute("PRAGMA user_version").fetchone()[0] == 3
