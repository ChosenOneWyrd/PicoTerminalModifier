"""
Import edited transparent PNG sprites into Digimon sprite BIN files.

Transparent PNG pixels are converted back to palette index 0, whose color is
forced to exact RGB #00FF00. This preserves transparency on the Pico Terminal.

The original embedded BMP header, record offset, dimensions, record length,
pixel orientation, and 256-entry palette layout are preserved.

Examples:
    python scripts/import_sprites.py \
        sd/gfx/digimon/d3c sprites \
        -o sd/gfx/digimon/d3c

    python scripts/import_sprites.py \
        sd/gfx/digimon/dvc sprites \
        -o sd/gfx/digimon/dvc

    python scripts/import_sprites.py \
        sd/gfx/digimon/vb sprites \
        -o sd/gfx/digimon/vb

For recursive folders:
    python scripts/import_sprites.py \
        sd/gfx/digimon sprites \
        -o sd/gfx/digimon_edited \
        --recursive
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

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
ALPHA_THRESHOLD = 128


class SpriteImportError(RuntimeError):
    pass


def parse_original_bmp(original_record: bytes) -> Dict[str, int]:
    if len(original_record) < 54:
        raise SpriteImportError("Original BMP record is too short.")

    if original_record[:2] != BMP_MAGIC:
        raise SpriteImportError(
            "Original record does not start with BMP magic."
        )

    file_size = int.from_bytes(
        original_record[2:6],
        "little",
    )
    pixel_offset = int.from_bytes(
        original_record[10:14],
        "little",
    )
    dib_size = int.from_bytes(
        original_record[14:18],
        "little",
    )
    width = int.from_bytes(
        original_record[18:22],
        "little",
        signed=True,
    )
    signed_height = int.from_bytes(
        original_record[22:26],
        "little",
        signed=True,
    )
    planes = int.from_bytes(
        original_record[26:28],
        "little",
    )
    bpp = int.from_bytes(
        original_record[28:30],
        "little",
    )
    compression = int.from_bytes(
        original_record[30:34],
        "little",
    )

    if file_size != len(original_record):
        raise SpriteImportError(
            "Original BMP size field does not match its record size.\n"
            f"Header size: {file_size}\n"
            f"Record size: {len(original_record)}"
        )

    if width <= 0 or signed_height == 0:
        raise SpriteImportError(
            f"Invalid original dimensions: {width}x{signed_height}"
        )

    if planes != 1:
        raise SpriteImportError(
            f"Unsupported BMP plane count: {planes}"
        )

    if bpp != 8:
        raise SpriteImportError(
            f"Unsupported BMP depth: {bpp}. "
            "Only 8-bit indexed sprite records are supported."
        )

    if compression != 0:
        raise SpriteImportError(
            f"Compressed BMP records are unsupported. "
            f"Compression value: {compression}"
        )

    palette_start = 14 + dib_size
    palette_end = palette_start + 256 * 4

    if pixel_offset < palette_end:
        raise SpriteImportError(
            "Original BMP does not reserve a full 256-entry palette.\n"
            f"Pixel offset:          {pixel_offset}\n"
            f"Required palette end:  {palette_end}"
        )

    height = abs(signed_height)
    row_stride = ((width + 3) // 4) * 4
    required_pixel_bytes = row_stride * height

    if pixel_offset + required_pixel_bytes > len(original_record):
        raise SpriteImportError(
            "Original BMP pixel data extends beyond the record."
        )

    return {
        "file_size": file_size,
        "pixel_offset": pixel_offset,
        "dib_size": dib_size,
        "palette_start": palette_start,
        "width": width,
        "height": height,
        "signed_height": signed_height,
        "bpp": bpp,
        "row_stride": row_stride,
    }


def validate_png(
    png_path: Path,
    expected_width: int,
    expected_height: int,
) -> Image.Image:
    try:
        with Image.open(png_path) as source:
            source.load()
            image = source.convert("RGBA")
    except Exception as exc:
        raise SpriteImportError(
            f"Could not open PNG {png_path}: {exc}"
        ) from exc

    if image.size != (expected_width, expected_height):
        raise SpriteImportError(
            f"{png_path} has the wrong dimensions.\n"
            f"Expected: {expected_width}x{expected_height}\n"
            f"Found:    {image.width}x{image.height}\n"
            "The import was cancelled. Resize the PNG without changing "
            "the canvas dimensions."
        )

    return image


def build_indexed_pixels(
    rgba: Image.Image,
) -> tuple[List[int], List[int]]:
    """
    Return:
        indexed_pixels:
            One palette index per image pixel. Index 0 is transparency.

        palette_rgb:
            Flat RGB palette containing exactly 256 entries.

    Opaque pixels are quantized to at most 255 colors. Palette index 0 is
    always reserved for exact green #00FF00.
    """

    width, height = rgba.size
    alpha_channel = rgba.getchannel("A")

    rgb_image = Image.new(
        "RGB",
        (width, height),
        (0, 0, 0),
    )

    # Only copy visible pixels into the image used for quantization.
    rgb_image.paste(
        rgba.convert("RGB"),
        mask=alpha_channel,
    )

    quantized = rgb_image.quantize(
        colors=255,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )

    quantized_palette = quantized.getpalette()

    if quantized_palette is None:
        raise SpriteImportError(
            "Pillow did not generate an indexed palette."
        )

    quantized_palette = quantized_palette[:255 * 3]

    while len(quantized_palette) < 255 * 3:
        quantized_palette.extend([0, 0, 0])

    # Palette index 0 is the device transparency key.
    palette_rgb = [
        TRANSPARENT_RGB[0],
        TRANSPARENT_RGB[1],
        TRANSPARENT_RGB[2],
    ]
    palette_rgb.extend(quantized_palette)

    if len(palette_rgb) != 256 * 3:
        raise SpriteImportError(
            f"Internal palette size error: {len(palette_rgb)} values"
        )

    source_indices = list(quantized.getdata())
    source_alpha = list(alpha_channel.getdata())

    indexed_pixels: List[int] = []

    semi_transparent_count = 0

    for color_index, alpha in zip(source_indices, source_alpha):
        if alpha < ALPHA_THRESHOLD:
            indexed_pixels.append(0)
        else:
            if alpha < 255:
                semi_transparent_count += 1

            # Quantized colors use 0–254. Shift them to 1–255 because
            # palette index 0 is reserved for transparency.
            indexed_pixels.append(color_index + 1)

    if semi_transparent_count:
        print(
            f"  WARNING: {semi_transparent_count} semi-transparent pixels "
            f"were treated as opaque because their alpha was "
            f">= {ALPHA_THRESHOLD}."
        )

    return indexed_pixels, palette_rgb


def replace_palette(
    output_record: bytearray,
    palette_start: int,
    palette_rgb: List[int],
) -> None:
    """
    BMP palette entries are stored as BGRA bytes.
    """

    for palette_index in range(256):
        source = palette_index * 3

        red = palette_rgb[source]
        green = palette_rgb[source + 1]
        blue = palette_rgb[source + 2]

        destination = palette_start + palette_index * 4

        output_record[destination:destination + 4] = bytes(
            [
                blue,
                green,
                red,
                0,
            ]
        )


def replace_pixels(
    output_record: bytearray,
    indexed_pixels: List[int],
    *,
    width: int,
    height: int,
    signed_height: int,
    pixel_offset: int,
    row_stride: int,
) -> None:
    """
    Write pixels using the orientation of the original BMP.

    Positive BMP height means rows are stored bottom-up.
    Negative BMP height means rows are stored top-down.
    """

    for stored_y in range(height):
        if signed_height > 0:
            source_y = height - 1 - stored_y
        else:
            source_y = stored_y

        source_start = source_y * width
        source_end = source_start + width
        row_pixels = indexed_pixels[source_start:source_end]

        destination = pixel_offset + stored_y * row_stride
        output_record[destination:destination + width] = bytes(row_pixels)

        padding_size = row_stride - width
        if padding_size:
            output_record[
                destination + width:
                destination + row_stride
            ] = b"\x00" * padding_size


def png_to_original_bmp_record(
    png_path: Path,
    original_record: bytes,
) -> bytes:
    info = parse_original_bmp(original_record)

    rgba = validate_png(
        png_path,
        expected_width=info["width"],
        expected_height=info["height"],
    )

    indexed_pixels, palette_rgb = build_indexed_pixels(rgba)

    output_record = bytearray(original_record)

    replace_palette(
        output_record,
        info["palette_start"],
        palette_rgb,
    )

    replace_pixels(
        output_record,
        indexed_pixels,
        width=info["width"],
        height=info["height"],
        signed_height=info["signed_height"],
        pixel_offset=info["pixel_offset"],
        row_stride=info["row_stride"],
    )

    if len(output_record) != len(original_record):
        raise SpriteImportError(
            f"{png_path}: converted record size changed unexpectedly.\n"
            f"Expected: {len(original_record)} bytes\n"
            f"Found:    {len(output_record)} bytes"
        )

    if output_record[:2] != BMP_MAGIC:
        raise SpriteImportError(
            f"{png_path}: converted record lost BMP magic."
        )

    return bytes(output_record)


def validate_manifest_header(
    fieldnames: List[str] | None,
    manifest_path: Path,
) -> None:
    required = {
        "index",
        "filename",
        "offset_hex",
        "size",
        "width",
        "height",
        "bpp",
    }

    if fieldnames is None:
        raise SpriteImportError(
            f"Manifest has no header: {manifest_path}"
        )

    missing = required.difference(fieldnames)

    if missing:
        raise SpriteImportError(
            f"Manifest is missing columns: {', '.join(sorted(missing))}\n"
            f"Manifest: {manifest_path}"
        )


def import_one_bin(
    bin_in: Path,
    sprite_dir: Path,
    bin_out: Path,
) -> bool:
    manifest_path = sprite_dir / "manifest.csv"

    if not manifest_path.exists():
        print(f"SKIP: missing manifest.csv in {sprite_dir}")
        return False

    original_data = bin_in.read_bytes()
    output_data = bytearray(original_data)

    replacements = []
    errors = []

    with manifest_path.open(
        newline="",
        encoding="utf-8-sig",
    ) as manifest_file:
        reader = csv.DictReader(manifest_file)
        validate_manifest_header(reader.fieldnames, manifest_path)

        for csv_line, row in enumerate(reader, start=2):
            try:
                index = int(row["index"])
                filename = row["filename"]
                offset = int(row["offset_hex"], 16)
                expected_size = int(row["size"])
                expected_width = int(row["width"])
                expected_height = abs(int(row["height"]))
                expected_bpp = int(row["bpp"])

                if not filename.lower().endswith(".png"):
                    raise SpriteImportError(
                        f"Manifest filename is not a PNG: {filename}"
                    )

                png_path = sprite_dir / filename

                if not png_path.exists():
                    # Missing PNG means this sprite is intentionally unchanged.
                    continue

                if offset < 0 or offset + expected_size > len(original_data):
                    raise SpriteImportError(
                        f"Sprite {index} has an invalid BIN range.\n"
                        f"Offset: 0x{offset:X}\n"
                        f"Size:   {expected_size}\n"
                        f"BIN:    {len(original_data)}"
                    )

                original_record = original_data[
                    offset:offset + expected_size
                ]

                original_info = parse_original_bmp(original_record)

                if original_info["width"] != expected_width:
                    raise SpriteImportError(
                        f"Manifest width does not match the original record.\n"
                        f"Manifest: {expected_width}\n"
                        f"Original: {original_info['width']}"
                    )

                if original_info["height"] != expected_height:
                    raise SpriteImportError(
                        f"Manifest height does not match the original record.\n"
                        f"Manifest: {expected_height}\n"
                        f"Original: {original_info['height']}"
                    )

                if original_info["bpp"] != expected_bpp:
                    raise SpriteImportError(
                        f"Manifest bpp does not match the original record.\n"
                        f"Manifest: {expected_bpp}\n"
                        f"Original: {original_info['bpp']}"
                    )

                replacement = png_to_original_bmp_record(
                    png_path,
                    original_record,
                )

                replacements.append(
                    (
                        index,
                        png_path,
                        offset,
                        expected_size,
                        replacement,
                    )
                )

            except Exception as exc:
                errors.append(
                    f"{manifest_path}, CSV line {csv_line}: {exc}"
                )

    # Validate everything before changing or writing the output.
    if errors:
        print("\nIMPORT FAILED")
        print("No output file was written.\n")

        for error in errors:
            print(f"ERROR: {error}\n")

        raise SpriteImportError(
            f"Found {len(errors)} import error(s)."
        )

    for index, png_path, offset, size, replacement in replacements:
        output_data[offset:offset + size] = replacement
        print(f"Imported sprite {index}: {png_path.name}")

    bin_out.parent.mkdir(parents=True, exist_ok=True)

    temporary_output = bin_out.with_name(
        bin_out.name + ".tmp"
    )
    temporary_output.write_bytes(output_data)
    temporary_output.replace(bin_out)

    print(
        f"Done:\n"
        f"  Input:   {bin_in}\n"
        f"  Output:  {bin_out}\n"
        f"  Changed: {len(replacements)}"
    )

    return True


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


def import_path(
    input_path: Path,
    sprites_dir: Path,
    out_path: Path,
    recursive: bool = False,
) -> None:
    if not input_path.exists():
        raise RuntimeError(f"Input not found: {input_path}")

    if input_path.is_file():
        import_one_bin(
            input_path,
            sprites_dir,
            out_path,
        )
        return

    bin_files = collect_bin_files(
        input_path,
        recursive=recursive,
    )

    if not bin_files:
        raise RuntimeError(
            f"No .bin files found in {input_path}"
        )

    for bin_path in bin_files:
        relative_path = bin_path.relative_to(input_path)
        sprite_subdir = sprites_dir / relative_path.with_suffix("")
        output_bin = out_path / relative_path

        import_one_bin(
            bin_path,
            sprite_subdir,
            output_bin,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import transparent PNG sprites into embedded "
            "8-bit BMP sprite BIN files."
        )
    )
    parser.add_argument(
        "input",
        help=(
            "Original .bin file or folder, "
            "for example sd/gfx/digimon/d3c"
        ),
    )
    parser.add_argument(
        "sprites",
        help="Edited PNG sprite folder created by export_sprites.py",
    )
    parser.add_argument(
        "-o",
        "--out",
        required=True,
        help="Output .bin file or output folder",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search input subfolders recursively",
    )

    args = parser.parse_args()

    import_path(
        Path(args.input),
        Path(args.sprites),
        Path(args.out),
        recursive=args.recursive,
    )


if __name__ == "__main__":
    main()