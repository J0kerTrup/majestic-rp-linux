from __future__ import annotations

import configparser
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from .heroic import heroic_gta_candidates, legendary_gta_candidates
from .platform import detect_gta_platform, select_platform

MAJESTIC_LOCAL_DIRS = ("MajesticLauncher", "MajesticLauncherGLOBAL")
MAJESTIC_EXE_NAME = "Majestic Launcher.exe"
GTA_MARKER_FILES = ("GTA5.exe", "PlayGTAV.exe", "GTAVLauncher.exe")
GTA_DIR_KEYWORDS = ("gtav", "gta v", "grand theft auto")
BROAD_GTA_SEARCH_ROOTS = (Path.home(), Path("/mnt"), Path("/media"), Path("/run") / "media" / os.environ.get("USER", ""))


def majestic_exe_candidates(compatdata: Path) -> list[Path]:
    pfx = compatdata / "pfx"
    candidates = [
        pfx / "drive_c" / "Program Files" / "Majestic Launcher" / MAJESTIC_EXE_NAME,
        pfx / "drive_c" / "Program Files (x86)" / "Majestic Launcher" / MAJESTIC_EXE_NAME,
    ]
    for dirname in MAJESTIC_LOCAL_DIRS:
        candidates.append(pfx / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / dirname / MAJESTIC_EXE_NAME)
        candidates.extend(pfx.glob(f"drive_c/users/*/AppData/Local/{dirname}/{MAJESTIC_EXE_NAME}"))
    candidates.extend(
        [
            pfx / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "Programs" / "Majestic Launcher" / MAJESTIC_EXE_NAME,
            pfx / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "Programs" / "majestic-launcher" / MAJESTIC_EXE_NAME,
        ]
    )
    candidates.extend(pfx.glob(f"drive_c/users/*/AppData/Local/Programs/Majestic Launcher/{MAJESTIC_EXE_NAME}"))
    candidates.extend(pfx.glob(f"drive_c/users/*/AppData/Local/Programs/majestic-launcher/{MAJESTIC_EXE_NAME}"))
    return list(dict.fromkeys(candidates))


def find_majestic_exes(config: RunnerConfig, compatdata: Path | None) -> list[Path]:
    found = []
    if config.majestic_exe and config.majestic_exe.exists():
        found.append(config.majestic_exe)
    if not config.auto_detect or compatdata is None:
        return found
    found.extend(path for path in majestic_exe_candidates(compatdata) if path.exists())
    return list(dict.fromkeys(found))


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
    return _unique_existing_paths(libraries)


def steam_libraries(steam_root: Path | None) -> list[Path]:
    return _steam_libraries(steam_root)


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
    return next(iter(gta_path_candidates(steam_root)), None)


def gta_path_candidates(steam_root: Path | None, *, deep_scan: bool = False) -> list[Path]:
    candidates: list[Path] = []
    libraries = _steam_libraries(steam_root)
    for library in libraries:
        manifest = library / "steamapps" / "appmanifest_271590.acf"
        install_dir = _manifest_install_dir(manifest) if manifest.exists() else None
        if install_dir:
            candidates.append(library / "steamapps" / "common" / install_dir)
        candidates.extend(
            [
                library / "steamapps" / "common" / "Grand Theft Auto V",
                library / "steamapps" / "common" / "GTAV",
            ]
        )
        candidates.extend(_compatdata_gta_candidates(library / "steamapps" / "compatdata"))
    candidates.extend(heroic_gta_candidates())
    candidates.extend(legendary_gta_candidates())
    candidates.extend(_keyword_gta_candidates(_gta_search_roots(libraries, deep_scan=deep_scan)))
    return _unique_existing_paths(path for path in candidates if looks_like_gta(path))


def _compatdata_gta_candidates(compatdata_root: Path) -> list[Path]:
    candidates: list[Path] = []
    if not compatdata_root.exists():
        return candidates
    for compatdata in compatdata_root.iterdir():
        if not compatdata.is_dir():
            continue
        drive_c = compatdata / "pfx" / "drive_c"
        candidates.extend(
            [
                drive_c / "Program Files" / "Epic Games" / "GTAV",
                drive_c / "Program Files (x86)" / "Epic Games" / "GTAV",
                drive_c / "Program Files" / "Rockstar Games" / "Grand Theft Auto V",
                drive_c / "Program Files (x86)" / "Rockstar Games" / "Grand Theft Auto V",
            ]
        )
    return candidates


def _gta_search_roots(steam_libraries: list[Path], *, deep_scan: bool = False) -> list[Path]:
    roots: list[Path] = []
    for library in steam_libraries:
        roots.append(library / "steamapps" / "common")
    if deep_scan:
        for library in steam_libraries:
            roots.append(library / "steamapps" / "compatdata")
        roots.extend(BROAD_GTA_SEARCH_ROOTS)
    roots.extend(
        [
            Path.home() / "Games",
        ]
    )
    if deep_scan:
        roots.extend(
            [
                Path.home() / ".local" / "share",
                Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl",
                Path.home() / ".var" / "app" / "com.valvesoftware.Steam",
            ]
        )
    return _unique_existing_paths(roots)


def _keyword_gta_candidates(roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        max_depth = _search_depth(root)
        found = _find_gta_paths(root, max_depth=max_depth)
        if found is None:
            candidates.extend(_find_gta_dirs_by_markers(root, max_depth=max_depth))
            candidates.extend(_find_gta_dirs_by_keywords(root, max_depth=max_depth))
        else:
            candidates.extend(found)
    common_roots = [
        Path.home() / "Games",
        Path.home() / "Games" / "Heroic",
        Path.home() / "Games" / "legendary",
        Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common",
    ]
    for root in common_roots:
        candidates.extend([root / "Grand Theft Auto V", root / "GTAV"])
    return _unique_existing_paths(path for path in candidates if looks_like_gta(path))


def _search_depth(root: Path) -> int:
    if "compatdata" in root.parts:
        return 9
    if root == Path.home():
        return 6
    if root in {Path("/mnt"), Path("/media")} or root.parts[:2] == ("/", "run"):
        return 10
    return 5


def _find_gta_dirs_by_markers(root: Path, *, max_depth: int) -> list[Path]:
    marker_paths = _find_by_name(root, max_depth=max_depth, names=GTA_MARKER_FILES, path_type="f")
    if marker_paths is not None:
        return [path.parent for path in marker_paths]
    found: list[Path] = []
    for current, dirs, files in os.walk(root):
        path = Path(current)
        depth = len(path.relative_to(root).parts)
        if depth >= max_depth:
            dirs[:] = []
        _prune_search_dirs(dirs)
        if any(marker in files for marker in GTA_MARKER_FILES):
            found.append(path)
            dirs[:] = []
    return found


def _find_gta_dirs_by_keywords(root: Path, *, max_depth: int) -> list[Path]:
    found = _find_by_name(root, max_depth=max_depth, names=GTA_DIR_KEYWORDS, path_type="d", substring=True)
    if found is not None:
        return found
    found: list[Path] = []
    for current, dirs, _files in os.walk(root):
        path = Path(current)
        depth = len(path.relative_to(root).parts)
        if depth >= max_depth:
            dirs[:] = []
        _prune_search_dirs(dirs)
        for dirname in list(dirs):
            if _name_looks_like_gta(dirname):
                found.append(path / dirname)
    return found


def _find_gta_paths(root: Path, *, max_depth: int) -> list[Path] | None:
    found = _find_by_gta_patterns(root, max_depth=max_depth)
    if found is None:
        return None
    candidates: list[Path] = []
    for path in found:
        candidates.append(path.parent if path.is_file() else path)
    return candidates


def _find_by_gta_patterns(root: Path, *, max_depth: int) -> list[Path] | None:
    find = shutil.which("find")
    if not find:
        return None
    args = [find, str(root), "-maxdepth", str(max_depth)]
    prune = _find_prune_args()
    if prune:
        args.extend(["("])
        args.extend(prune)
        args.extend([")", "-prune", "-o"])
    args.extend(["("])
    args.extend(["(", "-type", "f", "("])
    for index, marker in enumerate(GTA_MARKER_FILES):
        if index:
            args.append("-o")
        args.extend(["-iname", marker])
    args.extend([")", ")"])
    args.append("-o")
    args.extend(["(", "-type", "d", "("])
    for index, keyword in enumerate(GTA_DIR_KEYWORDS):
        if index:
            args.append("-o")
        args.extend(["-iname", f"*{keyword}*"])
    args.extend([")", ")"])
    args.extend([")", "-print"])
    try:
        proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode not in {0, 1}:
        return []
    return [Path(line).expanduser() for line in proc.stdout.splitlines() if line]


def _find_by_name(root: Path, *, max_depth: int, names: tuple[str, ...], path_type: str, substring: bool = False) -> list[Path] | None:
    find = shutil.which("find")
    if not find:
        return None
    args = [find, str(root), "-maxdepth", str(max_depth)]
    prune = _find_prune_args()
    if prune:
        args.extend(["("])
        args.extend(prune)
        args.extend([")", "-prune", "-o"])
    args.extend(["-type", path_type, "("])
    for index, name in enumerate(names):
        if index:
            args.append("-o")
        pattern = f"*{name}*" if substring else name
        args.extend(["-iname", pattern])
    args.extend([")", "-print"])
    try:
        proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode not in {0, 1}:
        return []
    return [Path(line).expanduser() for line in proc.stdout.splitlines() if line]


def _find_prune_args() -> list[str]:
    args: list[str] = []
    for index, dirname in enumerate(_ignored_search_dirs()):
        if index:
            args.append("-o")
        args.extend(["-name", dirname])
    return args


def _prune_search_dirs(dirs: list[str]) -> None:
    ignored = _ignored_search_dirs()
    dirs[:] = [dirname for dirname in dirs if dirname not in ignored]


def _ignored_search_dirs() -> set[str]:
    return {
        ".cache",
        ".cargo",
        ".gradle",
        ".npm",
        ".nvm",
        ".rustup",
        ".venv",
        "__pycache__",
        "cache",
        "Cache",
        "CachedData",
        "Code Cache",
        "downloading",
        "logs",
        "node_modules",
        "shadercache",
        "temp",
        "tmp",
    }


def _name_looks_like_gta(name: str) -> bool:
    normalized = name.replace("_", " ").replace("-", " ").lower()
    return any(keyword in normalized for keyword in GTA_DIR_KEYWORDS)


def _unique_existing_paths(paths) -> list[Path]:
    unique: dict[Path, Path] = {}
    for path in paths:
        if path is None or not path.exists():
            continue
        try:
            key = path.resolve()
        except OSError:
            key = path.absolute()
        unique.setdefault(key, path)
    return list(unique.values())


def find_proton(config: RunnerConfig, steam_root: Path | None) -> Path | None:
    if config.proton_path and config.proton_path.exists():
        return config.proton_path
    if not config.auto_detect:
        return None
    return next(iter(proton_path_candidates(steam_root)), None)


def proton_path_candidates(steam_root: Path | None, *, include_wine: bool = True) -> list[Path]:
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
        candidates.extend(sorted(common.glob("Proton-GE*/proton"), reverse=True))
        candidates.extend(sorted(common.glob("*Proton*/proton"), reverse=True))
    for root in _proton_tool_roots(steam_root):
        candidates.extend(sorted(root.glob("GE-Proton*/proton"), reverse=True))
        candidates.extend(sorted(root.glob("Proton-GE*/proton"), reverse=True))
        candidates.extend(sorted(root.glob("*Proton*/proton"), reverse=True))
        candidates.extend(sorted(root.glob("proton*/proton"), reverse=True))
        if include_wine:
            candidates.extend(sorted(root.glob("Wine-GE*/bin/wine"), reverse=True))
            candidates.extend(sorted(root.glob("wine-ge*/bin/wine"), reverse=True))
            candidates.extend(sorted(root.glob("*Wine*/bin/wine"), reverse=True))
            candidates.extend(sorted(root.glob("*wine*/bin/wine"), reverse=True))
    if include_wine:
        for name in ("wine", "wine64"):
            wine = shutil.which(name)
            if wine:
                candidates.append(Path(wine))
    return _unique_existing_paths(path for path in candidates if path.is_file())


def _proton_tool_roots(steam_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    for library in _steam_libraries(steam_root):
        roots.extend(
            [
                library / "compatibilitytools.d",
                library / "steamapps" / "compatibilitytools.d",
                library / "steamapps" / "common",
            ]
        )
    roots.extend(
        [
            Path.home() / ".steam" / "root" / "compatibilitytools.d",
            Path.home() / ".steam" / "steam" / "compatibilitytools.d",
            Path.home() / ".local" / "share" / "Steam" / "compatibilitytools.d",
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "compatibilitytools.d",
            Path.home() / ".config" / "heroic" / "tools" / "proton",
            Path.home() / ".config" / "heroic" / "tools" / "wine",
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "tools" / "proton",
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "tools" / "wine",
            Path.home() / ".local" / "share" / "lutris" / "runners" / "wine",
        ]
    )
    return _unique_existing_paths(roots)


def find_majestic_exe(config: RunnerConfig, compatdata: Path | None) -> Path | None:
    return next(iter(find_majestic_exes(config, compatdata)), None)


def looks_like_gta(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    return any((path / name).exists() for name in GTA_MARKER_FILES)


def detect_all(config: RunnerConfig, logger: logging.Logger | None = None) -> DetectionResult:
    if not config.auto_detect:
        return _detect_configured(config, logger)
    steam_root = find_steam_root(config)
    compatdata = find_compatdata(config, steam_root)
    gta_path = find_gta_path(config, steam_root)
    proton_path = find_proton(config, steam_root)
    majestic_exe = find_majestic_exe(config, compatdata)
    detected = detect_gta_platform(gta_path)
    selected = select_platform(config.selected_platform, detected, config.platform_explicit, logger)
    return DetectionResult(steam_root, proton_path, compatdata, gta_path, majestic_exe, detected, selected)


def _detect_configured(config: RunnerConfig, logger: logging.Logger | None = None) -> DetectionResult:
    steam_root = config.steam_root if config.steam_root and config.steam_root.exists() else None
    compatdata = config.compatdata_path if config.compatdata_path and config.compatdata_path.exists() else None
    gta_path = config.gta_path if config.gta_path and config.gta_path.exists() else None
    proton_path = config.proton_path if config.proton_path and config.proton_path.exists() else None
    majestic_exe = config.majestic_exe if config.majestic_exe and config.majestic_exe.exists() else None
    detected = detect_gta_platform(gta_path)
    selected = select_platform(config.selected_platform, detected, config.platform_explicit, logger)
    return DetectionResult(steam_root, proton_path, compatdata, gta_path, majestic_exe, detected, selected)
