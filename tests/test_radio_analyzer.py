import tempfile
import unittest
from pathlib import Path

from majestic_linux.radio.log_analyzer import analyze_logs


class RadioAnalyzerTest(unittest.TestCase):
    def test_ranks_cef_and_gstreamer_causes(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "launcher.log"
            log.write_text("CEF gpu process crash\nwinegstreamer exception during radio stream\n", encoding="utf-8")
            analysis = analyze_logs([log])
            titles = [cause.title for cause in analysis.causes]
            self.assertIn("CEF/Chromium media or GPU crash", titles)
            self.assertIn("Missing multimedia codec or GStreamer plugin", titles)
            self.assertGreaterEqual(len(analysis.hits), 3)

    def test_ranks_proton_gstreamer_dependency_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "proton-run.log"
            log.write_text("Failed to load plugin libgstlibav.so: libbz2.so.1.0: cannot open shared object file\n", encoding="utf-8")
            analysis = analyze_logs([log])
            self.assertEqual(analysis.causes[0].title, "Proton GStreamer dependency failure")


if __name__ == "__main__":
    unittest.main()
