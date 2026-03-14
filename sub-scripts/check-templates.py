#!/usr/bin/env python3
"""Check preview URLs for FreeMarker template errors. Uses token from migration-kit/.preview-token.
Paths are discovered by listing all index.xml under sandbox/site/website (data-driven)."""
import sys
from pathlib import Path

import urllib.request

# Script lives in migration-kit/sub-scripts/; token is in migration-kit/
MIGRATION_KIT = Path(__file__).resolve().parent.parent
TOKEN_FILE = MIGRATION_KIT / ".preview-token"
BASE = "http://localhost:8080"
# Sandbox root = parent of migration-kit (override with --sandbox)
DEFAULT_SANDBOX = MIGRATION_KIT.parent


def discover_website_paths(sandbox: Path) -> list[str]:
    """Return URL paths for every page under site/website (each index.xml -> one path)."""
    website_dir = sandbox / "site" / "website"
    if not website_dir.is_dir():
        return []
    paths = []
    for index_file in website_dir.rglob("index.xml"):
        try:
            rel = index_file.parent.relative_to(website_dir)
            path = rel.as_posix()  # "" for website/index.xml, "about" for website/about/index.xml
            paths.append(path)
        except ValueError:
            continue
    # Sort so "" (home) first, then alphabetical
    paths.sort(key=lambda p: (p != "", p))
    return paths


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Check preview URLs for FreeMarker errors. Paths from site/website.")
    ap.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX, help="Sandbox root (default: parent of migration-kit)")
    ap.add_argument("--site", type=str, default=None, help="Crafter site name (default: sandbox directory name)")
    args = ap.parse_args()
    sandbox = args.sandbox.resolve()
    site = args.site or sandbox.name

    if not TOKEN_FILE.exists():
        print(f"Token file not found: {TOKEN_FILE}", file=sys.stderr)
        sys.exit(1)
    token = TOKEN_FILE.read_text().strip()
    cookie = f"crafterPreview={token}"

    paths = discover_website_paths(sandbox)
    if not paths:
        print("No pages found under site/website.", file=sys.stderr)
        sys.exit(1)

    errors = []
    for path in paths:
        url = f"{BASE}/{path}?crafterSite={site}" if path else f"{BASE}/?crafterSite={site}"
        label = path or "(home)"
        try:
            req = urllib.request.Request(url, headers={"Cookie": cookie})
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"FAIL {label}: {e}")
            errors.append((label, str(e)))
            continue
        if "FreeMarker template error" in body.lower() or "template error" in body.lower():
            print(f"FAIL {label}: FreeMarker template error in response")
            errors.append((label, "FreeMarker template error"))
            # Print the error section (typically in <pre> or body)
            lower = body.lower()
            for start in ("freemarker template error", "<pre>", "exception"):
                idx = lower.find(start)
                if idx != -1:
                    snippet = body[max(0, idx - 100) : idx + 1500]
                    print("--- Error snippet ---")
                    print(snippet[:2000])
                    print("---")
                    break
        else:
            print(f"OK {label}")
    if errors:
        sys.exit(1)
    print("All checked URLs OK.")


if __name__ == "__main__":
    main()
