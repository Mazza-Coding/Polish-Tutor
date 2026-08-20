from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from polish_tutor.course import CourseCatalog
from polish_tutor.db import Database, Profile
from polish_tutor.engine import StudyEngine
from polish_tutor.models import SelfForm
from polish_tutor.scheduling import FakeClock, SchedulingService


@pytest.fixture(scope="session")
def catalog() -> CourseCatalog:
    return CourseCatalog.load_bundled()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 1, 15, 12, 0, tzinfo=UTC))


@pytest.fixture
def database(tmp_path, catalog: CourseCatalog, clock: FakeClock):
    database = Database(tmp_path / "progress.sqlite3")
    database.sync_course(catalog, clock.now())
    yield database
    database.close()


@pytest.fixture
def engine(
    catalog: CourseCatalog,
    database: Database,
    clock: FakeClock,
) -> StudyEngine:
    database.save_profile(Profile(SelfForm.MASCULINE), clock.now())
    return StudyEngine(
        catalog=catalog,
        database=database,
        scheduler=SchedulingService(enable_fuzzing=False),
        clock=clock,
        rng=random.Random(1),
    )
