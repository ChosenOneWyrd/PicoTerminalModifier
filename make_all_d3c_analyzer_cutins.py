#!/usr/bin/env python3
# Needs full sd folder to be pasted
# Usage: python make_all_d3c_analyzer_cutins.py
# For properly sized crops for pico terminal, use: python make_all_d3c_analyzer_cutins.py --fit crop
# For taking profile data from sd/profile folder instead of Wikimon, use:
# python make_all_d3c_analyzer_cutins.py --fit crop --data-source terminal
from pathlib import Path
import argparse
import csv
import re
import subprocess
import sys
from PIL import Image
import requests
import traceback
import contextlib

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

CUTIN_SIZE = 0xE536
BMP_MAGIC = b"BM"

# -----------------------------
# CONFIGURABLE IMAGE SETTINGS
# -----------------------------
ANALYZER_INPUT_WIDTH = 640
ANALYZER_INPUT_HEIGHT = 480

CUTIN_OUTPUT_WIDTH = 240
CUTIN_OUTPUT_HEIGHT = 240
CROP_ZOOM = 0.82

CUTIN_BACKGROUND_COLOR = (0, 0, 0)  # black

# For D3C 240x240 8-bit BMPs this should stay 0xE536.
# If you change CUTIN_OUTPUT_WIDTH/HEIGHT, the BMP size will probably change.
EXPECTED_CUTIN_SIZE = CUTIN_SIZE

DIGI_API_LIST_URL = "https://digi-api.com/api/v1/digimon?pageSize=3000"
_DIGI_API_ROWS = None
MANUAL_NAME_FIXES = {
    "holsmom": "Holsmon",
    "rapidmongold": "Rapidmon Armor",
    "rapidmonarmor": "Rapidmon Armor",
    "cherubimonvice": "Cherubimon_(Vice)",
    "scumon": "Scumon",
    "okuwamon": "Okuwamon",
    "fujitsumon": "Octmon"
}

TRACE_LOG_PATH = Path("trace.log")
ERROR_LOG_PATH = Path("error.log")


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def log_error(message="", exc=None):
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        if message:
            f.write(message + "\n")

        if exc is not None:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)

        f.write("\n")

def normalize_api_name(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def get_digi_api_rows():
    global _DIGI_API_ROWS
    if _DIGI_API_ROWS is not None:
        return _DIGI_API_ROWS

    r = requests.get(DIGI_API_LIST_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    _DIGI_API_ROWS = data.get("content", [])
    return _DIGI_API_ROWS

def resolve_analyzer_search_name(raw_name):
    original = str(raw_name).strip()

    manual_key = normalize_api_name(original)
    if manual_key in MANUAL_NAME_FIXES:
        return MANUAL_NAME_FIXES[manual_key]

    candidates = []

    # Original
    candidates.append(original)

    # Common cleanup variants
    candidates.append(original.replace(":", " "))
    candidates.append(original.replace(":", " Mode "))
    candidates.append(original.replace("-", ""))
    candidates.append(original.replace("-", " "))
    candidates.append(original.replace(":", " ").replace("-", " "))

    # Split glued "mode" names:
    # Dragonmode -> Dragon Mode
    # Fightermode -> Fighter Mode
    # Paladinmode -> Paladin Mode
    candidates += [
        re.sub(r"([A-Za-z]+)mode\b", r"\1 Mode", c, flags=re.I)
        for c in list(candidates)
    ]

    # Deduplicate
    seen = set()
    clean_candidates = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c).strip()
        key = normalize_api_name(c)
        if key and key not in seen:
            seen.add(key)
            clean_candidates.append(c)

    api_rows = get_digi_api_rows()

    best_name = original
    best_score = -1

    for candidate in clean_candidates:
        ckey = normalize_api_name(candidate)

        for row in api_rows:
            api_name = str(row.get("name", ""))
            akey = normalize_api_name(api_name)

            if not akey:
                continue

            score = -1

            if akey == ckey:
                score = 10000
            elif ckey in akey:
                score = 8000 + len(ckey)
            elif akey in ckey:
                score = 7000 + len(akey)

            if score > best_score:
                best_score = score
                best_name = api_name

    # Digi-API uses names like Imperialdramon(Dragon Mode).
    # Your analyzer/Wikimon script usually works better with spaces.
    best_name = best_name.replace("(", " ").replace(")", " ")
    best_name = re.sub(r"\s+", " ", best_name).strip()

    return best_name

def safe_name(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip())


def export_to_csv(data_path, csv_path):
    rows = []

    for line in Path(data_path).read_text(encoding="utf-8").splitlines():
        row = line.split("\t")
        while len(row) < len(COLS):
            row.append("")
        rows.append(row[:len(COLS)])

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLS)
        writer.writerows(rows)

    print(f"Exported {data_path} -> {csv_path}")
    return rows


def choose_digimon_name(row):
    # Prefer the cleaned English/web names.
    for col in ["name_web", "name_en", "link", "katakana"]:
        value = row.get(col, "").strip()
        if value:
            return value
    return ""


def run_analyzer(
    script,
    digimon_name,
    template,
    jpg_out,
    debug=False,
    data_source="wikimon",
    profile_root="sd/profile",
):
    cmd = [
        sys.executable,
        str(script),
        digimon_name,
        "--template",
        str(template),
        "--output",
        str(jpg_out),
        "--data-source",
        str(data_source),
        "--profile-root",
        str(profile_root),
    ]

    if debug:
        cmd.append("--debug")

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.stdout:
        print(result.stdout, end="")

    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("Command failed:\n")
            f.write(" ".join(cmd) + "\n\n")
            if result.stdout:
                f.write("STDOUT:\n")
                f.write(result.stdout + "\n")
            if result.stderr:
                f.write("STDERR / TRACEBACK:\n")
                f.write(result.stderr + "\n")
            f.write("\n")

        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr=result.stderr,
        )


def convert_jpg_to_d3c_bmp(jpg_path, bmp_path, fit="pad"):
    img = Image.open(jpg_path).convert("RGB")

    # Optional safety resize if analyzer output is not the expected size.
    if img.size != (ANALYZER_INPUT_WIDTH, ANALYZER_INPUT_HEIGHT):
        img = img.resize(
            (ANALYZER_INPUT_WIDTH, ANALYZER_INPUT_HEIGHT),
            Image.Resampling.LANCZOS,
        )

    out_size = (CUTIN_OUTPUT_WIDTH, CUTIN_OUTPUT_HEIGHT)

    if fit == "stretch":
        img = img.resize(out_size, Image.Resampling.LANCZOS)

    elif fit == "crop":
        w, h = img.size
        target_w, target_h = out_size

        source_ratio = w / h
        target_ratio = target_w / target_h

        if source_ratio > target_ratio:
            new_w = int(h * target_ratio)
            new_h = h
        else:
            new_w = w
            new_h = int(w / target_ratio)

        # Lower CROP_ZOOM = show more of the original image.
        # 1.00 = current crop behavior.
        # 0.85 = slightly wider / more visible.
        # 0.75 = even more visible.
        new_w = int(new_w / CROP_ZOOM)
        new_h = int(new_h / CROP_ZOOM)

        new_w = min(new_w, w)
        new_h = min(new_h, h)

        left = (w - new_w) // 2
        top = (h - new_h) // 2

        img = img.crop((left, top, left + new_w, top + new_h))
        img = img.resize(out_size, Image.Resampling.LANCZOS)

    else:
        # pad mode: keep full analyzer visible.
        img.thumbnail(out_size, Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", out_size, CUTIN_BACKGROUND_COLOR)

        x = (CUTIN_OUTPUT_WIDTH - img.width) // 2
        y = (CUTIN_OUTPUT_HEIGHT - img.height) // 2

        canvas.paste(img, (x, y))
        img = canvas

    img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    img.save(bmp_path, "BMP")

    data = bmp_path.read_bytes()

    if data[:2] != BMP_MAGIC:
        raise RuntimeError(f"{bmp_path} does not start with BMP magic.")

    if len(data) != EXPECTED_CUTIN_SIZE:
        raise RuntimeError(
            f"{bmp_path} has wrong size: 0x{len(data):X}. "
            f"Expected 0x{EXPECTED_CUTIN_SIZE:X}.\n"
            f"Your configured output size is "
            f"{CUTIN_OUTPUT_WIDTH}x{CUTIN_OUTPUT_HEIGHT}."
        )

def load_csv_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def process_table(
    label,
    csv_path,
    bin_path,
    out_bin_path,
    analyzer_script,
    template,
    workdir,
    fit,
    debug=False,
    start=None,
    end=None,
    skip_existing=False,
    data_source="wikimon",
    profile_root="sd/profile",
):
    rows = load_csv_rows(csv_path)
    original = bytearray(Path(bin_path).read_bytes())

    if len(original) % CUTIN_SIZE != 0:
        raise RuntimeError(f"{bin_path} is not a valid D3C cut-in bin.")

    bin_slots = len(original) // CUTIN_SIZE

    print()
    print("=" * 60)
    print(f"Processing {label}")
    print(f"CSV rows: {len(rows)}")
    print(f"BIN slots: {bin_slots}")
    print("=" * 60)

    if len(rows) > bin_slots:
        print(f"WARNING: CSV has {len(rows)} rows but BIN only has {bin_slots} slots.")
        print("Extra CSV rows will be skipped.")

    table_workdir = workdir / label
    jpg_dir = table_workdir / "jpg"
    bmp_dir = table_workdir / "bmp"
    jpg_dir.mkdir(parents=True, exist_ok=True)
    bmp_dir.mkdir(parents=True, exist_ok=True)

    changed = 0
    failed = []

    max_i = min(len(rows), bin_slots)

    if start is None:
        start = 0
    if end is None or end > max_i:
        end = max_i

    for slot_id in range(start, end):
        row = rows[slot_id]
        digimon_name = choose_digimon_name(row)
        search_name = resolve_analyzer_search_name(digimon_name)

        if not digimon_name:
            print(f"[{label} {slot_id:03d}] SKIP: empty name")
            continue

        base = safe_name(digimon_name)
        jpg_out = jpg_dir / f"{label}_{slot_id:03d}_{base}.jpg"
        bmp_out = bmp_dir / f"{label}_{slot_id:03d}_{base}.bmp"

        print(f"[{label} {slot_id:03d}] {digimon_name} -> {search_name}")

        try:
            if skip_existing and bmp_out.exists():
                print("  using existing BMP")
            else:
                run_analyzer(
                    analyzer_script,
                    search_name,
                    template,
                    jpg_out,
                    debug=debug,
                    data_source=data_source,
                    profile_root=profile_root,
                )
                convert_jpg_to_d3c_bmp(jpg_out, bmp_out, fit=fit)

            bmp = bmp_out.read_bytes()

            if len(bmp) != CUTIN_SIZE:
                raise RuntimeError(f"BMP size mismatch for {bmp_out}")

            start_off = slot_id * CUTIN_SIZE
            original[start_off:start_off + CUTIN_SIZE] = bmp
            changed += 1

        except Exception as e:
            print(f"  FAILED: {e}")

            log_error(
                message=f"[{label} {slot_id:03d}] {digimon_name} -> {search_name}",
                exc=e,
            )

            failed.append((slot_id, digimon_name, str(e)))
            continue

    Path(out_bin_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_bin_path).write_bytes(original)

    print()
    print(f"{label} done.")
    print(f"Imported cut-ins: {changed}")
    print(f"Saved patched BIN: {out_bin_path}")

    if failed:
        fail_csv = table_workdir / f"{label}_failed.csv"
        with open(fail_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["slot", "name", "error"])
            writer.writerows(failed)

        print(f"Failures: {len(failed)}")
        print(f"Failure log: {fail_csv}")

    return changed, failed


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--analyzer-script", default="make_digimon_analyzer_v27.py")
    parser.add_argument("--template", default="Digimon_analyzer_blank.jpg")

    parser.add_argument("--partner-data", default="sd/data/d3c/partner.data")
    parser.add_argument("--friend-data", default="sd/data/d3c/friend.data")

    parser.add_argument("--partner-csv", default="d3c_partner_data.csv")
    parser.add_argument("--friend-csv", default="d3c_friend_data.csv")

    parser.add_argument("--partner-bin", default="sd/gfx/cutin/d3c/partner.bin")
    parser.add_argument("--friend-bin", default="sd/gfx/cutin/d3c/friend.bin")

    parser.add_argument("--out-partner-bin", default="sd/gfx/cutin/d3c/partner.bin")
    parser.add_argument("--out-friend-bin", default="sd/gfx/cutin/d3c/friend.bin")

    parser.add_argument("--workdir", default="generated_d3c_analyzer_cutins")
    parser.add_argument("--fit", choices=["pad", "stretch", "crop"], default="pad")

    parser.add_argument("--only", choices=["both", "partner", "friend"], default="both")

    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end", type=int, default=None)

    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--debug", action="store_true")

    parser.add_argument("--data-source", choices=["wikimon", "terminal"], default="wikimon")
    parser.add_argument("--profile-root", default="sd/profile")

    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    if args.only in ["both", "partner"]:
        export_to_csv(args.partner_data, args.partner_csv)

    if args.only in ["both", "friend"]:
        export_to_csv(args.friend_data, args.friend_csv)

    all_failed = []

    if args.only in ["both", "partner"]:
        _, failed = process_table(
            label="partner",
            csv_path=args.partner_csv,
            bin_path=args.partner_bin,
            out_bin_path=args.out_partner_bin,
            analyzer_script=args.analyzer_script,
            template=args.template,
            workdir=workdir,
            fit=args.fit,
            debug=args.debug,
            start=args.start,
            end=args.end,
            skip_existing=args.skip_existing,
            data_source=args.data_source,
            profile_root=args.profile_root,
        )
        all_failed.extend(("partner", *x) for x in failed)

    if args.only in ["both", "friend"]:
        _, failed = process_table(
            label="friend",
            csv_path=args.friend_csv,
            bin_path=args.friend_bin,
            out_bin_path=args.out_friend_bin,
            analyzer_script=args.analyzer_script,
            template=args.template,
            workdir=workdir,
            fit=args.fit,
            debug=args.debug,
            start=args.start,
            end=args.end,
            skip_existing=args.skip_existing,
            data_source=args.data_source,
            profile_root=args.profile_root,
        )
        all_failed.extend(("friend", *x) for x in failed)

    print()
    print("=" * 60)
    print("MASTER PROCESS COMPLETE")
    print("=" * 60)

    if all_failed:
        print(f"Total failures: {len(all_failed)}")
        print("Check the failed CSV files inside the workdir.")
    else:
        print("No failures.")


if __name__ == "__main__":
    TRACE_LOG_PATH.write_text("", encoding="utf-8")
    ERROR_LOG_PATH.write_text("", encoding="utf-8")

    with open(TRACE_LOG_PATH, "a", encoding="utf-8") as trace_file:
        tee_stdout = Tee(sys.__stdout__, trace_file)
        tee_stderr = Tee(sys.__stderr__, trace_file)

        try:
            with contextlib.redirect_stdout(tee_stdout), contextlib.redirect_stderr(tee_stderr):
                main()
        except Exception as e:
            log_error("FATAL ERROR", e)
            raise