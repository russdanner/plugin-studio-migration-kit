# Migration Kit

This folder holds documentation for the CrafterCMS migration kit.

## Layout

- **`migration-kit/`**
  - **`import.py`** – Parent script: runs CSV import, optional template generation, then (optionally) content-type doc generation.
  - **`sub-scripts/`** – Individual Python scripts (import, template generator, doc generator, check-templates, etc.).
  - **`content-import/`** – Actual CSV data used by the importer: `content-types.csv`, `datasources.csv`, `content.csv`, plus `content-import/docs/CSV_MIGRATION_README.md`. A reference copy of the same data lives in `content-import/examples/example-import-data/` for anyone using the kit.
  - **`docs/`** – This folder; optional output for generated content-type docs when using `import.py --docs-dir migration-kit/docs`.

## Full import

From the **Crafter sandbox root** (directory that contains `migration-kit/` and `config/`):

```bash
# Run full migration (content types + content + content-type docs into sandbox/docs)
python3 migration-kit/import.py

# Write content-type docs into this folder instead of sandbox/docs
python3 migration-kit/import.py --docs-dir migration-kit/docs

# Dry run (no files written for CSV import; docs still generated)
python3 migration-kit/import.py --dry-run

# Only import content types (no content, no docs)
python3 migration-kit/import.py --types-only --skip-docs
```

With explicit sandbox:

```bash
python3 /path/to/migration-kit/import.py --sandbox /path/to/sandbox
```

## Check templates (FreeMarker)

After import, verify pages render without template errors. Put your preview token in `migration-kit/.preview-token`, then:

```bash
python3 migration-kit/sub-scripts/check-templates.py
```

Paths are **data-driven**: the script discovers all pages by listing `index.xml` under `site/website`. Use `--sandbox` and `--site` to override sandbox root and site name.

See **`content-import/docs/CSV_MIGRATION_README.md`** for CSV format and individual script usage.
