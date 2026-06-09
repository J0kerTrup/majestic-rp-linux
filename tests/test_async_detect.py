import unittest
from pathlib import Path

from majestic_linux.core.config import RunnerConfig
from majestic_linux.detection.async_paths import detect_all_async


class AsyncDetectTest(unittest.IsolatedAsyncioTestCase):
    async def test_async_detect_respects_disabled_auto_detect(self):
        cfg = RunnerConfig(config_path=Path("x"), auto_detect=False)
        result = await detect_all_async(cfg)
        self.assertIsNone(result.steam_root)
        self.assertIsNone(result.proton_path)
        self.assertIsNone(result.compatdata_path)
        self.assertIsNone(result.gta_path)
        self.assertEqual(result.selected_platform, "rgl")


if __name__ == "__main__":
    unittest.main()
