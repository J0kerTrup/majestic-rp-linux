import unittest
from pathlib import Path

from majestic_linux.core.config import RunnerConfig
from majestic_linux.runtime.input import input_env


class InputEnvTest(unittest.TestCase):
    def test_russian_locale_overrides_lc_all(self):
        env = input_env(RunnerConfig(config_path=Path("x")))
        self.assertEqual(env["LANG"], "ru_RU.UTF-8")
        self.assertEqual(env["LC_ALL"], "ru_RU.UTF-8")
        self.assertEqual(env["LC_CTYPE"], "ru_RU.UTF-8")

    def test_default_xkb_layout_has_russian(self):
        env = input_env(RunnerConfig(config_path=Path("x")))
        self.assertEqual(env["XKB_DEFAULT_LAYOUT"], "us,ru")
        self.assertEqual(env["XKB_DEFAULT_OPTIONS"], "grp:alt_shift_toggle")


if __name__ == "__main__":
    unittest.main()
