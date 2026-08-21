#!/usr/bin/env python3
"""Search RoadOfFlower's independently researched direct Skill catalog."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "skills" / "direct" / "catalog.csv"
FIELDS = ("name", "description", "category", "publisher", "repository", "compatibility")


def tokens(query: str) -> list[str]:
    return [part.casefold() for part in re.findall(r"[\w.+#/-]+", query, flags=re.UNICODE) if part.strip()]


def score(row: dict[str, str], query_tokens: list[str]) -> int:
    if not query_tokens:
        return 0
    values = {field: str(row.get(field, "")).casefold() for field in FIELDS}
    points = 0
    for token in query_tokens:
        best = 0
        if token in values["name"]:
            best = max(best, 12)
        if token in values["category"]:
            best = max(best, 8)
        if token in values["description"]:
            best = max(best, 6)
        if token in values["publisher"] or token in values["repository"]:
            best = max(best, 5)
        if token in values["compatibility"]:
            best = max(best, 3)
        if not best:
            return 0
        points += best
    try:
        points += int(row.get("usefulness_score", "0")) // 12
    except ValueError:
        pass
    return points


def load(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--category")
    parser.add_argument("--publisher")
    parser.add_argument("--repository")
    parser.add_argument("--source-tier", choices=["official", "scientific", "maintainer", "community", "discovered"])
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = load(args.catalog)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    query_tokens = tokens(args.query)
    matches: list[tuple[int, dict[str, str]]] = []
    for row in rows:
        if args.category and args.category.casefold() not in row.get("category", "").casefold():
            continue
        if args.publisher and args.publisher.casefold() not in row.get("publisher", "").casefold():
            continue
        if args.repository and args.repository.casefold() not in row.get("repository", "").casefold():
            continue
        if args.source_tier and row.get("source_tier") != args.source_tier:
            continue
        value = score(row, query_tokens)
        if value:
            matches.append((value, row))
    matches.sort(key=lambda item: (-item[0], -int(item[1].get("usefulness_score", "0") or 0), item[1].get("name", "").casefold()))
    chosen = matches[: max(args.limit, 0)]
    if args.format == "json":
        print(json.dumps([{"match_score": value, **row} for value, row in chosen], ensure_ascii=False, indent=2))
    else:
        for value, row in chosen:
            print(f"{value:02d} | {row['name']} | {row['category']} | {row['repository']}")
            print(f"     {row['description']}")
            print(f"     {row['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
