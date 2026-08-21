#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("generate_zmz2_wish.py")
spec = importlib.util.spec_from_file_location("generate_zmz2_wish", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class WishGeneratorTests(unittest.TestCase):
    def test_generates_complete_personal_wish_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            person = mod.generate(root)
            mod.validate(person)
            text = (person / "WISH_LIST.md").read_text(encoding="utf-8")
            self.assertGreater(len(text.splitlines()), 1000)
            self.assertEqual(len(re.findall(r"^### 第 \d{3} 个愿望：", text, flags=re.M)), 120)
            self.assertIn("中很多篇真正有价值的论文", text)
            self.assertIn("祝愿 LED", text)
            self.assertTrue((root / "wish/README.md").exists())
            self.assertTrue((person / "MANIFEST.md").exists())

    def test_attachments_and_assets_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            person = mod.generate(Path(tmp))
            with (person / "attachments/06_IDEA_BACKLOG.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 41)
            svgs = list((person / "assets").glob("*.svg"))
            self.assertEqual(len(svgs), 3)
            for svg in svgs:
                ET.parse(svg)

    def test_expected_internal_links_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            person = mod.generate(Path(tmp))
            readme = (person / "README.md").read_text(encoding="utf-8")
            links = re.findall(r"\[[^\]]+\]\((\./[^)#]+)", readme)
            self.assertGreaterEqual(len(links), 8)
            for link in links:
                self.assertTrue((person / link).resolve().exists(), link)


if __name__ == "__main__":
    unittest.main()
