#!/usr/bin/env python3
# Usage: python make_and_import_d3c_analyzer_cutin.py "Paildramon" --target partner --partner-data d3c_partner_data.csv
from pathlib import Path
import argparse
import csv
import json
import re
import subprocess
import sys
from PIL import Image

CUTIN_SIZE = 0xE536
BMP_MAGIC = b"BM"

def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def find_id_in_csv(path, digimon_name):
    target = norm(digimon_name)

    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for row_index, row in enumerate(rows):
        # Your CSV uses these name columns:
        possible_name_columns = [
            "name_web",
            "name_en",
            "link",
            "katakana",
            "name",
            "Name",
        ]

        for col in possible_name_columns:
            if col in row and norm(row.get(col, "")) == target:
                return row_index

    # Partial fallback, useful for names like Imperialdramon Paladin Mode
    for row_index, row in enumerate(rows):
        for col in ["name_web", "name_en", "link"]:
            if col in row:
                value = norm(row.get(col, ""))
                if target in value or value in target:
                    return row_index

    raise RuntimeError(f"Could not find {digimon_name!r} in {path}")

def find_id_in_json(path, digimon_name):
    target = norm(digimon_name)
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(data, dict):
        data = list(data.values())

    for row in data:
        if not isinstance(row, dict):
            continue

        name = row.get("name") or row.get("Name") or row.get("digimon_name")
        if norm(name) == target:
            for key in ["id", "ID", "index", "Index", "slot", "Slot"]:
                if key in row and str(row[key]).isdigit():
                    return int(row[key])

    raise RuntimeError(f"Could not find {digimon_name!r} in {path}")

def find_digimon_id(data_file, digimon_name):
    path = Path(data_file)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return find_id_in_csv(path, digimon_name)

    if suffix == ".json":
        return find_id_in_json(path, digimon_name)

    raise RuntimeError("Data file must be CSV or JSON.")

def run_analyzer(script, digimon_name, template, jpg_out, debug=False):
    cmd = [
        sys.executable,
        str(script),
        digimon_name,
        "--template",
        str(template),
        "--output",
        str(jpg_out),
    ]

    if debug:
        cmd.append("--debug")

    subprocess.run(cmd, check=True)

def convert_jpg_to_d3c_bmp(jpg_path, bmp_path, fit="pad"):
    img = Image.open(jpg_path).convert("RGB")

    if fit == "stretch":
        img = img.resize((240, 240), Image.Resampling.LANCZOS)

    elif fit == "crop":
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((240, 240), Image.Resampling.LANCZOS)

    else:
        # Default: keep full 640x480 analyzer visible.
        # Result is 240x180 centered inside 240x240.
        img.thumbnail((240, 240), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (240, 240), (0, 0, 0))
        x = (240 - img.width) // 2
        y = (240 - img.height) // 2
        canvas.paste(img, (x, y))
        img = canvas

    img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    img.save(bmp_path, "BMP")

    data = bmp_path.read_bytes()

    if data[:2] != BMP_MAGIC:
        raise RuntimeError("Generated BMP does not start with BM.")

    if len(data) != CUTIN_SIZE:
        raise RuntimeError(
            f"Generated BMP has wrong size: 0x{len(data):X}. "
            f"Expected 0x{CUTIN_SIZE:X}."
        )

def import_bmp_into_bin(bin_in, bmp_path, slot_id, bin_out):
    original = bytearray(Path(bin_in).read_bytes())
    bmp = Path(bmp_path).read_bytes()

    if len(original) % CUTIN_SIZE != 0:
        raise RuntimeError(f"{bin_in} is not a valid D3C cut-in bin size.")

    count = len(original) // CUTIN_SIZE

    if slot_id < 0 or slot_id >= count:
        raise RuntimeError(
            f"Slot ID {slot_id} is out of range. "
            f"This bin has slots 0 to {count - 1}."
        )

    if len(bmp) != CUTIN_SIZE:
        raise RuntimeError("BMP size mismatch.")

    start = slot_id * CUTIN_SIZE
    original[start:start + CUTIN_SIZE] = bmp

    Path(bin_out).write_bytes(original)

def safe_name(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("name", help='Example: "Paildramon"')
    parser.add_argument("--target", choices=["partner", "friend"], required=True)

    parser.add_argument("--analyzer-script", default="make_digimon_analyzer_v27.py")
    parser.add_argument("--template", default="Digimon_analyzer_blank.jpg")

    parser.add_argument("--partner-bin", default="sd/gfx/cutin/d3c/partner.bin")
    parser.add_argument("--friend-bin", default="sd/gfx/cutin/d3c/friend.bin")

    parser.add_argument("--partner-data", default=None)
    parser.add_argument("--friend-data", default=None)

    parser.add_argument("--id", type=int, default=None, help="Manual slot ID override")
    parser.add_argument("--id-base", type=int, default=0, choices=[0, 1])

    parser.add_argument("--out-bin", default=None)
    parser.add_argument("--workdir", default="generated_d3c_cutins")
    parser.add_argument("--fit", choices=["pad", "stretch", "crop"], default="pad")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    base = safe_name(args.name)

    jpg_out = workdir / f"{base}_analyzer.jpg"

    if args.id is not None:
        raw_id = args.id
    else:
        data_file = args.partner_data if args.target == "partner" else args.friend_data
        if not data_file:
            raise RuntimeError(
                f"You must provide --{args.target}-data, or use --id manually."
            )
        raw_id = find_digimon_id(data_file, args.name)

    slot_id = raw_id - args.id_base

    bmp_out = workdir / f"{slot_id:03d}.bmp"

    bin_in = Path(args.partner_bin if args.target == "partner" else args.friend_bin)

    if args.out_bin:
        bin_out = Path(args.out_bin)
    else:
        bin_out = bin_in.with_name(bin_in.stem + ".bin")

    print(f"Digimon: {args.name}")
    print(f"Target: {args.target}")
    print(f"Raw ID from data: {raw_id}")
    print(f"Actual bin slot: {slot_id}")

    run_analyzer(
        args.analyzer_script,
        args.name,
        args.template,
        jpg_out,
        debug=args.debug,
    )

    convert_jpg_to_d3c_bmp(jpg_out, bmp_out, fit=args.fit)

    # Rename final BMP with the ID.
    final_bmp = workdir / f"{args.target}_{slot_id:03d}_{base}.bmp"
    bmp_out.replace(final_bmp)

    import_bmp_into_bin(bin_in, final_bmp, slot_id, bin_out)

    print()
    print(f"Saved JPG: {jpg_out}")
    print(f"Saved BMP: {final_bmp}")
    print(f"Saved patched BIN: {bin_out}")

if __name__ == "__main__":
    main()