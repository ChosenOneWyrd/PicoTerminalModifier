#!/usr/bin/env python3
# python scripts/import_data_from_csv.py data/d3c_data.csv sd/data/d3c
# python scripts/import_data_from_csv.py data/dvc_data.csv sd/data/dvc
# python scripts/import_data_from_csv.py data/vb_data.csv sd/data/vb
# python scripts/import_data_from_csv.py data/dmc_data.csv sd/data/dmc
# python scripts/import_data_from_csv.py data/penc_data.csv sd/data/penc
# python scripts/import_data_from_csv.py data/dmx_data.csv sd/data/dmx
# python scripts/import_data_from_csv.py data/pen20_data.csv sd/data/pen20
# python scripts/import_data_from_csv.py data/penz_data.csv sd/data/penz
# python scripts/import_data_from_csv.py data/dm20_data.csv sd/data/dm20

import csv
import sys
from pathlib import Path
from collections import defaultdict

NUMERIC_COLS = {
    "level", "attribute", "field_or_stage", "power",
    "stat1", "stat2", "attack1", "attack2",
    "extra1", "extra2",
}

def fail(errors, row_num, field, msg):
    errors.append(f"CSV row {row_num}, {field}: {msg}")

def validate_row(row, row_num, data_cols, errors):
    if not row.get("file", "").endswith(".data"):
        fail(errors, row_num, "file", "must end with .data")

    try:
        int(row.get("row_index", ""))
    except ValueError:
        fail(errors, row_num, "row_index", "must be a number")

    skill = row.get("skill", "")
    if skill and not skill.startswith("・"):
        fail(errors, row_num, "skill", 'must start with Japanese dot "・"')

    for col in data_cols:
        if col not in row:
            fail(errors, row_num, col, "missing column")
            continue

        if col in NUMERIC_COLS:
            value = row[col].strip()
            if value == "":
                fail(errors, row_num, col, "cannot be blank")
                continue

            try:
                n = int(value)
            except ValueError:
                fail(errors, row_num, col, "must be a number")
                continue

            if not (0 <= n <= 65535):
                fail(errors, row_num, col, f"{n} out of range; allowed 0–65535")

def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/import_data_from_csv.py data/d3c_data.csv sd/data/d3c")
        sys.exit(1)
    csv_path = sys.argv[1]
    output_folder = sys.argv[2]
    output_folder = Path(output_folder)
    errors = []
    by_file = defaultdict(list)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            print("ERROR: CSV is empty.")
            return False

        if reader.fieldnames[:2] != ["file", "row_index"]:
            print("ERROR: CSV must start with: file,row_index")
            print("Found:", ",".join(reader.fieldnames))
            return False

        data_cols = reader.fieldnames[2:]

        for row_num, row in enumerate(reader, start=2):
            validate_row(row, row_num, data_cols, errors)
            by_file[row["file"]].append(row)

    if errors:
        print("Import failed. Fix these errors first:\n")
        for e in errors:
            print(" - " + e)
        print(f"\nNo files were written. Total errors: {len(errors)}")
        return False

    output_folder.mkdir(parents=True, exist_ok=True)

    written = 0

    for filename, rows in by_file.items():
        rows.sort(key=lambda r: int(r["row_index"]))

        lines = []
        for row in rows:
            lines.append("\t".join(row[col] for col in data_cols))

        out_path = output_folder / filename
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {out_path}")
        written += 1

    print(f"Import successful. Wrote {written} data file(s).")
    return True

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)