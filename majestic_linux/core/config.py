from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigError


CONFIG_KEYS = {
    "GAME_WIDTH",
    "GAME_HEIGHT",
    "GAME_WINDOWED",
    "GAME_BORDERLESS",
    "DISABLE_CEF_GPU",
    "MAJESTIC_LAUNCHER_FLAGS",
    "MAJESTIC_PLATFORM",
    "MAJESTIC_PROTON_NATIVE_PLATFORM",
    "GTA_WINE_DRIVE",
    "MAJESTIC_PERMISSIONS",
    "STEAM_ROOT",
    "STEAM_COMPAT_DATA_PATH",
    "GTA_PATH",
    "PROTON_PATH",
    "MAJESTIC_EXE",
    "MAJESTIC_SOURCE_ROOT",
    "MAJESTIC_INSTALLER_URL",
    "MAJESTIC_INSTALLER_PATH",
    "MAJESTIC_INSTALLER_ARGS",
    "MAJESTIC_INSTALLER_TIMEOUT",
    "APP_ID",
    "DRY_RUN",
}


@dataclass(slots=True)
class RunnerConfig:
    config_path: Path
    game_width: int = 1920
    game_height: int = 1080
    game_windowed: bool = True
    game_borderless: bool = True
    disable_cef_gpu: bool = True
    launcher_flags: str = "--no-sandbox --disable-dev-shm-usage --disable-gpu-sandbox"
    selected_platform: str = "auto"
    platform_explicit: bool = False
    native_platform: str = ""
    gta_wine_drive: str = "g"
    majestic_permissions: str = "1"
    steam_root: Path | None = None
    compatdata_path: Path | None = None
    gta_path: Path | None = None
    proton_path: Path | None = None
    majestic_exe: Path | None = None
    source_root: Path | None = None
    installer_url: str = "https://cdn.majestic-files.net/launcher/cis/MajesticLauncherSetup.exe"
    installer_path: Path | None = None
    installer_args: str = "/S"
    installer_timeout: int = 30
    app_id: str = "271590"
    dry_run: bool = False


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"Expected integer, got {value!r}") from exc


def _parse_path(value: str | None) -> Path | None:
    if value is None or value == "":
        return None
    return Path(value).expanduser()


def parse_shell_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key not in CONFIG_KEYS:
            continue
        value = raw_value.strip()
        try:
            parsed = shlex.split(value, posix=True)
        except ValueError as exc:
            raise ConfigError(f"{path}:{lineno}: cannot parse {key}") from exc
        values[key] = parsed[0] if parsed else ""
    return values


def _merged_values(config_path: Path) -> dict[str, str]:
    values = parse_shell_config(config_path)
    for key in CONFIG_KEYS:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def load_config(config_path: Path | str = "majestic-runner.conf", *, dry_run: bool | None = None) -> RunnerConfig:
    path = Path(config_path).expanduser()
    values = _merged_values(path)
    platform_raw = values.get("MAJESTIC_PLATFORM", "auto").strip().lower()
    platform_explicit = "MAJESTIC_PLATFORM" in values and platform_raw not in {"", "auto"}

    cfg = RunnerConfig(
        config_path=path,
        game_width=_parse_int(values.get("GAME_WIDTH"), 1920),
        game_height=_parse_int(values.get("GAME_HEIGHT"), 1080),
        game_windowed=_parse_bool(values.get("GAME_WINDOWED"), True),
        game_borderless=_parse_bool(values.get("GAME_BORDERLESS"), True),
        disable_cef_gpu=_parse_bool(values.get("DISABLE_CEF_GPU"), True),
        launcher_flags=values.get("MAJESTIC_LAUNCHER_FLAGS", RunnerConfig.launcher_flags),
        selected_platform=platform_raw or "rgl",
        platform_explicit=platform_explicit,
        native_platform=values.get("MAJESTIC_PROTON_NATIVE_PLATFORM", ""),
        gta_wine_drive=(values.get("GTA_WINE_DRIVE", "g") or "g").lower()[0],
        majestic_permissions=values.get("MAJESTIC_PERMISSIONS", "1"),
        steam_root=_parse_path(values.get("STEAM_ROOT")),
        compatdata_path=_parse_path(values.get("STEAM_COMPAT_DATA_PATH")),
        gta_path=_parse_path(values.get("GTA_PATH")),
        proton_path=_parse_path(values.get("PROTON_PATH")),
        majestic_exe=_parse_path(values.get("MAJESTIC_EXE")),
        source_root=_parse_path(values.get("MAJESTIC_SOURCE_ROOT")),
        installer_url=values.get("MAJESTIC_INSTALLER_URL", RunnerConfig.installer_url),
        installer_path=_parse_path(values.get("MAJESTIC_INSTALLER_PATH")),
        installer_args=values.get("MAJESTIC_INSTALLER_ARGS", "/S"),
        installer_timeout=_parse_int(values.get("MAJESTIC_INSTALLER_TIMEOUT"), 30),
        app_id=values.get("APP_ID") or "271590",
        dry_run=_parse_bool(values.get("DRY_RUN"), False),
    )
    if dry_run is not None:
        cfg.dry_run = dry_run
    return cfg


def config_summary(config: RunnerConfig) -> dict[str, Any]:
    return {
        "config": str(config.config_path),
        "platform": config.selected_platform,
        "platform_explicit": config.platform_explicit,
        "dry_run": config.dry_run,
        "steam_root": str(config.steam_root) if config.steam_root else "",
        "compatdata": str(config.compatdata_path) if config.compatdata_path else "",
        "gta_path": str(config.gta_path) if config.gta_path else "",
        "proton_path": str(config.proton_path) if config.proton_path else "",
        "majestic_exe": str(config.majestic_exe) if config.majestic_exe else "",
        "installer_path": str(config.installer_path) if config.installer_path else "",
        "installer_url": config.installer_url,
    }
