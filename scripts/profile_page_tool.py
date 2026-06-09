#!/usr/bin/env python3
# python scripts/profile_page_tool.py --mode export
# python scripts/profile_page_tool.py --mode import

from pathlib import Path
import argparse, csv, shutil

BMP_MAGIC = b"BM"

def list_bins(root):
    return sorted(p for p in Path(root).rglob("*.bin") if not p.name.startswith("._"))

def find_bmp_pages(data):
    pages = []
    pos = 0

    while True:
        start = data.find(BMP_MAGIC, pos)
        if start < 0:
            break

        if start + 6 > len(data):
            break

        size = int.from_bytes(data[start + 2:start + 6], "little")
        end = start + size

        if size <= 0 or end > len(data):
            pos = start + 2
            continue

        pages.append((start, end, size))
        pos = end

    return pages

def export_profiles(profile_root, out_dir, manifest_csv):
    profile_root = Path(profile_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    for bin_path in list_bins(profile_root):
        data = bin_path.read_bytes()
        pages = find_bmp_pages(data)

        if not pages:
            print(f"SKIP no BMP pages: {bin_path}")
            continue

        rel = bin_path.relative_to(profile_root)
        export_folder = out_dir / rel.with_suffix("")
        export_folder.mkdir(parents=True, exist_ok=True)

        for page_index, (start, end, size) in enumerate(pages):
            bmp_out = export_folder / f"page_{page_index:02d}.bmp"
            bmp_out.write_bytes(data[start:end])

            rows.append({
                "relative_bin": str(rel).replace("\\", "/"),
                "profile_name": bin_path.stem,
                "page_index": page_index,
                "offset": start,
                "size": size,
                "page_file": str(bmp_out.relative_to(out_dir)).replace("\\", "/"),
            })

        print(f"Exported {len(pages)} pages: {bin_path}")

    with open(manifest_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["relative_bin", "profile_name", "page_index", "offset", "size", "page_file"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nExport complete: {manifest_csv}")

def import_profiles(profile_root, export_dir, manifest_csv, backup=False):
    profile_root = Path(profile_root)
    export_dir = Path(export_dir)

    with open(manifest_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    by_bin = {}
    for row in rows:
        by_bin.setdefault(row["relative_bin"], []).append(row)

    changed_count = 0
    skipped = 0

    for rel_bin, bin_rows in by_bin.items():
        bin_path = profile_root / rel_bin
        if not bin_path.exists():
            print(f"SKIP missing bin: {bin_path}")
            skipped += 1
            continue

        data = bytearray(bin_path.read_bytes())
        changed = False

        for row in bin_rows:
            offset = int(row["offset"])
            size = int(row["size"])
            page_file = export_dir / row["page_file"]

            if not page_file.exists():
                print(f"SKIP missing page: {page_file}")
                skipped += 1
                continue

            new_bmp = page_file.read_bytes()

            if new_bmp[:2] != BMP_MAGIC:
                print(f"SKIP not BMP: {page_file}")
                skipped += 1
                continue

            if len(new_bmp) != size:
                print(f"SKIP wrong size: {page_file} is {len(new_bmp)}, expected {size}")
                skipped += 1
                continue

            data[offset:offset + size] = new_bmp
            changed = True

        if changed:
            if backup:
                bak = bin_path.with_suffix(bin_path.suffix + ".bak")
                if not bak.exists():
                    shutil.copy2(bin_path, bak)

            bin_path.write_bytes(data)
            changed_count += 1
            print(f"Imported: {bin_path}")

    print(f"\nImport complete. Changed: {changed_count}, skipped: {skipped}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["export", "import"], required=True)
    p.add_argument("--profile-root", default="sd/profile")
    p.add_argument("--export-dir", default="profile_pages")
    p.add_argument("--manifest", default="profile_pages_manifest.csv")
    p.add_argument("--no-backup", action="store_true")
    args = p.parse_args()

    if args.mode == "export":
        export_profiles(args.profile_root, args.export_dir, args.manifest)
    else:
        import_profiles(args.profile_root, args.export_dir, args.manifest, backup=not args.no_backup)

if __name__ == "__main__":
    main()