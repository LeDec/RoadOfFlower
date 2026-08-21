#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "skills" / "catalog.csv"
TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff.+#-]+", re.UNICODE)


def tokens(text: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(text)}


def score(row: dict[str, str], query_tokens: set[str]) -> int:
    fields = {
        "name": 6,
        "publisher": 4,
        "category": 4,
        "description": 2,
        "origin_repository": 3,
    }
    total = 0
    for field, weight in fields.items():
        haystack = row.get(field, "").casefold()
        total += sum(weight for token in query_tokens if token in haystack)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the RoadOfFlower real Skill index")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--category")
    parser.add_argument("--publisher")
    args = parser.parse_args()

    query_tokens = tokens(args.query)
    with CATALOG.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    results = []
    for row in rows:
        if args.category and args.category.casefold() not in row["category"].casefold():
            continue
        if args.publisher and args.publisher.casefold() not in row["publisher"].casefold():
            continue
        value = score(row, query_tokens)
        if value:
            results.append((value, row))
    results.sort(key=lambda item: (-item[0], item[1]["name"].casefold()))

    for value, row in results[: max(0, args.limit)]:
        print(f"{value:02d} | {row['name']} | {row['category']} | {row['publisher']}")
        print(f"     {row['description']}")
        print(f"     {row['url']}")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
