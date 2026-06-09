import tempfile
import unittest
from pathlib import Path

from majestic_linux.core.errors import PatchError
from majestic_linux.patching.patcher import patch_js_tree, patch_text, worker_adapter


class JsPatcherTest(unittest.TestCase):
    def make_extracted(self, root: Path, index_text: str) -> Path:
        main = root / "dist" / "electron" / "main"
        main.mkdir(parents=True)
        (main / "index.js").write_text(index_text, encoding="utf-8")
        return root

    def test_legacy_array_gets_steam(self):
        text, changed = patch_text('const p = ["rgl","egs"];')
        self.assertTrue(changed)
        self.assertIn('["steam","rgl","egs"]', text)
        self.assertNotIn('["rgl","egs"]', text)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_extracted(Path(tmp), 'const p = ["rgl","egs"];')
            file = root / "dist" / "electron" / "main" / "index.js"
            patch_js_tree(root)
            once = file.read_text(encoding="utf-8")
            patch_js_tree(root)
            self.assertEqual(once, file.read_text(encoding="utf-8"))

    def test_current_array_is_not_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_extracted(Path(tmp), 'const p = ["steam","rgl","egs"];')
            file = root / "dist" / "electron" / "main" / "index.js"
            before = file.read_text(encoding="utf-8")
            patch_js_tree(root)
            self.assertEqual(before, file.read_text(encoding="utf-8"))
            self.assertIn("steam", file.read_text(encoding="utf-8"))

    def test_absence_of_steam_after_patch_is_error(self):
        with self.assertRaises(PatchError):
            patch_text('const p = someCheck("rgl","egs");')

    def test_worker_adapter_contains_native_platform(self):
        text = worker_adapter("1,3,4")
        self.assertIn("nativePlatform", text)
        self.assertIn("'steam', 'rgl', 'egs'", text)

    def test_direct_index_hook_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_extracted(
                Path(tmp),
                'let Lc=!1,uf=!1;function x(){Ic.patchMultiplayerWithProgress(e,n=>{re("patcher_setPhase",n)})}',
            )
            patch_js_tree(root)
            text = (root / "dist" / "electron" / "main" / "index.js").read_text(encoding="utf-8")
            self.assertIn("JO_patchMultiplayerWithProgress", text)
            self.assertIn("JO_PROTON_NATIVE_PLATFORM", text)


if __name__ == "__main__":
    unittest.main()
