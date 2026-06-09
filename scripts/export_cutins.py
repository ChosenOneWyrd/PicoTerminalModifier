#!/usr/bin/env python3
# python scripts/export_cutins.py sd/gfx/cutin/d3c -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/dvc -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/vb -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/dmc -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/penc -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/dmx -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/pen20 -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/penz -o cutins
# python scripts/export_cutins.py sd/gfx/cutin/dm20 -o cutins
from pathlib import Path
import argparse
import shutil
import csv

BMP_MAGIC = b"BM"


def find_bmp_entries(data: bytes):
    entries = []
    offset = 0

    while offset < len(data):
        if data[offset:offset + 2] != BMP_MAGIC:
            raise RuntimeError(
                f"Expected BMP magic at offset 0x{offset:X}, "
                f"found {data[offset:offset+2]!r}"
            )

        if offset + 6 > len(data):
            raise RuntimeError(f"Truncated BMP header at offset 0x{offset:X}")

        size = int.from_bytes(data[offset + 2:offset + 6], "little")

        if size <= 0 or offset + size > len(data):
            raise RuntimeError(
                f"Bad BMP size at offset 0x{offset:X}: 0x{size:X}"
            )

        entries.append((offset, size))
        offset += size

    return entries


def export_one_bin(bin_path: Path, out_dir: Path, prefix: str, make_png: bool):
    data = bin_path.read_bytes()
    entries = find_bmp_entries(data)

    out_dir.mkdir(parents=True, exist_ok=True)

    pillow_ok = False
    if make_png:
        try:
            from PIL import Image
            pillow_ok = True
        except ImportError:
            print("Pillow not installed, skipping PNG export.")

    manifest_rows = []

    for i, (offset, size) in enumerate(entries):
        chunk = data[offset:offset + size]

        bmp_name = f"{prefix}_{i:03d}_0x{size:X}.bmp"
        bmp_path = out_dir / bmp_name
        bmp_path.write_bytes(chunk)

        png_name = ""
        if pillow_ok:
            png_name = f"{prefix}_{i:03d}_0x{size:X}.png"
            png_path = out_dir / png_name
            with Image.open(bmp_path) as img:
                img.save(png_path)

        manifest_rows.append({
            "index": i,
            "filename": bmp_name,
            "png": png_name,
            "offset_hex": f"0x{offset:X}",
            "size": size,
            "size_hex": f"0x{size:X}",
        })

    with open(out_dir / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "filename", "png", "offset_hex", "size", "size_hex"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Exported {len(entries)} cut-ins from {bin_path}")
    print(f"Output folder: {out_dir}")


def collect_bins(input_path: Path, recursive: bool):
    if input_path.is_file():
        return [input_path]

    if recursive:
        return sorted(input_path.rglob("*.bin"), key=lambda p: str(p).lower())

    return sorted(input_path.glob("*.bin"), key=lambda p: str(p).lower())


def export_path(input_path: Path, out_root: Path, make_png: bool, recursive: bool):
    if out_root.exists():
        print(f"Cleaning existing output folder: {out_root}")
        shutil.rmtree(out_root)

    out_root.mkdir(parents=True, exist_ok=True)

    bins = collect_bins(input_path, recursive)

    if not bins:
        raise RuntimeError(f"No .bin files found: {input_path}")

    total = 0

    for bin_path in bins:
        if input_path.is_file():
            subdir = out_root
        else:
            rel = bin_path.relative_to(input_path)
            subdir = out_root / rel.with_suffix("")

        prefix = bin_path.stem

        try:
            export_one_bin(bin_path, subdir, prefix, make_png)
            total += 1
        except Exception as e:
            print(f"SKIP not cut-in bin: {bin_path} ({e})")

    print()
    print(f"Done. Exported from {total} bin file(s).")
    print(f"Output folder: {out_root}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input .bin file or folder")
    parser.add_argument("-o", "--out", required=True, help="Output folder")
    parser.add_argument("--png", action="store_true", help="Also export PNG files")
    parser.add_argument("--recursive", action="store_true", help="Search folders recursively")
    args = parser.parse_args()

    export_path(
        Path(args.input),
        Path(args.out),
        make_png=args.png,
        recursive=args.recursive,
    )


if __name__ == "__main__":
    main()