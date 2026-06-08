import tempfile
import unittest
from pathlib import Path

from majestic_linux.detection.platform import detect_gta_platform, select_platform


class PlatformDetectTest(unittest.TestCase):
    def test_detect_egs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "EOSSDK-Win64-Shipping.dll").write_text("")
            self.assertEqual(detect_gta_platform(root), "egs")

    def test_detect_steam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "steam_api64.dll").write_text("")
            self.assertEqual(detect_gta_platform(root), "steam")

    def test_detect_rgl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "GTAVLauncher.exe").write_text("")
            self.assertEqual(detect_gta_platform(root), "rgl")

    def test_fallback_rgl(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_gta_platform(Path(tmp)), "rgl")

    def test_explicit_is_respected(self):
        self.assertEqual(select_platform("egs", "steam", True), "egs")


if __name__ == "__main__":
    unittest.main()
