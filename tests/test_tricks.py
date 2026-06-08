import unittest
from pathlib import Path
from unittest.mock import patch

from majestic_linux.core.config import RunnerConfig
from majestic_linux.runtime.tricks import build_win10_plan, select_tricks_tool


def fake_tools(*names):
    return patch("majestic_linux.runtime.tricks.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name in names else None)


class TricksSelectionTest(unittest.TestCase):
    def test_steam_uses_protontricks(self):
        with fake_tools("protontricks", "winetricks"):
            self.assertEqual(select_tricks_tool("steam")[0], "protontricks")

    def test_egs_uses_winetricks(self):
        with fake_tools("protontricks", "winetricks"):
            self.assertEqual(select_tricks_tool("egs")[0], "winetricks")

    def test_rgl_prefers_available_protontricks(self):
        with fake_tools("protontricks", "winetricks"):
            self.assertEqual(select_tricks_tool("rgl")[0], "protontricks")

    def test_rgl_falls_back_to_winetricks(self):
        with fake_tools("winetricks"):
            self.assertEqual(select_tricks_tool("rgl")[0], "winetricks")

    def test_winetricks_plan_sets_wineprefix(self):
        config = RunnerConfig(config_path=Path("x"))
        with fake_tools("winetricks"):
            plan = build_win10_plan(config, "egs", Path("/tmp/compat"))
        self.assertEqual(plan.argv, ["winetricks", "-q", "win10"])
        self.assertEqual(plan.env["WINEPREFIX"], "/tmp/compat/pfx")


if __name__ == "__main__":
    unittest.main()
