## Migration Kit – Architecture & Usage Overview

This document describes how the CSV‑driven migration kit for the `migration` sandbox is structured and how it works. It is intended as a durable reference so future work can extend or debug the kit without having to rediscover decisions we already made.

---

## 1. High‑level goals

- **Source of truth**: All content types and content are defined in CSV files, not hand‑edited XML.
- **Deterministic imports**: Running the importer scripts regenerates content types and content the same way every time.
- **Parity with the source site**: The generated XML in `migration` is structurally equivalent to the original source project’s XML (including embedded components, taxonomy, and system fields) so that:
  - Crafter Studio forms work (no parse errors).
  - Experience Builder can edit all fields.
  - Engine renders templates without FreeMarker or Groovy surprises.

---

## 2. Files & locations

All migration kit files live under:

- `migration-kit/`
  - **`import.py`** – Parent script: runs CSV import, optional template generation, then (optionally) content-type documentation generator. Run from sandbox root.
  - **`sub-scripts/`** – Python scripts:
    - `import_from_csv.py` – Imports from CSVs in `content-import/`. Output is data-driven from CSV; XML structure matches Crafter form-engine output for XB compatibility.
    - `generate_generic_template.py` – Generates FTL from a content type’s form-definition.
    - `generate_content_type_docs.py` – Writes Markdown docs from `config/studio/content-types/`.
    - `check-templates.py` – Checks preview URLs for FreeMarker errors. **Paths are data-driven**: discovers all pages by listing `site/website` for `index.xml` files (no hardcoded URL list).
    - `add_extra_site_navigators.py` – Optional post-import step.
  - **`docs/`** – Optional docs folder; can be used as output for generated content-type docs (`import.py --docs-dir migration-kit/docs`).
  - **`content-import/`**
    - `content-types.csv`, `content.csv`, `datasources.csv` (actual data; importer reads from here)
    - `docs/CSV_MIGRATION_README.md` (end‑user documentation)
    - `examples/source_site` (embedded copy of the original **hello** site used as the parity reference)
    - `examples/example-import-data/` (reference copy of the CSV data for kit users; importer does not use this folder)
  - **`MIGRATION_KIT_DEVELOPMENT_GUIDE.md`** (this document)

Generated output (never hand‑edit these; always change CSV + scripts instead):

- Content types:
  - `config/studio/content-types/page/...`
  - `config/studio/content-types/component/...`
  - `config/studio/content-types/taxonomy/...`
- Content items:
  - `site/website/...` (pages)
  - `site/components/...` (components and widgets)
  - `site/taxonomy/...` (taxonomy content)

---

## 3. CSV schemas

### 3.1 `content-types.csv`

Each row defines **one field** on a content type (page, component, taxonomy, etc.).

Columns:

- **Type Name**: Content type ID (e.g. `/page/home`, `/component/feature`, `/taxonomy`).
- **Type Label**: Human‑friendly label.
- **Section**: Form section name (e.g. `Page Properties`, `Hero Section`, `Content`).
- **Field Name**: Field ID in XML (e.g. `title_t`, `hero_text_html`, `features_o`).
- **Field Label**: Display label in the form.
- **Field Type**: Crafter field type (`input`, `checkbox`, `rte`, `image-picker`, `node-selector`, `repeat`, `dropdown`, `checkbox-group`, etc.).
- **Required**: `true`/`false` → drives `required` constraint.
- **Description / Help**: Optional text shown in Studio.
- **Item Manager**: Datasource ID for `node-selector` and some composite fields.
- **Image Manager**: Datasource ID(s) for `image-picker` and `rte` fields.
- **Allowed Content Types**: For `node-selector` fields, the `/component/...` or `/page/...` types this selector can pick.
- **Min Size / Max Size**: For `node-selector` list size constraints.
- **Dropdown Datasource**: Datasource ID for `dropdown` and `checkbox-group` fields.
- **Parent Field / Min Occurs / Max Occurs**: Used with `repeat` (repeat group definitions).

`import_from_csv.py` uses this to generate, per content type:

- `config.xml` in `config/studio/content-types/...`
- `form-definition.xml` in the same directory, with:
  - Sections and fields.
  - `datasources` section derived from `Item Manager`, `Image Manager`, and `Dropdown Datasource`.
  - Correct properties and constraints (e.g. `minSize`, `maxSize`, `contentTypes`, `datasource`, `minOccurs`, `maxOccurs`, `required`).

### 3.2 `datasources.csv`

Defines reusable datasources referenced by content type fields.

Key columns:

- **Datasource ID**: Used by `Item Manager`, `Image Manager`, or `Dropdown Datasource` in `content-types.csv`.
- **Type**: e.g. `components`, `shared-content`, `img-repository-upload`, `img-desktop-upload`, `simpleTaxonomy`.
- **Title / Interface**: Human label and interface (`item` or `image`).
- **Component Path / repoPath / baseRepositoryPath / baseBrowsePath**: Where the datasource pulls items from.

Examples:

- `components` datasource `featuresComponents` pointing at `/site/components` for `/component/feature`.
- `simpleTaxonomy` datasources `categories` and `segments` pointing at `/site/taxonomy/categories.xml` and `/site/taxonomy/segments.xml`.

### 3.3 `content.csv`

Defines **actual content items**, including:

- Pages under `/site/website/...`
- Components under `/site/components/...`
- Taxonomy content under `/site/taxonomy/...`

Columns:

- **Type Name**: Content type ID (e.g. `/page/home`, `/component/feature`, `/taxonomy`).
- **XML Path**: Repository path (e.g. `/site/website/index.xml`, `/site/components/features/310b0c87-...xml`).
- **Repeat Group**: Name for repeat groups (e.g. `socialMediaWidget_o.accounts_o`).
- **Item Index**: Index within the repeat group (0‑based).
- **Field**: Field name to set (e.g. `title_t`, `body_html`, `features_o`).
- **Value**: Raw value (plain text, HTML, or special `EMBEDDED|...` syntax).
- **Datasource ID**: Optional; used mainly for selectors to indicate which datasource is in play.

Special handling:

- All HTML values for `*_html` fields are **escaped and written as CDATA** in the final XML to avoid OpenSearch index failures.
- The home page (`/site/website/index.xml`) includes:
  - System fields such as `content-type`, `display-template`, `merge-strategy`, `no-template-required`, `file-name`, `internal-name`, `navLabel`, `disabled`.
  - Feature references in `features_o` including embedded components (see below).

---

## 4. Importer script design (`import_from_csv.py`)

The importer is responsible for:

1. **Loading datasources** from `datasources.csv` into a dictionary keyed by ID.
2. **Generating content types** from `content-types.csv`:
   - Group rows by `Type Name`.
   - Build `config.xml` with correct `content-type` name, preview/paths settings, and thumbnail image.
   - Build `form-definition.xml` with:
     - Sections and fields.
     - Properties for each field, including size, maxlength, `datasource`, `minSize`, `maxSize`, `contentTypes`, etc.
     - Constraints (`required`, `minSize` for checkbox groups, `minOccurs`/`maxOccurs` for repeats).
     - `<datasources>` block containing all image and item datasources referenced in the form.
3. **Generating content XML** from `content.csv`:
   - Output order and structure are driven by `content-types.csv` (field order, required vs optional) so that generated XML matches Crafter Studio form-save output (XB-compatible).
   - Top‑level fields become `<fieldName>value</fieldName>` (or self-closing when empty).
   - Node selectors (`*_o`) build `<fieldName item-list="true"><item>...</item>...</fieldName>` (or self-closing when empty). **Optional** node-selectors (e.g. `header_o`, `left_rail_o`) are emitted **after** all repeat groups to match form engine order.
   - Repeat groups: **checkbox-group** fields omit `item-list="true"`; other repeat groups use `item-list="true"`. Values inside repeat-group items (e.g. RTE `section_html`) are **entity-escaped** (not CDATA) to match form output. Empty repeat groups and empty scalars use self-closing tags.
   - Indentation uses **tabs** to match form output.
   - System fields (`objectId`, `createdDate_dt`, `lastModifiedDate_dt`) are auto‑injected if missing. Item Manager (datasource) on `<item>` tags is taken from the content type’s Item Manager column in the CSV.

### 4.1 Node selectors and embedded content

For node selector fields (like `features_o`, `header_o`, `left_rail_o`):

- Values in `content.csv` can be:
  - **Shared references**: A path such as `/site/components/features/4be0a368-...xml`.
  - **Embedded references**: A special string:

    ```text
    EMBEDDED|/site/components/features/310b0c87-...xml|/component
    ```

- The importer:
  - Recognizes `*_o` fields and collects all values into an item list.
  - For **shared** items:

    ```xml
    <features_o item-list="true">
      <item datasource="featuresComponents">
        <key>/site/components/features/4be0a368-...xml</key>
        <value>4be0a368-...</value>
        <include>/site/components/features/4be0a368-...xml</include>
        <disableFlattening>false</disableFlattening>
      </item>
      ...
    </features_o>
    ```

  - For **embedded** items specifically on `features_o`:
    - Loads the parent component XML (e.g. `/site/components/features/310b0c87-...xml`).
    - Extracts the `<component>` node.
    - Uses the file name stem (`310b0c87-...`) as:
      - `<key>310b0c87-...</key>`
      - `<component id="310b0c87-...">...</component>`
    - Emits:

    ```xml
    <item datasource="featuresComponents" inline="true">
      <key>310b0c87-...</key>
      <value>Download</value>
      <disableFlattening>false</disableFlattening>
      <component id="310b0c87-...">
        <content-type>/component/feature</content-type>
        <display-template>/templates/web/components/feature.ftl</display-template>
        <merge-strategy>inherit-levels</merge-strategy>
        <no-template-required />
        <file-name>310b0c87-...xml</file-name>
        <internal-name>Download</internal-name>
        <title_t>Download</title_t>
        <icon_s>fa-arrow-alt-circle-down far</icon_s>
        <body_html>...</body_html>
        <disabled>false</disabled>
      </component>
    </item>
    ```

This structure matches the `hello` project and is what Crafter Studio expects for inline components in a node selector.

---

## 5. Taxonomy & checkbox‑group fields

We brought over taxonomy from `hello` and wired it into article pages via checkbox groups:

- Content type `/taxonomy`:
  - Has a `repeat` field `items` with nested `key` and `value` fields.
  - Generated `config.xml` and `form-definition.xml` live under `config/studio/content-types/taxonomy/`.
- Taxonomy content:
  - `/site/taxonomy/categories.xml`
  - `/site/taxonomy/segments.xml`
  - Values in `content.csv` define each pair of `key`/`value`.
- `simpleTaxonomy` datasources:
  - `categories` → `/site/taxonomy/categories.xml`
  - `segments` → `/site/taxonomy/segments.xml`
- On `/page/article`:
  - `categories_o` and `segments_o` are `checkbox-group` fields with `Dropdown Datasource` set to `categories` / `segments`.
  - The importer:
    - Emits `<property><name>datasource</name>...` and `<property><name>selectAll</name>...` for `checkbox-group`.
    - Adds a `minSize` constraint based on `Min Occurs`.

---

## 6. Studio UI integration

The script `add_extra_site_navigators.py` updates `config/studio/ui.xml` so that non‑default roots under `/site` become visible in the Studio sidebar.

- Scans `/site` for top‑level folders (e.g. `taxonomy`) that don’t already have a `PathNavigatorTree`.
- Adds a `PathNavigatorTree` widget under the Tools panel for each missing root:
  - `id`: Based on folder name (e.g. `taxonomy-nav`).
  - `label`: Human label derived from folder name.
  - `rootPath`: `/site/taxonomy`, etc.

This is how `/site/taxonomy` was made visible without manually editing `ui.xml`.

---

## 7. Home template (`templates/web/pages/home.ftl`)

We replaced the original “Editorial” HTML with a **generic headless editing screen**:

- Purpose:
  - Not a public‑facing page.
  - Provides a clean layout to edit headless content in Studio / XB.
- Characteristics:
  - Simple two‑column card layout (`Page Properties` and `Layout & Sections`).
  - Uses generic CSS (no type‑specific theme) scoped to the template.
  - Uses Crafter XB macros for all editable fields:
    - `@crafter.span`, `@crafter.div`, `@crafter.img`, `@crafter.renderComponentCollection`.
  - Renders:
    - Core page fields: `internal-name`, `navLabel`, `disabled`, `title_t`.
    - Hero: `hero_title_html`, `hero_text_html`, `hero_image_s`.
    - Layout controls: `header_o`, `left_rail_o`.
    - Features: `features_title_t`, `features_o`.

Key design rules:

- **Template does not invoke Groovy widgets directly** (e.g., no custom controllers for latest/related articles); instead, it just renders the components selected via node selectors.
- **All author‑editable content** is wrapped in XB macros and backed by fields defined in `content-types.csv`.

---

## 8. Parity strategy and rules of engagement

Guiding principles for this migration kit:

1. **Never hand‑edit generated XML** (content or form definitions).
   - All changes should go into:
     - `content-types.csv`
     - `content.csv`
     - `datasources.csv`
     - `import_from_csv.py` / `add_extra_site_navigators.py`
   - Then rerun the scripts.
2. **Aim for structural parity, not necessarily byte‑for‑byte whitespace parity**:
   - Tag names, hierarchy, attributes, and key values must match the `hello` project.
   - Whitespace and ordering can differ as long as Studio and Engine behave the same.
3. **Test Studio behavior as the ultimate oracle**:
   - If the `hello` item can be opened/edited/saved and the `migration` item cannot, then we still have a structural mismatch.
   - Fix that mismatch in CSV or importer logic.
4. **curl is for templates, not XML parsing**:
   - Use curl (+ preview token) to find FreeMarker errors in templates.
   - Use Studio to reveal XML parse errors (content model vs. XML shape).

---

## 9. Known patterns & gotchas

Some specific patterns we already had to fix (and should remember):

- **Node selectors**:
  - Need correct `itemManager` and `contentTypes` in `content-types.csv`.
  - In `home/form-definition.xml`, `features_o` must use:
    - `itemManager = featuresComponents`
    - `contentTypes = /component/feature`
    - `minSize = 1`, `maxSize = 8`
- **Inline components**:
  - For `features_o`, Studio expects:
    - `<key>` == `<component @id>` == component file name (no `.xml`).
    - `<component>` nested with full payload (not an empty self‑closing tag).
- **System fields on pages**:
  - `content-type`, `display-template`, `merge-strategy`, `no-template-required`, `file-name`, `internal-name`, `navLabel`, `disabled`.
  - Our importer auto‑injects `objectId`, `createdDate_dt`, `lastModifiedDate_dt` if missing.
- **HTML fields**:
  - Top-level `*_html` content is wrapped in CDATA. **Repeat-group item** fields (e.g. `section_html` inside `sections_o`) are **entity-escaped** (e.g. `&lt;p&gt;`) to match Studio form-save output.
- **Taxonomy**:
  - `/taxonomy` lives under `config/studio/content-types/taxonomy`, not nested like `taxonomy/taxonomy`.
  - `simpleTaxonomy` datasources point at `/site/taxonomy/...xml`.

---

## 10. Typical workflow

1. **Adjust models or content**:
   - Edit `content-types.csv`, `datasources.csv`, or `content.csv`.
2. **Regenerate** (from sandbox root):

   ```bash
   cd .../migration/sandbox
   python3 migration-kit/import.py
   # Optional: add navigators for extra /site/* roots (e.g. taxonomy)
   python3 migration-kit/sub-scripts/add_extra_site_navigators.py
   ```

3. **Validate in Studio**:
   - Open relevant items (e.g. home page, article, taxonomy) and verify:
     - Forms load without XML parse errors.
     - All expected fields are present and populated.
     - Experience Builder can edit and save (canonical XML order and optional node-selectors last ensure this).
4. **Validate templates (optional)**:
   - Put the preview token in `migration-kit/.preview-token`, then run:
     ```bash
     python3 migration-kit/sub-scripts/check-templates.py
     ```
   - This discovers all page paths under `site/website` and checks each URL for FreeMarker errors. Override with `--sandbox` and `--site` if needed.

### 10.1 Data-driven vs convention-specific

The kit is **largely data-driven** from the CSVs: content types, fields, order, required flags, repeat groups, checkbox-groups, item managers, and content values come from `content-types.csv` and `content.csv`. A few behaviors remain **convention-specific** (not in CSV): e.g. which page types get `orderDefault_f` in the trail, which types use `no-template-required`, thumbnail per type for taxonomy, and the template generator’s special handling of `scripts_o` and page title (`title_t` / `internal-name`). See an audit of scripts for the full list. `check-templates.py` is fully data-driven: it discovers paths from `site/website` only.

---

This document should be kept in sync as we extend the migration kit (new content types, templates, or importer features). Whenever we add a capability (e.g., new embedded patterns, additional page types), we should:

- Update the CSVs.
- Update `import_from_csv.py` if behavior is non‑trivial.
- Add a short note here describing the new pattern and any constraints.

