#!/usr/bin/env python3
"""
Export embedded Digimon sprite BMP records as transparent PNG files named from
the Digimon data CSV.

This is a separate named-sprite exporter for PicoTerminalModifier-style SD data.

Expected mapping:
    131.bin sprite index 0  -> CSV row where file == 131.data and row_index == 0
    131.bin sprite index 1  -> CSV row where file == 131.data and row_index == 1
    ...

By default it uses col2 from the CSV because your vb_data.csv stores the display
Digimon name there. If your CSV has schema headers such as name_web/name_en,
you can pass --name-column name_web or --name-column name_en.

Examples:
    python scripts/export_sprites_with_names.py sd/gfx/digimon/vb \
        --csv data/vb_data.csv \
        -o named_sprites/vb

    python scripts/export_sprites_with_names.py sd/gfx/digimon/vb/131.bin \
        --csv data/vb_data.csv \
        -o named_sprites/131

    python scripts/export_sprites_with_names.py sd/gfx/digimon \
        --csv data/vb_data.csv \
        -o named_sprites \
        --recursive

Filename template fields:
    {index}       sprite index as an integer
    {index:03d}   sprite index padded to 3 digits
    {name}        sanitized Digimon name from CSV
    {bin}         source bin file stem, for example 131
    {width}       BMP width
    {height}      absolute BMP height
    {bpp}         BMP bits per pixel

Default template:
    {index:03d}_{name}.png
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple

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
    Return BMP records as:
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
                f"{bpp} bpp. This script requires 8-bit indexed BMP records."
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


def normalize_csv_file_key(value: str) -> str:
    """
    Match CSV file values robustly.

    export_data_to_csv.py writes file.name, for example 131.data.
    This also handles accidental relative paths by matching the basename.
    """

    value = (value or "").replace("\\", "/").strip()
    return Path(value).name.lower()


def pick_name_column(
    fieldnames: List[str],
    requested_column: str,
) -> str:
    """
    Choose the CSV column that contains the Digimon display name.

    For your vb_data.csv, requested_column='col2' is correct.
    For CSVs exported with known schemas, name_web/name_en may exist instead.
    """

    if requested_column in fieldnames:
        return requested_column

    fallbacks = [
        "name_web",
        "name_en",
        "col2",
        "col3",
        "col1",
    ]

    for column in fallbacks:
        if column in fieldnames:
            print(
                f"Requested name column {requested_column!r} was not found; "
                f"using {column!r} instead."
            )
            return column

    raise RuntimeError(
        "Could not find a usable name column in the CSV.\n"
        f"Requested: {requested_column}\n"
        f"Available columns: {', '.join(fieldnames)}"
    )


def load_name_map(
    csv_path: Path,
    name_column: str,
) -> Dict[Tuple[str, int], str]:
    """
    Return:
        {(data_filename_lower, row_index): digimon_name}

    Example key:
        ("131.data", 0) -> "Fusamon"
    """

    if not csv_path.exists():
        raise RuntimeError(f"CSV not found: {csv_path}")

    names: Dict[Tuple[str, int], str] = {}

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            raise RuntimeError(f"CSV has no header: {csv_path}")

        if "file" not in reader.fieldnames or "row_index" not in reader.fieldnames:
            raise RuntimeError(
                "CSV must contain the columns 'file' and 'row_index'.\n"
                "Please use the CSV created by export_data_to_csv.py."
            )

        chosen_name_column = pick_name_column(
            reader.fieldnames,
            name_column,
        )

        for csv_line_number, row in enumerate(reader, start=2):
            file_key = normalize_csv_file_key(row.get("file", ""))

            try:
                row_index = int((row.get("row_index") or "").strip())
            except ValueError:
                raise RuntimeError(
                    f"Invalid row_index at CSV line {csv_line_number}: "
                    f"{row.get('row_index')!r}"
                )

            name = (row.get(chosen_name_column) or "").strip()

            if not name:
                name = f"unnamed_{row_index:03d}"

            names[(file_key, row_index)] = name

    return names


# Windows-forbidden filename chars plus ASCII control chars.
_BAD_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]+')


def sanitize_filename_part(value: str) -> str:
    """
    Keep Digimon names readable while making them safe as filenames.

    Examples:
        "N.E.O" remains "N.E.O"
        "Agumon / Gabumon" becomes "Agumon_Gabumon"
    """

    value = unicodedata.normalize("NFC", value)
    value = value.strip()
    value = _BAD_FILENAME_CHARS.sub("_", value)
    value = re.sub(r"\s+", " ", value)
    value = value.replace(" ", "_")
    value = re.sub(r"_+", "_", value)
    value = value.strip(" ._")

    if not value:
        value = "unnamed"

    return value


def unique_path(path: Path) -> Path:
    """
    Avoid overwriting if two sprites produce the same filename.
    """

    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix

    counter = 2
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def make_sprite_filename(
    template: str,
    index: int,
    name: str,
    bin_stem: str,
    width: int,
    height: int,
    bpp: int,
) -> str:
    safe_name = sanitize_filename_part(name)
    safe_bin = sanitize_filename_part(bin_stem)

    try:
        filename = template.format(
            index=index,
            name=safe_name,
            bin=safe_bin,
            width=width,
            height=height,
            bpp=bpp,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Invalid filename template: {template!r}\n"
            "Available fields: {index}, {name}, {bin}, {width}, {height}, {bpp}"
        ) from exc

    filename = filename.strip()

    if not filename.lower().endswith(".png"):
        filename += ".png"

    # Sanitize the final filename too, but keep the extension dot.
    final_path = Path(filename)
    final_stem = sanitize_filename_part(final_path.stem)
    return f"{final_stem}.png"


def export_one_bin(
    bin_path: Path,
    out_dir: Path,
    name_map: Dict[Tuple[str, int], str],
    data_extension: str,
    filename_template: str,
    strict_names: bool,
) -> None:
    data = bin_path.read_bytes()
    entries = parse_bmps(data)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.csv"

    data_filename = f"{bin_path.stem}{data_extension}"
    data_key = data_filename.lower()

    missing_names = 0

    with manifest_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as manifest_file:
        writer = csv.writer(manifest_file)

        writer.writerow(
            [
                "index",
                "digimon_name",
                "filename",
                "source_bin",
                "source_data_file",
                "row_index",
                "offset_hex",
                "size",
                "width",
                "height",
                "bpp",
                "name_found",
            ]
        )

        for index, (offset, size, width, height, bpp) in enumerate(entries):
            display_height = abs(height)
            name_found = True
            digimon_name = name_map.get((data_key, index))

            if digimon_name is None:
                name_found = False
                missing_names += 1

                if strict_names:
                    raise RuntimeError(
                        f"No CSV name found for {bin_path.name} sprite index {index}.\n"
                        f"Expected CSV row: file={data_filename}, row_index={index}"
                    )

                digimon_name = f"{bin_path.stem}_{index:03d}"

            filename = make_sprite_filename(
                filename_template,
                index=index,
                name=digimon_name,
                bin_stem=bin_path.stem,
                width=width,
                height=display_height,
                bpp=bpp,
            )

            png_path = unique_path(out_dir / filename)

            bmp_record = data[offset:offset + size]
            bmp_record_to_transparent_png(bmp_record, png_path)

            writer.writerow(
                [
                    index,
                    digimon_name,
                    png_path.name,
                    bin_path.name,
                    data_filename,
                    index,
                    f"0x{offset:X}",
                    size,
                    width,
                    height,
                    bpp,
                    "yes" if name_found else "no",
                ]
            )

    print(
        f"Exported {len(entries)} transparent PNG sprites:\n"
        f"  Input:    {bin_path}\n"
        f"  Output:   {out_dir}\n"
        f"  Manifest: {manifest_path}"
    )

    if missing_names:
        print(
            f"  Warning: {missing_names} sprite(s) did not have CSV names "
            f"and used fallback names."
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
    csv_path: Path,
    name_column: str,
    data_extension: str,
    filename_template: str,
    recursive: bool = False,
    strict_names: bool = False,
    clean: bool = True,
) -> None:
    if not input_path.exists():
        raise RuntimeError(f"Input not found: {input_path}")

    if not data_extension.startswith("."):
        data_extension = "." + data_extension

    if clean:
        clean_out_dir(out_dir)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    name_map = load_name_map(
        csv_path=csv_path,
        name_column=name_column,
    )

    bin_files = collect_bin_files(
        input_path,
        recursive=recursive,
    )

    if not bin_files:
        raise RuntimeError(
            f"No .bin files found in {input_path}"
        )

    if input_path.is_file():
        export_one_bin(
            input_path,
            out_dir,
            name_map=name_map,
            data_extension=data_extension,
            filename_template=filename_template,
            strict_names=strict_names,
        )
        return

    for bin_path in bin_files:
        relative_path = bin_path.relative_to(input_path)
        sprite_subdir = out_dir / relative_path.with_suffix("")

        export_one_bin(
            bin_path,
            sprite_subdir,
            name_map=name_map,
            data_extension=data_extension,
            filename_template=filename_template,
            strict_names=strict_names,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export embedded 8-bit BMP sprite records as transparent PNG files "
            "named from Digimon data CSV rows."
        )
    )
    parser.add_argument(
        "input",
        help=(
            "Sprite .bin file or folder, for example sd/gfx/digimon/vb"
        ),
    )
    parser.add_argument(
        "--csv",
        required=True,
        help=(
            "CSV exported by export_data_to_csv.py, for example data/vb_data.csv"
        ),
    )
    parser.add_argument(
        "-o",
        "--out",
        required=True,
        help="Output sprite folder",
    )
    parser.add_argument(
        "--name-column",
        default="col2",
        help=(
            "CSV column to use for the Digimon name. "
            "Default: col2. You may also use name_web or name_en."
        ),
    )
    parser.add_argument(
        "--data-extension",
        default=".data",
        help=(
            "Data filename extension paired with each .bin file. "
            "Default: .data, so 131.bin maps to 131.data."
        ),
    )
    parser.add_argument(
        "--filename-template",
        default="{index:03d}_{name}.png",
        help=(
            "Output filename template. Default: {index:03d}_{name}.png. "
            "Available fields: {index}, {name}, {bin}, {width}, {height}, {bpp}"
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search input subfolders recursively",
    )
    parser.add_argument(
        "--strict-names",
        action="store_true",
        help=(
            "Fail if any sprite index does not have a matching CSV name."
        ),
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help=(
            "Do not delete the output folder before exporting. "
            "Duplicate filenames will get _2, _3, etc."
        ),
    )

    args = parser.parse_args()

    export_path(
        input_path=Path(args.input),
        out_dir=Path(args.out),
        csv_path=Path(args.csv),
        name_column=args.name_column,
        data_extension=args.data_extension,
        filename_template=args.filename_template,
        recursive=args.recursive,
        strict_names=args.strict_names,
        clean=not args.no_clean,
    )


if __name__ == "__main__":
    main()
