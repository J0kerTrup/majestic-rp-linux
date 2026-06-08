from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CleanupCandidate:
    path: Path
    reason: str


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


def _existing(paths: list[tuple[Path, str]], gta_path: Path | None) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    seen: set[Path] = set()
    for path, reason in paths:
        if not path.exists() and not path.is_symlink():
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
                (local / "MajesticLauncher", "Majestic Launcher install directory"),
                (local / "majestic-launcher-updater", "Majestic updater cache"),
                (roaming / "majestic-launcher", "Majestic roaming cache and multiplayer data"),
                (desktop / "Majestic Launcher.lnk", "Majestic desktop shortcut"),
                (start_menu / "Majestic Launcher.lnk", "Majestic start menu shortcut"),
            ]
        )

    proton_shortcuts = drive_c / "proton_shortcuts"
    paths.append((proton_shortcuts / "Majestic Launcher.desktop", "Proton shortcut"))
    paths.extend((path, "Proton shortcut icon") for path in proton_shortcuts.glob("icons/*/apps/*Majestic*.png"))
    paths.append((drive_c / "MajesticLauncherSetup.exe", "Majestic installer cache"))

    for launcher_dir in (drive_c / "users").glob("*/AppData/Local/MajesticLauncher"):
        resources = launcher_dir / "resources"
        paths.extend(
            [
                (resources / "app.asar.bak", "Majestic app.asar backup"),
                (resources / "app.asar.majestic-proton-bak", "Legacy Majestic app.asar backup"),
            ]
        )
        paths.extend((path, "Python patch backup") for path in launcher_dir.rglob("*.majestic-python-bak"))

    return _existing(paths, gta_path)


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
