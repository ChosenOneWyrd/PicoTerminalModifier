#!/usr/bin/env python3
# Usage: python export_d3c_cutins.py sd/gfx/cutin/d3c/friend.bin
# python export_d3c_cutins.py sd/gfx/cutin/d3c/friend.bin
from pathlib import Path
import argparse

CUTIN_SIZE = 0xE536  # 58678 bytes
BMP_MAGIC = b"BM"

def export_cutins(bin_path: Path, out_dir: Path, prefix: str, make_png: bool):
    data = bin_path.read_bytes()

    if len(data) % CUTIN_SIZE != 0:
        raise RuntimeError(
            f"{bin_path} size is not divisible by 0x{CUTIN_SIZE:X}. "
            f"Size = {len(data)} bytes"
        )

    count = len(data) // CUTIN_SIZE
    out_dir.mkdir(parents=True, exist_ok=True)

    pillow_ok = False
    if make_png:
        try:
            from PIL import Image
            pillow_ok = True
        except ImportError:
            print("Pillow not installed, skipping PNG export.")
            print("Install with: pip install pillow")

    for i in range(count):
        start = i * CUTIN_SIZE
        end = start + CUTIN_SIZE
        chunk = data[start:end]

        if chunk[:2] != BMP_MAGIC:
            raise RuntimeError(
                f"Entry {i} does not start with BMP magic at offset 0x{start:X}"
            )

        bmp_path = out_dir / f"{prefix}_{i:03d}.bmp"
        bmp_path.write_bytes(chunk)

        if pillow_ok:
            png_path = out_dir / f"{prefix}_{i:03d}.png"
            with Image.open(bmp_path) as img:
                img.save(png_path)

    print(f"Exported {count} cut-ins from {bin_path}")
    print(f"Output folder: {out_dir}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bin", help="partner.bin or friend.bin")
    parser.add_argument("-o", "--out", default=None, help="Output folder")
    parser.add_argument("--prefix", default=None, help="Output filename prefix")
    parser.add_argument("--png", action="store_true", help="Also export PNG files")
    args = parser.parse_args()

    bin_path = Path(args.bin)

    prefix = args.prefix
    if prefix is None:
        prefix = bin_path.stem

    out_dir = Path(args.out) if args.out else Path(f"{bin_path.stem}_cutins")

    export_cutins(bin_path, out_dir, prefix, args.png)

if __name__ == "__main__":
    main()