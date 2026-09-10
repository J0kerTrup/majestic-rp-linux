import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deck/scripts'))
import setup_rockstar_prefix as setup
from majestic_linux.core.config_parser import parse_shell_config
from majestic_linux.runtime.proton import apply_launch_options


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.gta = self.home / 'Games/моя игра с пробелами'
        self.gta.mkdir(parents=True)
        (self.gta / 'gTa5.ExE').touch()
        self.pfx = self.home / 'compat/pfx'
        self.pfx.mkdir(parents=True)
        self.home_patch = patch.object(Path, 'home', return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def test_case_insensitive_executable_and_arbitrary_directory(self):
        with patch.object(setup, '_steam_libraries', return_value=[]):
            found = setup.find_gta_installations()
        self.assertIn(self.gta, [path for path, _ in found])

    def test_missing_explicit_game_does_not_fall_back(self):
        with self.assertRaises(ValueError):
            setup.choose_game(str(self.home / 'unplugged SD'), None)

    def test_multiple_games_require_choice(self):
        with patch.object(setup, 'find_gta_installations', return_value=[(self.gta, ''), (self.home, '')]), patch('sys.stdin.isatty', return_value=False):
            with self.assertRaises(ValueError):
                setup.choose_game(None, None)

    def test_conflicting_directory_blocks_before_mutations(self):
        conflict = self.pfx / 'drive_c/Program Files/Rockstar Games/Grand Theft Auto V'
        conflict.mkdir(parents=True)
        marker = conflict / 'keep'
        marker.write_text('important')
        with self.assertRaises(ValueError):
            setup.preflight(self.pfx, self.gta)
        self.assertEqual(marker.read_text(), 'important')
        self.assertFalse((self.pfx / 'dosdevices').exists())

    def test_game_already_at_link_location(self):
        game = self.pfx / 'drive_c/Program Files/Rockstar Games/Grand Theft Auto V'
        game.mkdir(parents=True)
        (game / 'GTA5.exe').touch()
        setup.preflight(self.pfx, game)
        setup.setup_symlinks(self.pfx, game)
        self.assertFalse(game.is_symlink())

    def test_registry_repeat_and_preserve(self):
        before = ('WINE REGISTRY Version 2\n\n[Software\\\\Rockstar Games\\\\Grand Theft Auto V]\n'
                  '"InstallFolder"="D:"\n"OtherValue"="keep"\n\n'
                  '[Software\\\\Valve\\\\Steam\\\\Apps\\\\271590]\n"Installed"=dword:00000001\n\n'
                  '[Unrelated]\n"Value"="unchanged"\n')
        for name in ('system.reg', 'user.reg'):
            (self.pfx / name).write_text(before)
        setup.patch_registry(self.pfx)
        first = (self.pfx / 'system.reg').read_bytes()
        setup.patch_registry(self.pfx)
        self.assertEqual(first, (self.pfx / 'system.reg').read_bytes())
        text = first.decode()
        self.assertIn('"OtherValue"="keep"', text)
        self.assertIn('[Unrelated]', text)
        self.assertNotIn('Apps\\\\271590', text)
        self.assertIn('"InstallFolder"="G:\\\\"', text)
        self.assertEqual((self.pfx / 'system.reg.before-deck-setup').read_text(), before)

    def test_registry_duplicate_blocks_collapsed(self):
        block = '\n[Software\\\\Rockstar Games\\\\Grand Theft Auto V]\n"InstallFolder"="G:"\n'
        for name in ('system.reg', 'user.reg'):
            (self.pfx / name).write_text('WINE REGISTRY Version 2\n' + block * 3)
        setup.patch_registry(self.pfx)
        text = (self.pfx / 'system.reg').read_text()
        self.assertEqual(text.count('[Software\\\\Rockstar Games\\\\Grand Theft Auto V]'), 1)

    def test_commandline_preservation_and_exact_migration(self):
        path = self.gta / 'commandline.txt'
        original = '-windowed\n' + setup.LEGACY_DNS_RULE + '\n--disable-ipv6\n'
        path.write_text(original)
        setup.setup_symlinks(self.pfx, self.gta)
        self.assertEqual(path.read_text(), '-windowed\n')
        self.assertEqual(path.with_name(path.name + '.before-deck-setup').read_text(), original)
        setup.setup_symlinks(self.pfx, self.gta)
        self.assertEqual(path.read_text(), '-windowed\n')

    def test_custom_commandline_untouched(self):
        path = self.gta / 'commandline.txt'
        path.write_text('--disable-ipv6\n-windowed\n')
        setup.setup_symlinks(self.pfx, self.gta)
        self.assertEqual(path.read_text(), '--disable-ipv6\n-windowed\n')

    def test_existing_auth_is_never_overwritten(self):
        dest = self.pfx / 'drive_c/users/steamuser/Documents/Rockstar Games'
        dest.mkdir(parents=True)
        (dest / 'profile').write_text('keep')
        self.assertFalse(setup.sync_social_club_auth(self.pfx))
        self.assertEqual((dest / 'profile').read_text(), 'keep')

    def test_config_preserves_custom_values_and_roundtrips_paths(self):
        config = self.home / 'runner.conf'
        config.write_text('# custom\nGAME_WIDTH=1440\nMAJESTIC_LAUNCH_OPTIONS="gamescope %command%"\n[repair]\nwheel_error_threshold=30\n')
        setup.configure(config, self.gta, self.home, self.home / 'Proton/proton', self.pfx)
        values = parse_shell_config(config)
        self.assertEqual(values['GAME_WIDTH'], '1440')
        self.assertEqual(values['GTA_PATH'], str(self.gta))
        self.assertEqual(values['MAJESTIC_LAUNCH_OPTIONS'], 'gamescope %command%')
        first = config.read_bytes()
        setup.configure(config, self.gta, self.home, self.home / 'Proton/proton', self.pfx)
        self.assertEqual(first, config.read_bytes())

    def test_legacy_launch_config_migration(self):
        import shlex
        config = self.home / 'runner.conf'
        old = setup.LEGACY_DNS_RULE + ' --disable-ipv6'
        config.write_text('MAJESTIC_LAUNCH_OPTIONS=' + shlex.quote(old) + '\nMAJESTIC_LAUNCHER_FLAGS=' + shlex.quote('--disable-gpu ' + old) + '\n')
        setup.configure(config, self.gta, self.home, self.home / 'Proton/proton', self.pfx)
        values = parse_shell_config(config)
        self.assertEqual(values['MAJESTIC_LAUNCH_OPTIONS'], '')
        self.assertEqual(values['MAJESTIC_LAUNCHER_FLAGS'], '--disable-gpu')

    def test_application_flags_and_wrappers(self):
        command = ['/proton', 'waitforexitandrun', 'Launcher.exe']
        env = {}
        self.assertEqual(apply_launch_options(command, env, 'FOO=bar --disable-ipv6'), command + ['--disable-ipv6'])
        self.assertEqual(env['FOO'], 'bar')
        self.assertEqual(apply_launch_options(command, {}, 'gamescope -f %command%'), ['gamescope', '-f'] + command)
        self.assertEqual(apply_launch_options(command, {}, 'gamescope -f'), ['gamescope', '-f'] + command)

    def test_failed_atomic_replace_preserves_original(self):
        path = self.home / 'settings'
        path.write_text('old')
        with patch.object(os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                setup.atomic_write(path, 'new')
        self.assertEqual(path.read_text(), 'old')
        self.assertEqual(list(self.home.glob('.settings*')), [])

class DownloadTests(unittest.TestCase):
    def test_interrupted_download_does_not_poison_cache(self):
        from majestic_linux.core.config import RunnerConfig
        from majestic_linux.runtime.launcher import ensure_installer
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = RunnerConfig(config_path=root / 'config', installer_path=root / 'setup.exe')
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.side_effect = [b'partial', OSError('connection lost')]
            with patch('urllib.request.urlopen', return_value=response):
                with self.assertRaises(OSError):
                    ensure_installer(cfg, root, dry_run=False)
            self.assertFalse(cfg.installer_path.exists())
            self.assertEqual(list(root.glob('.majestic-download-*')), [])

    def test_complete_download_is_cached(self):
        from majestic_linux.core.config import RunnerConfig
        from majestic_linux.runtime.launcher import ensure_installer
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = RunnerConfig(config_path=root / 'config', installer_path=root / 'setup.exe')
            response = MagicMock()
            response.__enter__.return_value = response
            response.headers = {'Content-Length': '4'}
            response.read.side_effect = [b'data', b'']
            with patch('urllib.request.urlopen', return_value=response):
                path = ensure_installer(cfg, root, dry_run=False)
            self.assertEqual(path.read_bytes(), b'data')


class CommandLineTests(unittest.TestCase):
    def test_fresh_custom_home_check_configure_and_repeat(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            steam = home / '.local/share/Steam'
            proton = steam / 'steamapps/common/Proton Experimental/proton'
            proton.parent.mkdir(parents=True)
            proton.write_text('#!/bin/sh\nexit 0\n')
            proton.chmod(0o700)
            game = home / 'Games/Grand theft auto v'
            game.mkdir(parents=True)
            (game / 'GTA5.exe').touch()
            config = home / '.config/majestic-runner/majestic-runner.conf'
            env = {k: v for k, v in os.environ.items() if k not in {'GTA_PATH', 'STEAM_ROOT', 'STEAM_COMPAT_DATA_PATH', 'PROTON_PATH', 'WINEPREFIX'}}
            env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), PYTHONDONTWRITEBYTECODE='1')
            command = [sys.executable, str(setup.REPO_ROOT / 'deck/scripts/setup_rockstar_prefix.py')]
            def run(*args):
                result = subprocess.run(command + list(args), env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result
            run('--check')
            self.assertFalse(config.exists())
            self.assertFalse((steam / 'steamapps/compatdata').exists())
            run('--configure')
            values = parse_shell_config(config)
            self.assertEqual(values['GTA_PATH'], str(game))
            compat = Path(values['STEAM_COMPAT_DATA_PATH'])
            self.assertTrue(compat.is_dir())
            pfx = compat / 'pfx'
            pfx.mkdir()
            for name in ('system.reg', 'user.reg'):
                (pfx / name).write_text('WINE REGISTRY Version 2\n')
            run()
            first = (pfx / 'system.reg').read_bytes()
            run()
            self.assertEqual(first, (pfx / 'system.reg').read_bytes())


class ShortcutTests(unittest.TestCase):
    def test_vdf_roundtrip_and_truncation(self):
        from add_steam_shortcut import parse_vdf_dict, serialize_vdf_dict
        root = {'shortcuts': {'3': {'AppName': 'Игра', 'appid': -123}}}
        encoded = serialize_vdf_dict(root) + b'\x08'
        self.assertEqual(parse_vdf_dict(encoded)[0], root)
        with self.assertRaises(ValueError):
            parse_vdf_dict(b'\x01broken')


if __name__ == '__main__':
    unittest.main()
