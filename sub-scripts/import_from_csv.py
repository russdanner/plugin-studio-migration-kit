#!/usr/bin/env python3
"""
CrafterCMS CSV Migration Importer

Imports content types (config.xml + form-definition.xml) and content items from
content-types.csv, datasources.csv, and content.csv per CSV_MIGRATION_README.md.

Usage:
  Run from the Crafter sandbox root (parent of migration-kit/):
    python3 migration-kit/full-import.py
    # Or run the importer directly (CSVs in migration-kit/content-import/):
    python3 migration-kit/sub-scripts/import_from_csv.py [--sandbox PATH] [--content-import-dir PATH] [--dry-run] [--content-only]

  CSV dir is always migration-kit/content-import/ (not examples/example-import-data). When run from sub-scripts/, --content-import-dir defaults to that path.
"""

import csv
import os
import re
import sys
import uuid
import argparse
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET
from collections import defaultdict
from xml.sax.saxutils import escape as xml_escape


# ---------------------------------------------------------------------------
# Paths and config
# ---------------------------------------------------------------------------

def find_sandbox_root(script_dir: Path) -> Path:
    """Resolve sandbox root: parent of migration-kit, or from --sandbox."""
    # If we're in migration-kit/content-import/, sandbox is parent of migration-kit
    p = script_dir.resolve()
    if "migration-kit" in p.parts:
        for i, part in enumerate(p.parts):
            if part == "migration-kit":
                return Path(*p.parts[:i])
    return p.parent.parent  # assume script is in migration-kit/content-import


def default_csv_dir(script_dir: Path, migration_kit: Optional[Path] = None) -> Path:
    """CSV dir: always migration-kit/content-import (never examples/example-import-data)."""
    if migration_kit is not None:
        return migration_kit / "content-import"
    if script_dir.name == "sub-scripts":
        return script_dir.parent / "content-import"
    return script_dir


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _str(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


def _bool(row: dict, key: str) -> bool:
    v = _str(row, key).lower()
    return v in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Datasources
# ---------------------------------------------------------------------------

def load_datasources(csv_path: Path) -> dict:
    """Datasource ID -> dict of properties."""
    rows = read_csv(csv_path)
    by_id = {}
    for r in rows:
        did = _str(r, "Datasource ID")
        if not did:
            continue
        by_id[did] = {
            "type": _str(r, "Type"),
            "title": _str(r, "Title"),
            "interface": _str(r, "Interface"),
            "repo_path": _str(r, "Repo Path"),
            "browse_path": _str(r, "Browse Path"),
            "base_repository_path": _str(r, "Base Repository Path"),
            "base_browse_path": _str(r, "Base Browse Path"),
            "content_types": _str(r, "Content Types"),
            "allow_shared": _str(r, "Allow Shared"),
            "allow_embedded": _str(r, "Allow Embedded"),
            "enable_browse": _str(r, "Enable Browse"),
            "enable_search": _str(r, "Enable Search"),
            "enable_create_new": _str(r, "Enable Create New"),
            "enable_browse_existing": _str(r, "Enable Browse Existing"),
            "enable_search_existing": _str(r, "Enable Search Existing"),
            "component_path": _str(r, "Component Path"),
            "tags": _str(r, "Tags"),
            "use_search": _str(r, "Use Search"),
        }
    return by_id


def build_datasource_xml(dsid: str, d: dict) -> str:
    """One <datasource> element."""
    ds_type = d["type"]
    title = xml_escape(d["title"] or dsid)
    interface = d["interface"] or "item"
    lines = [
        f'<datasource>',
        f'  <type>{xml_escape(ds_type)}</type>',
        f'  <id>{xml_escape(dsid)}</id>',
        f'  <title>{title}</title>',
        f'  <interface>{interface}</interface>',
        f'  <properties>',
    ]
    if d["repo_path"]:
        # Image datasources: use content-path-input so Studio/XB can resolve paths for upload/browse
        repo_path_type = "content-path-input" if ds_type in ("img-desktop-upload", "img-repository-upload") else "undefined"
        lines.append(f'    <property><name>repoPath</name><value>{xml_escape(d["repo_path"])}</value><type>{repo_path_type}</type></property>')
    if d["browse_path"] is not None:
        lines.append(f'    <property><name>browsePath</name><value>{xml_escape(d["browse_path"])}</value><type>undefined</type></property>')
    if ds_type == "img-repository-upload":
        # useSearch: enable/disable search in repo; default false for predictable behavior
        use_search_val = d["use_search"] if d["use_search"] else "false"
        lines.append(f'    <property><name>useSearch</name><value>{xml_escape(use_search_val)}</value><type>boolean</type></property>')
    if ds_type == "shared-content":
        if d["enable_create_new"]:
            lines.append(f'    <property><name>enableCreateNew</name><value>{d["enable_create_new"]}</value><type>boolean</type></property>')
        if d["enable_browse_existing"]:
            lines.append(f'    <property><name>enableBrowseExisting</name><value>{d["enable_browse_existing"]}</value><type>boolean</type></property>')
        if d["enable_search_existing"]:
            lines.append(f'    <property><name>enableSearchExisting</name><value>{d["enable_search_existing"]}</value><type>boolean</type></property>')
    if ds_type == "components":
        if d["base_repository_path"]:
            lines.append(f'    <property><name>baseRepositoryPath</name><value>{xml_escape(d["base_repository_path"])}</value><type>string</type></property>')
        if d["base_browse_path"]:
            lines.append(f'    <property><name>baseBrowsePath</name><value>{xml_escape(d["base_browse_path"])}</value><type>string</type></property>')
        if d["content_types"]:
            lines.append(f'    <property><name>contentTypes</name><value>{xml_escape(d["content_types"])}</value><type>contentTypes</type></property>')
        if d["allow_shared"]:
            lines.append(f'    <property><name>allowShared</name><value>{d["allow_shared"]}</value><type>boolean</type></property>')
        if d["allow_embedded"]:
            lines.append(f'    <property><name>allowEmbedded</name><value>{d["allow_embedded"]}</value><type>boolean</type></property>')
        if d["enable_browse"]:
            lines.append(f'    <property><name>enableBrowse</name><value>{d["enable_browse"]}</value><type>boolean</type></property>')
        if d["enable_search"]:
            lines.append(f'    <property><name>enableSearch</name><value>{d["enable_search"]}</value><type>boolean</type></property>')
    if ds_type == "simpleTaxonomy" and d["component_path"]:
        lines.append(f'    <property><name>componentPath</name><value>{xml_escape(d["component_path"])}</value><type>string</type></property>')
    if d["use_search"] and ds_type != "img-repository-upload":
        # useSearch for non-image datasources (img-repository-upload handled above)
        lines.append(f'    <property><name>useSearch</name><value>{d["use_search"]}</value><type>boolean</type></property>')
    lines.append("  </properties>")
    lines.append("</datasource>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Content types: group by type and section
# ---------------------------------------------------------------------------

def type_name_to_slug(type_name: str) -> str:
    """e.g. /page/home -> home, /component/social-media-widget -> social-media-widget"""
    return type_name.strip("/").split("/")[-1].replace("_", "-")


def type_name_to_display_template(type_name: str, is_page: bool) -> str:
    if type_name == "/taxonomy":
        return ""
    slug = type_name_to_slug(type_name)
    if is_page:
        return f"/templates/web/pages/{slug}.ftl"
    return f"/templates/web/components/{slug}.ftl"


def load_content_type_rows(csv_path: Path) -> list[dict]:
    return read_csv(csv_path)


def required_fields_by_type(ct_rows: list[dict]) -> dict:
    """Build type_name -> list of (field_id, field_type) for fields marked Required=true. Only top-level (no Parent Field)."""
    by_type = defaultdict(list)
    for r in ct_rows:
        if not _bool(r, "Required"):
            continue
        type_name = _str(r, "Type Name")
        parent = _str(r, "Parent Field")
        if parent:
            continue
        fid = _str(r, "Field Name")
        ftype = _str(r, "Field Type") or "input"
        if type_name and fid:
            by_type[type_name].append((fid, ftype))
    return dict(by_type)


def checkbox_group_field_ids_by_type(ct_rows: list[dict]) -> dict:
    """Build type_name -> set of field ids where Field Type is checkbox-group. Only top-level (no Parent Field).
    Form engine does not write item-list=\"true\" on checkbox-group collections; XB expects that."""
    by_type = defaultdict(set)
    for r in ct_rows:
        if _str(r, "Field Type") != "checkbox-group":
            continue
        type_name = _str(r, "Type Name")
        parent = _str(r, "Parent Field")
        if parent:
            continue
        fid = _str(r, "Field Name")
        if type_name and fid:
            by_type[type_name].add(fid)
    return dict(by_type)


def top_level_field_order_by_type(ct_rows: list[dict]) -> dict:
    """Build type_name -> [(field_id, field_type), ...] in CSV row order. Top-level only (no Parent Field).
    Used to output all form-defined fields in form order with defaults for missing values (XB requires every field present)."""
    by_type = defaultdict(list)
    for r in ct_rows:
        type_name = _str(r, "Type Name")
        parent = _str(r, "Parent Field")
        if parent:
            continue
        fid = _str(r, "Field Name")
        ftype = _str(r, "Field Type") or "input"
        if type_name and fid:
            by_type[type_name].append((fid, ftype))
    return dict(by_type)


def item_manager_by_type_and_field(ct_rows: list[dict]) -> dict:
    """Build type_name -> { field_id -> Item Manager } from content-types.csv. Top-level only. Data-driven item datasource."""
    by_type = defaultdict(dict)
    for r in ct_rows:
        type_name = _str(r, "Type Name")
        parent = _str(r, "Parent Field")
        if parent:
            continue
        fid = _str(r, "Field Name")
        item_mgr = _str(r, "Item Manager")
        if type_name and fid and item_mgr:
            by_type[type_name][fid] = item_mgr
    return dict(by_type)


def default_value_for_field_type(ftype: str) -> object:
    """Default value for a required field when missing from content. Used so XB/Studio save does not fail."""
    if ftype == "checkbox":
        return "false"
    if ftype == "date-time":
        return "2020-01-01T00:00:00.000Z"
    if ftype in ("node-selector", "repeat", "checkbox-group"):
        return ("_item_list", [])
    return ""


def group_content_type_fields(rows: list[dict]) -> dict:
    """Group by Type Name -> sections -> list of field rows (top-level and repeat children)."""
    by_type = defaultdict(lambda: defaultdict(list))
    for r in rows:
        type_name = _str(r, "Type Name")
        section = _str(r, "Section")
        if not type_name or not section:
            continue
        by_type[type_name][section].append(r)
    return dict(by_type)


def collect_datasource_ids_from_type(rows: list[dict]) -> set:
    ids = set()
    for r in rows:
        for key in ("Item Manager", "Image Manager", "Dropdown Datasource"):
            v = _str(r, key)
            if not v:
                continue
            for part in v.replace("|", ",").split(","):
                ids.add(part.strip())
    return ids


def build_field_xml(field_row: dict, datasources: dict, indent: str = "				") -> str:
    """Single <field> element (no repeat children)."""
    field_type = _str(field_row, "Field Type") or "input"
    fid = _str(field_row, "Field Name")
    label = xml_escape(_str(field_row, "Field Label") or fid)
    desc = xml_escape(_str(field_row, "Description"))
    help_ = xml_escape(_str(field_row, "Help"))
    required = _bool(field_row, "Required")
    item_mgr = _str(field_row, "Item Manager")
    image_mgr = _str(field_row, "Image Manager")
    allowed = _str(field_row, "Allowed Content Types")
    min_size = _str(field_row, "Min Size")
    max_size = _str(field_row, "Max Size")
    dropdown_ds = _str(field_row, "Dropdown Datasource")

    lines = [
        f'{indent}<field>',
        f'{indent}	<type>{xml_escape(field_type)}</type>',
        f'{indent}	<id>{xml_escape(fid)}</id>',
        f'{indent}	<iceId></iceId>',
        f'{indent}	<title>{label}</title>',
        f'{indent}	<description>{desc}</description>',
        f'{indent}	<defaultValue></defaultValue>',
        f'{indent}	<help>{help_}</help>',
        f'{indent}	<properties>',
    ]
    # Associate control with datasources first (required for image-picker/RTE so Studio/XB binds them)
    if field_type == "image-picker":
        image_mgr_use = image_mgr or "uploadImages,existingImages"
        parts = [p.strip() for p in (image_mgr_use.replace("|", ",").split(",")) if p.strip()]
        upload_first = sorted(parts, key=lambda x: (0 if "upload" in x.lower() else 1, x))
        image_mgr_value = ",".join(upload_first)
        lines.append(f'{indent}		<property><name>imageManager</name><value>{xml_escape(image_mgr_value)}</value><type>datasource:image</type></property>')
    if field_type == "rte":
        image_mgr_use = image_mgr or "uploadImages,existingImages"
        parts = [p.strip() for p in (image_mgr_use.replace("|", ",").split(",")) if p.strip()]
        upload_first = sorted(parts, key=lambda x: (0 if "upload" in x.lower() else 1, x))
        image_mgr_value = ",".join(upload_first)
        lines.append(f'{indent}		<property><name>imageManager</name><value>{xml_escape(image_mgr_value)}</value><type>datasource:image</type></property>')
    # node-selector: associate with item datasource first
    if field_type == "node-selector":
        lines.append(f'{indent}		<property><name>minSize</name><value>{min_size or "0"}</value><type>int</type></property>')
        lines.append(f'{indent}		<property><name>maxSize</name><value>{max_size or "1"}</value><type>int</type></property>')
        if item_mgr:
            lines.append(f'{indent}		<property><name>itemManager</name><value>{xml_escape(item_mgr)}</value><type>datasource:item</type></property>')
        if allowed:
            lines.append(f'{indent}		<property><name>contentTypes</name><value>{xml_escape(allowed)}</value><type>contentTypes</type></property>')
    # Standard size/maxlength for input-like
    if field_type in ("input", "file-name"):
        lines.append(f'{indent}		<property><name>size</name><value>50</value><type>int</type></property>')
        lines.append(f'{indent}		<property><name>maxlength</name><value>50</value><type>int</type></property>')
    if field_type == "file-name":
        lines.append(f'{indent}		<property><name>readonly</name><value>true</value><type>boolean</type></property>')
    if field_type == "dropdown" and dropdown_ds:
        lines.append(f'{indent}		<property><name>datasource</name><value>{xml_escape(dropdown_ds)}</value><type>datasource:item</type></property>')
    if field_type == "checkbox-group":
        if dropdown_ds:
            lines.append(f'{indent}		<property><name>datasource</name><value>{xml_escape(dropdown_ds)}</value><type>datasource:item</type></property>')
        lines.append(f'{indent}		<property><name>selectAll</name><value>true</value><type>boolean</type></property>')
    if field_type == "repeat":
        min_occ = _str(field_row, "Min Occurs") or "0"
        max_occ = _str(field_row, "Max Occurs") or "*"
        lines.append(f'{indent}		<property><name>minOccurs</name><value>{min_occ}</value><type>string</type></property>')
        lines.append(f'{indent}		<property><name>maxOccurs</name><value>{max_occ}</value><type>string</type></property>')
    lines.append(f'{indent}	</properties>')
    lines.append(f'{indent}	<constraints>')
    if required:
        lines.append(f'{indent}		<constraint><name>required</name><value><![CDATA[true]]></value><type>boolean</type></constraint>')
    else:
        lines.append(f'{indent}		<constraint><name>required</name><value><![CDATA[]]></value><type>boolean</type></constraint>')
    if field_type == "checkbox-group":
        min_occ = _str(field_row, "Min Occurs")
        if min_occ and min_occ.isdigit():
            lines.append(f'{indent}		<constraint><name>minSize</name><value><![CDATA[{min_occ}]]></value><type>int</type></constraint>')
    lines.append(f'{indent}	</constraints>')
    lines.append(f'{indent}</field>')
    return "\n".join(lines)


def build_repeat_field_xml(repeat_row: dict, child_rows: list[dict], datasources: dict) -> str:
    """<field type="repeat"> with nested <fields>."""
    indent = "				"
    lines = [
        f'{indent}<field>',
        f'{indent}	<type>repeat</type>',
        f'{indent}	<id>{xml_escape(_str(repeat_row, "Field Name"))}</id>',
        f'{indent}	<iceId></iceId>',
        f'{indent}	<title>{xml_escape(_str(repeat_row, "Field Label"))}</title>',
        f'{indent}	<description></description>',
        f'{indent}	<minOccurs>{_str(repeat_row, "Min Occurs") or "0"}</minOccurs>',
        f'{indent}	<maxOccurs>{_str(repeat_row, "Max Occurs") or "*"}</maxOccurs>',
        f'{indent}	<properties>',
        f'{indent}		<property><name>minOccurs</name><value>{_str(repeat_row, "Min Occurs") or "0"}</value><type>string</type></property>',
        f'{indent}		<property><name>maxOccurs</name><value>{_str(repeat_row, "Max Occurs") or "*"}</value><type>string</type></property>',
        f'{indent}	</properties>',
        f'{indent}	<fields>',
    ]
    for cr in child_rows:
        lines.append(build_field_xml(cr, datasources, indent="				\t"))
    lines.append(f'{indent}	</fields>')
    lines.append(f'{indent}</field>')
    return "\n".join(lines)


def build_section_xml(section_title: str, field_rows: list[dict], datasources: dict) -> str:
    """One <section> with <fields>. Handles repeat groups: one row type=repeat, rest with Parent Field set."""
    top_level = [r for r in field_rows if not _str(r, "Parent Field")]
    repeat_ids = {_str(r, "Field Name") for r in top_level if _str(r, "Field Type") == "repeat"}
    # Build field XML for each top-level; if repeat, gather children and use build_repeat_field_xml
    field_parts = []
    for r in top_level:
        if _str(r, "Field Type") == "repeat":
            parent_id = _str(r, "Field Name")
            children = [c for c in field_rows if _str(c, "Parent Field") == parent_id]
            field_parts.append(build_repeat_field_xml(r, children, datasources))
        else:
            field_parts.append(build_field_xml(r, datasources))
    fields_xml = "\n".join(field_parts)
    return f"""		<section>
			<title>{xml_escape(section_title)}</title>
			<description></description>
			<defaultOpen>true</defaultOpen>
			<fields>
{fields_xml}
			</fields>
		</section>"""


def build_form_definition(type_name: str, type_label: str, sections: dict, datasources: dict, all_type_rows: list[dict]) -> str:
    is_page = type_name.startswith("/page/")
    object_type = "page" if is_page else "component"
    display_template = type_name_to_display_template(type_name, is_page)
    no_template_required = "true" if type_name in ("/component/level-descriptor", "/taxonomy") else ""
    image_thumbnail = "taxonomy.png" if type_name == "/taxonomy" else "image.jpg"

    sections_xml = "\n".join(
        build_section_xml(section_title, list(rows), datasources)
        for section_title, rows in sections.items()
    )
    ds_ids = collect_datasource_ids_from_type(all_type_rows)
    # Ensure image datasources are included when this type has image-picker or rte (associate control with datasource)
    has_image_control = any(
        _str(r, "Field Type") in ("image-picker", "rte") for r in all_type_rows
    )
    if has_image_control:
        for default_id in ("uploadImages", "existingImages", "upload_image", "existing_images", "imageUpload", "imageFromRepository"):
            if default_id in datasources and default_id not in ds_ids:
                ds_ids.add(default_id)
    # Emit image datasources first so controls (image-picker, rte) are clearly associated with them
    ds_id_list = [x for x in ds_ids if x in datasources]
    image_ds = [x for x in ds_id_list if datasources.get(x, {}).get("interface") == "image"]
    other_ds = [x for x in ds_id_list if x not in image_ds]
    ordered_ds_ids = image_ds + other_ds
    datasources_xml = "\n".join(
        build_datasource_xml(dsid, datasources[dsid])
        for dsid in ordered_ds_ids
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<form>
	<title>{xml_escape(type_label)}</title>
	<description></description>
	<objectType>{object_type}</objectType>
	<content-type>{xml_escape(type_name)}</content-type>
	<imageThumbnail>{image_thumbnail}</imageThumbnail>
	<quickCreate>false</quickCreate>
	<quickCreatePath></quickCreatePath>
	<properties>
		<property>
			<name>display-template</name>
			<label>Display Template</label>
			<value>{display_template}</value>
			<type>template</type>
		</property>
		<property>
			<name>no-template-required</name>
			<label>No Template Required</label>
			<value>{no_template_required}</value>
			<type>boolean</type>
		</property>
		<property>
			<name>merge-strategy</name>
			<label>Merge Strategy</label>
			<value>inherit-levels</value>
			<type>string</type>
		</property>
	</properties>
	<sections>
{sections_xml}
	</sections>
	<datasources>
{datasources_xml}
	</datasources>
</form>"""


def build_config_xml(type_name: str, type_label: str) -> str:
    is_page = type_name.startswith("/page/")
    is_taxonomy = type_name == "/taxonomy"
    slug = type_name_to_slug(type_name)
    content_as_folder = "true" if is_page else "false"
    if is_taxonomy:
        paths_dir = "includes"
        paths_pattern = "^/site/taxonomy/.*"
        previewable = "false"
        no_thumbnail = "false"
        image_thumbnail = "taxonomy.png"
    elif is_page:
        paths_dir = "excludes"
        paths_pattern = "^/site/components.*"
        previewable = "true"
        no_thumbnail = "true"
        image_thumbnail = "image.jpg"
    else:
        paths_dir = "includes"
        paths_pattern = "^/site/components/.*"
        previewable = "true"
        no_thumbnail = "true"
        image_thumbnail = "image.jpg"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<content-type name="{xml_escape(type_name)}" is-wcm-type="true">
	<label>{xml_escape(type_label)}</label>
	<form>{xml_escape(type_name)}</form>
	<form-path>simple</form-path>
	<model-instance-path>NOT-USED-BY-SIMPLE-FORM-ENGINE</model-instance-path>
	<file-extension>xml</file-extension>
	<content-as-folder>{content_as_folder}</content-as-folder>
	<previewable>{previewable}</previewable>
	<quickCreate>false</quickCreate>
	<quickCreatePath></quickCreatePath>
	<noThumbnail>{no_thumbnail}</noThumbnail>
	<image-thumbnail>{image_thumbnail}</image-thumbnail>
	<paths>
		<{paths_dir}>
			<pattern>{paths_pattern}</pattern>
		</{paths_dir}>
	</paths>
</content-type>"""



def write_content_types(sandbox: Path, csv_dir: Path, datasources: dict, dry_run: bool) -> None:
    ct_path = csv_dir / "content-types.csv"
    if not ct_path.exists():
        print(f"Skip content types: {ct_path} not found")
        return
    rows = load_content_type_rows(ct_path)
    grouped = group_content_type_fields(rows)
    for type_name, sections in grouped.items():
        slug = type_name_to_slug(type_name)
        is_page = type_name.startswith("/page/")
        if type_name == "/taxonomy":
            # Taxonomy: config and form live directly in content-types/taxonomy/ (no slug subfolder)
            out_dir = sandbox / "config" / "studio" / "content-types" / "taxonomy"
        else:
            dir_name = "page" if is_page else "component"
            out_dir = sandbox / "config" / "studio" / "content-types" / dir_name / slug
        if dry_run:
            print(f"[dry-run] Would create content type: {type_name} -> {out_dir}")
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        type_label = next((_str(r, "Type Label") for r in rows if _str(r, "Type Name") == type_name), slug)
        all_type_rows = [r for r in rows if _str(r, "Type Name") == type_name]
        config_xml = build_config_xml(type_name, type_label)
        form_xml = build_form_definition(type_name, type_label, sections, datasources, all_type_rows)
        (out_dir / "config.xml").write_text(config_xml, encoding="utf-8")
        (out_dir / "form-definition.xml").write_text(form_xml, encoding="utf-8")
        print(f"Created content type: {type_name} at {out_dir}")


# ---------------------------------------------------------------------------
# Content import
# ---------------------------------------------------------------------------

def load_content_rows(csv_path: Path) -> list[dict]:
    return read_csv(csv_path)


def content_root_element(type_name: str) -> str:
    return "page" if type_name.startswith("/page/") else "component"


# Canonical element order so saved XML matches Studio form-save output (XB-friendly).
# Pages: content-type, display-template, no-template-required, merge-strategy first; then objectId, dates, file-name; then form fields; then folder-name, orderDefault_f, disabled, createdDate, lastModifiedDate.
PAGE_LEAD_ORDER = (
    "content-type", "display-template", "no-template-required", "merge-strategy",
    "objectId", "createdDate_dt", "lastModifiedDate_dt", "file-name",
)
PAGE_TRAIL_ORDER = ("folder-name", "orderDefault_f", "disabled", "createdDate", "lastModifiedDate")
# Content types that have orderDefault_f in the form (get default 0.0 if missing).
PAGE_TYPES_WITH_ORDER_DEFAULT = ("/page/category-landing",)
COMPONENT_LEAD_ORDER = (
    "content-type", "display-template", "no-template-required", "merge-strategy",
    "objectId", "createdDate_dt", "lastModifiedDate_dt", "file-name",
)


def ordered_content_items(
    root: str,
    type_name: str,
    content_el: dict,
    out_file: Path,
    form_order: list[tuple[str, str]] | None = None,
    required_field_ids: set | None = None,
) -> list[tuple]:
    """Return (field_name, value) list in canonical order so saved XML matches Studio form-save (XB-friendly).
    When form_order is provided, every form-defined field is output in form order with default if missing.
    Optional node-selectors (not in required_field_ids) are skipped here and emitted after repeat groups by the writer."""
    is_page = root == "page"
    lead = PAGE_LEAD_ORDER if is_page else COMPONENT_LEAD_ORDER
    trail = PAGE_TRAIL_ORDER if is_page else ()
    seen = set()
    items = []

    for key in lead:
        if key == "no-template-required":
            items.append((key, None))  # self-closing
            seen.add(key)
            continue
        if key == "merge-strategy":
            items.append((key, content_el.get("merge-strategy", "inherit-levels")))
            seen.add(key)
            continue
        if key == "objectId":
            items.append((key, content_el.get("objectId") or f"{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:12]}"))
            seen.add(key)
            continue
        if key in ("createdDate_dt", "lastModifiedDate_dt"):
            items.append((key, content_el.get(key, "2020-01-01T00:00:00.000Z")))
            seen.add(key)
            continue
        if key in content_el:
            items.append((key, content_el[key]))
            seen.add(key)

    if form_order:
        # Data-driven: output every top-level form field in form order; use default when missing (XB needs every field present)
        # Optional node-selectors (not required) are emitted after repeat groups by writer to match form engine order
        required_ids = required_field_ids or set()
        for fid, ftype in form_order:
            if fid in seen or fid in trail:
                continue
            if ftype == "repeat":
                continue  # emitted in repeat-groups block
            if ftype == "node-selector" and fid not in required_ids:
                continue  # emitted after repeat groups to match form output
            value = content_el.get(fid, default_value_for_field_type(ftype))
            items.append((fid, value))
            seen.add(fid)
    else:
        for key in sorted(content_el.keys()):
            if key in seen or key in trail:
                continue
            items.append((key, content_el[key]))
            seen.add(key)

    if is_page:
        if "folder-name" not in seen:
            # Folder segment for URL: technology for site/website/technology/index.xml; empty for site/website/index.xml
            if out_file.name == "index.xml" and out_file.parent.name != "website":
                folder_val = out_file.parent.name
            else:
                folder_val = ""
            items.append(("folder-name", folder_val))
        if type_name in PAGE_TYPES_WITH_ORDER_DEFAULT and "orderDefault_f" not in seen:
            items.append(("orderDefault_f", content_el.get("orderDefault_f", "0.0")))
        if "disabled" not in seen:
            items.append(("disabled", content_el.get("disabled", "false")))
        dt_created = content_el.get("createdDate_dt", "2020-01-01T00:00:00.000Z")
        dt_modified = content_el.get("lastModifiedDate_dt", "2020-01-01T00:00:00.000Z")
        items.append(("createdDate", dt_created))
        items.append(("lastModifiedDate", dt_modified))

    return items


def escape_value_for_xml(value: str) -> str:
    if not value:
        return value
    if "<" in value or ">" in value or "&" in value:
        return f"<![CDATA[{value}]]>" if "]]>" not in value else xml_escape(value)
    return xml_escape(value)


def resolve_embedded_value(sandbox: Path, raw: str) -> str:
    """
    If raw is of the form:
      EMBEDDED|/site/path/to/parent.xml|/root/child/...
    load the parent XML and return the serialized XML for the selected node.
    On any error, return the original raw value.
    """
    if not raw.startswith("EMBEDDED|"):
        return raw
    parts = raw.split("|", 3)
    if len(parts) != 3:
        return raw
    _, parent_path, xpath = parts
    parent_path = parent_path.strip()
    xpath = xpath.strip()
    if not parent_path or not xpath:
        return raw

    # Normalize parent_path similar to XML Path handling
    if not parent_path.startswith("/"):
        parent_path = "/site/" + parent_path.lstrip("/")
    if not parent_path.startswith("/site/"):
        parent_path = "/site" + parent_path
    parent_file = sandbox / parent_path.lstrip("/")
    if not parent_file.exists():
        return raw

    try:
        tree = ET.parse(parent_file)
        node = tree.getroot()
        # Simple XPath-like traversal supporting segments and [index]
        segments = [s for s in xpath.strip().split("/") if s]
        for seg in segments:
            tag = seg
            index = 0
            if "[" in seg and seg.endswith("]"):
                try:
                    tag, idx_str = seg[:-1].split("[", 1)
                    index = int(idx_str)
                except Exception:
                    return raw
            children = [c for c in node if c.tag == tag]
            if not children or index < 0 or index >= len(children):
                return raw
            node = children[index]
        return ET.tostring(node, encoding="unicode")
    except Exception:
        return raw


def write_content(sandbox: Path, csv_dir: Path, dry_run: bool) -> None:
    content_path = csv_dir / "content.csv"
    if not content_path.exists():
        print("Skip content: content.csv not found")
        return
    rows = load_content_rows(content_path)
    # Load content-types for data-driven output: field order, required defaults, checkbox-group, item manager
    ct_path = csv_dir / "content-types.csv"
    required_by_type = {}
    checkbox_group_by_type = {}
    form_order_by_type = {}
    item_manager_by_type = {}
    if ct_path.exists():
        ct_rows = load_content_type_rows(ct_path)
        required_by_type = required_fields_by_type(ct_rows)
        checkbox_group_by_type = checkbox_group_field_ids_by_type(ct_rows)
        form_order_by_type = top_level_field_order_by_type(ct_rows)
        item_manager_by_type = item_manager_by_type_and_field(ct_rows)
    # Group by XML Path; then separate top-level vs repeat group rows
    by_path = defaultdict(list)
    for r in rows:
        path = _str(r, "XML Path")
        if not path:
            continue
        # Normalize path to start with /site/
        if not path.startswith("/"):
            path = "/site/" + path.lstrip("/")
        if not path.startswith("/site/"):
            path = "/site" + path
        by_path[path].append(r)

    for xml_path, path_rows in by_path.items():
        # Resolve path relative to sandbox: /site/website/index.xml -> site/website/index.xml
        rel = xml_path.lstrip("/")
        out_file = sandbox / rel
        type_name = next((_str(r, "Type Name") for r in path_rows if _str(r, "Type Name")), "")
        if not type_name:
            continue
        root = content_root_element(type_name)

        top_level = [r for r in path_rows if not _str(r, "Repeat Group")]
        repeat_rows = [r for r in path_rows if _str(r, "Repeat Group")]

        # Build element map: field name -> value (for simple fields); for node-selector/list we collect multiple
        elements = defaultdict(list)  # field -> list of values (for multi-value) or single
        for r in top_level:
            field = _str(r, "Field")
            raw_val = _str(r, "Value")
            # For node-selector fields we must preserve EMBEDDED markers so we can
            # later decide between inline components vs shared references.
            if field and field.endswith("_o") and field not in ("content-type", "display-template"):
                val = raw_val
            else:
                val = resolve_embedded_value(sandbox, raw_val)
            if not field:
                continue
            if field in ("content-type", "display-template", "merge-strategy", "no-template-required"):
                elements[field] = [val]
            else:
                elements[field].append(val)

        # Single-value fields: take first
        content_el = {}
        for k, vlist in elements.items():
            content_el[k] = vlist[0] if vlist else ""

        # Node-selector: field names ending with _o (except content-type etc.) -> item list
        node_selector_fields = set()
        for r in top_level:
            f = _str(r, "Field")
            if f.endswith("_o") and f not in ("content-type", "display-template"):
                node_selector_fields.add(f)
        for f in node_selector_fields:
            vals = [v for v in elements.get(f, []) if v]
            if vals:
                content_el[f] = ("_item_list", vals)

        # Ensure required system fields so canonical order can emit them
        if "content-type" not in content_el:
            content_el["content-type"] = type_name if type_name.startswith("/") else f"/{type_name}"
        if "display-template" not in content_el:
            content_el["display-template"] = type_name_to_display_template(type_name, type_name.startswith("/page/"))
        if "file-name" not in content_el:
            content_el["file-name"] = out_file.stem or "index"

        # Inject mandatory fields so XB/Studio save does not fail (required fields from content type)
        for fid, ftype in required_by_type.get(type_name, []):
            if fid not in content_el:
                content_el[fid] = default_value_for_field_type(ftype)

        # Repeat group data: by Repeat Group (may be dotted) and Item Index
        repeat_by_group = defaultdict(lambda: defaultdict(dict))  # repeat_key -> index -> {field: value}
        for r in repeat_rows:
            rg = _str(r, "Repeat Group")
            idx = _str(r, "Item Index")
            try:
                idx_int = int(idx) if idx else 0
            except ValueError:
                idx_int = 0
            field = _str(r, "Field")
            raw_val = _str(r, "Value")
            val = resolve_embedded_value(sandbox, raw_val)
            repeat_by_group[rg][idx_int][field] = val

        # Build XML body in canonical order (form order from content-types.csv when available)
        form_order = form_order_by_type.get(type_name, [])
        required_field_ids = {fid for fid, _ in required_by_type.get(type_name, [])}
        ordered = ordered_content_items(root, type_name, content_el, out_file, form_order=form_order, required_field_ids=required_field_ids)
        # Top-level repeat groups: emit only in "Add repeat groups" below to avoid duplicate elements
        repeat_top_level_keys = {k for k in repeat_by_group if "." not in k}
        lines = [f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>", f"<{root}>"]
        for field_name, value in ordered:
            if field_name in repeat_top_level_keys:
                continue
            if isinstance(value, tuple) and value[0] == "_item_list":
                # Node-selector / repeat / checkbox-group list; emit even when empty so required fields exist for XB save
                refs = value[1]
                # Empty collections: self-closing to match form engine output (XB expects this)
                if not refs:
                    lines.append(f'  <{field_name} item-list="true"/>')
                    continue
                lines.append(f'  <{field_name} item-list="true">')
                for ref in refs:
                    if not ref:
                        continue
                    # Embedded selector item: EMBEDDED|parent-path|xpath
                    if ref.startswith("EMBEDDED|"):
                        parts = ref.split("|", 3)
                        if len(parts) == 3:
                            _, parent_path, xpath = parts
                            parent_path = parent_path.strip()
                            xpath = xpath.strip() or "/component"
                            # Normalize parent_path like XML Path
                            if not parent_path.startswith("/"):
                                parent_path = "/site/" + parent_path.lstrip("/")
                            if not parent_path.startswith("/site/"):
                                parent_path = "/site" + parent_path
                            parent_file = sandbox / parent_path.lstrip("/")
                            try:
                                tree = ET.parse(parent_file)
                                comp_root = tree.getroot()
                                # Best-effort: if xpath points at the root component, use it;
                                # otherwise fall back to root.
                                comp_node = comp_root
                                segs = [s for s in xpath.strip().split("/") if s]
                                for seg in segs:
                                    tag = seg
                                    idx = 0
                                    if "[" in seg and seg.endswith("]"):
                                        try:
                                            tag, idx_str = seg[:-1].split("[", 1)
                                            idx = int(idx_str)
                                        except Exception:
                                            comp_node = comp_root
                                            break
                                    children = [c for c in comp_node if c.tag == tag]
                                    if not children or idx < 0 or idx >= len(children):
                                        comp_node = comp_root
                                        break
                                    comp_node = children[idx]
                                # Embedded: item/@datasource from content-type Item Manager when present
                                file_stem = Path(parent_path).stem.replace(".xml", "")
                                obj_id = comp_node.findtext("objectId") or file_stem
                                label = comp_node.findtext("internal-name") or file_stem
                                ds = item_manager_by_type.get(type_name, {}).get(field_name)
                                item_open = f'    <item datasource="{xml_escape(ds)}" inline="true">' if ds else '    <item inline="true">'
                                lines.append(item_open)
                                # Key should match the component/@id (file-stem), not the objectId
                                lines.append(f"      <key>{xml_escape(file_stem)}</key>")
                                lines.append(f"      <value>{xml_escape(label)}</value>")
                                lines.append("      <disableFlattening>false</disableFlattening>")
                                # Ensure embedded component has an id attribute mirroring file-name (file-stem)
                                comp_node.set("id", file_stem)
                                comp_xml = ET.tostring(comp_node, encoding="unicode")
                                lines.append(comp_xml.strip())
                                lines.append("    </item>")
                            except Exception:
                                # Fall back to a simple shared reference if anything goes wrong
                                display_val = Path(parent_path).stem.replace(".xml", "") if "/" in parent_path else parent_path
                                lines.append("    <item>")
                                lines.append(f"      <key>{xml_escape(parent_path)}</key>")
                                lines.append(f"      <value>{xml_escape(display_val)}</value>")
                                lines.append(f"      <include>{xml_escape(parent_path)}</include>")
                                lines.append("      <disableFlattening>false</disableFlattening>")
                                lines.append("    </item>")
                        else:
                            # Malformed EMBEDDED marker, skip
                            continue
                    else:
                        # Shared selector item; datasource from content-type Item Manager when present
                        p = ref
                        display_val = Path(p).stem.replace(".xml", "") if "/" in p else p
                        ds = item_manager_by_type.get(type_name, {}).get(field_name)
                        item_open = f'    <item datasource="{xml_escape(ds)}">' if ds else "    <item>"
                        lines.append(item_open)
                        lines.append(f"      <key>{xml_escape(p)}</key>")
                        lines.append(f"      <value>{xml_escape(display_val)}</value>")
                        lines.append(f"      <include>{xml_escape(p)}</include>")
                        lines.append("      <disableFlattening>false</disableFlattening>")
                        lines.append("    </item>")
                lines.append(f'  </{field_name}>')
            elif field_name == "no-template-required":
                lines.append("  <no-template-required/>")
            elif field_name in ("content-type", "display-template", "merge-strategy", "folder-name", "orderDefault_f", "disabled", "createdDate", "lastModifiedDate"):
                if value is None:
                    value = ""
                s = str(value).strip()
                if not s:
                    lines.append(f"  <{field_name}/>")
                else:
                    lines.append(f"  <{field_name}>{escape_value_for_xml(s)}</{field_name}>")
            else:
                if value is None:
                    value = ""
                s = str(value).strip()
                if not s:
                    lines.append(f"  <{field_name}/>")
                else:
                    lines.append(f"  <{field_name}>{escape_value_for_xml(s)}</{field_name}>")

        # Add repeat groups (top-level only) in form order when available; checkbox-group omits item-list="true"
        cb_group_ids = checkbox_group_by_type.get(type_name, set())
        repeat_keys_ordered = (
            [fid for fid, ftype in form_order if ftype == "repeat" and fid in repeat_by_group and "." not in fid]
            if form_order
            else [k for k in repeat_by_group if "." not in k]
        )
        for repeat_key in repeat_keys_ordered:
            index_map = repeat_by_group[repeat_key]
            sorted_indexes = sorted(index_map.keys())
            use_item_list = repeat_key not in cb_group_ids
            tag_open = f'  <{repeat_key} item-list="true">' if use_item_list else f'  <{repeat_key}>'
            lines.append(tag_open)
            for idx in sorted_indexes:
                item_fields = index_map[idx]
                lines.append("    <item>")
                for fn, v in item_fields.items():
                    # Entity-escape (not CDATA) to match form engine output for repeat-group item fields
                    lines.append(f"      <{fn}>{xml_escape(str(v or ''))}</{fn}>")
                lines.append("    </item>")
            lines.append(f"  </{repeat_key}>")

        # Emit optional node-selectors last to match form engine output (header_o, left_rail_o, etc.)
        for fid, ftype in (form_order or []):
            if ftype != "node-selector" or fid in required_field_ids:
                continue
            val = content_el.get(fid)
            if isinstance(val, tuple) and val[0] == "_item_list":
                refs = val[1]
                if not refs:
                    lines.append(f'  <{fid} item-list="true"/>')
                else:
                    lines.append(f'  <{fid} item-list="true">')
                    for ref in refs:
                        if not ref:
                            continue
                        p = ref
                        display_val = Path(p).stem.replace(".xml", "") if "/" in p else p
                        ds = item_manager_by_type.get(type_name, {}).get(fid)
                        item_open = f'    <item datasource="{xml_escape(ds)}">' if ds else "    <item>"
                        lines.append(item_open)
                        lines.append(f"      <key>{xml_escape(p)}</key>")
                        lines.append(f"      <value>{xml_escape(display_val)}</value>")
                        lines.append(f"      <include>{xml_escape(p)}</include>")
                        lines.append("      <disableFlattening>false</disableFlattening>")
                        lines.append("    </item>")
                    lines.append(f'  </{fid}>')
            else:
                lines.append(f'  <{fid} item-list="true"/>')

        body = "\n".join(lines) + "\n</" + root + ">\n"
        # Use tab indentation to match form engine output
        body = body.replace("      ", "\t\t\t").replace("    ", "\t\t").replace("  ", "\t")
        if dry_run:
            print(f"[dry-run] Would write content: {out_file} ({len(path_rows)} rows)")
            continue
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(body, encoding="utf-8")
        print(f"Wrote content: {out_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    script_dir = Path(__file__).parent.resolve()
    ap = argparse.ArgumentParser(description="Import CrafterCMS content types and content from CSV")
    ap.add_argument("--sandbox", type=Path, default=None, help="Sandbox root (default: parent of migration-kit)")
    ap.add_argument("--content-import-dir", type=Path, default=None, help="Directory with content-types.csv, datasources.csv, content.csv (default: content-import/ when in sub-scripts)")
    ap.add_argument("--dry-run", action="store_true", help="Do not write files")
    ap.add_argument("--content-only", action="store_true", help="Only import content, skip content types")
    ap.add_argument("--types-only", action="store_true", help="Only import content types, skip content")
    args = ap.parse_args()

    sandbox = args.sandbox or find_sandbox_root(script_dir)
    migration_kit = script_dir.parent if script_dir.name == "sub-scripts" else None
    csv_dir = args.content_import_dir if args.content_import_dir is not None else default_csv_dir(script_dir, migration_kit)

    if not (sandbox / "config").exists() and not args.dry_run:
        print("Warning: sandbox may be wrong (no config/). Use --sandbox or run from sandbox root.", file=sys.stderr)

    datasources = {}
    ds_path = csv_dir / "datasources.csv"
    if ds_path.exists():
        datasources = load_datasources(ds_path)
        print(f"Loaded {len(datasources)} datasources from datasources.csv")

    if not args.content_only:
        print("Importing content types...")
        write_content_types(sandbox, csv_dir, datasources, args.dry_run)
    if not args.types_only:
        print("Importing content...")
        write_content(sandbox, csv_dir, args.dry_run)
    print("Done.")


if __name__ == "__main__":
    main()
