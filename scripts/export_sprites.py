"""
Export embedded Digimon sprite BMP records as transparent PNG files.

The embedded BIN records remain BMP internally, but this script exports only
editable PNG files. Exact RGB green #00FF00 is converted to PNG transparency.

Examples:
    python scripts/export_sprites.py sd/gfx/digimon/d3c -o sprites
    python scripts/export_sprites.py sd/gfx/digimon/dvc -o sprites
    python scripts/export_sprites.py sd/gfx/digimon/vb  -o sprites
    python scripts/export_sprites.py sd/gfx/digimon/dmc -o sprites
    python scripts/export_sprites.py sd/gfx/digimon/penc -o sprites

For recursive folders:
    python scripts/export_sprites.py sd/gfx/digimon -o sprites --recursive
"""

from __future__ import annotations

import argparse
import csv
import shutil
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit(
        "Pillow is required.\n"
        "Install it with:\n"
        "  python -m pip install Pillow"
    ) from exc


BMP_MAGIC = b"BM"
TRANSPARENT_RGB = (0, 255, 0)


class SpriteFormatError(RuntimeError):
    pass


def parse_bmps(data: bytes) -> List[Tuple[int, int, int, int, int]]:
    """
    Return records as:
        (offset, size, width, signed_height, bits_per_pixel)
    """

    offset = 0
    entries: List[Tuple[int, int, int, int, int]] = []

    while offset < len(data):
        if offset + 54 > len(data):
            raise SpriteFormatError(
                f"Truncated BMP header at offset 0x{offset:X}"
            )

        if data[offset:offset + 2] != BMP_MAGIC:
            raise SpriteFormatError(
                f"Missing BMP magic at offset 0x{offset:X}"
            )

        size = int.from_bytes(
            data[offset + 2:offset + 6],
            "little",
        )
        width = int.from_bytes(
            data[offset + 18:offset + 22],
            "little",
            signed=True,
        )
        height = int.from_bytes(
            data[offset + 22:offset + 26],
            "little",
            signed=True,
        )
        bpp = int.from_bytes(
            data[offset + 28:offset + 30],
            "little",
        )
        compression = int.from_bytes(
            data[offset + 30:offset + 34],
            "little",
        )

        if size <= 0:
            raise SpriteFormatError(
                f"Invalid BMP size {size} at offset 0x{offset:X}"
            )

        if offset + size > len(data):
            raise SpriteFormatError(
                f"BMP at 0x{offset:X} extends beyond the BIN.\n"
                f"Record size: {size}\n"
                f"BIN size:    {len(data)}"
            )

        if width <= 0 or height == 0:
            raise SpriteFormatError(
                f"Invalid BMP dimensions at offset 0x{offset:X}: "
                f"{width}x{height}"
            )

        if bpp != 8:
            raise SpriteFormatError(
                f"Unsupported BMP depth at offset 0x{offset:X}: "
                f"{bpp} bpp. These scripts require 8-bit indexed BMP records."
            )

        if compression != 0:
            raise SpriteFormatError(
                f"Unsupported compressed BMP at offset 0x{offset:X}. "
                f"Compression value: {compression}"
            )

        entries.append((offset, size, width, height, bpp))
        offset += size

    if offset != len(data):
        raise SpriteFormatError(
            f"Parsing ended at 0x{offset:X}, but BIN size is 0x{len(data):X}"
        )

    return entries


def bmp_record_to_transparent_png(
    bmp_data: bytes,
    png_path: Path,
) -> None:
    """
    Decode an embedded BMP and export it as an RGBA PNG.

    Every exact #00FF00 source pixel becomes fully transparent.
    """

    try:
        with Image.open(BytesIO(bmp_data)) as source:
            rgba = source.convert("RGBA")
    except Exception as exc:
        raise SpriteFormatError(
            f"Could not decode embedded BMP for {png_path.name}: {exc}"
        ) from exc

    pixels = list(rgba.getdata())
    converted = []

    for red, green, blue, _alpha in pixels:
        if (red, green, blue) == TRANSPARENT_RGB:
            converted.append((0, 255, 0, 0))
        else:
            converted.append((red, green, blue, 255))

    rgba.putdata(converted)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(png_path, "PNG", optimize=False)


def clean_out_dir(out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)


def export_one_bin(bin_path: Path, out_dir: Path) -> None:
    data = bin_path.read_bytes()
    entries = parse_bmps(data)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.csv"

    with manifest_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as manifest_file:
        writer = csv.writer(manifest_file)

        writer.writerow(
            [
                "index",
                "filename",
                "offset_hex",
                "size",
                "width",
                "height",
                "bpp",
            ]
        )

        for index, (offset, size, width, height, bpp) in enumerate(entries):
            display_height = abs(height)

            filename = (
                f"{bin_path.stem}_{index:03d}_"
                f"{width}x{display_height}_{bpp}bpp.png"
            )
            png_path = out_dir / filename

            bmp_record = data[offset:offset + size]
            bmp_record_to_transparent_png(bmp_record, png_path)

            writer.writerow(
                [
                    index,
                    filename,
                    f"0x{offset:X}",
                    size,
                    width,
                    height,
                    bpp,
                ]
            )

    print(
        f"Exported {len(entries)} transparent PNG sprites:\n"
        f"  Input:    {bin_path}\n"
        f"  Output:   {out_dir}\n"
        f"  Manifest: {manifest_path}"
    )


def collect_bin_files(
    input_path: Path,
    recursive: bool = False,
) -> List[Path]:
    if input_path.is_file():
        return [input_path]

    if recursive:
        return sorted(
            input_path.rglob("*.bin"),
            key=lambda path: str(path).lower(),
        )

    return sorted(
        input_path.glob("*.bin"),
        key=lambda path: str(path).lower(),
    )


def export_path(
    input_path: Path,
    out_dir: Path,
    recursive: bool = False,
) -> None:
    if not input_path.exists():
        raise RuntimeError(f"Input not found: {input_path}")

    clean_out_dir(out_dir)

    bin_files = collect_bin_files(
        input_path,
        recursive=recursive,
    )

    if not bin_files:
        raise RuntimeError(
            f"No .bin files found in {input_path}"
        )

    if input_path.is_file():
        export_one_bin(input_path, out_dir)
        return

    for bin_path in bin_files:
        relative_path = bin_path.relative_to(input_path)
        sprite_subdir = out_dir / relative_path.with_suffix("")
        export_one_bin(bin_path, sprite_subdir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export embedded 8-bit BMP sprite records as "
            "transparent PNG files."
        )
    )
    parser.add_argument(
        "input",
        help=(
            "Sprite .bin file or folder, "
            "for example sd/gfx/digimon/d3c"
        ),
    )
    parser.add_argument(
        "-o",
        "--out",
        required=True,
        help="Output sprite folder",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search input subfolders recursively",
    )

    args = parser.parse_args()

    export_path(
        Path(args.input),
        Path(args.out),
        recursive=args.recursive,
    )


if __name__ == "__main__":
    main()