#!/usr/bin/env python3
"""
CrafterCMS Migration Kit – full import

Orchestrates the full migration: CSV import (content types + content), then
generic FTL template generation for each content type, then content-type
documentation generation. Run from the Crafter sandbox root or pass --sandbox.

Usage:
  From sandbox root:
    python3 migration-kit/import.py [options]

  From anywhere:
    python3 /path/to/migration-kit/import.py --sandbox /path/to/sandbox [options]

  CSV files are read from migration-kit/content-import/ (not examples/). To check templates after import:
    python3 migration-kit/sub-scripts/check-templates.py

Options:
  --sandbox PATH       Sandbox root (default: parent of migration-kit).
  --dry-run            Do not write files (CSV import only; docs still generated).
  --content-only       Only import content from CSV; skip content types.
  --types-only         Only import content types from CSV; skip content.
  --skip-templates     Do not run the generic template generator for content types.
  --skip-docs          Do not run the content-type documentation generator.
  --docs-dir PATH      Where to write generated docs (default: sandbox/docs).
                       Use migration-kit/docs to write into the kit, e.g. docs-dir=migration-kit/docs.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def find_migration_kit(script_path: Path) -> Path:
    """Resolve migration-kit directory (parent of this script)."""
    return script_path.resolve().parent


def find_sandbox(migration_kit: Path) -> Path:
    """Sandbox root = parent of migration-kit."""
    return migration_kit.parent


def discover_content_types_for_templates(ct_root: Path) -> list[tuple[str, Path]]:
    """Discover (content_type_path, form_path) for page and component types that have form-definition.xml.
    content_type_path is e.g. 'page/home', 'component/header' (used as input to generate_generic_template).
    """
    result = []
    for category in ("page", "component"):
        cat_dir = ct_root / category
        if not cat_dir.is_dir():
            continue
        # Single type in category (e.g. taxonomy/form-definition.xml)
        form_path = cat_dir / "form-definition.xml"
        if form_path.exists():
            result.append((category, form_path))
            continue
        # One subdir per type
        for slug_dir in sorted(cat_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            form_path = slug_dir / "form-definition.xml"
            if form_path.exists():
                result.append((f"{category}/{slug_dir.name}", form_path))
    return result


def main() -> None:
    script_path = Path(__file__)
    migration_kit = find_migration_kit(script_path)
    sub_scripts = migration_kit / "sub-scripts"
    # Always use migration-kit/content-import (not examples/example-import-data)
    content_import = migration_kit / "content-import"

    ap = argparse.ArgumentParser(
        description="Run full migration: CSV import + content-type docs.",
    )
    ap.add_argument(
        "--sandbox",
        type=Path,
        default=None,
        help="Sandbox root (default: parent of migration-kit)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files (CSV import only)",
    )
    ap.add_argument(
        "--content-only",
        action="store_true",
        help="Only import content from CSV; skip content types",
    )
    ap.add_argument(
        "--types-only",
        action="store_true",
        help="Only import content types from CSV; skip content",
    )
    ap.add_argument(
        "--skip-templates",
        action="store_true",
        help="Do not run the generic template generator for content types",
    )
    ap.add_argument(
        "--skip-docs",
        action="store_true",
        help="Do not run the content-type documentation generator",
    )
    ap.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Output directory for generated docs, relative to sandbox (default: docs)",
    )
    args = ap.parse_args()

    sandbox = args.sandbox.resolve() if args.sandbox else find_sandbox(migration_kit)
    if not (sandbox / "config").exists() and not args.dry_run:
        print("Warning: sandbox may be wrong (no config/). Use --sandbox.", file=sys.stderr)

    # 1. CSV import
    import_script = sub_scripts / "import_from_csv.py"
    if not import_script.exists():
        print(f"Error: {import_script} not found.", file=sys.stderr)
        sys.exit(1)
    cmd = [
        sys.executable,
        str(import_script),
        "--sandbox",
        str(sandbox),
        "--content-import-dir",
        str(content_import),
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.content_only:
        cmd.append("--content-only")
    if args.types_only:
        cmd.append("--types-only")
    print("Running CSV import...")
    r = subprocess.run(cmd, cwd=str(sandbox))
    if r.returncode != 0:
        sys.exit(r.returncode)

    # 2. Generic FTL templates for each content type
    if not args.skip_templates and not args.dry_run:
        template_script = sub_scripts / "generate_generic_template.py"
        ct_root = sandbox / "config" / "studio" / "content-types"
        if template_script.exists() and ct_root.exists():
            discovered = discover_content_types_for_templates(ct_root)
            if discovered:
                print("Generating generic templates for content types...")
                for ct_path, _form_path in discovered:
                    # Map page/foo -> templates/web/pages/foo.ftl, component/foo -> templates/web/components/foo.ftl
                    parts = ct_path.split("/", 1)
                    category, slug = parts[0], parts[1] if len(parts) > 1 else parts[0]
                    out_rel = f"templates/web/{'pages' if category == 'page' else 'components'}/{slug}.ftl"
                    r = subprocess.run(
                        [
                            sys.executable,
                            str(template_script),
                            "--sandbox",
                            str(sandbox),
                            ct_path,
                            "-o",
                            out_rel,
                        ],
                        cwd=str(sandbox),
                    )
                    if r.returncode != 0:
                        sys.exit(r.returncode)
            else:
                print("No content types with form-definition found for templates.", file=sys.stderr)
        else:
            if not template_script.exists():
                print("Skipping templates: generate_generic_template.py not found.", file=sys.stderr)
            elif not ct_root.exists():
                print("Skipping templates: config/studio/content-types not found.", file=sys.stderr)

    # 3. Content-type documentation
    if not args.skip_docs:
        docs_script = sub_scripts / "generate_content_type_docs.py"
        if docs_script.exists():
            out_dir = args.docs_dir if args.docs_dir.is_absolute() else sandbox / args.docs_dir
            print(f"Generating content-type docs in {out_dir}...")
            r = subprocess.run(
                [
                    sys.executable,
                    str(docs_script),
                    "--sandbox",
                    str(sandbox),
                    "--output",
                    str(out_dir),
                ],
                cwd=str(sandbox),
            )
            if r.returncode != 0:
                sys.exit(r.returncode)
        else:
            print("Skipping docs: generate_content_type_docs.py not found.", file=sys.stderr)

    print("Full import done.")


if __name__ == "__main__":
    main()
