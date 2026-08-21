from __future__ import annotations

import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("sync_actual_skills.py")
spec = importlib.util.spec_from_file_location("sync_actual_skills", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

SAMPLE = r'''
# Awesome Agent Skills

<div><a href="https://example.com">Sponsor</a></div>

<details open>
<summary><h3 style="display:inline">Official Claude Skills</h3></summary>

- **[anthropics/docx](https://officialskills.sh/anthropics/skills/docx)** - Create and edit Word documents
- **[anthropics/pdf](https://github.com/anthropics/skills/tree/main/skills/pdf)** — Work with PDF documents
</details>

<details>
<summary><h3 style="display:inline">Community Skills</h3></summary>

- **[alice/research-review](https://github.com/alice/agent-skills/tree/main/research-review)**: Review research evidence
- **[alice/research-review-duplicate](https://github.com/alice/agent-skills/tree/main/research-review/)** - Duplicate URL
- [Become a Sponsor](https://sponsors.example.com) - Advertisement
</details>
'''


class ParserTests(unittest.TestCase):
    def test_extracts_real_skill_entries_and_categories(self) -> None:
        records = module.parse_skill_index(SAMPLE, source_key="sample")
        self.assertEqual(3, len(records))
        by_name = {record["name"]: record for record in records}
        self.assertEqual("Official Claude Skills", by_name["anthropics/docx"]["category"])
        self.assertEqual("anthropics", by_name["anthropics/docx"]["publisher"])
        self.assertEqual("anthropics/skills", by_name["anthropics/pdf"]["origin_repository"])
        self.assertEqual("Community Skills", by_name["alice/research-review"]["category"])

    def test_deduplicates_canonical_urls(self) -> None:
        records = module.parse_skill_index(SAMPLE, source_key="sample")
        urls = [record["url"] for record in records]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertNotIn("https://github.com/alice/agent-skills/tree/main/research-review/", urls)

    def test_sets_truth_boundary_fields(self) -> None:
        record = module.parse_skill_index(SAMPLE, source_key="sample")[0]
        self.assertEqual("real-skill-index-entry", record["record_type"])
        self.assertEqual("not-installed", record["install_status"])
        self.assertEqual("indexed-link-not-audited", record["verification_status"])
        self.assertTrue(record["id"].startswith("skill-"))

    def test_rejects_non_skill_advertisements(self) -> None:
        records = module.parse_skill_index(SAMPLE, source_key="sample")
        self.assertFalse(any("Sponsor" in record["name"] for record in records))

    def test_plain_text_removes_markdown_and_html(self) -> None:
        text = module.plain_text("Use **strong** and [docs](https://example.com) <code>x</code>")
        self.assertEqual("Use strong and docs x", text)

    def test_renderer_writes_catalog_and_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            records = module.parse_skill_index(SAMPLE, source_key="sample")
            metadata = {
                "source_key": "sample",
                "source_name": "Sample",
                "source_repository": "sample/repo",
                "source_page": "https://github.com/sample/repo",
                "source_index_url": "https://example.com/README.md",
                "source_commit": "abc123",
                "source_commit_date": "2026-08-14T00:00:00Z",
                "source_license": "MIT",
            }
            module.render_repository(pathlib.Path(tmp), records, metadata, "MIT sample license")
            self.assertTrue((pathlib.Path(tmp) / "README.md").exists())
            self.assertTrue((pathlib.Path(tmp) / "skills/catalog.csv").exists())
            self.assertTrue((pathlib.Path(tmp) / "skills/catalog.json").exists())
            self.assertTrue((pathlib.Path(tmp) / "skills/INDEX.md").exists())
            self.assertIn("3", (pathlib.Path(tmp) / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
