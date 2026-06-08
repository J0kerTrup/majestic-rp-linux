from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from .heroic import heroic_gta_candidates
from .platform import detect_gta_platform, select_platform


@dataclass(slots=True)
class DetectionResult:
    steam_root: Path | None
    proton_path: Path | None
    compatdata_path: Path | None
    gta_path: Path | None
    majestic_exe: Path | None
    detected_platform: str
    selected_platform: str


def find_steam_root(config: RunnerConfig) -> Path | None:
    if config.steam_root is None and not config.auto_detect:
        return None
    candidates = [
        config.steam_root,
        Path.home() / ".steam" / "steam",
        Path.home() / ".local" / "share" / "Steam",
        Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
    ]
    return next((path for path in candidates if path and path.exists()), None)


def _steam_libraries(steam_root: Path | None) -> list[Path]:
    if steam_root is None:
        return []
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for line in vdf.read_text(encoding="utf-8", errors="ignore").splitlines():
            if '"path"' not in line:
                continue
            parts = line.split('"')
            if len(parts) >= 4:
                libraries.append(Path(parts[3]).expanduser())
    return list(dict.fromkeys(libraries))


def find_compatdata(config: RunnerConfig, steam_root: Path | None) -> Path | None:
    if config.compatdata_path and config.compatdata_path.exists():
        return config.compatdata_path
    if not config.auto_detect:
        return None
    for library in _steam_libraries(steam_root):
        path = library / "steamapps" / "compatdata" / "271590"
        if path.exists():
            return path
    return None


def _manifest_install_dir(manifest: Path) -> str | None:
    parser = configparser.ConfigParser(strict=False)
    text = "[app]\n" + manifest.read_text(encoding="utf-8", errors="ignore").replace("\t", "=")
    try:
        parser.read_string(text)
    except configparser.Error:
        return None
    return parser.get("app", "installdir", fallback=None)


def find_gta_path(config: RunnerConfig, steam_root: Path | None) -> Path | None:
    if config.gta_path and config.gta_path.exists():
        return config.gta_path
    if not config.auto_detect:
        return None
    for library in _steam_libraries(steam_root):
        manifest = library / "steamapps" / "appmanifest_271590.acf"
        install_dir = _manifest_install_dir(manifest) if manifest.exists() else None
        candidates = []
        if install_dir:
            candidates.append(library / "steamapps" / "common" / install_dir)
        candidates.extend(
            [
                library / "steamapps" / "common" / "Grand Theft Auto V",
                library / "steamapps" / "common" / "GTAV",
            ]
        )
        for path in candidates:
            if looks_like_gta(path):
                return path
    for path in heroic_gta_candidates():
        if looks_like_gta(path):
            return path
    return None


def find_proton(config: RunnerConfig, steam_root: Path | None) -> Path | None:
    if config.proton_path and config.proton_path.exists():
        return config.proton_path
    if not config.auto_detect:
        return None
    candidates: list[Path] = []
    for library in _steam_libraries(steam_root):
        common = library / "steamapps" / "common"
        candidates.extend(
            [
                common / "Proton Experimental" / "proton",
                common / "Proton - Experimental" / "proton",
            ]
        )
        candidates.extend(sorted(common.glob("GE-Proton*/proton"), reverse=True))
        candidates.extend(sorted(common.glob("*Proton*/proton"), reverse=True))
    return next((path for path in candidates if path.exists()), None)


def find_majestic_exe(config: RunnerConfig, compatdata: Path | None) -> Path | None:
    if config.majestic_exe and config.majestic_exe.exists():
        return config.majestic_exe
    if not config.auto_detect:
        return None
    if compatdata is None:
        return None
    pfx = compatdata / "pfx"
    candidates = [
        pfx / "drive_c" / "Program Files" / "Majestic Launcher" / "Majestic Launcher.exe",
        pfx / "drive_c" / "Program Files (x86)" / "Majestic Launcher" / "Majestic Launcher.exe",
        pfx / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "MajesticLauncher" / "Majestic Launcher.exe",
        pfx / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "Programs" / "Majestic Launcher" / "Majestic Launcher.exe",
        pfx / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "Programs" / "majestic-launcher" / "Majestic Launcher.exe",
    ]
    candidates.extend(pfx.glob("drive_c/users/*/AppData/Local/MajesticLauncher/Majestic Launcher.exe"))
    candidates.extend(pfx.glob("drive_c/users/*/AppData/Local/Programs/Majestic Launcher/Majestic Launcher.exe"))
    candidates.extend(pfx.glob("drive_c/users/*/AppData/Local/Programs/majestic-launcher/Majestic Launcher.exe"))
    return next((path for path in candidates if path.exists()), None)


def looks_like_gta(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    return any((path / name).exists() for name in ("GTA5.exe", "PlayGTAV.exe", "GTAVLauncher.exe"))


def detect_all(config: RunnerConfig, logger: logging.Logger | None = None) -> DetectionResult:
    steam_root = find_steam_root(config)
    compatdata = find_compatdata(config, steam_root)
    gta_path = find_gta_path(config, steam_root)
    proton_path = find_proton(config, steam_root)
    majestic_exe = find_majestic_exe(config, compatdata)
    detected = detect_gta_platform(gta_path)
    selected = select_platform(config.selected_platform, detected, config.platform_explicit, logger)
    return DetectionResult(steam_root, proton_path, compatdata, gta_path, majestic_exe, detected, selected)
