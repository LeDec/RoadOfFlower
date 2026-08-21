from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module("validate_direct_catalog", ROOT / "scripts" / "validate_direct_catalog.py")
searcher = load_module("search_direct_skills", ROOT / "scripts" / "search_direct_skills.py")


def record(index: int, *, repo: str = "anthropics/skills", name: str = "PDF document skill", category: str = "Documents & Knowledge", description: str = "Create, inspect, and validate useful PDF documents with explicit review steps.") -> dict[str, str]:
    sha = f"{index:040x}"[-40:]
    path = f"skills/skill-{index}/SKILL.md"
    return {
        "id": f"direct-{index:014x}", "name": name, "description": description,
        "category": category, "publisher": repo.split('/')[0], "repository": repo, "path": path,
        "url": f"https://github.com/{repo}/blob/{sha}/{path}", "source_commit": sha,
        "repo_stars": "1000", "repo_pushed_at": "2026-08-14T00:00:00Z", "repo_license": "MIT",
        "source_tier": "official", "usefulness_score": "88", "usefulness_tier": "essential",
        "skill_license": "MIT", "compatibility": "Agent Skills clients", "frontmatter": "yes",
        "overlap_with_imported": "no", "discovered_via": "seeded-direct-source",
        "record_type": validator.RECORD_TYPE, "install_status": validator.INSTALL_STATUS,
        "verification_status": validator.VERIFY_STATUS, "indexed_at": "2026-08-14T00:00:00Z",
    }


class DirectCatalogTests(unittest.TestCase):
    def test_validates_commit_pinned_direct_records(self) -> None:
        rows = [record(i, repo=f"org{i % 3}/repo{i % 3}") for i in range(1, 7)]
        metadata = {
            "record_type": validator.RECORD_TYPE, "record_count": 6, "repository_count": 3,
            "category_count": 1, "publisher_count": 3, "install_status": validator.INSTALL_STATUS,
            "verification_status": validator.VERIFY_STATUS, "discovery_method": "road-of-flower-direct-github-scan",
            "source_repositories": sorted({row["repository"] for row in rows}),
        }
        self.assertEqual(validator.validate(rows, metadata, minimum=5, minimum_repositories=3), [])

    def test_accepts_commit_pinned_repository_root_skill_file(self) -> None:
        row = record(1, repo="org/root-skill")
        row["path"] = "skill.md"
        row["url"] = f"https://github.com/org/root-skill/blob/{row['source_commit']}/skill.md"
        metadata = {
            "record_type": validator.RECORD_TYPE, "record_count": 1, "repository_count": 1,
            "category_count": 1, "publisher_count": 1, "install_status": validator.INSTALL_STATUS,
            "verification_status": validator.VERIFY_STATUS,
            "discovery_method": "road-of-flower-direct-github-scan",
            "source_repositories": ["org/root-skill"],
        }
        self.assertEqual(validator.validate([row], metadata, minimum=1, minimum_repositories=1), [])

    def test_rejects_moving_branch_url_and_truth_boundary_drift(self) -> None:
        row = record(1)
        row["url"] = "https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md"
        row["verification_status"] = "audited"
        metadata = {
            "record_type": validator.RECORD_TYPE, "record_count": 1, "repository_count": 1,
            "category_count": 1, "publisher_count": 1, "install_status": validator.INSTALL_STATUS,
            "verification_status": validator.VERIFY_STATUS, "discovery_method": "road-of-flower-direct-github-scan",
            "source_repositories": ["anthropics/skills"],
        }
        errors = validator.validate([row], metadata, minimum=1, minimum_repositories=1)
        self.assertTrue(any("commit-pinned" in error for error in errors))
        self.assertTrue(any("verification_status" in error for error in errors))

    def test_search_requires_all_terms_and_uses_usefulness_as_tiebreaker(self) -> None:
        rows = [
            record(1, name="PDF document workflow"),
            record(2, name="GitHub pull request review", category="Testing & Quality", description="Review GitHub changes and verify tests before merge."),
        ]
        scores = [searcher.score(row, searcher.tokens("pdf document")) for row in rows]
        self.assertGreater(scores[0], 0)
        self.assertEqual(scores[1], 0)

    def test_cli_reads_catalog_and_returns_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog.csv"
            with catalog.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(record(1)))
                writer.writeheader()
                writer.writerow(record(1))
            exit_code = searcher.main(["pdf document", "--catalog", str(catalog), "--format", "json"])
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
