from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ActualCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "skills/catalog.csv").open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))
        cls.metadata = json.loads((ROOT / "skills/catalog_metadata.json").read_text(encoding="utf-8"))

    def test_at_least_one_thousand_actual_links(self) -> None:
        self.assertGreaterEqual(len(self.rows), 1000)
        self.assertTrue(all(row["record_type"] == "real-skill-index-entry" for row in self.rows))

    def test_unique_ids_and_urls(self) -> None:
        self.assertEqual(len(self.rows), len({row["id"] for row in self.rows}))
        self.assertEqual(len(self.rows), len({row["url"] for row in self.rows}))

    def test_truth_boundary(self) -> None:
        self.assertTrue(all(row["install_status"] == "not-installed" for row in self.rows))
        self.assertTrue(
            all(row["verification_status"] == "indexed-link-not-audited" for row in self.rows)
        )

    def test_metadata_matches(self) -> None:
        self.assertEqual(len(self.rows), self.metadata["record_count"])
        self.assertEqual("real-skill-index-entry", self.metadata["record_type"])

    def test_project_docs_exist(self) -> None:
        required = [
            "README.md",
            "skills/INDEX.md",
            "skills/README.md",
            "docs/01-agent-basics.md",
            "docs/05-verify-results-and-control-risk.md",
            "CONTRIBUTING.md",
            "THIRD_PARTY_NOTICES.md",
            "LICENSE",
        ]
        for path in required:
            self.assertTrue((ROOT / path).exists(), path)


if __name__ == "__main__":
    unittest.main()
