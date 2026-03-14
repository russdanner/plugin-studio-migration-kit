#!/usr/bin/env python3
"""
Clean up import data: empty assets-to-import and remove data rows from CSV files.

Keeps CSV header rows so the files remain valid. Run manually when you want to
reset for a fresh import (e.g. after testing or before re-running with new data).

Usage:
  From sandbox root:
    python3 migration-kit/sub-scripts/cleanup_import_data.py
    python3 migration-kit/sub-scripts/cleanup_import_data.py --yes   # skip confirmation
"""

import argparse
import shutil
import sys
from pathlib import Path

MIGRATION_KIT = Path(__file__).resolve().parent.parent
CONTENT_IMPORT = MIGRATION_KIT / "content-import"
ASSETS_TO_IMPORT = CONTENT_IMPORT / "assets-to-import"
CSV_FILES = ("content-types.csv", "content.csv", "datasources.csv")


def empty_directory(path: Path) -> tuple[bool, str]:
    """Remove all contents of path, leave the folder itself. Returns (success, error_message)."""
    if not path.is_dir():
        return True, ""
    try:
        shutil.rmtree(path)
        path.mkdir(parents=True)
        return True, ""
    except Exception as e:
        return False, str(e)


def strip_csv_data(csv_path: Path) -> tuple[bool, str]:
    """Keep only the header row. Returns (success, error_message)."""
    if not csv_path.exists():
        return True, ""
    try:
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return True, ""
        header = lines[0]
        csv_path.write_text(header + "\n", encoding="utf-8")
        return True, ""
    except Exception as e:
        return False, str(e)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Clean up import data: empty assets-to-import and clear data rows from CSVs (headers kept).",
    )
    ap.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = ap.parse_args()

    if not args.yes:
        print("This will:")
        print(f"  1. Empty: {ASSETS_TO_IMPORT}")
        print(f"  2. Remove all data rows (keep headers) from: {', '.join(CSV_FILES)}")
        print()
        try:
            answer = input("Continue? [y/N]: ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    errors = []

    # 1. Empty assets-to-import
    if ASSETS_TO_IMPORT.exists():
        ok, msg = empty_directory(ASSETS_TO_IMPORT)
        if not ok:
            errors.append(f"assets-to-import: {msg}")
            print(f"Failed to empty assets-to-import: {msg}", file=sys.stderr)
        else:
            print("Emptied assets-to-import.")
    else:
        print("assets-to-import not found (skip).")

    # 2. Strip CSV data rows
    for name in CSV_FILES:
        csv_path = CONTENT_IMPORT / name
        ok, msg = strip_csv_data(csv_path)
        if not ok:
            errors.append(f"{name}: {msg}")
            print(f"Failed {name}: {msg}", file=sys.stderr)
        elif csv_path.exists():
            print(f"Cleared data rows in {name}.")

    if errors:
        sys.exit(1)
    print("Cleanup done.")


if __name__ == "__main__":
    main()
