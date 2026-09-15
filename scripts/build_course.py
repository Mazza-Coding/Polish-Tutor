"""Validate the bundled textbook corpus; optionally export YAML and a source guide."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def build() -> dict:
    from polish_tutor.book import build_course

    return build_course()


def source_guide() -> str:
    from polish_tutor.book import book_items, rows
    from polish_tutor.data.teach_yourself import LESSONS, SOURCE

    lines = [f"# {SOURCE['title']} — Lessons 1–7", "", SOURCE["author"], "",
             "Source: the user-supplied Roy Publishers scan, printed pp. 7–31; "
             "answer key pp. 217–219. PDF page numbers are printed pages +8.", "",
             SOURCE["adaptation"], "",
             "Speech drills are reading-aloud material, not automatically graded audio exercises.", ""]
    items = book_items()
    for lesson in LESSONS:
        lines.extend([f"## Lesson {lesson['number']}: {lesson['title']}", ""])
        for note in lesson["notes"]:
            lines.extend([note, ""])
        lines.extend(["### Speech practice", "", lesson["speech"], "", "### Vocabulary", ""])
        for lemma, pos, gloss, _ in rows(lesson["vocabulary"], 4):
            lines.append(f"**{lemma}** — {gloss} ({pos}).  ")
        lines.extend(["", "### Examples and exercises", ""])
        for item in items:
            if item.lesson != lesson["number"]:
                continue
            lines.extend([f"#### {item.section} {item.reference} · printed p. {item.page}", "",
                          item.provenance, "", item.english, "",
                          "**Polish:** " + " / ".join(item.polish), ""])
    return "\n".join(lines)


def main() -> None:
    import yaml
    from polish_tutor.course import CourseCatalog

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Export the expanded course as UTF-8 YAML")
    parser.add_argument("--notes", type=Path, help="Export the source guide as UTF-8 Markdown")
    args = parser.parse_args()
    catalog = CourseCatalog.load_bundled()
    raw = build()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if args.notes:
        args.notes.parent.mkdir(parents=True, exist_ok=True)
        args.notes.write_text(source_guide(), encoding="utf-8")
    counts = Counter(item.unit_id for item in catalog.course.objectives)
    print(f"Validated {len(catalog.units)} lessons, {len(catalog.concepts)} vocabulary concepts, "
          f"{len(catalog.objectives)} objectives, "
          f"{sum(len(x.variants) for x in catalog.course.objectives)} practice variants.")
    for unit in catalog.course.units:
        print(f"  {unit.id}: {counts[unit.id]} objectives")


if __name__ == "__main__":
    main()
