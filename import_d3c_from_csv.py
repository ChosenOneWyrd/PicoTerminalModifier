#!/usr/bin/env python3
# import_d3c_from_csv_validated.py

import csv
import sys
from pathlib import Path

COLS = [
    "katakana", "link", "name_web", "name_en", "skill", "type",
    "level", "attribute", "power", "attack1", "attack2", "info",
]

LIMITS = {
    "name_web": 12,
    "name_en": 14,
    "skill": 18,
}

NUMERIC_LIMITS = {
    "level": (0, 8),
    "attribute": (0, 7),
    "power": (1, 255),
    "attack1": (0, 50),
    "attack2": (0, 50),
}


def fail(errors, row_num, field, msg):
    errors.append(f"Row {row_num}, {field}: {msg}")


def validate_int(value, field, row_num, errors):
    lo, hi = NUMERIC_LIMITS[field]

    if value == "":
        fail(errors, row_num, field, "cannot be blank")
        return

    try:
        n = int(value)
    except ValueError:
        fail(errors, row_num, field, f"must be a number between {lo} and {hi}")
        return

    if not (lo <= n <= hi):
        fail(errors, row_num, field, f"{n} is out of range; allowed {lo}–{hi}")


def validate_row(row, row_num, errors):
    while len(row) < len(COLS):
        row.append("")

    row = row[:len(COLS)]
    data = dict(zip(COLS, row))

    for field, max_len in LIMITS.items():
        if len(data[field]) > max_len:
            fail(errors, row_num, field, f"too long: {len(data[field])} chars; max {max_len}")

    if data["skill"] and not data["skill"].startswith("・"):
        fail(errors, row_num, "skill", 'must start with Japanese dot "・"')

    for field in NUMERIC_LIMITS:
        validate_int(data[field], field, row_num, errors)

    return row


def import_from_csv(csv_path, data_path):
    errors = []
    output_rows = []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        if header is None:
            print("ERROR: CSV is empty.")
            return False

        if header[:len(COLS)] != COLS:
            print("ERROR: CSV header mismatch.")
            print("Expected:")
            print(",".join(COLS))
            print("Found:")
            print(",".join(header))
            return False

        for row_num, row in enumerate(reader, start=2):
            row = validate_row(row, row_num, errors)
            output_rows.append("\t".join(row[:len(COLS)]))

    if errors:
        print("Import failed. Fix these errors first:\n")
        for e in errors:
            print(" - " + e)
        print(f"\nNo file was written. Total errors: {len(errors)}")
        return False

    Path(data_path).write_text("\n".join(output_rows) + "\n", encoding="utf-8")
    print(f"Import successful → {data_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python import_d3c_from_csv_validated.py input.csv output.data")
        sys.exit(1)

    ok = import_from_csv(sys.argv[1], sys.argv[2])
    sys.exit(0 if ok else 1)