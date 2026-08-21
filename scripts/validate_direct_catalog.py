#!/usr/bin/env python3
"""Validate RoadOfFlower's independently researched direct Skill index."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "skills" / "direct" / "catalog.csv"
DEFAULT_METADATA = ROOT / "skills" / "direct" / "metadata.json"
RECORD_TYPE = "direct-skill-file"
INSTALL_STATUS = "not-installed"
VERIFY_STATUS = "direct-file-fetched-frontmatter-parsed-not-audited"
REQUIRED = {
    "id", "name", "description", "category", "publisher", "repository", "path",
    "url", "source_commit", "repo_stars", "repo_pushed_at", "repo_license",
    "source_tier", "usefulness_score", "usefulness_tier", "skill_license",
    "compatibility", "frontmatter", "overlap_with_imported", "discovered_via",
    "record_type", "install_status", "verification_status", "indexed_at",
}
PINNED_URL = re.compile(r"^https://github\.com/[^/]+/[^/]+/blob/([0-9a-f]{40})/(?:.+/)?SKILL\.md$", re.I)
SHA = re.compile(r"^[0-9a-f]{40}$", re.I)
TIERS = {"official", "scientific", "maintainer", "community", "discovered"}
USEFULNESS = {"essential", "high", "useful", "specialized"}


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def validate(rows: list[dict[str, str]], metadata: dict[str, object], *, minimum: int, minimum_repositories: int) -> list[str]:
    errors: list[str] = []
    if len(rows) < minimum:
        errors.append(f"record count {len(rows)} is below minimum {minimum}")
    ids = [row.get("id", "") for row in rows]
    urls = [row.get("url", "") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate id")
    if len(urls) != len(set(urls)):
        errors.append("duplicate url")
    repositories = {row.get("repository", "") for row in rows if row.get("repository")}
    if len(repositories) < minimum_repositories:
        errors.append(f"repository count {len(repositories)} is below minimum {minimum_repositories}")

    for index, row in enumerate(rows, 2):
        prefix = f"row {index}"
        missing = sorted(field for field in REQUIRED if not str(row.get(field, "")).strip())
        # Compatibility and license fields may legitimately be absent upstream.
        missing = [field for field in missing if field not in {"compatibility", "skill_license"}]
        if missing:
            errors.append(f"{prefix}: missing {', '.join(missing)}")
            continue
        match = PINNED_URL.match(row["url"])
        if not match:
            errors.append(f"{prefix}: URL is not a commit-pinned SKILL.md: {row['url']}")
        if not SHA.fullmatch(row["source_commit"]):
            errors.append(f"{prefix}: invalid source_commit")
        elif match and match.group(1).casefold() != row["source_commit"].casefold():
            errors.append(f"{prefix}: URL SHA differs from source_commit")
        if not row["path"].casefold().endswith("skill.md"):
            errors.append(f"{prefix}: path does not end in SKILL.md")
        if row["record_type"] != RECORD_TYPE:
            errors.append(f"{prefix}: invalid record_type")
        if row["install_status"] != INSTALL_STATUS:
            errors.append(f"{prefix}: invalid install_status")
        if row["verification_status"] != VERIFY_STATUS:
            errors.append(f"{prefix}: invalid verification_status")
        if row["source_tier"] not in TIERS:
            errors.append(f"{prefix}: invalid source_tier")
        if row["usefulness_tier"] not in USEFULNESS:
            errors.append(f"{prefix}: invalid usefulness_tier")
        try:
            score = int(row["usefulness_score"])
            if not 0 <= score <= 100:
                raise ValueError
        except ValueError:
            errors.append(f"{prefix}: usefulness_score must be an integer in [0, 100]")

    expected = {
        "record_type": RECORD_TYPE,
        "record_count": len(rows),
        "repository_count": len(repositories),
        "category_count": len({row.get('category', '') for row in rows}),
        "publisher_count": len({row.get('publisher', '') for row in rows}),
        "install_status": INSTALL_STATUS,
        "verification_status": VERIFY_STATUS,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            errors.append(f"metadata {key} mismatch: expected {value!r}, found {metadata.get(key)!r}")
    if metadata.get("discovery_method") != "road-of-flower-direct-github-scan":
        errors.append("metadata discovery_method mismatch")
    sources = metadata.get("source_repositories")
    if not isinstance(sources, list) or set(map(str, sources)) != repositories:
        errors.append("metadata source_repositories mismatch")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--minimum", type=int, default=350)
    parser.add_argument("--minimum-repositories", type=int, default=15)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        header, rows = load_rows(args.catalog)
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors: list[str] = []
    if set(header) != REQUIRED or len(header) != len(REQUIRED):
        errors.append("catalog header does not match the direct-index schema")
    errors.extend(validate(rows, metadata, minimum=args.minimum, minimum_repositories=args.minimum_repositories))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"FAIL: {len(errors)} validation error(s)")
        return 1
    tiers = Counter(row["source_tier"] for row in rows)
    print(
        f"PASS: {len(rows)} direct Skill files, "
        f"{len({row['repository'] for row in rows})} repositories, "
        f"{len({row['category'] for row in rows})} categories; tiers={dict(sorted(tiers.items()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
