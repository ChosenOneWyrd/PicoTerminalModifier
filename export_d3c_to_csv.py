#!/usr/bin/env python3
# python export_d3c_to_csv.py sd/data/d3c/friend.data d3c_friend_data.csv

import csv
from pathlib import Path

COLS = [
    "katakana",
    "link",
    "name_web",
    "name_en",
    "skill",
    "type",
    "level",
    "attribute",
    "power",
    "attack1",
    "attack2",
    "info",
]


def read_data(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        rows.append(line.split("\t"))
    return rows


def ensure_len(row, n):
    while len(row) < n:
        row.append("")
    return row


def export_to_csv(data_path, csv_path):
    rows = read_data(data_path)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLS)

        for row in rows:
            row = ensure_len(row, len(COLS))
            writer.writerow(row[:len(COLS)])

    print(f"Exported → {csv_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python export_d3c_to_csv.py input.data output.csv")
        exit(1)

    export_to_csv(sys.argv[1], sys.argv[2])