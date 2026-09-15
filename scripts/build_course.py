from __future__ import annotations

from pathlib import Path

import yaml

from polish_tutor.course import CourseCatalog


def source_path() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "polish_tutor" / "data" / "course_v1.yaml"


def build() -> dict:
    catalog = CourseCatalog.load_path(source_path())
    return catalog.course.model_dump(mode="json")


if __name__ == "__main__":
    print(yaml.safe_dump(build(), allow_unicode=True, sort_keys=False, width=100), end="")
