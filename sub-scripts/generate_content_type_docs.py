#!/usr/bin/env python3
"""
Generate content type documentation for a migrated CrafterCMS project.

Scans config/studio/content-types/ and produces Markdown docs in docs/:
- README.md (overview and index)
- pages.md (page content types)
- components.md (component content types)
- global.md (level-descriptor if present)
- taxonomy.md (taxonomy types if any)

Each type is documented with content type path, label, display template, and
per-section field tables: Name, Type, Description, Required, Constraints, Notes.

Usage:
  From sandbox root:
    python3 migration-kit/content-import/generate_content_type_docs.py
    python3 migration-kit/content-import/generate_content_type_docs.py -o docs
  With --sandbox /path/to/sandbox when not in sandbox root.

Requirements: Python 3.9+ (stdlib only: xml.etree, argparse, pathlib).
"""

import argparse
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


def _strip_ns(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _find_child(el, tag: str):
    for c in el:
        if _strip_ns(c.tag) == tag:
            return c
    return None


def _text(el, default: str = "") -> str:
    if el is None:
        return default
    return (el.text or "").strip() or default


def _get_prop(field_el, name: str) -> str:
    props = _find_child(field_el, "properties")
    if props is None:
        return ""
    for p in props:
        if _strip_ns(p.tag) != "property":
            continue
        n = _find_child(p, "name")
        v = _find_child(p, "value")
        if n is not None and _text(n) == name and v is not None:
            return _text(v)
    return ""


def _get_constraint(field_el, name: str) -> str:
    constraints = _find_child(field_el, "constraints")
    if constraints is None:
        return ""
    for c in constraints:
        if _strip_ns(c.tag) != "constraint":
            continue
        n = _find_child(c, "name")
        v = _find_child(c, "value")
        if n is not None and _text(n) == name and v is not None:
            return _text(v)
    return ""


def parse_config_xml(path: Path) -> dict:
    """Parse config.xml; return name, label, file_extension, content_as_folder, paths_excludes."""
    tree = ET.parse(path)
    root = tree.getroot()
    name = root.get("name", "")
    label_el = _find_child(root, "label")
    form_el = _find_child(root, "form")
    ext_el = _find_child(root, "file-extension")
    folder_el = _find_child(root, "content-as-folder")
    paths_el = _find_child(root, "paths")
    excludes = []
    if paths_el is not None:
        excl_el = _find_child(paths_el, "excludes")
        if excl_el is not None:
            for p in excl_el.findall(".//*"):
                if _strip_ns(p.tag) == "pattern" and p.text:
                    excludes.append(p.text.strip())
    return {
        "name": name,
        "label": _text(label_el, name.split("/")[-1] if name else ""),
        "form": _text(form_el, ""),
        "file_extension": _text(ext_el, "xml"),
        "content_as_folder": _text(folder_el, "false").lower() == "true",
        "paths_excludes": excludes,
    }


def parse_form_definition(path: Path) -> dict:
    """Parse form-definition.xml; return title, content_type, object_type, display_template, sections with fields."""
    tree = ET.parse(path)
    root = tree.getroot()
    title_el = _find_child(root, "title")
    desc_el = _find_child(root, "description")
    object_el = _find_child(root, "objectType")
    ct_el = _find_child(root, "content-type")
    props_el = _find_child(root, "properties")
    display_template = ""
    if props_el is not None:
        for p in props_el:
            if _strip_ns(p.tag) != "property":
                continue
            n = _find_child(p, "name")
            v = _find_child(p, "value")
            if n is not None and _text(n) == "display-template" and v is not None:
                display_template = _text(v)
                break
    sections_el = _find_child(root, "sections")
    if sections_el is None:
        sections_el = root
    sections = []
    for sec in sections_el:
        if _strip_ns(sec.tag) != "section":
            continue
        st = _find_child(sec, "title")
        sd = _find_child(sec, "description")
        fields_el = _find_child(sec, "fields")
        if fields_el is None:
            fields_el = sec
        fields = []
        for f in fields_el:
            if _strip_ns(f.tag) != "field":
                continue
            ftype = _text(_find_child(f, "type"), "input")
            fid = _text(_find_child(f, "id"), "")
            ftitle = _text(_find_child(f, "title"), fid or "Field")
            fdesc = _text(_find_child(f, "description"), "")
            if not fid:
                continue
            required_val = _get_constraint(f, "required")
            required = required_val.lower() in ("true", "1", "yes") if required_val else False
            min_size = _get_prop(f, "minSize")
            max_size = _get_prop(f, "maxSize")
            item_manager = _get_prop(f, "itemManager")
            content_types = _get_prop(f, "contentTypes")
            image_manager = _get_prop(f, "imageManager")
            size = _get_prop(f, "size")
            maxlength = _get_prop(f, "maxlength")
            readonly = _get_prop(f, "readonly")
            pattern = _get_constraint(f, "pattern")
            constraints_parts = []
            if maxlength:
                constraints_parts.append(f"maxlength={maxlength}")
            if size:
                constraints_parts.append(f"size={size}")
            if readonly:
                constraints_parts.append("readonly")
            if pattern:
                constraints_parts.append(f"pattern={pattern[:30]}…" if len(pattern) > 30 else f"pattern={pattern}")
            notes_parts = []
            if content_types:
                notes_parts.append(f"contentTypes: {content_types}")
            if item_manager:
                notes_parts.append(f"itemManager: {item_manager}")
            if min_size or max_size:
                notes_parts.append(f"minSize={min_size or '—'}; maxSize={max_size or '—'}")
            if image_manager:
                notes_parts.append(f"imageManager: {image_manager}")
            if ftype == "node-selector":
                notes_parts.append("node-selector (list)" if max_size and int(max_size) != 1 else "node-selector (single)")
            field_info = {
                "id": fid,
                "type": ftype,
                "title": ftitle,
                "description": fdesc,
                "required": required,
                "constraints": "; ".join(constraints_parts) if constraints_parts else "—",
                "notes": " ".join(notes_parts) if notes_parts else "—",
            }
            fields.append(field_info)
        if fields:
            sections.append({
                "title": _text(st, "Section"),
                "description": _text(sd, ""),
                "fields": fields,
            })
    return {
        "title": _text(title_el, "Content"),
        "description": _text(desc_el, ""),
        "content_type": _text(ct_el, ""),
        "object_type": _text(object_el, "page"),
        "display_template": display_template,
        "sections": sections,
    }


def discover_content_types(ct_root: Path) -> list[tuple[str, Path, Path]]:
    """Return list of (content_type_path, config_path, form_path)."""
    found = []
    for category in ("page", "component", "taxonomy"):
        cat_dir = ct_root / category
        if not cat_dir.is_dir():
            continue
        # Case 1: config + form directly in category dir (e.g. taxonomy/)
        config_path = cat_dir / "config.xml"
        form_path = cat_dir / "form-definition.xml"
        if config_path.exists() and form_path.exists():
            try:
                config = parse_config_xml(config_path)
                name = config.get("name") or f"/{category}/{category}"
            except Exception:
                name = f"/{category}/{category}"
            found.append((name, config_path, form_path))
            continue
        # Case 2: one subdir per type (e.g. page/home/, component/header/)
        for slug_dir in sorted(cat_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            config_path = slug_dir / "config.xml"
            form_path = slug_dir / "form-definition.xml"
            if not config_path.exists() or not form_path.exists():
                continue
            try:
                config = parse_config_xml(config_path)
                name = config.get("name") or f"/{category}/{slug_dir.name}"
            except Exception:
                name = f"/{category}/{slug_dir.name}"
            found.append((name, config_path, form_path))
    return sorted(found, key=lambda x: x[0])


def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def render_field_table(fields: list[dict]) -> str:
    lines = [
        "| Name | Type | Description | Required | Constraints | Notes |",
        "|------|------|-------------|----------|-------------|-------|",
    ]
    for f in fields:
        name = md_escape(f["id"])
        typ = md_escape(f["type"])
        desc = md_escape(f["description"]) or "—"
        req = "true" if f["required"] else "false"
        constraints = md_escape(f["constraints"]) or "—"
        notes = md_escape(f["notes"]) or "—"
        lines.append(f"| {name} | {typ} | {desc} | {req} | {constraints} | {notes} |")
    return "\n".join(lines)


def render_type_doc(ct_name: str, config: dict, form: dict) -> str:
    lines = [
        f"## {form.get('title') or ct_name}",
        "",
        f"- **Content type:** `{ct_name}`",
        f"- **Label:** {config.get('label', '')}",
        f"- **Display template:** `{form.get('display_template', '')}`",
        f"- **Object type:** {form.get('object_type', '')}",
        f"- **File extension:** {config.get('file_extension', 'xml')}",
        f"- **Content as folder:** {config.get('content_as_folder', False)}",
        "",
    ]
    if form.get("description"):
        lines.append(form["description"] + "\n")
    for sec in form.get("sections", []):
        lines.append(f"### {sec['title']}")
        lines.append("")
        lines.append(render_field_table(sec["fields"]))
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="Generate content type documentation for a migrated CrafterCMS project.",
    )
    ap.add_argument(
        "-s", "--sandbox",
        type=Path,
        default=None,
        help="Sandbox root (default: auto-detect)",
    )
    ap.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("docs"),
        help="Output directory for Markdown files (default: docs)",
    )
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    if args.sandbox is None:
        sandbox = script_dir.parent.parent
        if not (sandbox / "config" / "studio" / "content-types").exists():
            sandbox = Path.cwd()
    else:
        sandbox = Path(args.sandbox).resolve()

    ct_root = sandbox / "config" / "studio" / "content-types"
    if not ct_root.exists():
        print("Error: config/studio/content-types not found.", file=sys.stderr)
        sys.exit(1)

    out_dir = args.output if args.output.is_absolute() else (sandbox / args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    discovered = discover_content_types(ct_root)
    if not discovered:
        print("No content types found.", file=sys.stderr)
        sys.exit(0)

    by_category = {"page": [], "component": [], "taxonomy": []}
    for ct_name, config_path, form_path in discovered:
        if ct_name.startswith("/page/"):
            by_category["page"].append((ct_name, config_path, form_path))
        elif ct_name.startswith("/component/"):
            by_category["component"].append((ct_name, config_path, form_path))
        elif ct_name.startswith("/taxonomy") or ct_name == "/taxonomy":
            by_category["taxonomy"].append((ct_name, config_path, form_path))

    # README.md
    readme_lines = [
        "# Content type documentation",
        "",
        "Generated by `generate_content_type_docs.py` from this project's content types.",
        "",
        "## Index",
        "",
    ]
    if by_category["page"]:
        readme_lines.append("- [Page types](pages.md)")
        readme_lines.append("")
    if by_category["component"]:
        readme_lines.append("- [Component types](components.md)")
        readme_lines.append("")
    if by_category["taxonomy"]:
        readme_lines.append("- [Taxonomy types](taxonomy.md)")
        readme_lines.append("")
    if any(ct == "/component/level-descriptor" for ct, _, _ in by_category["component"]):
        readme_lines.append("- [Level descriptor (global)](global.md)")
        readme_lines.append("")
    readme_lines.append("---")
    readme_lines.append("")
    (out_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")

    # pages.md
    if by_category["page"]:
        page_lines = ["# Page content types", ""]
        for ct_name, config_path, form_path in by_category["page"]:
            config = parse_config_xml(config_path)
            form = parse_form_definition(form_path)
            page_lines.append(render_type_doc(ct_name, config, form))
            page_lines.append("")
        (out_dir / "pages.md").write_text("\n".join(page_lines), encoding="utf-8")

    # components.md
    if by_category["component"]:
        comp_lines = ["# Component content types", ""]
        for ct_name, config_path, form_path in by_category["component"]:
            config = parse_config_xml(config_path)
            form = parse_form_definition(form_path)
            comp_lines.append(render_type_doc(ct_name, config, form))
            comp_lines.append("")
        (out_dir / "components.md").write_text("\n".join(comp_lines), encoding="utf-8")

    # global.md (level-descriptor only)
    level_desc = [(ct, cp, fp) for ct, cp, fp in by_category["component"] if ct == "/component/level-descriptor"]
    if level_desc:
        ct_name, config_path, form_path = level_desc[0]
        config = parse_config_xml(config_path)
        form = parse_form_definition(form_path)
        global_lines = ["# Level descriptor (global)", "", "Section defaults, header, footer, and shared content.", "", render_type_doc(ct_name, config, form)]
        (out_dir / "global.md").write_text("\n".join(global_lines), encoding="utf-8")

    # taxonomy.md
    if by_category["taxonomy"]:
        tax_lines = ["# Taxonomy content types", ""]
        for ct_name, config_path, form_path in by_category["taxonomy"]:
            config = parse_config_xml(config_path)
            form = parse_form_definition(form_path)
            tax_lines.append(render_type_doc(ct_name, config, form))
            tax_lines.append("")
        (out_dir / "taxonomy.md").write_text("\n".join(tax_lines), encoding="utf-8")

    print(f"Wrote documentation to {out_dir}", file=sys.stderr)
    for f in sorted(out_dir.glob("*.md")):
        print(f"  - {f.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
