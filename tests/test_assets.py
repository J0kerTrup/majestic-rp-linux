import tempfile
import unittest
from pathlib import Path

from majestic_linux.runtime.assets import inspect_launcher_assets


class AssetInspectTest(unittest.TestCase):
    def test_finds_fonts_icons_and_broken_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            (root / "assets" / "icon.svg").write_text("<svg />", encoding="utf-8")
            (root / "assets" / "icons.woff2").write_text("", encoding="utf-8")
            css = "@font-face{src:url('./assets/icons.woff2')} .x{background:url('./missing.svg')}"
            (root / "style.css").write_text(css, encoding="utf-8")
            report = inspect_launcher_assets(root)
            self.assertEqual(len(report.fonts), 1)
            self.assertEqual(len(report.icons), 1)
            self.assertEqual(len(report.font_faces), 1)
            self.assertEqual(len(report.broken_urls), 1)


if __name__ == "__main__":
    unittest.main()
