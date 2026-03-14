#!/usr/bin/env python3
"""
Add PathNavigatorTree widgets in config/studio/ui.xml
for any /site/* roots that are not /site/website or /site/components.

Run from the sandbox root, e.g.:

  cd /home/russdanner/crafter-installs/4-4-xE/crafter-authoring/data/repos/sites/migration/sandbox
  python3 migration-kit/content-import/add_extra_site_navigators.py
"""

from pathlib import Path
import xml.etree.ElementTree as ET


def find_sandbox_root(script_path: Path) -> Path:
    """
    Infer sandbox root from this script location.
    Expected layout:
      sandbox/
        config/
        site/
        migration-kit/content-import/add_extra_site_navigators.py
    """
    # .../sandbox/migration-kit/content-import/add_extra_site_navigators.py
    # go up two levels to reach sandbox
    return script_path.parent.parent.parent


def title_from_folder(name: str) -> str:
    """Convert a folder name to a nice id (taxonomy -> Taxonomy)."""
    return (
        name.replace("_", " ")
        .replace("-", " ")
        .title()
        .replace(" ", "")
    )


def main() -> None:
    script_path = Path(__file__).resolve()
    sandbox = find_sandbox_root(script_path)

    ui_xml_path = sandbox / "config" / "studio" / "ui.xml"
    site_root = sandbox / "site"

    if not ui_xml_path.exists():
        raise SystemExit(f"ui.xml not found at {ui_xml_path}")
    if not site_root.exists():
        raise SystemExit(f"site root not found at {site_root}")

    tree = ET.parse(ui_xml_path)
    root = tree.getroot()

    # Locate ToolsPanel and its <widgets> container
    tools_panel = None
    for w in root.findall(".//widget"):
        if w.get("id") == "craftercms.components.ToolsPanel":
            tools_panel = w
            break

    if tools_panel is None:
        raise SystemExit("Could not find craftercms.components.ToolsPanel in ui.xml")

    config_el = tools_panel.find("configuration")
    if config_el is None:
        raise SystemExit("ToolsPanel has no <configuration> in ui.xml")

    widgets_el = config_el.find("widgets")
    if widgets_el is None:
        raise SystemExit("ToolsPanel configuration has no <widgets> element")

    # Collect existing rootPath values for PathNavigatorTree widgets
    existing_roots = set()
    for w in widgets_el.findall("widget"):
        if w.get("id") != "craftercms.components.PathNavigatorTree":
            continue
        cfg = w.find("configuration")
        if cfg is None:
            continue
        rp = cfg.findtext("rootPath")
        if rp:
            existing_roots.add(rp.strip())

    # Folders under /site that we don't auto-add (already covered)
    skip_folders = {"website", "components"}

    # Default icon for new navigators
    default_icon = "@mui/icons-material/FolderOpenOutlined"

    new_widgets_added = 0

    for child in sorted(site_root.iterdir()):
        if not child.is_dir():
            continue
        folder_name = child.name
        if folder_name in skip_folders:
            continue

        root_path = f"/site/{folder_name}"
        if root_path in existing_roots:
            continue

        # Build new PathNavigatorTree widget
        label = folder_name.replace("_", " ").replace("-", " ").title()
        nav_id = title_from_folder(folder_name)

        widget_el = ET.Element("widget", id="craftercms.components.PathNavigatorTree")
        cfg_el = ET.SubElement(widget_el, "configuration")

        id_el = ET.SubElement(cfg_el, "id")
        id_el.text = nav_id

        label_el = ET.SubElement(cfg_el, "label")
        label_el.text = label

        icon_el = ET.SubElement(cfg_el, "icon")
        icon_el.set("id", default_icon)

        rp_el = ET.SubElement(cfg_el, "rootPath")
        rp_el.text = root_path

        locale_el = ET.SubElement(cfg_el, "locale")
        locale_el.text = "en"

        widgets_el.append(widget_el)
        new_widgets_added += 1
        print(f"Added navigator for {root_path} with id={nav_id}")

    if new_widgets_added:
        tree.write(ui_xml_path, encoding="utf-8", xml_declaration=True)
        print(f"Updated {ui_xml_path} with {new_widgets_added} new navigator widget(s).")
    else:
        print("No new /site/* roots found that required navigator widgets.")


if __name__ == "__main__":
    main()

