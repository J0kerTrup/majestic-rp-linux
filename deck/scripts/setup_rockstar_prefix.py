#!/usr/bin/env python3
"""Repeatable Steam Deck setup. --check is read-only; --configure saves paths."""
from __future__ import annotations

import argparse
import fcntl
import os
import re
import shlex
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from majestic_linux.core.config import RunnerConfig
from majestic_linux.core.config_file import default_config_path
from majestic_linux.core.config_parser import parse_shell_config
from majestic_linux.detection.paths import find_steam_root, find_proton, _steam_libraries
from majestic_linux.detection.platform import detect_gta_platform


def atomic_write(path: Path, text: str | bytes) -> None:
    """Keep the first pre-setup copy; replace a complete file on the same filesystem."""
    if path.is_symlink():
        path = path.resolve(strict=True)
    data = text.encode('utf-8') if isinstance(text, str) else text
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + '.before-deck-setup')
        if not backup.exists():
            shutil.copy2(path, backup)
            backup.chmod(0o600)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def looks_like_legacy(path: Path) -> bool:
    if not path.is_dir():
        return False
    names = {p.name.casefold() for p in path.iterdir() if p.is_file()}
    return 'gta5.exe' in names


def find_gta_installations(steam_root: Path | None = None) -> list[tuple[Path, str]]:
    roots = [Path.home() / 'Games', Path.home() / 'Downloads']
    roots += [p / 'steamapps/common' for p in _steam_libraries(steam_root)]
    pp = Path.home() / '.var/app/ru.linux_gaming.PortProton/data/prefixes'
    if pp.exists():
        roots += list(pp.glob('*/drive_c/Program Files/Rockstar Games'))
    # Only bounded, conventional mount locations; never recursively scan a whole SD card.
    media = Path('/run/media')
    if media.exists():
        mounts = list(media.glob('*')) + list(media.glob('*/*'))
        for mount in mounts:
            roots += [mount, mount / 'Games', mount / 'steamapps/common', mount / 'SteamLibrary/steamapps/common']
    found = {}
    for directory in dict.fromkeys(roots):
        try:
            if directory.is_dir():
                for candidate in directory.iterdir():
                    if looks_like_legacy(candidate):
                        found[candidate.resolve()] = str(directory)
        except OSError:
            continue
    return sorted(found.items(), key=lambda item: str(item[0]).casefold())


def choose_game(explicit: str | None, steam_root: Path | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not looks_like_legacy(path):
            raise ValueError(f'В выбранной папке нет GTA5.exe: {path}. Проверьте путь и подключение SD-карты.')
        return path.resolve()
    candidates = find_gta_installations(steam_root)
    if len(candidates) == 1:
        return candidates[0][0]
    if candidates:
        print('Найдено несколько установок:')
        for index, (path, _) in enumerate(candidates, 1):
            print(f'  {index}) {path}')
    if not sys.stdin.isatty():
        raise ValueError('Укажите папку GTA V Legacy: --gta-path ПУТЬ или GTA_PATH. Автоматический выбор неоднозначен либо игра не найдена.')
    value = input('Введите полный путь к GTA V Legacy' + (' или номер установки' if candidates else '') + ': ').strip()
    if value.isdigit() and 1 <= int(value) <= len(candidates):
        return candidates[int(value)-1][0]
    if not value:
        raise ValueError('Папка игры не выбрана.')
    return choose_game(value, steam_root)


def ensure_writable(path: Path) -> None:
    ancestor = path
    while not ancestor.exists():
        if ancestor.is_symlink():
            raise ValueError(f'Нерабочая ссылка: {ancestor}')
        ancestor = ancestor.parent
    if not os.access(ancestor, os.W_OK | os.X_OK):
        raise ValueError(f'Нет доступа на запись: {ancestor}')


def check_prefix_idle(pfx: Path) -> None:
    # Registry files must not be edited while Wine can flush an older in-memory copy.
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            environ = (proc / 'environ').read_bytes().split(b'\0')
            for value in environ:
                if value.startswith(b'WINEPREFIX='):
                    if Path(os.fsdecode(value.split(b'=', 1)[1])).resolve() == pfx.resolve():
                        raise ValueError('Закройте игру и процессы Wine этого префикса перед настройкой.')
        except (OSError, PermissionError):
            continue


def link_targets(pfx: Path, gta_path: Path) -> list[tuple[Path, Path]]:
    rg = pfx / 'drive_c/Program Files/Rockstar Games'
    return [(pfx / 'dosdevices/g:', gta_path)] + [(rg / name, gta_path) for name in ('Grand Theft Auto V', 'Grand Theft Auto V Legacy')]


def preflight(pfx: Path, gta_path: Path) -> None:
    ensure_writable(pfx)
    ensure_writable(gta_path)
    check_prefix_idle(pfx)
    for target, source in link_targets(pfx, gta_path):
        if target.exists() and not target.is_symlink() and target.resolve() != source.resolve():
            raise ValueError(f'На месте ссылки находится настоящий файл или каталог: {target}. Он сохранён; выберите другой префикс или устраните конфликт вручную.')
        if target.is_symlink() and target.resolve() != source.resolve():
            raise ValueError(f'Ссылка уже ведёт к другой установке: {target} -> {target.resolve()}. Выберите соответствующий префикс.')
        ensure_writable(target.parent)
    for filename in ('system.reg', 'user.reg'):
        path = pfx / filename
        if path.exists():
            if not path.read_text(encoding='utf-8').startswith('WINE REGISTRY Version 2'):
                raise ValueError(f'Неизвестный формат реестра: {path}')


def sync_social_club_auth(dst_pfx: Path) -> bool:
    """Import only into an empty destination; saved credentials are not proof of login."""
    relative = [Path('drive_c/users/steamuser') / part / 'Rockstar Games'
                for part in ('AppData/Local', 'Documents')]
    if any((dst_pfx / part).exists() for part in relative):
        print('[+] Данные Rockstar уже существуют: оставлены без изменений.')
        return False
    pp = Path.home() / '.var/app/ru.linux_gaming.PortProton/data/prefixes'
    sources = sorted(p for p in pp.glob('*') if (p / relative[1] / 'Social Club/Profiles/autosignin.dat').is_file())
    if len(sources) != 1:
        print('[*] Однозначный источник авторизации не найден. Войдите в Rockstar при запуске.')
        return False
    for part in relative:
        source = sources[0] / part
        if source.is_dir():
            shutil.copytree(source, dst_pfx / part)
    print('[+] Скопированы сохранённые данные Rockstar. Возможность входа проверяется лаунчером.')
    return True


def setup_symlinks(pfx: Path, gta_path: Path) -> None:
    for target, source in link_targets(pfx, gta_path):
        if target.is_symlink() and target.resolve() == source.resolve():
            continue
        if target.exists() and target.resolve() == source.resolve():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source)
    # Remove only the exact old generated workaround, retaining other user options.
    cmdline = gta_path / 'commandline.txt'
    if cmdline.exists():
        text = cmdline.read_text(encoding='utf-8')
        lines = text.splitlines(keepends=True)
        owned = [line for line in lines if line.strip() == LEGACY_DNS_RULE]
        if owned:
            atomic_write(cmdline, ''.join(line for line in lines if line not in owned and line.strip() != '--disable-ipv6'))


DXVK_CONF_CONTENT = (
    "# DXVK memory limit configuration for GTA V on Steam Deck\n"
    "# Prevents RAGE engine from over-allocating unified APU memory\n\n"
    "# Cap reported VRAM to 3072 MB (3 GB) instead of 6 GB\n"
    "# This forces GTA V to aggressively unload cached cars/clothes/textures\n"
    "dxgi.maxDeviceMemory = 3072\n"
    "dxgi.maxSharedMemory = 2048\n\n"
    "# Optimize dynamic image buffers\n"
    "d3d11.maxDynamicImageBufferSize = 64\n"
)


def setup_dxvk_config(pfx: Path, gta_path: Path) -> None:
    targets = [
        gta_path / 'dxvk.conf',
        pfx / 'drive_c/users/steamuser/AppData/Roaming/majestic-launcher/Multiplayer/backup/dxvk.conf',
    ]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, DXVK_CONF_CONTENT)


LEGACY_DNS_RULE = '--host-resolver-rules="MAP cdn.majestic-files.net cdn.majestic-files.com, MAP cdn-world.majestic-files.net cdn.majestic-files.com, MAP api.majestic-files.net api.majestic-files.com, MAP *.majestic-files.net *.majestic-files.com"'


def patch_registry(pfx: Path) -> None:
    keys = [r'Software\\Rockstar Games\\Grand Theft Auto V', r'Software\\Wow6432Node\\Rockstar Games\\Grand Theft Auto V']
    conflicts = [r'Software\\Valve\\Steam\\Apps\\271590', r'Software\\Wow6432Node\\Valve\\Steam\\Apps\\271590']
    for filename in ('system.reg', 'user.reg'):
        path = pfx / filename
        if not path.exists():
            raise ValueError(f'Префикс не инициализирован: {path}. Сначала установите лаунчер (пункт 5).')
        text = path.read_text(encoding='utf-8')
        for key in conflicts:
            text = re.sub(r'\n\[' + re.escape(key) + r'\][^\n]*\n.*?(?=\n\[|\Z)', '', text, flags=re.S)
        for key in keys:
            pattern = r'\n\[' + re.escape(key) + r'\][^\n]*\n(.*?)(?=\n\[|\Z)'
            blocks = list(re.finditer(pattern, text, re.S))
            # Merge repeated old blocks, preserving values unrelated to InstallFolder.
            values = {}
            for block in blocks:
                for line in block.group(1).splitlines():
                    if line and not line.startswith('"InstallFolder"='):
                        values[line.split('=', 1)[0]] = line
            text = re.sub(pattern, '', text, flags=re.S)
            body = '\n'.join([*values.values(), '"InstallFolder"="G:\\\\"'])
            text = text.rstrip('\n') + f'\n\n[{key}]\n{body}\n'
        atomic_write(path, text)


def configure(path: Path, gta: Path, steam: Path, proton: Path, pfx: Path) -> None:
    template = (REPO_ROOT / 'deck/majestic-runner.defaults.conf').read_text()
    original = path.read_text() if path.exists() else template
    current = parse_shell_config(path)
    updates = {'GTA_PATH': str(gta), 'STEAM_ROOT': str(steam), 'PROTON_PATH': str(proton), 'STEAM_COMPAT_DATA_PATH': str(pfx.parent)}
    # Precisely migrate the old generated command. Custom flags are retained.
    old = LEGACY_DNS_RULE + ' --disable-ipv6'
    if current.get('MAJESTIC_LAUNCH_OPTIONS') == old:
        updates['MAJESTIC_LAUNCH_OPTIONS'] = ''
    flags = current.get('MAJESTIC_LAUNCHER_FLAGS', '')
    if flags.endswith(' ' + old):
        updates['MAJESTIC_LAUNCHER_FLAGS'] = flags[:-len(' ' + old)]
    for key, value in updates.items():
        line = key + '=' + shlex.quote(value)
        pattern = r'^' + re.escape(key) + r'=.*$'
        if re.search(pattern, original, re.M):
            original = re.sub(pattern, lambda _: line, original, flags=re.M)
        else:
            # Global keys must precede [shutdown]/[repair].
            original = line + '\n' + original
    pfx.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, original)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gta-path')
    parser.add_argument('--prefix', help='Path ending in pfx, or its compatdata parent')
    parser.add_argument('--config', type=Path, default=default_config_path())
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--configure', action='store_true')
    args = parser.parse_args()
    values = parse_shell_config(args.config)
    cfg = RunnerConfig(config_path=args.config)
    for attr, key in [('steam_root', 'STEAM_ROOT'), ('proton_path', 'PROTON_PATH')]:
        value = os.environ.get(key, values.get(key))
        if value:
            setattr(cfg, attr, Path(value).expanduser())
    steam = find_steam_root(cfg)
    if steam is None:
        raise ValueError('Steam не найден. Запустите Steam или задайте STEAM_ROOT.')
    proton = find_proton(cfg, steam)
    if proton is None:
        raise ValueError('Proton не найден. Установите Proton Experimental через Steam.')
    gta = choose_game(args.gta_path or os.environ.get('GTA_PATH') or values.get('GTA_PATH'), steam)
    if detect_gta_platform(gta) != 'rgl':
        raise ValueError('Этот мастер предназначен для Rockstar Edition. Для Steam/Epic используйте основной раннер: README.md.')
    raw = args.prefix or os.environ.get('STEAM_COMPAT_DATA_PATH') or values.get('STEAM_COMPAT_DATA_PATH')
    compat = Path(raw).expanduser() if raw else steam / 'steamapps/compatdata/271590'
    pfx = compat if compat.name == 'pfx' else compat / 'pfx'
    pfx = pfx.resolve()
    preflight(pfx, gta)
    print(f'Игра: {gta}\nПрефикс: {pfx}\nProton: {proton}')
    if args.check:
        print('[+] Предварительные проверки пройдены. Изменений нет.')
        return
    # Serialize setup processes before changing any files, then repeat preflight.
    lock_path = Path(os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir())) / f'majestic-deck-setup-{os.getuid()}.lock'
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Другой процесс настройки уже запущен.')
        preflight(pfx, gta)
        if args.configure:
            configure(args.config, gta, steam, proton, pfx)
            print('[+] Конфигурация сохранена; пользовательские параметры сохранены.')
            return
        for filename in ('system.reg', 'user.reg'):
            if not (pfx / filename).is_file():
                raise ValueError('Сначала инициализируйте префикс установкой лаунчера (пункт 5).')
        sync_social_club_auth(pfx)
        setup_symlinks(pfx, gta)
        setup_dxvk_config(pfx, gta)
        patch_registry(pfx)
        print('[+] Настройка завершена. Вход Rockstar и подключение Majestic проверяются запуском игры.')


if __name__ == '__main__':
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print('[!] Настройка прервана пользователем.', file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError) as exc:
        print(f'[!] {exc}', file=sys.stderr)
        sys.exit(1)
