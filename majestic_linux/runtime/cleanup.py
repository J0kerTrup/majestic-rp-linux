from __future__ import annotations

import glob
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..detection.paths import MAJESTIC_LOCAL_DIRS


@dataclass(frozen=True, slots=True)
class CleanupCandidate:
    path: Path
    reason: str


@dataclass(frozen=True, slots=True)
class UninstallCleanupOptions:
    include_trash: bool = False
    include_installers: bool = False
    include_projects: bool = False
    home: Path | None = None
    project_root: Path | None = None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
    except OSError:
        return False


def _is_protected_gta_path(path: Path, gta_path: Path | None) -> bool:
    if gta_path is None:
        return False
    if _is_relative_to(path, gta_path):
        return True
    if path.is_symlink():
        try:
            return _is_relative_to(path.resolve(), gta_path)
        except OSError:
            return False
    return False


def _is_protected_target(path: Path, gta_path: Path | None, protected_roots: list[Path] | None = None) -> bool:
    protected_roots = protected_roots or []
    dangerous = [Path("/"), *protected_roots]
    for root in dangerous:
        if path == root:
            return True
    if _is_protected_gta_path(path, gta_path):
        return True
    text = str(path)
    return any(token in text for token in ("/steamapps/common", "/Grand Theft Auto V", "/GTA V", "/GTA5.exe"))


def _existing(paths: list[tuple[Path, str]], gta_path: Path | None, protected_roots: list[Path] | None = None) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    seen: set[Path] = set()
    for path, reason in paths:
        if not path.exists() and not path.is_symlink():
            continue
        if _is_protected_target(path, gta_path, protected_roots):
            continue
        if _is_protected_gta_path(path, gta_path):
            continue
        resolved_key = path.resolve() if path.exists() else path.absolute()
        if resolved_key in seen:
            continue
        seen.add(resolved_key)
        candidates.append(CleanupCandidate(path, reason))
    filtered: list[CleanupCandidate] = []
    for candidate in candidates:
        covered_by_parent = False
        for parent in candidates:
            if parent == candidate or not parent.path.is_dir() or parent.path.is_symlink():
                continue
            if _is_relative_to(candidate.path, parent.path):
                covered_by_parent = True
                break
        if not covered_by_parent:
            filtered.append(candidate)
    return sorted(filtered, key=lambda item: str(item.path).lower())


def find_majestic_cleanup_candidates(compatdata: Path, gta_path: Path | None = None) -> list[CleanupCandidate]:
    pfx = compatdata / "pfx"
    drive_c = pfx / "drive_c"
    paths: list[tuple[Path, str]] = []

    for user_dir in (drive_c / "users").glob("*"):
        local = user_dir / "AppData" / "Local"
        roaming = user_dir / "AppData" / "Roaming"
        desktop = user_dir / "Desktop"
        start_menu = roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        paths.extend(
            [
                *[(local / dirname, "Majestic Launcher install directory") for dirname in MAJESTIC_LOCAL_DIRS],
                (local / "majestic-launcher-updater", "Majestic updater cache"),
                (roaming / "majestic-launcher", "Majestic roaming cache and multiplayer data"),
                (desktop / "Majestic Launcher.lnk", "Majestic desktop shortcut"),
                (start_menu / "Majestic Launcher.lnk", "Majestic start menu shortcut"),
            ]
        )

    proton_shortcuts = drive_c / "proton_shortcuts"
    paths.append((drive_c / "Games" / "MAJESTIC_GTA", "Majestic GTA multiplayer folder"))
    paths.append((proton_shortcuts / "Majestic Launcher.desktop", "Proton shortcut"))
    paths.extend((path, "Proton shortcut icon") for path in proton_shortcuts.glob("icons/*/apps/*Majestic*.png"))
    paths.append((drive_c / "MajesticLauncherSetup.exe", "Majestic installer cache"))

    for dirname in MAJESTIC_LOCAL_DIRS:
        for launcher_dir in (drive_c / "users").glob(f"*/AppData/Local/{dirname}"):
            resources = launcher_dir / "resources"
            paths.extend(
                [
                    (resources / "app.asar.bak", "Majestic app.asar backup"),
                    (resources / "app.asar.majestic-proton-bak", "Legacy Majestic app.asar backup"),
                ]
            )
            paths.extend((path, "Python patch backup") for path in launcher_dir.rglob("*.majestic-python-bak"))

    return _existing(paths, gta_path)


def find_majestic_uninstall_candidates(
    *,
    compatdata: Path | None = None,
    gta_path: Path | None = None,
    steam_root: Path | None = None,
    majestic_exe: Path | None = None,
    options: UninstallCleanupOptions | None = None,
) -> list[CleanupCandidate]:
    options = options or UninstallCleanupOptions()
    home = options.home or Path.home()
    project_root = options.project_root or Path.cwd()
    paths: list[tuple[Path, str]] = []
    protected_roots = [home, project_root]
    if steam_root:
        protected_roots.append(steam_root)

    _add_native_targets(paths, home)
    if majestic_exe and majestic_exe.exists():
        launcher_dir = majestic_exe.parent
        paths.append((launcher_dir, "Majestic Launcher install directory"))
        _add_windows_user_targets(paths, _windows_user_dir(majestic_exe))
    if compatdata:
        paths.extend((candidate.path, candidate.reason) for candidate in find_majestic_cleanup_candidates(compatdata, gta_path))
    for root in _steam_roots(home, steam_root):
        protected_roots.append(root)
        for compat in _compatdata_roots(root):
            if _compatdata_looks_majestic(compat):
                paths.extend((candidate.path, candidate.reason) for candidate in find_majestic_cleanup_candidates(compat, gta_path))
    _add_installer_cache_targets(paths, home)
    if options.include_installers:
        _add_installer_targets(paths, home)
    if options.include_trash:
        _add_trash_targets(paths, home)
    if options.include_projects:
        _add_project_targets(paths, home)
    return _existing(paths, gta_path, protected_roots)


def _add_native_targets(paths: list[tuple[Path, str]], home: Path) -> None:
    for path in (
        home / ".config" / "majestic-launcher",
        home / ".config" / "MajesticLauncher",
        home / ".config" / "majestic-linux-runner",
        home / ".cache" / "majestic-launcher",
        home / ".cache" / "MajesticLauncher",
        home / ".local" / "share" / "majestic-launcher",
        home / ".local" / "share" / "MajesticLauncher",
        home / ".Majestic",
        home / ".majestic",
    ):
        paths.append((path, "Native Linux Majestic cache/config"))


def _add_windows_user_targets(paths: list[tuple[Path, str]], user_dir: Path | None) -> None:
    if user_dir is None:
        return
    local = user_dir / "AppData" / "Local"
    roaming = user_dir / "AppData" / "Roaming"
    paths.extend(
        [
            (local / "MajesticLauncher", "Majestic Launcher install directory"),
            (local / "MajesticLauncherGLOBAL", "Majestic Launcher install directory"),
            (local / "majestic-launcher", "Majestic Launcher install directory"),
            (local / "majestic-launcher-updater", "Majestic updater cache"),
            (local / "Programs" / "Majestic Launcher", "Majestic Launcher install directory"),
            (local / "Programs" / "majestic-launcher", "Majestic Launcher install directory"),
            (roaming / "majestic-launcher", "Majestic roaming cache and multiplayer data"),
            (roaming / "MajesticLauncher", "Majestic roaming cache"),
            (roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Majestic Launcher", "Majestic start menu directory"),
            (user_dir / "Desktop" / "Majestic Launcher.lnk", "Majestic desktop shortcut"),
        ]
    )


def _windows_user_dir(path: Path) -> Path | None:
    parts = path.parts
    for index in range(len(parts) - 3):
        if parts[index : index + 3] == ("pfx", "drive_c", "users") and index + 3 < len(parts):
            return Path(*parts[: index + 4])
    return None


def _steam_roots(home: Path, configured: Path | None) -> list[Path]:
    candidates = [
        configured,
        home / ".local" / "share" / "Steam",
        home / ".steam" / "root",
        home / ".steam" / "steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "root",
        home / "snap" / "steam" / "common" / ".local" / "share" / "Steam",
    ]
    return _unique_existing_dirs(path for path in candidates if path is not None and (path / "steamapps").is_dir())


def _compatdata_roots(steam_root: Path) -> list[Path]:
    compat_dir = steam_root / "steamapps" / "compatdata"
    if not compat_dir.is_dir():
        return []
    return sorted((path for path in compat_dir.iterdir() if path.is_dir()), key=lambda path: str(path).lower())


def _compatdata_looks_majestic(compatdata: Path) -> bool:
    drive_c = compatdata / "pfx" / "drive_c"
    if (drive_c / "Games" / "MAJESTIC_GTA").exists():
        return True
    if (drive_c / "proton_shortcuts" / "Majestic Launcher.desktop").exists():
        return True
    users = drive_c / "users"
    if not users.is_dir():
        return False
    patterns = ("*Majestic*", "majestic-launcher")
    return any(path.exists() for pattern in patterns for path in users.glob(f"*/AppData/**/{pattern}"))


def _add_installer_cache_targets(paths: list[tuple[Path, str]], home: Path) -> None:
    cache = home / ".cache"
    if not cache.is_dir():
        return
    for pattern in ("**/$R0/Uninstall Majestic Launcher.exe", "**/$PLUGINSDIR/app-64/Majestic Launcher.exe"):
        for path in cache.glob(pattern):
            try:
                if len(path.relative_to(cache).parts) > 4:
                    continue
            except ValueError:
                continue
            paths.append((path, "Majestic installer cache"))


def _add_installer_targets(paths: list[tuple[Path, str]], home: Path) -> None:
    for pattern in (
        "MajesticLauncherSetup*.exe",
        "Downloads/MajesticLauncherSetup*.exe",
        "Загрузки/MajesticLauncherSetup*.exe",
        "Downloads/*Majestic*.exe",
        "Загрузки/*Majestic*.exe",
    ):
        paths.extend((path, "Majestic installer") for path in _glob_home(home, pattern))


def _add_trash_targets(paths: list[tuple[Path, str]], home: Path) -> None:
    for pattern in (
        ".local/share/Trash/files/*majestic*",
        ".local/share/Trash/files/*Majestic*",
        ".local/share/Trash/info/*majestic*",
        ".local/share/Trash/info/*Majestic*",
    ):
        paths.extend((path, "Majestic trash entry") for path in _glob_home(home, pattern))


def _add_project_targets(paths: list[tuple[Path, str]], home: Path) -> None:
    for pattern in (
        "Рабочий стол/majescit/git/majestic-rp-linux",
        "Рабочий стол/majescit/git/majestic-rp-linux.zip",
        "Загрузки/majestic-rp-linux*.zip",
        "Downloads/majestic-rp-linux*.zip",
    ):
        paths.extend((path, "Majestic project copy/archive") for path in _glob_home(home, pattern))


def _glob_home(home: Path, pattern: str) -> list[Path]:
    return [Path(path) for path in glob.glob(str(home / pattern))]


def _unique_existing_dirs(paths) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(path)
    return result


def delete_cleanup_candidates(candidates: list[CleanupCandidate]) -> int:
    deleted = 0
    for candidate in candidates:
        path = candidate.path
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        deleted += 1
    return deleted
