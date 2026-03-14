#!/usr/bin/env python3
"""
Generate a generic headless FTL template for any CrafterCMS content type.

Reads a form-definition.xml and outputs an FTL file that matches the style of
templates/web/pages/examples/home-example.ftl: white section headers, gradient
section bodies, drop shadow, and section/field/field-type class structure.

Usage:
  From sandbox root:
    python3 migration-kit/content-import/generate_generic_template.py config/studio/content-types/page/article/form-definition.xml
    python3 migration-kit/content-import/generate_generic_template.py page/article --sandbox /path/to/sandbox -o templates/web/pages/article.ftl
  From migration-kit/content-import:
    python3 generate_generic_template.py --sandbox /path/to/sandbox page/entry --output ../templates/web/pages/entry.ftl

Requirements: Python 3.9+ (stdlib only: xml.etree, argparse, pathlib).
"""

import argparse
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Form definition parsing
# ---------------------------------------------------------------------------

def _text(el, default=""):
    if el is None:
        return default
    return (el.text or "").strip() or default


def _find(el, tag):
    child = el.find(tag)
    return child if child is not None else el.find(f".//{tag}")


def _strip_ns(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _find_child(el, tag: str):
    for c in el:
        if _strip_ns(c.tag) == tag:
            return c
    return None


def parse_form_definition(path: Path) -> dict:
    """Parse form-definition.xml; return dict with title, content_type, object_type, sections."""
    tree = ET.parse(path)
    root = tree.getroot()

    title_el = _find_child(root, "title")
    content_type_el = _find_child(root, "content-type")
    object_type_el = _find_child(root, "objectType")
    sections_el = _find_child(root, "sections")
    if sections_el is None:
        sections_el = root

    title = _text(title_el, "Content")
    content_type = _text(content_type_el, "")
    object_type = _text(object_type_el, "page")

    sections = []
    for sec in sections_el:
        if _strip_ns(sec.tag) != "section":
            continue
        sec_title_el = _find_child(sec, "title")
        sec_title = _text(sec_title_el, "Section")
        fields_el = _find_child(sec, "fields")
        if fields_el is None:
            fields_el = sec
        fields = []
        for f in fields_el:
            if _strip_ns(f.tag) != "field":
                continue
            ftype_el = _find_child(f, "type")
            fid_el = _find_child(f, "id")
            ftitle_el = _find_child(f, "title")
            ftype = _text(ftype_el, "input")
            fid = _text(fid_el, "")
            ftitle = _text(ftitle_el, fid or "Field")
            if not fid:
                continue
            field_dict = {"type": ftype, "id": fid, "title": ftitle}
            # Parse nested fields inside repeat groups (e.g. sections_o -> section_html)
            if ftype == "repeat":
                nested_el = _find_child(f, "fields")
                if nested_el is not None:
                    children = []
                    for cf in nested_el:
                        if _strip_ns(cf.tag) != "field":
                            continue
                        ctype_el = _find_child(cf, "type")
                        cid_el = _find_child(cf, "id")
                        ctitle_el = _find_child(cf, "title")
                        ctype = _text(ctype_el, "input")
                        cid = _text(cid_el, "")
                        ctitle = _text(ctitle_el, cid or "Field")
                        if cid:
                            children.append({"type": ctype, "id": cid, "title": ctitle})
                    if children:
                        field_dict["children"] = children
            fields.append(field_dict)
        if fields:
            sections.append({"title": sec_title, "fields": fields})

    return {
        "title": title,
        "content_type": content_type,
        "object_type": object_type,
        "sections": sections,
    }


def ftl_safe_id(fid: str) -> str:
    """Use bracket notation in FTL if id contains hyphen."""
    if "-" in fid:
        return f'contentModel["{fid}"]!""'
    return f'contentModel.{fid}!""'


def ftl_safe_expr(fid: str, suffix: str = '!""') -> str:
    """FTL expression for contentModel access; use bracket notation if id contains hyphen."""
    if "-" in fid:
        return f'contentModel["{fid}"]{suffix}'
    return f'contentModel.{fid}{suffix}'


def field_uses_bracket(fid: str) -> bool:
    return "-" in fid


def ice_field_id(fid: str) -> str:
    """Return the field id used by ICE/XB for $field attribute. Uses camelCase for standard hyphenated fields."""
    if fid == "file-name":
        return "fileName"
    if fid == "internal-name":
        return "internalName"
    return fid


# ---------------------------------------------------------------------------
# FTL snippet generation per field type
# ---------------------------------------------------------------------------

# One accent per page (body background); two complementary colors per gradient; sections stay white.
PAGE_ACCENTS = [
    "linear-gradient(165deg, #dbeafe 0%, #fed7aa 100%)",   # blue ↔ orange
    "linear-gradient(165deg, #e9d5ff 0%, #fef08a 100%)",   # violet ↔ yellow
    "linear-gradient(165deg, #bbf7d0 0%, #fecaca 100%)",   # green ↔ red (soft)
    "linear-gradient(165deg, #bfdbfe 0%, #fde047 100%)",   # blue ↔ amber
    "linear-gradient(165deg, #fbcfe8 0%, #a7f3d0 100%)",   # pink ↔ mint
    "linear-gradient(165deg, #c7d2fe 0%, #fdba74 100%)",   # indigo ↔ orange
]


def _item_ref(cid: str) -> str:
    """FTL expression for repeat group item field (use bracket notation if hyphen in id)."""
    if "-" in cid:
        return f'item["{cid}"]!""'
    return f"item.{cid}!\"\""


def render_repeat_child_ftl(parent_id: str, child: dict) -> str:
    """Generate XB-editable markup for one nested field inside a repeat group (item, idx in scope)."""
    ctype = child["type"]
    cid = child["id"]
    parent_ice = ice_field_id(parent_id)
    child_ice = ice_field_id(cid)
    field_path = f"{parent_ice}.{child_ice}"
    item_val = _item_ref(cid)
    if ctype == "rte":
        return f'<@crafter.div $field="{field_path}" $index=idx>\n              ${{{item_val}}}\n            </@crafter.div>'
    if ctype in ("input", "textarea", "file-name"):
        return f'<@crafter.span $field="{field_path}" $index=idx>\n              ${{{item_val}}}\n            </@crafter.span>'
    if ctype == "date-time":
        item_opt = f'item["{cid}"]' if "-" in cid else f"item.{cid}"
        return f'<@crafter.span $field="{field_path}" $index=idx>\n              <#if {item_opt}??>${{{item_opt}?datetime?string(\'yyyy-MM-dd\')}}</#if>\n            </@crafter.span>'
    if ctype == "checkbox":
        item_opt = f'item["{cid}"]' if "-" in cid else f"item.{cid}"
        return f'<@crafter.span $field="{field_path}" $index=idx>\n              <#assign _v = ({item_opt}!false)?string /><#if _v == \'true\'>Yes<#else>No</#if>\n            </@crafter.span>'
    if ctype == "image-picker":
        return f'<@crafter.img $field="{field_path}" $index=idx src=({item_val}) alt=""/>'
    # default
    return f'<@crafter.span $field="{field_path}" $index=idx>\n              ${{{item_val}}}\n            </@crafter.span>'


def render_field_ftl(field: dict) -> str:
    ftype = field["type"]
    fid = field["id"]
    ftitle = field["title"]
    ice_id = ice_field_id(fid)  # ICE/XB expects fileName, internalName for $field
    bracket = field_uses_bracket(fid)
    model_val = ftl_safe_id(fid)

    if ftype in ("file-name", "input", "textarea"):
        mod = "field--input"
        inner = f'<@crafter.span $field="{ice_id}">\n                ${{{model_val}}}\n              </@crafter.span>'
    elif ftype == "date-time":
        mod = "field--input"
        # FreeMarker needs ?datetime?string so date-like values convert to string without error
        dt_ref = f'contentModel["{fid}"]' if "-" in fid else f'contentModel.{fid}'
        inner = f'<@crafter.span $field="{ice_id}">\n                <#if {dt_ref}??>${{{dt_ref}?datetime?string(\'yyyy-MM-dd\')}}</#if>\n              </@crafter.span>'
    elif ftype == "checkbox":
        mod = "field--checkbox"
        # Null-safe: (contentModel.field!false)?string so missing/null boolean does not throw
        bool_expr = f'contentModel["{fid}"]' if "-" in fid else f'contentModel.{fid}'
        checkbox_expr = f'({bool_expr}!false)?string'
        inner = f'<@crafter.span $field="{ice_id}">\n                <#assign _disabledStr = {checkbox_expr} /><#if _disabledStr == \'true\'>Yes<#elseif _disabledStr == \'false\'>No<#else>${{_disabledStr}}</#if>\n              </@crafter.span>'
    elif ftype == "rte":
        mod = "field--rte"
        inner = f'<@crafter.div $field="{ice_id}">\n                ${{{model_val}}}\n              </@crafter.div>'
    elif ftype == "image-picker":
        mod = "field--image"
        inner = f'<@crafter.img $field="{ice_id}" src=({model_val}) alt=""/>'
    elif ftype == "node-selector":
        mod = "field--collection"
        # scripts_o references Groovy scripts; render as path list, not as components
        if fid == "scripts_o":
            inner = f'''<div class="field__collection-inner">
                <#if contentModel.scripts_o?? && contentModel.scripts_o.item??>
                  <#list contentModel.scripts_o.item as script>
                    <span class="field__collection-item">${{script.key!script.include!''}}</span>
                  </#list>
                </#if>
              </div>'''
        else:
            inner = f'<@crafter.renderComponentCollection\n                $field="{ice_id}"\n                $containerAttributes={{ "class": "field__collection-inner" }}\n                $itemAttributes={{ "class": "field__collection-item" }}\n              />'
    elif ftype == "repeat":
        mod = "field--collection"
        # Null guard: ICE renderRepeatGroup requires collection to be non-null
        model_ref = f'contentModel["{ice_id}"]' if "-" in ice_id else f"contentModel.{ice_id}"
        guard_open = f"<#if {model_ref}??>"
        guard_else = '<#else>\n              <div class="field__repeat-group">No items.</div>'
        guard_close = "\n              </#if>"
        children = field.get("children") or []
        if children:
            # XB-editable repeat group: render each item with nested field markup ($field="parent.child" $index=idx)
            parts = [
                guard_open,
                f'<@crafter.renderRepeatGroup $field="{ice_id}" $containerAttributes={{ "class": "field__repeat-group" }}; item, idx>',
                '              <div class="field__collection-item field__repeat-item">',
            ]
            for i, ch in enumerate(children):
                ch_title = ch.get("title") or ch.get("id") or ""
                if ch_title:
                    parts.append('                <div class="field field--repeat-child">')
                    parts.append('                  <span class="field__label">' + ch_title + ' (${idx + 1})</span>')
                    parts.append('                  <div class="field__value">')
                parts.append("                " + render_repeat_child_ftl(fid, ch))
                if ch.get("title"):
                    parts.append(f'                  </div>')
                    parts.append(f'                </div>')
                if i < len(children) - 1:
                    parts.append('                <hr class="field__repeat-divider" />')
            parts.append("              </div>")
            parts.append("            </@crafter.renderRepeatGroup>")
            parts.append(guard_else)
            parts.append(guard_close)
            inner = "\n              ".join(parts)
        else:
            inner = f"{guard_open}\n              <@crafter.renderRepeatGroup $field=\"{ice_id}\"; item, idx>\n                <span class=\"field__collection-item\">Item ${{idx + 1}}</span>\n              </@crafter.renderRepeatGroup>{guard_else}{guard_close}"
    elif ftype == "checkbox-group":
        mod = "field--collection"
        list_expr = ftl_safe_expr(fid, "![]")
        inner = f'<@crafter.span $field="{ice_id}">\n                <#assign _list = {list_expr} /><#if _list?is_sequence>${{_list?size}} selected<#else>—</#if></@crafter.span>'
    else:
        mod = "field--input"
        inner = f'<@crafter.span $field="{ice_id}">\n                ${{{model_val}}}\n              </@crafter.span>'

    label_esc = ftitle.replace("&", "&amp;").replace("<", "&lt;")
    return f"""          <div class="field {mod}">
            <span class="field__label">{label_esc}</span>
            <div class="field__value">
              {inner}
            </div>
          </div>"""


def get_page_title_field(data: dict) -> str:
    """Prefer title_t, else internal-name, else form title."""
    has_internal_name = False
    for sec in data["sections"]:
        for f in sec["fields"]:
            if f["id"] == "title_t":
                return '${contentModel.title_t!\'\'}'
            if f["id"] == "internal-name":
                has_internal_name = True
    if has_internal_name:
        return '${contentModel["internal-name"]!\'\'}'
    return "'" + data["title"] + "'"


# ---------------------------------------------------------------------------
# Full template CSS: white sections, one page accent (varies by page)
# ---------------------------------------------------------------------------

def _page_accent_for_content_type(content_type_path: str) -> str:
    """Pick a stable accent gradient for this content type (page or component)."""
    idx = hash(content_type_path) % len(PAGE_ACCENTS)
    if idx < 0:
        idx += len(PAGE_ACCENTS)
    return PAGE_ACCENTS[idx]


def build_css(num_sections: int, content_type_path: str = "") -> str:
    page_accent = _page_accent_for_content_type(content_type_path) if content_type_path else PAGE_ACCENTS[0]
    lines = [
        "    /* White sections; page-level accent background */",
        "    :root {",
        "      --bg: #f7f6f3; --bg-subtle: #f1f0ed; --surface: #ffffff; --surface-alt: #fafafa;",
        "      --border: rgba(55, 53, 47, 0.09); --text: #37352f; --text-secondary: #6b6b6b; --muted: #9b9a97;",
        "      --radius: 4px; --radius-sm: 3px;",
        '      --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        "    }",
        "    * { box-sizing: border-box; }",
        f"    body {{ margin: 0; font-family: var(--font-sans); background: {page_accent}; color: var(--text); -webkit-font-smoothing: antialiased; line-height: 1.6; }}",
        "    .page { min-height: 100vh; display: flex; flex-direction: column; }",
        "    .page__main { flex: 1; max-width: 1100px; margin: 0 auto; padding: 2.5rem 2rem 3rem; width: 100%; }",
        "    .page__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 2.5rem; gap: 1.5rem; }",
        "    .page__header-primary { display: flex; flex-direction: column; gap: 0.2rem; }",
        "    .page__title { font-size: 1.25rem; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }",
        "    .sections-grid { display: grid; gap: 1.75rem; align-items: flex-start; "
        + ("grid-template-columns: minmax(0, 2.2fr) minmax(0, 1.6fr); " if num_sections == 2 else "grid-template-columns: minmax(0, 1fr); ")
        + "}",
        "    .section { border-radius: var(--radius); border: 1px solid var(--border); overflow: hidden; box-shadow: 0 12px 28px -8px rgba(0, 0, 0, 0.18), 0 6px 14px -6px rgba(0, 0, 0, 0.12); }",
        "    .section__header { background: #f3f4f6; padding: 1rem 1.75rem; border-bottom: 1px solid rgba(0, 0, 0, 0.1); }",
        "    .section__title { margin: 0; font-size: 1.0625rem; font-weight: 600; color: #374151; letter-spacing: -0.01em; }",
        "    .section__body { display: grid; grid-template-columns: minmax(0, 1fr); gap: 1rem; padding: 1.5rem 1.75rem; background: var(--surface); }",
        "    .field { display: flex; flex-direction: column; gap: 0.3rem; }",
        "    .field__label { font-size: 0.75rem; font-weight: 700; color: var(--muted); }",
        "    .field__value { font-size: 0.9375rem; font-weight: 400; line-height: 1.6; color: var(--text); }",
        "    .field--rte .field__value { line-height: 1.65; }",
        "    .field--image .field__value img { max-width: 100%; height: auto; border-radius: var(--radius-sm); border: 1px solid var(--border); }",
        "    .field--collection .field__value { display: flex; flex-wrap: wrap; gap: 0.5rem; }",
        "    .field__collection-inner { display: flex; flex-wrap: wrap; gap: 0.5rem; }",
        "    .field__collection-item { border: 1px solid var(--border); border-radius: var(--radius); padding: 0.3rem 0.65rem; font-size: 0.8125rem; font-weight: 400; background: var(--surface); color: var(--text); }",
        "    .field__help { margin-top: 0.35rem; font-size: 0.8125rem; color: var(--muted); }",
        "    .page__footer { padding: 1.5rem 2rem 2rem; font-size: 0.8125rem; text-align: center; color: var(--muted); border-top: 1px solid var(--border); margin-top: 2.5rem; }",
        "    @media (max-width: 960px) { .sections-grid { grid-template-columns: minmax(0, 1fr); } }",
        "  </style>",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Full FTL document
# ---------------------------------------------------------------------------

def _is_page_template(content_type_path: str, object_type: str) -> bool:
    """Only content under /site/website/ (pages) gets full HTML document; components are fragments."""
    if content_type_path.startswith("page/"):
        return True
    return (object_type or "").lower() == "page"


def generate_ftl(data: dict, page_title_expr: str, content_type_path: str = "") -> str:
    object_type = (data.get("object_type") or "").strip()
    is_page = _is_page_template(content_type_path, object_type)
    slug = content_type_path.split("/")[-1] if "/" in content_type_path else (content_type_path or "fragment")

    # Shared: section grid and sections (indentation differs for page vs fragment)
    section_lines = []
    for sec in data["sections"]:
        sec_title_esc = sec["title"].replace("&", "&amp;").replace("<", "&lt;")
        section_lines.append("      <section class=\"section\">")
        section_lines.append("        <div class=\"section__header\">")
        section_lines.append(f"          <h2 class=\"section__title\">{sec_title_esc}</h2>")
        section_lines.append("        </div>")
        section_lines.append("        <div class=\"section__body\">")
        for field in sec["fields"]:
            section_lines.append(render_field_ftl(field))
        section_lines.append("        </div>")
        section_lines.append("      </section>")
        section_lines.append("")

    if is_page:
        parts = [
            '<#import "/templates/system/common/crafter.ftl" as crafter />',
            "",
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            "  <meta charset=\"utf-8\" />",
            "  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
            f"  <title>{page_title_expr}</title>",
            "",
            "  <style>",
            build_css(len(data["sections"]), content_type_path),
            "  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">",
            "  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
            "  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">",
            "  <@crafter.head/>",
            "</head>",
            "<body>",
            "<@crafter.body_top/>",
            "",
            "<@crafter.section $model=contentModel>",
            "<div class=\"page\">",
            "  <main class=\"page__main\">",
            "    <header class=\"page__header\">",
            "      <div class=\"page__header-primary\">",
            f"        <div class=\"page__title\">{data['title']} content</div>",
            "      </div>",
            "    </header>",
            "",
            "    <div class=\"sections-grid\">",
        ]
        parts.extend(section_lines)
        parts.extend([
            "    </div>",
            "  </main>",
            "",
            f"  <footer class=\"page__footer\">",
            f"    Editing headless fields for <strong>{data['title']}</strong>.",
            "  </footer>",
            "</div>",
            "</@crafter.section>",
            "",
            "<@crafter.body_bottom/>",
            "</body>",
            "</html>",
        ])
    else:
        # Fragment only: no html/head/body; for components rendered inside pages
        # Visible wrapper: dashed border and light tint so component boundary is obvious in XB/preview
        parts = [
            '<#import "/templates/system/common/crafter.ftl" as crafter />',
            "",
            f'<div class="component-fragment component-fragment--{slug}" style="border: 2px dashed rgba(59, 130, 246, 0.5); border-radius: 8px; padding: 1rem; margin: 0.5rem 0; background: rgba(59, 130, 246, 0.04);">',
            "  <div class=\"sections-grid\">",
        ]
        parts.extend(section_lines)
        parts.extend([
            "  </div>",
            "</div>",
        ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Generate a generic headless FTL template from a CrafterCMS form-definition.xml.",
    )
    ap.add_argument(
        "input",
        nargs="?",
        help="Path to form-definition.xml, or content type path (e.g. page/article) relative to config/studio/content-types/",
    )
    ap.add_argument(
        "-s", "--sandbox",
        type=Path,
        default=None,
        help="Sandbox root (default: auto-detect from script path or cwd)",
    )
    ap.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output FTL path (default: stdout)",
    )
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    if args.sandbox is None:
        sandbox = script_dir.parent.parent
        if (sandbox / "config" / "studio" / "content-types").exists():
            pass
        else:
            sandbox = Path.cwd()
    else:
        sandbox = Path(args.sandbox).resolve()

    content_types_dir = sandbox / "config" / "studio" / "content-types"
    if not content_types_dir.exists():
        print("Error: config/studio/content-types not found under sandbox.", file=sys.stderr)
        sys.exit(1)

    if not args.input:
        ap.print_help()
        sys.exit(0)

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = input_path.resolve()
    if not input_path.exists():
        candidate = content_types_dir / args.input.replace(".", "/") / "form-definition.xml"
        if candidate.exists():
            input_path = candidate
        else:
            print(f"Error: not found: {args.input} or {candidate}", file=sys.stderr)
            sys.exit(1)
    if input_path.suffix != ".xml":
        form_path = input_path / "form-definition.xml"
        if form_path.exists():
            input_path = form_path
        else:
            print(f"Error: no form-definition.xml at {input_path}", file=sys.stderr)
            sys.exit(1)

    data = parse_form_definition(input_path)
    if not data["sections"]:
        print("Error: no sections with fields found in form definition.", file=sys.stderr)
        sys.exit(1)

    # Content type path e.g. "page/home" or "component/header" for page-specific accent
    try:
        content_type_path = str(input_path.parent.relative_to(content_types_dir))
    except ValueError:
        content_type_path = ""
    page_title_expr = get_page_title_field(data)
    out = generate_ftl(data, page_title_expr, content_type_path)

    if args.output is not None:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = (sandbox if (sandbox / out_path).exists() else Path.cwd()) / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
