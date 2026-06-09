#!/usr/bin/env python3
# python scripts/import_sprites.py sd/gfx/digimon/d3c sprites -o sd/gfx/digimon/d3c
# python scripts/import_sprites.py sd/gfx/digimon/dvc sprites -o sd/gfx/digimon/dvc
# python scripts/import_sprites.py sd/gfx/digimon/dvc sprites -o sd/gfx/digimon/vb
# python scripts/import_sprites.py sd/gfx/digimon/dmc sprites -o sd/gfx/digimon/dmc
# python scripts/import_sprites.py sd/gfx/digimon/penc sprites -o sd/gfx/digimon/penc
from pathlib import Path
import argparse, csv, tempfile

BMP_MAGIC = b"BM"

def force_full_256_palette_bmp(data: bytes) -> bytes:
    if data[:2] != BMP_MAGIC:
        return data

    file_size = int.from_bytes(data[2:6], "little")
    pixel_offset = int.from_bytes(data[10:14], "little")
    dib_size = int.from_bytes(data[14:18], "little")
    bpp = int.from_bytes(data[28:30], "little")

    if bpp != 8:
        return data

    palette_start = 14 + dib_size
    wanted_pixel_offset = palette_start + (256 * 4)

    if pixel_offset >= wanted_pixel_offset:
        return data

    missing = wanted_pixel_offset - pixel_offset

    new_data = (
        data[:pixel_offset] +
        (b"\x00" * missing) +
        data[pixel_offset:]
    )

    new_size = len(new_data)

    new_data = (
        new_data[:2] +
        new_size.to_bytes(4, "little") +
        new_data[6:10] +
        wanted_pixel_offset.to_bytes(4, "little") +
        new_data[14:]
    )

    return new_data


def image_to_matching_bmp_bytes(path, width, height, bpp):
    from PIL import Image
    import tempfile

    target_size = (abs(width), abs(height))

    with Image.open(path) as img:
        img = img.convert("RGB")
        img = img.resize(target_size, Image.Resampling.NEAREST)

        if bpp == 8:
            img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
        elif bpp == 24:
            img = img.convert("RGB")
        else:
            raise RuntimeError(f"Unsupported BMP bit depth: {bpp}")

        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
            temp_path = Path(tmp.name)

        img.save(temp_path, "BMP")
        data = temp_path.read_bytes()
        temp_path.unlink()

    if bpp == 8:
        data = force_full_256_palette_bmp(data)

    return data

def read_replacement(path, width, height, bpp, expected_size):
    data = image_to_matching_bmp_bytes(path, width, height, bpp)

    if data[:2] != BMP_MAGIC:
        raise RuntimeError(f"{path} did not convert to a valid BMP.")

    if len(data) != expected_size:
        raise RuntimeError(
            f"{path} converted to wrong size.\n"
            f"Expected: {expected_size} bytes / 0x{expected_size:X}\n"
            f"Found:    {len(data)} bytes / 0x{len(data):X}"
        )

    return data

def import_one_bin(bin_in, sprite_dir, bin_out):
    original = bytearray(bin_in.read_bytes())
    manifest_path = sprite_dir / "manifest.csv"

    if not manifest_path.exists():
        print(f"SKIP: missing manifest.csv in {sprite_dir}")
        return False

    changed = 0

    with open(manifest_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            index = int(row["index"])
            filename = row["filename"]
            off = int(row["offset_hex"], 16)
            size = int(row["size"])

            bmp_path = sprite_dir / filename
            png_path = bmp_path.with_suffix(".png")

            if bmp_path.exists():
                repl_path = bmp_path
            elif png_path.exists():
                repl_path = png_path
            else:
                continue

            width = int(row["width"])
            height = int(row["height"])
            bpp = int(row["bpp"])

            repl = read_replacement(repl_path, width, height, bpp, size)

            if len(repl) != size:
                raise RuntimeError(
                    f"{repl_path} has wrong size for sprite {index}.\n"
                    f"Expected: {size} bytes / 0x{size:X}\n"
                    f"Found:    {len(repl)} bytes / 0x{len(repl):X}\n"
                    f"Import stopped. No output written."
                )

            if repl[:2] != BMP_MAGIC:
                raise RuntimeError(f"{repl_path} does not start with BMP magic.")

            original[off:off + size] = repl
            changed += 1
            print(f"Imported sprite {index}: {repl_path.name}")

    bin_out.parent.mkdir(parents=True, exist_ok=True)
    bin_out.write_bytes(original)

    print(f"Done: {bin_in} -> {bin_out} | changed {changed}")
    return True


def collect_bin_files(input_path, recursive=False):
    if input_path.is_file():
        return [input_path]

    if recursive:
        return sorted(input_path.rglob("*.bin"), key=lambda p: str(p).lower())

    return sorted(input_path.glob("*.bin"), key=lambda p: str(p).lower())


def import_path(input_path, sprites_dir, out_path, recursive=False):
    input_path = Path(input_path)
    sprites_dir = Path(sprites_dir)
    out_path = Path(out_path)

    if not input_path.exists():
        raise RuntimeError(f"Input not found: {input_path}")

    if input_path.is_file():
        import_one_bin(input_path, sprites_dir, out_path)
        return

    bin_files = collect_bin_files(input_path, recursive=recursive)

    if not bin_files:
        raise RuntimeError(f"No .bin files found in {input_path}")

    for bin_path in bin_files:
        rel = bin_path.relative_to(input_path)
        sprite_subdir = sprites_dir / rel.with_suffix("")
        out_bin = out_path / rel

        import_one_bin(bin_path, sprite_subdir, out_bin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Original .bin file or folder, e.g. sd/gfx/digimon/dmc")
    parser.add_argument("sprites", help="Edited exported sprite folder")
    parser.add_argument("-o", "--out", required=True, help="Output .bin file or output folder")
    parser.add_argument("--recursive", action="store_true", help="Search subfolders recursively")
    args = parser.parse_args()

    import_path(args.input, args.sprites, args.out, recursive=args.recursive)


if __name__ == "__main__":
    main()