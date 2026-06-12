#!/usr/bin/env python3
# python scripts/export_data_to_csv.py sd/data/d3c data/d3c_data.csv
# python scripts/export_data_to_csv.py sd/data/dvc data/dvc_data.csv
# python scripts/export_data_to_csv.py sd/data/vb data/vb_data.csv
# python scripts/export_data_to_csv.py sd/data/dmc data/dmc_data.csv
# python scripts/export_data_to_csv.py sd/data/penc data/penc_data.csv
# python scripts/export_data_to_csv.py sd/data/dmx data/dmx_data.csv
# python scripts/export_data_to_csv.py sd/data/pen20 data/pen20_data.csv
# python scripts/export_data_to_csv.py sd/data/penz data/penz_data.csv
# python scripts/export_data_to_csv.py sd/data/dm20 data/dm20_data.csv

import csv
import sys
from pathlib import Path

SCHEMAS = {
    11: ["katakana", "link", "name_web", "name_en", "skill", "type",
         "level", "attribute", "power", "attack1", "attack2"],

    12: ["katakana", "link", "name_web", "name_en", "skill", "type",
         "level", "attribute", "power", "attack1", "attack2", "info"],

    16: ["katakana", "link", "name_web", "name_en", "skill", "type",
         "level", "attribute", "field_or_stage", "power", "stat1", "stat2",
         "attack1", "attack2", "extra1", "extra2"],
}

def sort_key(path: Path):
    try:
        return int(path.stem)
    except ValueError:
        return path.name.lower()

def collect_files(path: Path):
    if path.is_file():
        return [path]
    return sorted(path.glob("*.data"), key=sort_key)

def ensure_len(row, n):
    while len(row) < n:
        row.append("")
    return row[:n]

def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/export_data_to_csv.py sd/data/d3c data/d3c_data.csv")
        sys.exit(1)
    input_path = sys.argv[1]
    csv_path = sys.argv[2]
    input_path = Path(input_path)
    files = collect_files(input_path)

    if not files:
        raise RuntimeError(f"No .data files found: {input_path}")

    max_cols = 0
    all_rows = []

    for data_file in files:
        lines = data_file.read_text(encoding="utf-8").splitlines()
        for row_index, line in enumerate(lines):
            row = line.split("\t")
            max_cols = max(max_cols, len(row))
            all_rows.append((data_file.name, row_index, row))

    data_cols = SCHEMAS.get(max_cols)
    if data_cols is None:
        data_cols = [f"col{i}" for i in range(max_cols)]

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "row_index"] + data_cols)

        for filename, row_index, row in all_rows:
            writer.writerow([filename, row_index] + ensure_len(row, len(data_cols)))

    print(f"Exported {len(files)} data file(s), {len(all_rows)} rows -> {csv_path}")
    print(f"Detected {max_cols} columns.")

if __name__ == "__main__":
    main()