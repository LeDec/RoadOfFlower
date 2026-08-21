#!/usr/bin/env python3
"""Repair direct-Skill URL validators for real repository file layouts.

GitHub commit-pinned URLs may legally end in `/SKILL.md` at repository root or
in `/<directories>/SKILL.md`. Real repositories also sometimes use lowercase
`skill.md`. The first crawler release rejected these valid layouts. This
migration is idempotent and installs regression tests.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once_or_verify(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one old pattern in {path}, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def insert_before_once(path: Path, marker: str, insertion: str, sentinel: str) -> None:
    text = path.read_text(encoding="utf-8")
    if sentinel in text:
        return
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"expected exactly one insertion marker in {path}, found {count}")
    path.write_text(text.replace(marker, insertion + marker), encoding="utf-8", newline="\n")


def main() -> int:
    replace_once_or_verify(
        ROOT / ".bootstrap" / "sync_direct_skills.py",
        'r"/blob/[0-9a-f]{40}/.+/SKILL\\.md$"',
        'r"/blob/[0-9a-f]{40}/(?:.+/)?SKILL\\.md$"',
    )
    replace_once_or_verify(
        ROOT / "scripts" / "validate_direct_catalog.py",
        'r"^https://github\\.com/[^/]+/[^/]+/blob/([0-9a-f]{40})/.+/SKILL\\.md$"',
        'r"^https://github\\.com/[^/]+/[^/]+/blob/([0-9a-f]{40})/(?:.+/)?SKILL\\.md$"',
    )
    replace_once_or_verify(
        ROOT / "scripts" / "validate_direct_catalog.py",
        'if not row["path"].endswith("SKILL.md"):',
        'if not row["path"].casefold().endswith("skill.md"):',
    )

    sync_test = '''    def test_validate_result_accepts_repository_root_skill_file(self) -> None:\n        sha = "a" * 40\n        row = {\n            "id": "root-skill",\n            "repository": "org/root-skill",\n            "url": f"https://github.com/org/root-skill/blob/{sha}/SKILL.md",\n            "record_type": mod.RECORD_TYPE,\n            "verification_status": mod.VERIFY_STATUS,\n        }\n        mod.validate_result(\n            [row],\n            {"record_count": 1},\n            {"minimum_count": 1, "minimum_repositories": 1},\n        )\n\n'''
    insert_before_once(
        ROOT / ".bootstrap" / "test_sync_direct_skills.py",
        "    def test_output_renderer_writes_truth_boundary_and_readme_block(self) -> None:\n",
        sync_test,
        "test_validate_result_accepts_repository_root_skill_file",
    )

    validator_test = '''    def test_accepts_commit_pinned_repository_root_skill_file(self) -> None:\n        row = record(1, repo="org/root-skill")\n        row["path"] = "skill.md"\n        row["url"] = f"https://github.com/org/root-skill/blob/{row['source_commit']}/skill.md"\n        metadata = {\n            "record_type": validator.RECORD_TYPE, "record_count": 1, "repository_count": 1,\n            "category_count": 1, "publisher_count": 1, "install_status": validator.INSTALL_STATUS,\n            "verification_status": validator.VERIFY_STATUS,\n            "discovery_method": "road-of-flower-direct-github-scan",\n            "source_repositories": ["org/root-skill"],\n        }\n        self.assertEqual(validator.validate([row], metadata, minimum=1, minimum_repositories=1), [])\n\n'''
    insert_before_once(
        ROOT / "tests" / "test_direct_catalog.py",
        "    def test_rejects_moving_branch_url_and_truth_boundary_drift(self) -> None:\n",
        validator_test,
        "test_accepts_commit_pinned_repository_root_skill_file",
    )
    print("PASS: root-level and case-insensitive commit-pinned Skill validation repaired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
