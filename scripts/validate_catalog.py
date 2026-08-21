#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "skills" / "catalog.csv"
METADATA = ROOT / "skills" / "catalog_metadata.json"
README = ROOT / "README.md"
REQUIRED = {
    "id", "name", "publisher", "category", "description", "url",
    "record_type", "install_status", "verification_status", "listing_source",
    "source_commit", "indexed_at",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    with CATALOG.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED.issubset(reader.fieldnames or []):
            fail(f"missing fields: {sorted(REQUIRED - set(reader.fieldnames or []))}")
        rows = list(reader)
    if len(rows) < 1000:
        fail(f"expected at least 1000 actual Skill entries, got {len(rows)}")
    ids = [row["id"] for row in rows]
    urls = [row["url"] for row in rows]
    if len(ids) != len(set(ids)):
        fail("duplicate IDs")
    if len(urls) != len(set(urls)):
        fail("duplicate URLs")
    for row in rows:
        if any(not row[field].strip() for field in REQUIRED):
            fail(f"empty required field in {row.get('id')}")
        if row["record_type"] != "real-skill-index-entry":
            fail(f"non-real record in catalog: {row['id']}")
        if row["install_status"] != "not-installed":
            fail(f"invalid install status: {row['id']}")
        if row["verification_status"] != "indexed-link-not-audited":
            fail(f"invalid verification status: {row['id']}")
        parsed = urlsplit(row["url"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            fail(f"invalid URL: {row['url']}")
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata["record_count"] != len(rows):
        fail("metadata count mismatch")
    readme = README.read_text(encoding="utf-8")
    if f"{len(rows):,} 条真实 Skill" not in readme:
        fail("README count is stale")
    if "not-installed / indexed-link-not-audited" not in readme:
        fail("README truth boundary missing")
    categories = Counter(row["category"] for row in rows)
    print(
        f"PASS: {len(rows)} real Skill links, {len(categories)} categories, "
        f"{len({row['publisher'] for row in rows})} publishers"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
