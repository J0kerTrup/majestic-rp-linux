import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from majestic_linux.core.config import RunnerConfig
from majestic_linux.detection.paths import find_gta_path, find_majestic_exe, find_steam_root
from majestic_linux.runtime.wine import wine_path_for


class PathDetectTest(unittest.TestCase):
    def test_env_gta_path_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            gta = Path(tmp) / "GTA"
            gta.mkdir()
            (gta / "GTA5.exe").write_text("")
            cfg = RunnerConfig(config_path=Path("x"), gta_path=gta)
            self.assertEqual(find_gta_path(cfg, None), gta)

    def test_steam_root_common_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            steam = Path(tmp) / ".local" / "share" / "Steam"
            steam.mkdir(parents=True)
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                self.assertEqual(find_steam_root(RunnerConfig(config_path=Path("x"))), steam)

    def test_heroic_path_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            heroic = Path(tmp) / "Games" / "Heroic" / "Grand Theft Auto V"
            heroic.mkdir(parents=True)
            (heroic / "GTA5.exe").write_text("")
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                self.assertEqual(find_gta_path(RunnerConfig(config_path=Path("x")), None), heroic)

    def test_majestic_local_appdata_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            compat = Path(tmp)
            exe = compat / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "MajesticLauncher" / "Majestic Launcher.exe"
            exe.parent.mkdir(parents=True)
            exe.write_text("")
            self.assertEqual(find_majestic_exe(RunnerConfig(config_path=Path("x")), compat), exe)

    def test_wine_mapped_gta_path_is_drive_root(self):
        self.assertEqual(wine_path_for(Path("/home/user/GTA"), "g"), "G:\\")


if __name__ == "__main__":
    unittest.main()
