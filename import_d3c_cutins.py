#!/usr/bin/env python3
# Usage: python import_d3c_cutins.py sd/gfx/cutin/d3c/partner.bin partner_cutins
from pathlib import Path
import argparse
import shutil
import tempfile

CUTIN_SIZE = 0xE536
BMP_MAGIC = b"BM"

def png_to_bmp_bytes(path: Path) -> bytes:
    from PIL import Image

    with Image.open(path) as img:
        img = img.convert("P")  # 8-bit indexed BMP

        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
            temp_path = Path(tmp.name)

        img.save(temp_path, "BMP")
        data = temp_path.read_bytes()
        temp_path.unlink()

    return data

def read_replacement(path: Path) -> bytes:
    if path.suffix.lower() == ".png":
        return png_to_bmp_bytes(path)

    data = path.read_bytes()

    if data[:2] != BMP_MAGIC:
        raise RuntimeError(f"{path} is not a BMP file.")

    return data

def import_cutins(bin_in: Path, folder: Path, bin_out: Path, prefix: str):
    original = bytearray(bin_in.read_bytes())

    if len(original) % CUTIN_SIZE != 0:
        raise RuntimeError(
            f"{bin_in} size is not divisible by 0x{CUTIN_SIZE:X}"
        )

    count = len(original) // CUTIN_SIZE
    changed = 0

    for i in range(count):
        bmp_path = folder / f"{prefix}_{i:03d}.bmp"
        png_path = folder / f"{prefix}_{i:03d}.png"

        if bmp_path.exists():
            repl_path = bmp_path
        elif png_path.exists():
            repl_path = png_path
        else:
            continue

        repl = read_replacement(repl_path)

        if len(repl) != CUTIN_SIZE:
            raise RuntimeError(
                f"{repl_path} has wrong size.\n"
                f"Expected: {CUTIN_SIZE} bytes / 0x{CUTIN_SIZE:X}\n"
                f"Found:    {len(repl)} bytes / 0x{len(repl):X}\n"
                f"Import stopped. No output written."
            )

        if repl[:2] != BMP_MAGIC:
            raise RuntimeError(f"{repl_path} does not start with BMP magic.")

        start = i * CUTIN_SIZE
        original[start:start + CUTIN_SIZE] = repl
        changed += 1
        print(f"Imported {repl_path.name} into slot {i}")

    bin_out.write_bytes(original)

    print()
    print(f"Done. Imported {changed} cut-ins.")
    print(f"Output written to: {bin_out}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bin", help="Original partner.bin or friend.bin")
    parser.add_argument("folder", help="Folder containing edited cut-ins")
    parser.add_argument("-o", "--out", default=None, help="Output bin path")
    parser.add_argument("--prefix", default=None, help="Filename prefix")

    args = parser.parse_args()

    bin_in = Path(args.bin)
    folder = Path(args.folder)

    prefix = args.prefix if args.prefix else bin_in.stem
    bin_out = Path(args.out) if args.out else bin_in.with_name(bin_in.stem + ".bin")

    import_cutins(bin_in, folder, bin_out, prefix)

if __name__ == "__main__":
    main()