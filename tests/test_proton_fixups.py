import tempfile
import unittest
from pathlib import Path

from majestic_linux.core.config import RunnerConfig
from majestic_linux.runtime.fixups import apply_library_path, prepare_proton_runtime_fixups
from majestic_linux.runtime.proton import build_proton_command
from majestic_linux.runtime.wine import WineMapping


class ProtonFixupsTest(unittest.TestCase):
    def test_build_command_exports_cef_and_launcher_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = RunnerConfig(config_path=root / "majestic-runner.conf", runtime_library_paths=[root / "libs"])
            mapping = WineMapping(root / "pfx", root / "dosdevices", "g", root / "gta", "G:\\")
            cmd = build_proton_command(cfg, root / "proton", root / "compat", root / "steam", root / "Launcher.exe", "steam", mapping)
            self.assertEqual(cmd.env["MAJESTIC_DISABLE_CEF_GPU"], "1")
            self.assertIn("--disable-direct-composition", cmd.argv)
            self.assertIn(str(root / "libs"), cmd.env["LD_LIBRARY_PATH"])
            self.assertNotIn("GST_PLUGIN_PATH_1_0", cmd.env)

    def test_build_command_can_disable_winegstreamer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = RunnerConfig(config_path=root / "majestic-runner.conf", radio_disable_winegstreamer=True)
            mapping = WineMapping(root / "pfx", root / "dosdevices", "g", root / "gta", "G:\\")
            cmd = build_proton_command(cfg, root / "proton", root / "compat", root / "steam", root / "Launcher.exe", "steam", mapping)
            self.assertEqual(cmd.env["WINEDLLOVERRIDES"], "winegstreamer=d")

    def test_apply_library_path_prepends_paths(self):
        env = {"LD_LIBRARY_PATH": "/old"}
        apply_library_path(env, [Path("/new")])
        self.assertEqual(env["LD_LIBRARY_PATH"], "/new:/old")

    def test_prepare_fixup_returns_empty_without_proton_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            proton = Path(tmp) / "proton"
            proton.parent.mkdir(parents=True, exist_ok=True)
            self.assertEqual(prepare_proton_runtime_fixups(proton, dry_run=True), [])

if __name__ == "__main__":
    unittest.main()
