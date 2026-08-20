from __future__ import annotations

import argparse
import random
import sys

from polish_tutor import __version__
from polish_tutor.app import PolishTutorApp
from polish_tutor.course import CourseCatalog, CourseValidationError
from polish_tutor.db import Database, ProgressDatabaseError, default_database_path
from polish_tutor.engine import StudyEngine
from polish_tutor.scheduling import SchedulingService, SystemClock


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polish-tutor",
        description="Learn Polish through typed recall in the terminal.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="change self-reference preference without resetting progress",
    )
    parser.add_argument(
        "--data-path",
        action="store_true",
        help="print the local progress database path and exit",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    database_path = default_database_path()
    if args.data_path:
        print(database_path)
        return

    clock = SystemClock()
    try:
        catalog = CourseCatalog.load_bundled()
        with Database(database_path) as database:
            database.sync_course(catalog, clock.now())
            scheduler = SchedulingService(enable_fuzzing=True)
            engine = StudyEngine(
                catalog=catalog,
                database=database,
                scheduler=scheduler,
                clock=clock,
                rng=random.Random(),
            )
            app = PolishTutorApp(
                catalog=catalog,
                database=database,
                engine=engine,
                clock=clock,
                force_setup=args.setup,
            )
            app.run()
    except (CourseValidationError, ProgressDatabaseError) as error:
        print(f"polish-tutor: {error}", file=sys.stderr)
        raise SystemExit(2) from error
