#!/usr/bin/env python3
"""
Import images, videos, and documents from content-import/assets-to-import into the project's static-assets.

Two modes:
  - Copy mode (--no-blobs): Recursively copy all files from assets-to-import into static-assets.
  - Blob mode (--blobs): Do not copy files; create a .blob XML file at each asset location
    with storeId and content hash. The actual binary is expected to be in blob storage (e.g. S3).

Usage:
  From sandbox root:
    python3 migration-kit/sub-scripts/import_assets.py
    python3 migration-kit/sub-scripts/import_assets.py --blobs
    python3 migration-kit/sub-scripts/import_assets.py --no-blobs --dry-run

  With explicit paths:
    python3 migration-kit/sub-scripts/import_assets.py --sandbox /path/to/sandbox --assets-dir /path/to/content-import/assets-to-import --blobs
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

# Default paths relative to migration-kit
MIGRATION_KIT = Path(__file__).resolve().parent.parent
DEFAULT_ASSETS_DIR = MIGRATION_KIT / "content-import" / "assets-to-import"
STORE_ID = "s3-store"
BLOB_HASH_SUFFIX = "-1"


def get_sandbox_root() -> Path:
    """Sandbox root = parent of migration-kit."""
    return MIGRATION_KIT.parent


def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of file content; return hexdigest + suffix (e.g. ...-1)."""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest() + BLOB_HASH_SUFFIX


def blob_xml_content(store_id: str, content_hash: str) -> str:
    """Return the blob XML body (no XML declaration)."""
    return f"""<blob>
  <storeId>{store_id}</storeId>
  <hash>{content_hash}</hash>
</blob>
"""


def collect_asset_files(root: Path) -> list[Path]:
    """Return all regular files under root (recursive), relative to root."""
    if not root.is_dir():
        return []
    out = []
    for f in root.rglob("*"):
        if f.is_file():
            try:
                out.append(f.relative_to(root))
            except ValueError:
                pass
    return sorted(out, key=lambda p: p.as_posix())


def run_copy_mode(assets_dir: Path, static_assets: Path, dry_run: bool) -> tuple[int, list[str]]:
    """Copy all files from assets_dir into static_assets. Returns (count, errors)."""
    errors = []
    count = 0
    for rel in collect_asset_files(assets_dir):
        src = assets_dir / rel
        dst = static_assets / rel
        if not src.is_file():
            continue
        try:
            if dry_run:
                print(f"[dry-run] Would copy: {rel}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            count += 1
        except Exception as e:
            msg = f"Copy failed {rel}: {e}"
            errors.append(msg)
            print(msg, file=sys.stderr)
    return count, errors


def run_blob_mode(assets_dir: Path, static_assets: Path, dry_run: bool) -> tuple[int, list[str]]:
    """Create .blob XML files for each asset; do not copy the binary. Returns (count, errors)."""
    errors = []
    count = 0
    for rel in collect_asset_files(assets_dir):
        src = assets_dir / rel
        if not src.is_file():
            continue
        blob_rel = Path(rel.as_posix() + ".blob")
        dst = static_assets / blob_rel
        try:
            content_hash = compute_file_hash(src)
            xml = blob_xml_content(STORE_ID, content_hash)
            if dry_run:
                print(f"[dry-run] Would create blob: {blob_rel} (hash={content_hash})")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(xml, encoding="utf-8")
            count += 1
        except Exception as e:
            msg = f"Blob failed {rel}: {e}"
            errors.append(msg)
            print(msg, file=sys.stderr)
    return count, errors


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Import assets from assets-to-import into static-assets (copy or blob mode).",
        epilog="If neither --blobs nor --no-blobs is given, you will be prompted.",
    )
    ap.add_argument(
        "--sandbox",
        type=Path,
        default=get_sandbox_root(),
        help="Sandbox root (default: parent of migration-kit)",
    )
    ap.add_argument(
        "--assets-dir",
        type=Path,
        default=DEFAULT_ASSETS_DIR,
        help="Folder containing assets to import (default: migration-kit/content-import/assets-to-import)",
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--blobs",
        action="store_true",
        help="Use blob mode: create .blob XML files with storeId and hash instead of copying files",
    )
    group.add_argument(
        "--no-blobs",
        action="store_true",
        help="Use copy mode: copy files into static-assets (default if not prompted)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; only report what would be done",
    )
    args = ap.parse_args()

    sandbox = args.sandbox.resolve()
    assets_dir = args.assets_dir.resolve()
    static_assets = sandbox / "static-assets"

    if not assets_dir.is_dir():
        print(f"Assets directory not found: {assets_dir}", file=sys.stderr)
        print("Create content-import/assets-to-import and add images, videos, PDFs, etc., then run this script again.", file=sys.stderr)
        sys.exit(1)

    use_blobs = args.blobs
    if not args.blobs and not args.no_blobs:
        while True:
            try:
                answer = input("Do you plan to use BLOBS (blob storage) for these assets? [y/N]: ").strip().lower()
            except EOFError:
                answer = "n"
            if answer in ("", "n", "no"):
                use_blobs = False
                break
            if answer in ("y", "yes"):
                use_blobs = True
                break
            print("Please answer y/yes or n/no.")

    mode = "blob" if use_blobs else "copy"
    print(f"Mode: {mode}")
    print(f"Source: {assets_dir}")
    print(f"Target: {static_assets}")
    if args.dry_run:
        print("Dry run: no files will be written.")

    if use_blobs:
        count, errors = run_blob_mode(assets_dir, static_assets, args.dry_run)
    else:
        count, errors = run_copy_mode(assets_dir, static_assets, args.dry_run)

    if not args.dry_run and count:
        print(f"Created/updated {count} item(s) under static-assets.")
    elif args.dry_run and count:
        print(f"[dry-run] Would process {count} file(s).")

    if not count and not errors:
        print("No files found under the assets directory.", file=sys.stderr)
        sys.exit(1)
    if errors:
        print(f"{len(errors)} error(s) occurred.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
