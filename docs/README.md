# CrafterCMS Migration Kit
This tool helps you bulk migrate / import your content into CrafterCMS.

## Project Layout

- **`migration-kit/`**
  - **`import.py`** – Parent script: runs CSV import, optional template generation, then (optionally) content-type doc generation.
  - **`sub-scripts/`** – Individual Python scripts (import, template generator, doc generator, check-templates, asset import, cleanup, etc.).
  - **`content-import/`** – Actual CSV data used by the importer: `content-types.csv`, `datasources.csv`, `content.csv`, plus `content-import/docs/CSV_MIGRATION_README.md`. Optional folder `content-import/assets-to-import/` holds images, videos, and documents for the asset import script. A reference copy of the same data lives in `content-import/examples/example-import-data/` for anyone using the kit.
  - **`docs/`** – This folder; optional output for generated content-type docs when using `import.py --docs-dir migration-kit/docs`.

## Content Import
The content importer scripts can handle:
- Basic content type properties
- Repeat groups
- Shared and embedded content relationships
- Importing assets (images, video, documents, etc) into the repository directly (for a small projects / asset volume)
- Creating blob objects for assets in the repository and importing the related assets (images, video, documents, etc) into S3 (for projects with a large volume of assets)
- Create generic templates for Experience Builder Editing
  
### Usage Instructions:

#### Prepare the Data / Content
- Add the migration git to your project at the `SANDBOX ROOT`
- Create the CSV files that contain your content model and content
  - content-import/content-types.csv
  - content-import/datasources.csv
  - content-import/content.csv
  - Optionally, add assets (images, videos, PDFs, etc.) under content-import/assets-to-import/

See **`content-import/docs/CSV_MIGRATION_README.md`** for CSV format and individual script usage.

#### Run the Content Import
From the **Crafter sandbox root** (directory that contains `migration-kit/` and `config/`):

```bash
# Run full migration (content types + content + content-type docs into sandbox/docs)
python3 migration-kit/import.py
```
### Test
- Commit the changes made by the script to your sandbox
- Use Crafter Studio to test content types, content forms and the Experience Builder templates created by the importer.
