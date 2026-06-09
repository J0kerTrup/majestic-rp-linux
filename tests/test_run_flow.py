import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from majestic_linux.app.actions import cmd_run
from majestic_linux.app.context import AppContext
from majestic_linux.core.config import RunnerConfig
from majestic_linux.detection.paths import DetectionResult
from majestic_linux.discord.bridge import DiscordBridge
from majestic_linux.runtime.wine import WineMapping


class RunFlowTest(unittest.TestCase):
    def test_discord_bridge_is_started_with_keyword_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RunnerConfig(config_path=root / "majestic-runner.conf", dry_run=True)
            result = DetectionResult(
                steam_root=root / "steam",
                proton_path=root / "proton",
                compatdata_path=root / "compatdata",
                gta_path=root / "gta",
                majestic_exe=root / "Majestic Launcher.exe",
                detected_platform="steam",
                selected_platform="steam",
            )
            result.gta_path.mkdir()
            result.compatdata_path.mkdir()
            result.majestic_exe.write_text("", encoding="utf-8")
            mapping = WineMapping(result.compatdata_path / "pfx", result.compatdata_path / "pfx" / "dosdevices", "g", result.gta_path, "G:\\")
            context = AppContext(config, result)

            with patch("majestic_linux.app.actions.load_context", return_value=(context, Mock())), \
                patch("majestic_linux.app.actions.prepare_wine_mapping", return_value=mapping), \
                patch("majestic_linux.app.actions.apply_xkb_layout"), \
                patch("majestic_linux.app.actions.apply_win10_mode"), \
                patch("majestic_linux.app.actions.patch_js_tree"), \
                patch("majestic_linux.app.actions.run_proton_managed", return_value=0), \
                patch("majestic_linux.app.actions.stop_discord_bridge"), \
                patch("majestic_linux.app.actions.start_discord_bridge", return_value=DiscordBridge()) as start:
                code = cmd_run(argparse.Namespace(debug=False, dry_run=True, config=str(config.config_path)))

            self.assertEqual(code, 0)
            self.assertEqual(start.call_args.kwargs["compatdata"], result.compatdata_path)
            self.assertEqual(start.call_args.kwargs["proton_path"], result.proton_path)


if __name__ == "__main__":
    unittest.main()
