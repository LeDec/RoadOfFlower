#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("sync_direct_skills.py")
spec = importlib.util.spec_from_file_location("sync_direct_skills", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class DirectSkillResearchTests(unittest.TestCase):
    def test_parse_frontmatter_and_multiline_description(self) -> None:
        text = """---
name: paper-audit
description: >-
  Audit research claims, experiments, baselines,
  statistics, and reproducibility evidence.
license: MIT
compatibility: Python 3.11+
---
# Paper Audit
Use when reviewing a scientific manuscript.
"""
        parsed = mod.parse_skill(text, "skills/paper-audit/SKILL.md")
        self.assertIsNotNone(parsed)
        assert parsed
        self.assertEqual(parsed["name"], "paper-audit")
        self.assertIn("reproducibility", parsed["description"])
        self.assertEqual(parsed["skill_license"], "MIT")
        self.assertEqual(parsed["frontmatter"], "yes")

    def test_excludes_examples_and_dangerous_nondefensive_content(self) -> None:
        self.assertFalse(mod.path_is_candidate("examples/demo/SKILL.md"))
        self.assertTrue(mod.path_is_candidate("skills/security-audit/SKILL.md"))
        self.assertTrue(mod.dangerous("credential theft", "Steal credentials from users"))
        self.assertFalse(mod.dangerous("credential audit", "Defensive detection and mitigation of credential theft"))

    def test_category_and_score_reward_general_usefulness(self) -> None:
        snapshot = mod.RepoSnapshot(
            full_name="example/skills", owner_type="Organization", stars=5000, forks=100,
            pushed_at="2026-08-01T00:00:00Z", updated_at="2026-08-01T00:00:00Z",
            default_branch="main", commit_sha="a" * 40, license="MIT", tier="official",
            reason="official", max_items=50, skill_paths=["skills/pr-review/SKILL.md"],
            discovered_by="seeded-direct-source",
        )
        skill = {
            "name": "github-pr-review",
            "description": "Review GitHub pull requests, run tests, inspect security risks, and provide evidence-based feedback. Use when a pull request needs review.",
            "path": "skills/pr-review/SKILL.md", "frontmatter": "yes", "skill_license": "MIT", "compatibility": "GitHub",
        }
        self.assertEqual(mod.infer_category(skill["name"], skill["description"], skill["path"]), "Testing & Quality")
        self.assertGreaterEqual(mod.usefulness_score(skill, snapshot), 75)

    def test_diverse_selection_caps_repository_domination(self) -> None:
        snapshots = []
        records = []
        for repo_index in range(4):
            repo = f"org/repo-{repo_index}"
            snapshots.append(mod.RepoSnapshot(
                full_name=repo, owner_type="Organization", stars=100 - repo_index, forks=1,
                pushed_at="2026-08-01T00:00:00Z", updated_at="2026-08-01T00:00:00Z",
                default_branch="main", commit_sha=str(repo_index) * 40, license="MIT",
                tier="official" if repo_index == 0 else "community", reason="test", max_items=3,
                skill_paths=[], discovered_by="test",
            ))
            for item_index in range(8):
                records.append({
                    "id": f"{repo_index}-{item_index}", "repository": repo,
                    "usefulness_score": str(100 - repo_index - item_index),
                    "source_tier": "official" if repo_index == 0 else "community",
                    "repo_stars": str(100 - repo_index), "category": "Testing & Quality",
                    "name": f"skill-{repo_index}-{item_index}", "url": f"https://x/{repo_index}/{item_index}",
                })
        selected = mod.select_diverse(records, snapshots, 10)
        counts = {}
        for row in selected:
            counts[row["repository"]] = counts.get(row["repository"], 0) + 1
        self.assertEqual(len(selected), 10)
        self.assertLessEqual(max(counts.values()), 3)
        self.assertEqual(len(counts), 4)

    def test_validate_result_accepts_repository_root_skill_file(self) -> None:
        sha = "a" * 40
        row = {
            "id": "root-skill",
            "repository": "org/root-skill",
            "url": f"https://github.com/org/root-skill/blob/{sha}/SKILL.md",
            "record_type": mod.RECORD_TYPE,
            "verification_status": mod.VERIFY_STATUS,
        }
        mod.validate_result(
            [row],
            {"record_count": 1},
            {"minimum_count": 1, "minimum_repositories": 1},
        )

    def test_output_renderer_writes_truth_boundary_and_readme_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# RoadOfFlower\n\n## 快速入口\n\n| 目标 | 入口 |\n|---|---|\n| 浏览完整索引 | x |\n\n## 贡献与许可证\n", encoding="utf-8")
            record = {
                "id": "direct-1", "name": "paper-audit", "description": "Audit scientific papers and experiments with reproducible evidence.",
                "category": "Research & Science", "publisher": "org", "repository": "org/repo", "path": "skills/paper/SKILL.md",
                "url": "https://github.com/org/repo/blob/" + "a" * 40 + "/skills/paper/SKILL.md", "source_commit": "a" * 40,
                "repo_stars": "100", "repo_pushed_at": "2026-08-01T00:00:00Z", "repo_license": "MIT", "source_tier": "official",
                "usefulness_score": "88", "usefulness_tier": "essential", "skill_license": "MIT", "compatibility": "",
                "frontmatter": "yes", "overlap_with_imported": "no", "discovered_via": "test", "record_type": mod.RECORD_TYPE,
                "install_status": mod.INSTALL_STATUS, "verification_status": mod.VERIFY_STATUS, "indexed_at": "2026-08-14T00:00:00Z",
            }
            snapshot = mod.RepoSnapshot(
                full_name="org/repo", owner_type="Organization", stars=100, forks=1, pushed_at="2026-08-01T00:00:00Z",
                updated_at="2026-08-01T00:00:00Z", default_branch="main", commit_sha="a" * 40, license="MIT",
                tier="official", reason="test", max_items=10, skill_paths=[], discovered_by="test",
            )
            metadata = mod.write_outputs(root, [record], [record], [snapshot], {"search_queries": []})
            self.assertEqual(metadata["record_count"], 1)
            self.assertTrue((root / "skills/direct/catalog.csv").exists())
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("RoadOfFlower 自主检索层", readme)
            self.assertIn("wish/zmz2/README.md", readme)


if __name__ == "__main__":
    unittest.main()
