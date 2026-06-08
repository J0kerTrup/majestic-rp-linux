import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from majestic_linux.core.config import RunnerConfig
from majestic_linux.discord.bridge import cache_path_for_url, find_discord_bridge, is_url


class DiscordBridgeTest(unittest.TestCase):
    def test_url_detection(self):
        self.assertTrue(is_url("https://example.test/bridge.exe"))
        self.assertFalse(is_url("/tmp/bridge.exe"))

    def test_cache_path_keeps_url_filename(self):
        path = cache_path_for_url("https://example.test/files/winediscordipcbridge.exe?x=1")
        self.assertEqual(path, Path("cache/winediscordipcbridge.exe"))

    def test_configured_local_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge = Path(tmp) / "bridge.exe"
            bridge.write_text("x")
            config = RunnerConfig(config_path=Path("x"), discord_bridge_path=str(bridge))
            self.assertEqual(find_discord_bridge(config, Path(tmp)), bridge)

    def test_configured_url_uses_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = RunnerConfig(config_path=Path("x"), discord_bridge_path="https://example.test/bridge.exe")
            with patch("majestic_linux.discord.bridge.download_bridge", return_value=Path("cache/bridge.exe")):
                self.assertEqual(find_discord_bridge(config, Path(tmp)), Path("cache/bridge.exe"))


if __name__ == "__main__":
    unittest.main()
