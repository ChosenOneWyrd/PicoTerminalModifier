#!/usr/bin/env python3
# python scripts/import_cutins.py sd/gfx/cutin/d3c cutins -o sd/gfx/cutin/d3c
# python scripts/import_cutins.py sd/gfx/cutin/dvc cutins -o sd/gfx/cutin/dvc
# python scripts/import_cutins.py sd/gfx/cutin/vb cutins -o sd/gfx/cutin/vb
# python scripts/import_cutins.py sd/gfx/cutin/dmc cutins -o sd/gfx/cutin/dmc
# python scripts/import_cutins.py sd/gfx/cutin/penc cutins -o sd/gfx/cutin/penc
# python scripts/import_cutins.py sd/gfx/cutin/dmx cutins -o sd/gfx/cutin/dmx
# python scripts/import_cutins.py sd/gfx/cutin/pen20 cutins -o sd/gfx/cutin/pen20
# python scripts/import_cutins.py sd/gfx/cutin/penz cutins -o sd/gfx/cutin/penz
# python scripts/import_cutins.py sd/gfx/cutin/dm20 cutins -o sd/gfx/cutin/dm20

from pathlib import Path
import argparse
import csv
import tempfile

BMP_MAGIC = b"BM"


def png_to_bmp_bytes(path: Path, expected_size: int) -> bytes:
    from PIL import Image

    with Image.open(path) as img:
        img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)

        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
            temp_path = Path(tmp.name)

        img.save(temp_path, "BMP")
        data = temp_path.read_bytes()
        temp_path.unlink()

    if len(data) != expected_size:
        raise RuntimeError(
            f"{path} converted to wrong BMP size.\n"
            f"Expected: {expected_size} / 0x{expected_size:X}\n"
            f"Found:    {len(data)} / 0x{len(data):X}"
        )

    return data


def read_replacement(path: Path, expected_size: int) -> bytes:
    if path.suffix.lower() == ".png":
        return png_to_bmp_bytes(path, expected_size)

    data = path.read_bytes()

    if data[:2] != BMP_MAGIC:
        raise RuntimeError(f"{path} is not a BMP file.")

    if len(data) != expected_size:
        raise RuntimeError(
            f"{path} has wrong size.\n"
            f"Expected: {expected_size} / 0x{expected_size:X}\n"
            f"Found:    {len(data)} / 0x{len(data):X}"
        )

    return data


def import_one_bin(bin_in: Path, cutin_dir: Path, bin_out: Path):
    manifest_path = cutin_dir / "manifest.csv"

    if not manifest_path.exists():
        print(f"SKIP missing manifest: {cutin_dir}")
        return False

    original = bytearray(bin_in.read_bytes())
    changed = 0

    with open(manifest_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            index = int(row["index"])
            offset = int(row["offset_hex"], 16)
            size = int(row["size"])

            bmp_path = cutin_dir / row["filename"]
            png_path = bmp_path.with_suffix(".png")

            if bmp_path.exists():
                repl_path = bmp_path
            elif png_path.exists():
                repl_path = png_path
            else:
                continue

            repl = read_replacement(repl_path, size)

            if original[offset:offset + 2] != BMP_MAGIC:
                raise RuntimeError(
                    f"Original bin has no BMP at offset 0x{offset:X} for slot {index}"
                )

            original[offset:offset + size] = repl
            changed += 1
            print(f"Imported slot {index}: {repl_path.name}")

    bin_out.parent.mkdir(parents=True, exist_ok=True)
    bin_out.write_bytes(original)

    print(f"Done: {bin_in} -> {bin_out} | changed {changed}")
    return True


def collect_bins(input_path: Path, recursive: bool):
    if input_path.is_file():
        return [input_path]

    if recursive:
        return sorted(input_path.rglob("*.bin"), key=lambda p: str(p).lower())

    return sorted(input_path.glob("*.bin"), key=lambda p: str(p).lower())


def import_path(input_path: Path, cutins_root: Path, out_path: Path, recursive: bool):
    bins = collect_bins(input_path, recursive)

    if not bins:
        raise RuntimeError(f"No .bin files found: {input_path}")

    for bin_path in bins:
        if input_path.is_file():
            cutin_dir = cutins_root
            bin_out = out_path
        else:
            rel = bin_path.relative_to(input_path)
            cutin_dir = cutins_root / rel.with_suffix("")
            bin_out = out_path / rel

        import_one_bin(bin_path, cutin_dir, bin_out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Original .bin file or folder")
    parser.add_argument("cutins", help="Edited exported cutins folder")
    parser.add_argument("-o", "--out", required=True, help="Output .bin file or folder")
    parser.add_argument("--recursive", action="store_true", help="Search folders recursively")
    args = parser.parse_args()

    import_path(
        Path(args.input),
        Path(args.cutins),
        Path(args.out),
        recursive=args.recursive,
    )


if __name__ == "__main__":
    main()