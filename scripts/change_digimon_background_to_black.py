#!/usr/bin/env python3
from pathlib import Path
from collections import deque
import argparse

import numpy as np
from PIL import Image


# For your 640x480 analyzer images.
# This is the inside of the left Digimon image panel.
BASE_W = 640
BASE_H = 480
BASE_ROI = (25, 131, 355, 379)  # x1, y1, x2, y2


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def scaled_roi(width, height, roi=BASE_ROI):
    x1, y1, x2, y2 = roi
    sx = width / BASE_W
    sy = height / BASE_H

    return (
        int(round(x1 * sx)),
        int(round(y1 * sy)),
        int(round(x2 * sx)),
        int(round(y2 * sy)),
    )


def flood_fill_white_background(
    roi_rgb,
    white_threshold=235,
    neutral_tolerance=35,
    feather=1,
):
    """
    Finds white/near-white background pixels connected to the border of the
    Digimon picture box.

    This avoids changing most white parts inside the Digimon itself, because
    those are usually separated from the background by outlines.
    """

    arr = roi_rgb.astype(np.int16)

    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    max_channel = np.maximum.reduce([r, g, b])
    min_channel = np.minimum.reduce([r, g, b])

    # Strict background candidate: bright and almost neutral.
    strict_bg = (
        (min_channel >= white_threshold)
        & ((max_channel - min_channel) <= neutral_tolerance)
    )

    h, w = strict_bg.shape
    bg_mask = np.zeros((h, w), dtype=bool)
    q = deque()

    # Seed flood fill from the ROI border only.
    for x in range(w):
        if strict_bg[0, x]:
            bg_mask[0, x] = True
            q.append((0, x))
        if strict_bg[h - 1, x]:
            bg_mask[h - 1, x] = True
            q.append((h - 1, x))

    for y in range(h):
        if strict_bg[y, 0]:
            bg_mask[y, 0] = True
            q.append((y, 0))
        if strict_bg[y, w - 1]:
            bg_mask[y, w - 1] = True
            q.append((y, w - 1))

    # 4-connected flood fill.
    while q:
        y, x = q.popleft()

        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w:
                if strict_bg[ny, nx] and not bg_mask[ny, nx]:
                    bg_mask[ny, nx] = True
                    q.append((ny, nx))

    # Optional small expansion to remove white JPEG halos near the Digimon edge.
    if feather > 0:
        soft_bg = (
            (min_channel >= max(180, white_threshold - 25))
            & ((max_channel - min_channel) <= neutral_tolerance + 20)
        )

        for _ in range(feather):
            neighbor = np.zeros_like(bg_mask)

            neighbor[:-1, :] |= bg_mask[1:, :]
            neighbor[1:, :] |= bg_mask[:-1, :]
            neighbor[:, :-1] |= bg_mask[:, 1:]
            neighbor[:, 1:] |= bg_mask[:, :-1]

            bg_mask |= neighbor & soft_bg

    return bg_mask


def process_image(
    input_path,
    output_path,
    roi=None,
    white_threshold=235,
    neutral_tolerance=35,
    feather=1,
):
    img = Image.open(input_path).convert("RGB")
    arr = np.array(img)

    h, w = arr.shape[:2]

    if roi is None:
        x1, y1, x2, y2 = scaled_roi(w, h)
    else:
        x1, y1, x2, y2 = roi

    x1 = max(0, min(w, x1))
    x2 = max(0, min(w, x2))
    y1 = max(0, min(h, y1))
    y2 = max(0, min(h, y2))

    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid ROI for {input_path}: {(x1, y1, x2, y2)}")

    roi_arr = arr[y1:y2, x1:x2].copy()

    bg_mask = flood_fill_white_background(
        roi_arr,
        white_threshold=white_threshold,
        neutral_tolerance=neutral_tolerance,
        feather=feather,
    )

    roi_arr[bg_mask] = [0, 0, 0]
    arr[y1:y2, x1:x2] = roi_arr

    output_path.parent.mkdir(parents=True, exist_ok=True)

    out_img = Image.fromarray(arr)

    ext = output_path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        out_img.save(output_path, quality=95, subsampling=0)
    else:
        out_img.save(output_path)


def collect_images(input_path, recursive=False):
    if input_path.is_file():
        if input_path.suffix.lower() in IMAGE_EXTS:
            return [input_path]
        return []

    if recursive:
        return [
            p for p in input_path.rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ]

    return [
        p for p in input_path.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Change the white Digimon picture background to black without touching the rest of the analyzer image."
    )

    parser.add_argument("input", help="Input image file or folder")
    parser.add_argument("output", help="Output image file or folder")

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process folders recursively",
    )

    parser.add_argument(
        "--suffix",
        default="",
        help="Suffix used when output is a folder.",
    )

    parser.add_argument(
        "--roi",
        nargs=4,
        type=int,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Manual picture-box ROI. Default is scaled from 640x480 analyzer layout.",
    )

    parser.add_argument(
        "--white-threshold",
        type=int,
        default=235,
        help="Higher is safer but may leave white edges. Lower removes more. Default: 235",
    )

    parser.add_argument(
        "--neutral-tolerance",
        type=int,
        default=35,
        help="Allowed difference between RGB channels for white/gray background. Default: 35",
    )

    parser.add_argument(
        "--feather",
        type=int,
        default=1,
        help="Small edge cleanup amount. Use 0 if white Digimon parts are affected. Default: 1",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    roi = tuple(args.roi) if args.roi else None

    images = collect_images(input_path, recursive=args.recursive)

    if not images:
        raise SystemExit("No supported image files found.")

    if input_path.is_file():
        process_image(
            input_path,
            output_path,
            roi=roi,
            white_threshold=args.white_threshold,
            neutral_tolerance=args.neutral_tolerance,
            feather=args.feather,
        )
        print(f"Saved: {output_path}")
        return

    for img_path in images:
        rel = img_path.relative_to(input_path)
        out_name = rel.with_name(rel.stem + args.suffix + rel.suffix)
        out_file = output_path / out_name

        process_image(
            img_path,
            out_file,
            roi=roi,
            white_threshold=args.white_threshold,
            neutral_tolerance=args.neutral_tolerance,
            feather=args.feather,
        )

        print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()