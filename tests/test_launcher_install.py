import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from majestic_linux.core.config import RunnerConfig
from majestic_linux.runtime.launcher import wait_for_majestic_exe


class LauncherInstallTest(unittest.TestCase):
    def test_wait_for_majestic_exe_polls_until_file_appears(self):
        with tempfile.TemporaryDirectory() as tmp:
            compat = Path(tmp)
            exe = compat / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "MajesticLauncher" / "Majestic Launcher.exe"
            cfg = RunnerConfig(config_path=Path("x"))
            ticks = iter([0, 0, 1])

            def fake_sleep(_seconds):
                exe.parent.mkdir(parents=True, exist_ok=True)
                exe.write_text("", encoding="utf-8")

            with patch("majestic_linux.runtime.launcher.time.monotonic", side_effect=lambda: next(ticks)), \
                patch("majestic_linux.runtime.launcher.time.sleep", side_effect=fake_sleep):
                self.assertEqual(wait_for_majestic_exe(cfg, compat, timeout=1), exe)


if __name__ == "__main__":
    unittest.main()
