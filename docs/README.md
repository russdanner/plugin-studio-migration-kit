# Migration Kit

## Project Layout

- **`migration-kit/`**
  - **`import.py`** – Parent script: runs CSV import, optional template generation, then (optionally) content-type doc generation.
  - **`sub-scripts/`** – Individual Python scripts (import, template generator, doc generator, check-templates, etc.).
  - **`content-import/`** – Actual CSV data used by the importer: `content-types.csv`, `datasources.csv`, `content.csv`, plus `content-import/docs/CSV_MIGRATION_README.md`. A reference copy of the same data lives in `content-import/examples/example-import-data/` for anyone using the kit.
  - **`docs/`** – This folder; optional output for generated content-type docs when using `import.py --docs-dir migration-kit/docs`.

## Content Import
The content importer scripts can handle:
- Basic content type properties
- Repeat groups
- Shared and embedded content relationships
- Importing images directly
- Creating blob objects and importing images into S3
- Create generic templates for Experience Builder Editing
  
### Basic instructions:

#### Prepare the data / content
- Add the migration git to your project at the `SANDBOX ROOT`
- Create the CSV files that contain your content model and content
  - content-import/content-types.csv
  - content-import/data-sources.csv
  - content.csv

See **`content-import/docs/CSV_MIGRATION_README.md`** for CSV format and individual script usage.

#### Run the Content Import
From the **Crafter sandbox root** (directory that contains `migration-kit/` and `config/`):

```bash
# Run full migration (content types + content + content-type docs into sandbox/docs)
python3 migration-kit/import.py
```
### Test
- Commit the changes made by the script to your sandbox
- Use Crafter Studio to test content types, content forms and the Experience Builder temnplates created by the importer.
