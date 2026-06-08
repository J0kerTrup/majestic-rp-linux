import tempfile
import unittest
from pathlib import Path

from majestic_linux.runtime.cleanup import find_majestic_cleanup_candidates


class CleanupTest(unittest.TestCase):
    def test_cleanup_includes_regular_and_global_launcher_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            compat = Path(tmp)
            local = compat / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local"
            regular = local / "MajesticLauncher"
            global_dir = local / "MajesticLauncherGLOBAL"
            regular.mkdir(parents=True)
            global_dir.mkdir(parents=True)

            paths = {candidate.path for candidate in find_majestic_cleanup_candidates(compat)}

            self.assertIn(regular, paths)
            self.assertIn(global_dir, paths)


if __name__ == "__main__":
    unittest.main()
