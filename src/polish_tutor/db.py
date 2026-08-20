from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fsrs import Card, Rating, ReviewLog
from platformdirs import user_data_path

from polish_tutor.course import CourseCatalog
from polish_tutor.models import SelfForm

SCHEMA_VERSION = 3


class ProgressDatabaseError(RuntimeError):
    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{message}\nProgress database: {path}")
        self.path = path


@dataclass(frozen=True)
class Profile:
    self_form: SelfForm


@dataclass(frozen=True)
class CardProgress:
    id: int
    objective_id: str
    card: Card | None
    due: datetime | None
    introduced_at: datetime | None
    clean_cloze_count: int
    mature_review_count: int
    pending_variant_id: str | None
    active: bool

    @property
    def introduced(self) -> bool:
        return self.introduced_at is not None

    @property
    def ready(self) -> bool:
        return self.clean_cloze_count >= 2


def default_database_path() -> Path:
    directory = user_data_path("PolishTypingTutor", "OpenAI")
    return directory / "progress.sqlite3"


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.execute("PRAGMA busy_timeout = 2500")
            self.connection.execute("PRAGMA journal_mode = WAL")
            integrity = self.connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ProgressDatabaseError(path, f"SQLite integrity check failed: {integrity}")
            self._initialize_schema()
        except ProgressDatabaseError:
            raise
        except sqlite3.DatabaseError as error:
            raise ProgressDatabaseError(
                path, f"Could not open the SQLite database: {error}"
            ) from error

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            with self.connection:
                yield self.connection
        except sqlite3.DatabaseError as error:
            raise ProgressDatabaseError(self.path, f"Could not save progress: {error}") from error

    def _initialize_schema(self) -> None:
        current = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if current not in (0, 1, 2, SCHEMA_VERSION):
            raise ProgressDatabaseError(
                self.path,
                f"Unsupported progress schema {current}; this build supports {SCHEMA_VERSION}",
            )
        with self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    self_form TEXT NOT NULL CHECK (self_form IN ('masculine', 'feminine')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS course_meta (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    course_version INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    synced_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS card_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    objective_id TEXT NOT NULL UNIQUE,
                    fsrs_json TEXT,
                    due_utc TEXT,
                    introduced_at TEXT,
                    clean_cloze_count INTEGER NOT NULL DEFAULT 0,
                    mature_review_count INTEGER NOT NULL DEFAULT 0,
                    pending_variant_id TEXT,
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_card_progress_due
                    ON card_progress(active, due_utc);

                CREATE TABLE IF NOT EXISTS variant_history (
                    objective_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 0,
                    last_seen TEXT,
                    PRIMARY KEY (objective_id, variant_id)
                );

                CREATE TABLE IF NOT EXISTS review_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    objective_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 4),
                    answer_class TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    first_try INTEGER NOT NULL,
                    hint_used INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    normalized_ms_per_char REAL NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    fsrs_log_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_review_log_speed
                    ON review_log(first_try, hint_used, reviewed_at);

                CREATE TABLE IF NOT EXISTS form_exposure (
                    concept_id TEXT NOT NULL,
                    form TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    objective_id TEXT NOT NULL,
                    variant_id TEXT,
                    PRIMARY KEY (concept_id, form)
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(card_progress)").fetchall()
            }
            if "pending_variant_id" not in columns:
                connection.execute("ALTER TABLE card_progress ADD COLUMN pending_variant_id TEXT")
            profile_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(profile)").fetchall()
            }
            if "daily_new_limit" in profile_columns:
                connection.execute("ALTER TABLE profile RENAME TO profile_with_daily_limit")
                connection.execute(
                    """
                    CREATE TABLE profile (
                        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                        self_form TEXT NOT NULL CHECK (
                            self_form IN ('masculine', 'feminine')
                        ),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO profile(singleton, self_form, created_at, updated_at)
                    SELECT singleton, self_form, created_at, updated_at
                    FROM profile_with_daily_limit
                    """
                )
                connection.execute("DROP TABLE profile_with_daily_limit")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def sync_course(self, catalog: CourseCatalog, now: datetime) -> None:
        with self.transaction() as connection:
            connection.execute("UPDATE card_progress SET active = 0")
            for objective in catalog.objectives_in_order:
                connection.execute(
                    """
                    INSERT INTO card_progress(objective_id, active)
                    VALUES (?, 1)
                    ON CONFLICT(objective_id) DO UPDATE SET active = 1
                    """,
                    (objective.id,),
                )
            connection.execute(
                """
                INSERT INTO course_meta(singleton, course_version, content_hash, synced_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    course_version = excluded.course_version,
                    content_hash = excluded.content_hash,
                    synced_at = excluded.synced_at
                """,
                (catalog.course.version, catalog.content_hash, now.isoformat()),
            )

    def get_profile(self) -> Profile | None:
        row = self.connection.execute(
            "SELECT self_form FROM profile WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return None
        return Profile(SelfForm(row["self_form"]))

    def save_profile(self, profile: Profile, now: datetime) -> None:
        timestamp = now.isoformat()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO profile(singleton, self_form, created_at, updated_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    self_form = excluded.self_form,
                    updated_at = excluded.updated_at
                """,
                (profile.self_form.value, timestamp, timestamp),
            )

    @staticmethod
    def _row_to_progress(row: sqlite3.Row) -> CardProgress:
        card = Card.from_json(row["fsrs_json"]) if row["fsrs_json"] else None
        due = datetime.fromisoformat(row["due_utc"]) if row["due_utc"] else None
        introduced_at = (
            datetime.fromisoformat(row["introduced_at"]) if row["introduced_at"] else None
        )
        return CardProgress(
            id=row["id"],
            objective_id=row["objective_id"],
            card=card,
            due=due,
            introduced_at=introduced_at,
            clean_cloze_count=row["clean_cloze_count"],
            mature_review_count=row["mature_review_count"],
            pending_variant_id=row["pending_variant_id"],
            active=bool(row["active"]),
        )

    def progress_for(self, objective_id: str) -> CardProgress:
        row = self.connection.execute(
            "SELECT * FROM card_progress WHERE objective_id = ?", (objective_id,)
        ).fetchone()
        if row is None:
            raise KeyError(objective_id)
        return self._row_to_progress(row)

    def all_progress(self, *, active_only: bool = True) -> tuple[CardProgress, ...]:
        where = "WHERE active = 1" if active_only else ""
        rows = self.connection.execute(
            f"SELECT * FROM card_progress {where} ORDER BY id"  # noqa: S608
        ).fetchall()
        return tuple(self._row_to_progress(row) for row in rows)

    def due_progress(self, now: datetime) -> tuple[CardProgress, ...]:
        rows = self.connection.execute(
            """
            SELECT * FROM card_progress
            WHERE active = 1 AND introduced_at IS NOT NULL AND due_utc <= ?
            ORDER BY due_utc, id
            """,
            (now.isoformat(),),
        ).fetchall()
        return tuple(self._row_to_progress(row) for row in rows)

    def next_due(self) -> datetime | None:
        row = self.connection.execute(
            """
            SELECT due_utc FROM card_progress
            WHERE active = 1 AND introduced_at IS NOT NULL
            ORDER BY due_utc LIMIT 1
            """
        ).fetchone()
        return datetime.fromisoformat(row["due_utc"]) if row else None

    def introduced_concepts(self, catalog: CourseCatalog) -> set[str]:
        progress = {item.objective_id: item for item in self.all_progress()}
        return {
            concept_id
            for concept_id, objective in catalog.concept_objective.items()
            if progress[objective.id].introduced
        }

    def ready_concepts(self, catalog: CourseCatalog) -> set[str]:
        progress = {item.objective_id: item for item in self.all_progress()}
        return {
            concept_id
            for concept_id, objective in catalog.concept_objective.items()
            if progress[objective.id].ready
        }

    @staticmethod
    def _insert_form_exposures(
        connection: sqlite3.Connection,
        exposures: Iterable[tuple[str, str]],
        *,
        objective_id: str,
        variant_id: str | None,
        seen_at: datetime,
    ) -> None:
        connection.executemany(
            """
            INSERT INTO form_exposure(
                concept_id, form, first_seen, objective_id, variant_id
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(concept_id, form) DO NOTHING
            """,
            (
                (concept_id, form, seen_at.isoformat(), objective_id, variant_id)
                for concept_id, form in set(exposures)
            ),
        )

    def known_forms(self) -> set[tuple[str, str]]:
        rows = self.connection.execute("SELECT concept_id, form FROM form_exposure").fetchall()
        return {(row["concept_id"], row["form"]) for row in rows}

    def reset_progress(self) -> None:
        """Delete all study history while preserving profile preferences and course data."""
        with self.transaction() as connection:
            connection.execute("DELETE FROM review_log")
            connection.execute("DELETE FROM variant_history")
            connection.execute("DELETE FROM form_exposure")
            connection.execute(
                """
                UPDATE card_progress SET
                    fsrs_json = NULL,
                    due_utc = NULL,
                    introduced_at = NULL,
                    clean_cloze_count = 0,
                    mature_review_count = 0,
                    pending_variant_id = NULL
                """
            )

    def introduce(
        self,
        objective_id: str,
        card: Card,
        now: datetime,
        *,
        exposures: Iterable[tuple[str, str]] = (),
    ) -> None:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE card_progress
                SET fsrs_json = ?, due_utc = ?, introduced_at = ?, pending_variant_id = NULL
                WHERE objective_id = ? AND introduced_at IS NULL AND active = 1
                """,
                (card.to_json(), card.due.isoformat(), now.isoformat(), objective_id),
            )
            if cursor.rowcount != 1:
                raise ProgressDatabaseError(
                    self.path, f"Objective {objective_id} was already introduced or is unavailable"
                )
            self._insert_form_exposures(
                connection,
                exposures,
                objective_id=objective_id,
                variant_id=None,
                seen_at=now,
            )

    def record_form_introduction(
        self,
        *,
        objective_id: str,
        variant_id: str,
        card: Card,
        exposures: Iterable[tuple[str, str]],
        introduced_at: datetime,
    ) -> None:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE card_progress SET
                    fsrs_json = ?,
                    due_utc = ?,
                    pending_variant_id = ?
                WHERE objective_id = ? AND introduced_at IS NOT NULL AND active = 1
                """,
                (card.to_json(), card.due.isoformat(), variant_id, objective_id),
            )
            if cursor.rowcount != 1:
                raise ProgressDatabaseError(
                    self.path, f"Objective {objective_id} is unavailable for form practice"
                )
            self._insert_form_exposures(
                connection,
                exposures,
                objective_id=objective_id,
                variant_id=variant_id,
                seen_at=introduced_at,
            )

    def variant_history(self, objective_id: str) -> dict[str, tuple[int, datetime | None]]:
        rows = self.connection.execute(
            """
            SELECT variant_id, seen_count, last_seen FROM variant_history
            WHERE objective_id = ?
            """,
            (objective_id,),
        ).fetchall()
        return {
            row["variant_id"]: (
                row["seen_count"],
                datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None,
            )
            for row in rows
        }

    def clean_speed_samples(self, *, limit: int = 200) -> tuple[float, ...]:
        rows = self.connection.execute(
            """
            SELECT normalized_ms_per_char FROM review_log
            WHERE first_try = 1 AND hint_used = 0 AND rating IN (3, 4)
            ORDER BY reviewed_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(row["normalized_ms_per_char"] for row in rows)

    def record_review(
        self,
        *,
        objective_id: str,
        variant_id: str,
        card: Card,
        review_log: ReviewLog,
        rating: Rating,
        answer_class: str,
        attempt_count: int,
        first_try: bool,
        hint_used: bool,
        duration_ms: int,
        normalized_ms_per_char: float,
        reviewed_at: datetime,
        clean_cloze_increment: bool,
        exposures: Iterable[tuple[str, str]] = (),
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE card_progress SET
                    fsrs_json = ?,
                    due_utc = ?,
                    clean_cloze_count = clean_cloze_count + ?,
                    mature_review_count = mature_review_count + 1,
                    pending_variant_id = NULL
                WHERE objective_id = ? AND active = 1
                """,
                (
                    card.to_json(),
                    card.due.isoformat(),
                    int(clean_cloze_increment),
                    objective_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO variant_history(objective_id, variant_id, seen_count, last_seen)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(objective_id, variant_id) DO UPDATE SET
                    seen_count = seen_count + 1,
                    last_seen = excluded.last_seen
                """,
                (objective_id, variant_id, reviewed_at.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO review_log(
                    objective_id, variant_id, rating, answer_class, attempt_count,
                    first_try, hint_used, duration_ms, normalized_ms_per_char,
                    reviewed_at, fsrs_log_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    objective_id,
                    variant_id,
                    rating.value,
                    answer_class,
                    attempt_count,
                    int(first_try),
                    int(hint_used),
                    duration_ms,
                    normalized_ms_per_char,
                    reviewed_at.isoformat(),
                    review_log.to_json(),
                ),
            )
            self._insert_form_exposures(
                connection,
                exposures,
                objective_id=objective_id,
                variant_id=variant_id,
                seen_at=reviewed_at,
            )
