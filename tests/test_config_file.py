import tempfile
import unittest
from pathlib import Path

from majestic_linux.core.config import load_config
from majestic_linux.core.config_file import ensure_config_file


class ConfigFileTest(unittest.TestCase):
    def test_ensure_config_file_creates_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "majestic-runner.conf"
            self.assertTrue(ensure_config_file(path))
            self.assertIn("MAJESTIC_PLATFORM=auto", path.read_text(encoding="utf-8"))

    def test_load_config_auto_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "majestic-runner.conf"
            cfg = load_config(path)
            self.assertEqual(cfg.config_path, path)
            self.assertTrue(path.exists())
            self.assertTrue(cfg.auto_detect)

    def test_load_config_reads_shutdown_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "majestic-runner.conf"
            path.write_text("[shutdown]\nkill_wine_on_exit=false\nkill_timeout_seconds=3\n", encoding="utf-8")
            cfg = load_config(path)
            self.assertFalse(cfg.kill_wine_on_exit)
            self.assertEqual(cfg.kill_timeout_seconds, 3)

    def test_load_config_reads_radio_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "majestic-runner.conf"
            path.write_text("[radio]\nsafe_mode=true\nanalyze_cef=false\ndisable_winegstreamer=true\n", encoding="utf-8")
            cfg = load_config(path)
            self.assertTrue(cfg.radio_safe_mode)
            self.assertFalse(cfg.radio_analyze_cef)
            self.assertTrue(cfg.radio_disable_winegstreamer)


if __name__ == "__main__":
    unittest.main()
