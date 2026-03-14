# CSV Migration Format for CrafterCMS

This project supports importing content types, **datasources**, and content into CrafterCMS from CSV files.

**Where the importer reads from:** The scripts use the CSV files in **`migration-kit/content-import/`** (`content-types.csv`, `datasources.csv`, `content.csv`). That is the actual data location; keep your live data there.

**Reference copy:** A copy of the same CSV data is kept in **`migration-kit/content-import/examples/example-import-data/`** for reference only. Anyone using the kit can look there to see example structure and content; the importer does not read from that folder. The example files are derived from the **hello** sample site, which is also under:

- `migration-kit/content-import/examples/source_site`

---

## Full import (recommended)

**`import.py`** (in `migration-kit/`, outside `sub-scripts/`) runs the CSV import, optional template generation, and then the content-type documentation generator.

From the **Crafter sandbox root** (the directory that contains `migration-kit/` and `config/`):

```bash
# Full migration: content types + content + generated docs (into sandbox/docs)
python3 migration-kit/import.py

# Dry run (no files written for import; docs still generated)
python3 migration-kit/import.py --dry-run

# Write docs into migration-kit/docs instead of sandbox/docs
python3 migration-kit/import.py --docs-dir migration-kit/docs

# Skip doc generation
python3 migration-kit/import.py --skip-docs
```

From another directory:

```bash
python3 /path/to/migration-kit/import.py --sandbox /path/to/sandbox
```

---

## Import script (direct)

**`import_from_csv.py`** (in `migration-kit/sub-scripts/`) reads `content-types.csv`, `datasources.csv`, and `content.csv` from **`migration-kit/content-import/`** and writes Crafter content type definitions and content XML under the sandbox.

### Usage

From the **Crafter sandbox root**:

```bash
# Preview only (no files written)
python3 migration-kit/sub-scripts/import_from_csv.py --dry-run

# Import content types and content (CSV dir defaults to migration-kit/content-import/)
python3 migration-kit/sub-scripts/import_from_csv.py

# Only content types (no content)
python3 migration-kit/sub-scripts/import_from_csv.py --types-only

# Only content (no content types)
python3 migration-kit/sub-scripts/import_from_csv.py --content-only
```

From another directory, specify sandbox and optionally the directory containing the CSVs:

```bash
python3 /path/to/migration-kit/sub-scripts/import_from_csv.py --sandbox /path/to/sandbox
python3 /path/to/migration-kit/sub-scripts/import_from_csv.py --sandbox /path/to/sandbox --content-import-dir /path/to/migration-kit/content-import
```

### Requirements

- Python 3.9+ (uses standard library only: `csv`, `pathlib`, `uuid`, `argparse`, `xml.sax.saxutils`).

### What it does

1. **Content types:** For each Type Name in `content-types.csv`, creates `config/studio/content-types/{page|component|taxonomy}/{slug}/config.xml` and `form-definition.xml`, including sections, fields, repeat groups with nested fields, checkbox-group fields (for taxonomy-backed categories/segments), and a `<datasources>` block from `datasources.csv`. The `/taxonomy` type is written under `config/studio/content-types/taxonomy/` and is used for taxonomy files under `/site/taxonomy/` (e.g. `categories.xml`, `segments.xml`).
2. **Content:** For each XML Path in `content.csv`, builds a content XML file under `site/` with root `<page>` or `<component>`. Field order and structure are driven by `content-types.csv` so that **generated XML matches Crafter Studio form-save output** (Experience Builder compatible):
   - **Canonical order:** Lead fields (content-type, display-template, objectId, dates, file-name), then form fields in CSV order, then trail (folder-name, disabled, createdDate, lastModifiedDate), then repeat groups, then **optional node-selectors last** (e.g. `header_o`, `left_rail_o`).
   - **Repeat groups:** Checkbox-group fields omit `item-list="true"`; other repeat groups use `item-list="true"`. RTE/content inside repeat items is **entity-escaped** (e.g. `&lt;p&gt;`), not CDATA, to match form output. Empty collections and empty scalars use self-closing tags; indentation uses tabs.
   - Item Manager (datasource) on node-selector `<item>` tags is taken from the content type’s Item Manager column. Generates `objectId`, `createdDate_dt`, and `lastModifiedDate_dt` when missing.

### Notes

- The script **overwrites** existing content type directories and content files at the target paths. Back up or use version control before running.
- Repeat group data with a **dotted** Repeat Group (e.g. `socialMediaWidget_o.accounts_o` for embedded components) is not written by the script; only top-level repeat groups on the content item are emitted. Embedded repeat data remains in CSV for reference or a future importer pass.
- Display templates are inferred from the content type name (e.g. `/page/home` → `/templates/web/pages/home.ftl`). Ensure those FTL templates exist in the project or add them separately.

---

## Generic template generator

**`generate_generic_template.py`** (in `migration-kit/sub-scripts/`) creates a headless FTL template for any content type from its `form-definition.xml`. The output matches the style of `templates/web/pages/examples/home-example.ftl` (white section headers, gradient section bodies, drop shadow, section/field/field-type classes).

### Usage

From the **sandbox root**:

```bash
# By path to form-definition.xml
python3 migration-kit/sub-scripts/generate_generic_template.py config/studio/content-types/page/article/form-definition.xml -o templates/web/pages/article.ftl

# By content type path (resolved under config/studio/content-types/)
python3 migration-kit/sub-scripts/generate_generic_template.py page/entry -o templates/web/pages/entry.ftl

# Print to stdout
python3 migration-kit/sub-scripts/generate_generic_template.py component/feature
```

With `--sandbox /path/to/sandbox` when not run from the sandbox root.

### Requirements

- Python 3.9+ (stdlib only: `xml.etree`, `argparse`, `pathlib`).

---

## Content type documentation generator

**`generate_content_type_docs.py`** (in `migration-kit/sub-scripts/`) scans `config/studio/content-types/` and generates Markdown documentation in `docs/` (or `-o dir`): README (index), pages.md, components.md, global.md (level-descriptor), and taxonomy.md. Each content type is documented with its path, label, display template, and per-section field tables (Name, Type, Description, Required, Constraints, Notes). **`import.py`** runs this automatically after the CSV import unless `--skip-docs` is used.

### Usage

From the **sandbox root**:

```bash
# Generate docs into sandbox/docs/
python3 migration-kit/sub-scripts/generate_content_type_docs.py

# Custom output directory (e.g. migration-kit docs folder)
python3 migration-kit/sub-scripts/generate_content_type_docs.py -o migration-kit/docs
```

With `--sandbox /path/to/sandbox` when not run from the sandbox root.

### Requirements

- Python 3.9+ (stdlib only: `xml.etree`, `argparse`, `pathlib`).

---

## Check templates

**`check-templates.py`** (in `migration-kit/sub-scripts/`) checks preview URLs for FreeMarker template errors. **Paths are data-driven**: it discovers all page URLs by listing every `index.xml` under `sandbox/site/website` (no hardcoded path list). Requires a preview token in `migration-kit/.preview-token`.

### Usage

From the **sandbox root** (or with `--sandbox`):

```bash
# Discover all pages under site/website and check each URL
python3 migration-kit/sub-scripts/check-templates.py

# Override sandbox and site name
python3 migration-kit/sub-scripts/check-templates.py --sandbox /path/to/sandbox --site my-site
```

- **`--sandbox`** – Sandbox root (default: parent of `migration-kit`).
- **`--site`** – Crafter site name for `crafterSite=` (default: sandbox directory name).

Exits with status 1 if any checked URL returns a FreeMarker template error or if no pages are found under `site/website`.

---

## Import assets

**`import_assets.py`** (in `migration-kit/sub-scripts/`) imports images, videos, and documents from **`content-import/assets-to-import/`** into the project’s **`static-assets`** folder.

- **Copy mode (`--no-blobs`):** Recursively copies all files into `static-assets`, preserving directory structure.
- **Blob mode (`--blobs`):** Does not copy binaries. Creates a `.blob` XML file at each asset path (e.g. `photo.jpg` → `static-assets/images/photo.jpg.blob`) with `storeId` (e.g. `s3-store`) and a content hash. The actual file is assumed to be in blob/S3 storage.

If you omit both `--blobs` and `--no-blobs`, the script prompts: *Do you plan to use BLOBS (blob storage) for these assets? [y/N]*

### Usage

From the **sandbox root**:

```bash
# Prompt for mode, then run
python3 migration-kit/sub-scripts/import_assets.py

# Copy files into static-assets
python3 migration-kit/sub-scripts/import_assets.py --no-blobs

# Create .blob XMLs only (for S3/blob store)
python3 migration-kit/sub-scripts/import_assets.py --blobs

# Custom paths
python3 migration-kit/sub-scripts/import_assets.py --sandbox /path/to/sandbox --assets-dir /path/to/assets-to-import --blobs --dry-run
```

- **`--sandbox`** – Sandbox root (default: parent of `migration-kit`).
- **`--assets-dir`** – Source folder (default: `migration-kit/content-import/assets-to-import`).
- **`--dry-run`** – Report what would be done without writing files.

---

## Cleanup import data

**`cleanup_import_data.py`** (in `migration-kit/sub-scripts/`) is for **manual use only**. It resets import data so you can run a fresh import:

1. **Empties** `content-import/assets-to-import/` (removes all contents; leaves the folder).
2. **Strips data rows** from `content-types.csv`, `content.csv`, and `datasources.csv` in `content-import/`, leaving only the header row in each file.

The script asks for confirmation unless you pass `--yes` or `-y`.

### Usage

From the **sandbox root**:

```bash
# Interactive (prompt before running)
python3 migration-kit/sub-scripts/cleanup_import_data.py

# Non-interactive
python3 migration-kit/sub-scripts/cleanup_import_data.py --yes
```

---

## Content Types CSV (`content-types.csv`)

Defines content type structure (types and their fields). Use this to create or update content type definitions before importing content.

### Columns

| Column        | Description |
|---------------|-------------|
| **Type Name** | Crafter content type path (e.g. `/page/home`, `/component/header`). |
| **Type Label** | Human-readable label for the type (e.g. Home, Header). |
| **Section**    | Form section title that groups the field (e.g. Page Properties, Hero Section). |
| **Field Name** | Field ID as used in XML and form (e.g. `title_t`, `hero_image_s`). |
| **Field Label**| Display label for the field (e.g. Title, Hero Image). |
| **Field Type** | Crafter field type: `input`, `rte`, `checkbox`, `image-picker`, `node-selector`, `file-name`, `auto-filename`, `dropdown`, `repeat`, `checkbox-group`, etc. |
| **Required**   | `true` or `false`. |
| **Description**| Optional field description. |
| **Help**       | Optional help text. |
| **Item Manager** | Datasource ID for `node-selector` fields (references a row in `datasources.csv`). |
| **Image Manager** | Datasource ID(s) for `image-picker` and `rte` image fields. Use pipe to separate multiple IDs (e.g. `existingImages|uploadImages`). References `datasources.csv`. |
| **Allowed Content Types** | For `node-selector`: allowed content type path(s), e.g. `/component/header`. Comma-separated if multiple. |
| **Min Size**  | For `node-selector`: minimum number of items (integer). |
| **Max Size**  | For `node-selector`: maximum number of items (integer). |
| **Dropdown Datasource** | For `dropdown` and `checkbox-group` fields: datasource ID (e.g. taxonomy or item datasource). For categories/segments use `categories` or `segments` (simpleTaxonomy). References `datasources.csv`. |
| **Parent Field** | For repeat group child fields: the Field Name of the repeat group (e.g. `accounts_o`). Empty for top-level fields. |
| **Min Occurs** | For `repeat` fields: minimum occurrences (integer or `*`). |
| **Max Occurs** | For `repeat` fields: maximum occurrences (integer or `*`). |

### Repeat groups

- **Repeat field:** One row with Field Type = `repeat` and Field Name = the repeat group id (e.g. `accounts_o`). Set Min Occurs and Max Occurs (e.g. `0`, `*`). **Leave Parent Field empty** (no value in that column).
- **Nested fields:** Rows with **Parent Field** = that repeat group id define child fields (e.g. `network_s`, `url_s`). Same Section as the repeat; child fields can use Dropdown Datasource, Image Manager, etc.
- The importer should emit `<field type="repeat">` with `<minOccurs>`, `<maxOccurs>`, and nested `<fields>` from rows where Parent Field matches.
- **Column alignment:** Parent Field is column 16. Ensure each row has exactly 18 columns so Parent Field and Min/Max Occurs are read correctly. For repeat rows, use enough empty commas so Min Occurs and Max Occurs land in columns 17–18; for child rows, put the parent field id in column 16 (e.g. nine empty commas after `false` for a typical child row so `categories_o` or `sections_o` is in the Parent Field column).

### Taxonomy and checkbox-group

- **Taxonomy content type** (`/taxonomy`): Define a type with Section "Taxonomy Properties", fields `file-name`, `internal-name`, and a repeat group `items` with nested `key` and `value` (for taxonomy option key/label pairs). The importer writes it under `config/studio/content-types/taxonomy/` and restricts it to paths under `/site/taxonomy/`.
- **Taxonomy content**: In `content.csv`, add rows for Type Name `/taxonomy`, XML Path `/site/taxonomy/categories.xml` and `/site/taxonomy/segments.xml`, with repeat group `items` and Item Index 0,1,… and Field `key`/`value` for each option (e.g. style/Style, technology/Technology).
- **Categories/segments as checkbox-group**: For article (or other) types, use Field Type `checkbox-group`, Field Name `categories_o` or `segments_o`, and **Dropdown Datasource** `categories` or `segments`. In `datasources.csv` define `categories` and `segments` as Type `simpleTaxonomy` with **Component Path** `/site/taxonomy/categories.xml` and `/site/taxonomy/segments.xml`. Column alignment for Dropdown Datasource and Min Occurs must be correct (see Content Types CSV columns).

### Usage

- One row per field. The same Type Name + Section can appear on multiple rows (one per field).
- An importer should create `config.xml` and `form-definition.xml` under `/config/studio/content-types/` from this CSV, and inject a `<datasources>` section by resolving Item Manager, Image Manager, and Dropdown Datasource IDs against `datasources.csv`.

---

## Datasources CSV (`datasources.csv`)

Defines datasources used by content type fields (image pickers, node selectors, dropdowns). Import or resolve this when building form definitions so that `itemManager`, `imageManager`, and dropdown `datasource` properties point to valid datasource IDs.

### Columns

| Column        | Description |
|---------------|-------------|
| **Datasource ID** | Unique ID referenced from content-types (e.g. `existingImages`, `components-header`). |
| **Type**      | Crafter datasource type: `img-repository-upload`, `img-desktop-upload`, `shared-content`, `components`, `simpleTaxonomy`. |
| **Title**     | Display title (e.g. Existing Images, Components Header). |
| **Interface** | `image` or `item`. |
| **Repo Path** | For image and shared-content: repository path (e.g. `/static-assets/images/`, `/site/components/headers/`). |
| **Browse Path** | For shared-content: optional browse path. |
| **Base Repository Path** | For `components` type: e.g. `/site/components`. |
| **Base Browse Path** | For `components` type: e.g. `/site/components`. |
| **Content Types** | For `components` type: allowed content type (e.g. `/component/feature`). |
| **Allow Shared** | For `components`: `true` or `false`. |
| **Allow Embedded** | For `components`: `true` or `false`. |
| **Enable Browse** | For `components`: `true` or `false`. |
| **Enable Search** | For `components`: `true` or `false`. |
| **Enable Create New** | For shared-content: `true` or `false`. |
| **Enable Browse Existing** | For shared-content: `true` or `false`. |
| **Enable Search Existing** | For shared-content: `true` or `false`. |
| **Component Path** | For `simpleTaxonomy`: path to taxonomy XML (e.g. `/site/taxonomy/feature-icons.xml`). |
| **Tags**       | For `components`: optional tags. |
| **Use Search** | For `img-repository-upload`: `true` or `false`. |

### Usage

- One row per datasource. Types and required columns:
  - **img-repository-upload** / **img-desktop-upload**: Repo Path, Interface=image.
  - **shared-content**: Repo Path, Interface=item; optional Browse Path, Enable Create New, Enable Browse Existing, Enable Search Existing.
  - **components**: Base Repository Path, Base Browse Path, Content Types, Interface=item; optional Allow Shared, Allow Embedded, Enable Browse, Enable Search.
  - **simpleTaxonomy**: Component Path, Interface=item.
- An importer should emit a `<datasources>` block in each form-definition.xml and ensure every Item Manager, Image Manager, and Dropdown Datasource in `content-types.csv` refers to a Datasource ID in this file.

---

## Content CSV (`content.csv`)

Defines content item field values. Use this to create or update content items (pages and components) in the site.

### Columns

| Column     | Description |
|------------|-------------|
| **Type Name** | Content type of the item (e.g. `/page/home`, `/component/feature`). Must match a type from the content-types CSV or existing studio config. |
| **XML Path**  | Repository path to the content item XML (e.g. `/site/website/index.xml`, `/site/components/headers/header.xml`). For folder-based items this is the path to `index.xml` inside the folder. |
| **Repeat Group** | Optional. When this row is a value for a **repeat group** item: the repeat field id, or a dotted path when the repeat is inside a node-selector (e.g. `accounts_o` for top-level repeat, or `socialMediaWidget_o.accounts_o` for the repeat `accounts_o` inside the component selected in `socialMediaWidget_o`). |
| **Item Index** | Optional, 0-based. When Repeat Group is set, the index of the occurrence (0 = first item, 1 = second, etc.). |
| **Field**     | Field name (e.g. `title_t`, `internal-name`, `hero_image_s`). For repeat group rows, the **nested** field name (e.g. `network_s`, `url_s`). |
| **Value**     | Field value. For HTML/RTE use the actual markup; for node-selector references use the target item path (e.g. `/site/components/headers/header.xml`). To embed content from another XML, use `EMBEDDED\|parent-xml-path\|xpath` (see below). **If the value contains commas**, wrap the entire value in double quotes so the CSV parser does not split it (e.g. `"<p>First paragraph, second sentence.</p>"`). |
| **Datasource ID** | Optional. When the field uses a datasource (image-picker, node-selector, dropdown), the ID of the datasource this value is associated with. Used for validation or documentation; does not change the stored value. |

### Repeat group content

- Rows with **Repeat Group** and **Item Index** set define values for one occurrence of a repeat group. **Field** is the nested field name; **Value** is the value for that occurrence.
- Multiple rows with the same Repeat Group and Item Index define different nested fields of the same occurrence. Multiple rows with the same Repeat Group and different Item Index define multiple occurrences (items) of the repeat group.
- **Nested repeat (inside node-selector):** Use a dotted Repeat Group (e.g. `socialMediaWidget_o.accounts_o`) when the repeat lives inside an embedded/selected component. The importer should resolve the selector first, then write the repeat data into that component’s repeat field.
- Example: header with embedded social media widget and three accounts: use `Repeat Group=socialMediaWidget_o.accounts_o`, `Item Index=0,1,2`, with `Field=network_s`, `url_s`, etc., and corresponding values.

### Embedded content values

Sometimes a field needs to contain **embedded XML** copied from another content item (rather than just a reference path). To support this, `content.csv` can use a special `Value` encoding:

- **Format**:  
  `EMBEDDED|<parent-xml-path>|<xpath>`

  - `<parent-xml-path>`: Repository path to the source XML (e.g. `/site/components/headers/header.xml`).
  - `<xpath>`: Simple element path from the root of that XML to the node to embed (e.g. `/component/items` or `/component/items/item[0]`). The importer supports tag names with optional `[index]` (0-based) at each segment.

- **Importer behavior**:
  - When `Value` starts with `EMBEDDED|`, the importer:
    1. Normalizes `parent-xml-path` to start with `/site/` if needed.
    2. Loads the XML file under the sandbox at that path.
    3. Traverses the root using the provided XPath-like path and selects the target node.
    4. Serializes that node (including its children) to XML and stores the resulting XML string as the field value.
  - For **top-level** fields, the importer wraps embedded/HTML content in CDATA when it contains `<`/`>`. For **repeat-group item** fields (e.g. `section_html` inside `sections_o`), the importer uses **entity escaping** (e.g. `&lt;p&gt;`) to match Studio form-save output.
  - If the file or path cannot be resolved, the importer leaves the original `EMBEDDED|...` string as the value.

- **Examples**:
  - Embed a taxonomy `<items>` block into another component field:
    - `Value = EMBEDDED|/site/taxonomy/categories.xml|/component/items`
  - Embed the first `<item>` under `<items>`:
    - `Value = EMBEDDED|/site/taxonomy/categories.xml|/component/items/item[0]`

### Usage

- One row per field value per content item. Multiple rows with the same Type Name + XML Path represent different fields of the same item. Leave Repeat Group and Item Index empty for top-level fields.
- **Node-selector / multi-value:** For a single selected item, use one row with the referenced path as Value. For multiple items (e.g. `sections_o`, `features_o`), use one row per reference with the same Field; the importer should treat multiple rows for the same Field as an ordered list (or use a convention such as pipe-separated values in one row if preferred).
- **Datasource ID:** Optional. When present, the importer can validate that the Value is valid for that datasource (e.g. image path under repo path, or reference path allowed by content type).
- **System fields:** Include `content-type`, `display-template`, and `file-name` so the importer can create valid Crafter XML. `objectId`, `createdDate_dt`, and `lastModifiedDate_dt` may be generated by the importer if omitted.
- **Paths:** XML Path is the full store path (e.g. `/site/website/articles/2020/7/new-acme-phone-released-today/index.xml`). The importer is responsible for creating the folder structure and file when the path does not exist.

---

## Example Files

- **content-types.csv** – Content types and fields from the hello project, including datasource columns and **repeat group** support (Parent Field, Min Occurs, Max Occurs). Example: `accounts_o` repeat with nested fields `network_s`, `title_s`, `url_s`, `icon_s`.
- **datasources.csv** – Datasource definitions from the hello project: image (existingImages, uploadImages, existing_images, upload_image), shared-content (components-header, components-left-rail, components, scripts), components (featuresComponents, socialMedia), simpleTaxonomy (feature_icons, networks).
- **content.csv** – Sample content from hello with optional Datasource ID and **repeat group** rows (Repeat Group, Item Index). Includes: article **sections_o** (repeat with section_html), **categories_o** / **segments_o** (repeat with key, value_smv), header embedded social media accounts, left-rails with **widgets_o**, contact-widget, articles-widget (latest and related), category-landing pages (technology, health, entertainment, style), and search-results. Quote any Value that contains commas (e.g. HTML with commas).

---

## Implementing an Importer

1. **Datasources:** Read `datasources.csv` and build a map of Datasource ID → datasource definition. Resolve Type, Interface, and the relevant properties (Repo Path, Content Types, Component Path, etc.) to emit `<datasource>` elements.
2. **Content types:** Read `content-types.csv`, group by Type Name, then by Section. For each type, create the directory under `/config/studio/content-types/`, then emit `config.xml` and `form-definition.xml`. For each field, set `itemManager`, `imageManager`, `contentTypes`, `minSize`/`maxSize`, and dropdown `datasource` as above. For rows with **Parent Field** set, emit them as nested `<field>` elements inside the parent `<field type="repeat">` (use Min Occurs / Max Occurs on the repeat row for `minOccurs`/`maxOccurs`). Inject the `<datasources>` section from `datasources.csv`.
3. **Content:** Read `content.csv`, group by XML Path. For each path, build the content XML in **canonical order** (lead, form fields from content-types order, trail, repeat groups, then optional node-selectors last) so output matches form-save. For **checkbox-group** repeat fields, omit `item-list="true"` on the wrapper; for other repeat groups use `item-list="true"`. For repeat **item** values that are HTML/RTE, use entity escaping (not CDATA) to match form. Use self-closing tags for empty collections and empty scalars; use tabs for indentation. For rows with **Repeat Group** and **Item Index** set, group by (Repeat Group, Item Index) and emit items. If Repeat Group contains a dot (e.g. `selector_o.repeat_o`), resolve the selector first, then write the repeat items into that component’s repeat field. For node-selector fields, set `<item datasource="...">` from the content type’s Item Manager. Generate `objectId`, `createdDate_dt`, and `lastModifiedDate_dt` if not provided.
4. **Order:** Import datasources (or inlined in content types) first, then content types, then content, so that content type definitions and datasources exist when content is validated or edited in Studio.

---

## Notes

- CSV values that contain commas, newlines, or double quotes should be quoted and internal quotes escaped (standard CSV).
- **Image Manager** in content-types uses pipe `|` to separate multiple datasource IDs (e.g. `existingImages|uploadImages`) to avoid comma inside a single cell.
- Rich text (RTE) values in the content CSV may contain HTML; preserve it exactly. Top-level `*_html` fields are typically wrapped in CDATA in the generated XML; **repeat-group item** RTE fields (e.g. `section_html` inside `sections_o`) are entity-escaped to match Studio form-save output.
- **Repeat groups:** Content-types use Parent Field + Min Occurs / Max Occurs; content uses Repeat Group + Item Index. For repeats inside embedded components, use a dotted Repeat Group (e.g. `socialMediaWidget_o.accounts_o`). Nested repeat groups (repeat inside repeat) can use a longer dotted path if the importer supports it.
- Datasource IDs in content-types and content must match **Datasource ID** in datasources.csv; an importer should resolve them when generating form-definition.xml.
