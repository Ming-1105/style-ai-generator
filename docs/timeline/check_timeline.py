"""Check the timeline CSV files in this folder against FORMAT.md.

Run from the repo root:

    python docs/timeline/check_timeline.py
    python docs/timeline/check_timeline.py --ban "Some Brand,Other Brand"   # names never written to a file

Uses only the Python standard library. Exits with status 1 if any error is found.
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

HEADER = ["id", "datetime", "person", "type", "title", "what", "why", "links", "after"]
PEOPLE = ["A", "B", "C"]
TYPES = {"milestone", "decision", "problem", "experiment"}
TITLE_MAX = 60


def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))


def check(folder: Path, banned: list[str]) -> tuple[list[str], list[str], int]:
    errors, warnings, total = [], [], 0
    all_ids: dict[str, str] = {}
    pending_after: list[tuple[str, str, str]] = []  # (file, id, referenced id)
    present = []

    for letter in PEOPLE:
        path = folder / f"{letter}.csv"
        if not path.exists():
            warnings.append(f"{letter}.csv does not exist yet")
            continue
        present.append(letter)
        rows = read_rows(path)
        if not rows or rows[0] != HEADER:
            errors.append(f"{path.name}: first line must be exactly: {','.join(HEADER)}")
            continue
        for number, row in enumerate(rows[1:], start=2):
            if not any(cell.strip() for cell in row):
                continue
            where = f"{path.name} line {number}"
            if len(row) != len(HEADER):
                errors.append(f"{where}: {len(row)} columns, expected {len(HEADER)} (quote fields that contain commas)")
                continue
            total += 1
            entry = dict(zip(HEADER, (cell.strip() for cell in row)))
            event_id = entry["id"]
            if not re.fullmatch(rf"{letter}-\d{{3}}", event_id):
                errors.append(f"{where}: id '{event_id}' must look like {letter}-001")
            if event_id in all_ids:
                errors.append(f"{where}: id {event_id} is also used in {all_ids[event_id]}")
            all_ids[event_id] = path.name
            try:
                datetime.strptime(entry["datetime"], "%Y-%m-%d %H:%M")
            except ValueError:
                errors.append(f"{where}: datetime '{entry['datetime']}' must be YYYY-MM-DD HH:MM")
            if entry["person"] != letter:
                errors.append(f"{where}: person '{entry['person']}' must be {letter} in {path.name}")
            if entry["type"] not in TYPES:
                errors.append(f"{where}: type '{entry['type']}' must be one of {', '.join(sorted(TYPES))}")
            if not entry["title"]:
                errors.append(f"{where}: title is empty")
            elif len(entry["title"]) > TITLE_MAX:
                errors.append(f"{where}: title is {len(entry['title'])} characters, max {TITLE_MAX}")
            if not entry["what"]:
                errors.append(f"{where}: 'what' is empty")
            if entry["type"] != "milestone" and not entry["why"]:
                errors.append(f"{where}: 'why' is required for a {entry['type']}")
            for ref in filter(None, (r.strip() for r in entry["after"].split(";"))):
                pending_after.append((where, event_id, ref))
            for word in banned:
                for column in ("title", "what", "why", "links"):
                    if word.lower() in entry[column].lower():
                        errors.append(f"{where}: contains the banned name '{word}' in {column}")

    for where, event_id, ref in pending_after:
        if ref == event_id:
            errors.append(f"{where}: {event_id} cannot come after itself")
        elif ref not in all_ids:
            owner = ref[:1]
            message = f"{where}: 'after' refers to {ref}, which does not exist"
            if owner in PEOPLE and owner not in present:
                warnings.append(message + f" (yet: {owner}.csv has not been added)")
            else:
                errors.append(message)
    return errors, warnings, total


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the timeline CSV files.")
    parser.add_argument("--ban", default="", help="comma-separated names that must not appear anywhere")
    parser.add_argument("--folder", default=str(Path(__file__).parent))
    args = parser.parse_args()
    banned = [name.strip() for name in args.ban.split(",") if name.strip()]

    errors, warnings, total = check(Path(args.folder), banned)
    for message in warnings:
        print(f"warning: {message}")
    for message in errors:
        print(f"ERROR:   {message}")
    print(f"\n{total} events checked, {len(errors)} errors, {len(warnings)} warnings.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
