#!/usr/bin/env python3
# python scripts/export_sprites.py sd/gfx/digimon/d3c -o sprites
# python scripts/export_sprites.py sd/gfx/digimon/dvc -o sprites
# python scripts/export_sprites.py sd/gfx/digimon/vb -o sprites
# python scripts/export_sprites.py sd/gfx/digimon/dmc -o sprites
# python scripts/export_sprites.py sd/gfx/digimon/penc -o sprites
from pathlib import Path
import argparse, csv, shutil

BMP_MAGIC = b"BM"

def parse_bmps(data):
    off = 0
    entries = []

    while off < len(data):
        if data[off:off + 2] != BMP_MAGIC:
            raise RuntimeError(f"Missing BMP magic at offset 0x{off:X}")

        size = int.from_bytes(data[off + 2:off + 6], "little")
        width = int.from_bytes(data[off + 18:off + 22], "little", signed=True)
        height = int.from_bytes(data[off + 22:off + 26], "little", signed=True)
        bpp = int.from_bytes(data[off + 28:off + 30], "little")

        if size <= 0 or off + size > len(data):
            raise RuntimeError(f"Bad BMP size 0x{size:X} at offset 0x{off:X}")

        entries.append((off, size, width, height, bpp))
        off += size

    return entries


def clean_out_dir(out_dir):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)


def export_one_bin(bin_path, out_dir, make_png):
    data = bin_path.read_bytes()
    entries = parse_bmps(data)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.csv"

    pillow_ok = False
    if make_png:
        try:
            from PIL import Image
            pillow_ok = True
        except ImportError:
            print("Pillow not installed, skipping PNG export.")

    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "filename", "offset_hex", "size", "width", "height", "bpp"])

        for i, (off, size, width, height, bpp) in enumerate(entries):
            filename = f"{bin_path.stem}_{i:03d}_{width}x{abs(height)}_{bpp}bpp.bmp"
            bmp_path = out_dir / filename
            bmp_path.write_bytes(data[off:off + size])

            writer.writerow([i, filename, f"0x{off:X}", size, width, height, bpp])

            if pillow_ok:
                png_path = bmp_path.with_suffix(".png")
                with Image.open(bmp_path) as img:
                    img.save(png_path)

    print(f"Exported {len(entries)} sprites: {bin_path} -> {out_dir}")


def collect_bin_files(input_path, recursive=False):
    if input_path.is_file():
        return [input_path]

    if recursive:
        return sorted(input_path.rglob("*.bin"), key=lambda p: str(p).lower())

    return sorted(input_path.glob("*.bin"), key=lambda p: str(p).lower())


def export_path(input_path, out_dir, make_png, recursive=False):
    input_path = Path(input_path)
    out_dir = Path(out_dir)

    if not input_path.exists():
        raise RuntimeError(f"Input not found: {input_path}")

    clean_out_dir(out_dir)

    bin_files = collect_bin_files(input_path, recursive=recursive)

    if not bin_files:
        raise RuntimeError(f"No .bin files found in {input_path}")

    if input_path.is_file():
        export_one_bin(input_path, out_dir, make_png)
        return

    for bin_path in bin_files:
        rel = bin_path.relative_to(input_path)
        subdir = out_dir / rel.with_suffix("")
        export_one_bin(bin_path, subdir, make_png)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Sprite .bin file or folder, e.g. sd/gfx/digimon/dmc")
    parser.add_argument("-o", "--out", required=True, help="Output folder")
    parser.add_argument("--png", action="store_true", help="Also export PNG files")
    parser.add_argument("--recursive", action="store_true", help="Search subfolders recursively")
    args = parser.parse_args()

    export_path(args.input, args.out, args.png, recursive=args.recursive)


if __name__ == "__main__":
    main()