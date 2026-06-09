import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from majestic_linux.core.config import RunnerConfig
from majestic_linux.runtime.tricks import build_win10_plan, prefix_is_win10, select_tricks_tool


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
        self.assertEqual(plan.env["FC_FONTATIONS"], "0")

    def test_prefix_is_win10_checks_64_and_32_bit_registry_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            (prefix / "system.reg").write_text(
                '\n'.join(
                    [
                        'WINE REGISTRY Version 2',
                        '',
                        r'[Software\\Microsoft\\Windows NT\\CurrentVersion] 1',
                        '"CurrentMajorVersionNumber"=dword:0000000a',
                        '"ProductName"="Microsoft Windows 10"',
                        '',
                        r'[Software\\Wow6432Node\\Microsoft\\Windows NT\\CurrentVersion] 1',
                        '"CurrentMajorVersionNumber"=dword:0000000a',
                        '"ProductName"="Microsoft Windows 10"',
                    ]
                ),
                encoding="utf-8",
            )
            self.assertTrue(prefix_is_win10(prefix))


if __name__ == "__main__":
    unittest.main()
