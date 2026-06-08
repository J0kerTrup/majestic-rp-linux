from __future__ import annotations

import logging
import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from .fixups import apply_library_path
from .input import input_env
from .lifecycle import run_with_lifecycle
from .wine import WineMapping


@dataclass(slots=True)
class ProtonCommand:
    argv: list[str]
    env: dict[str, str]
    cwd: Path | None = None


def build_proton_command(
    config: RunnerConfig,
    proton_path: Path,
    compatdata: Path,
    steam_root: Path | None,
    majestic_exe: Path,
    platform: str,
    wine_mapping: WineMapping,
) -> ProtonCommand:
    app_id = "271590" if platform == "steam" else (config.app_id if config.app_id != "271590" else "0")
    env = os.environ.copy()
    env.update(input_env(config))
    env.update(
        {
            "STEAM_COMPAT_DATA_PATH": str(compatdata),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or ""),
            "STEAM_COMPAT_APP_ID": app_id,
            "SteamAppId": app_id,
            "SteamGameId": app_id,
            "MAJESTIC_PLATFORM": platform,
            "MAJESTIC_PROTON_PLATFORM": config.native_platform or platform,
            "MAJESTIC_DISABLE_CEF_GPU": "1" if config.disable_cef_gpu else "0",
            "MAJESTIC_LAUNCHER_FLAGS": config.launcher_flags,
            "GTA_PATH": str(wine_mapping.gta_path),
            "MAJESTIC_GTA_WIN_PATH": wine_mapping.wine_gta_path,
            "DISABLE_CEF_GPU": "1" if config.disable_cef_gpu else "0",
            "GAME_WIDTH": str(config.game_width),
            "GAME_HEIGHT": str(config.game_height),
            "GAME_WINDOWED": "1" if config.game_windowed else "0",
            "GAME_BORDERLESS": "1" if config.game_borderless else "0",
        }
    )
    if config.disable_cef_gpu:
        env.setdefault("CEF_DISABLE_GPU", "1")
    if config.radio_disable_winegstreamer:
        env["WINEDLLOVERRIDES"] = _with_dll_override(env.get("WINEDLLOVERRIDES", ""), "winegstreamer=d")
    apply_library_path(env, getattr(config, "runtime_library_paths", []))
    argv = [str(proton_path), "waitforexitandrun", str(majestic_exe), *shlex.split(config.launcher_flags)]
    return ProtonCommand(argv, env, majestic_exe.parent)


def run_proton(command: ProtonCommand, *, dry_run: bool = False, logger: logging.Logger | None = None) -> int:
    compatdata_raw = command.env.get("STEAM_COMPAT_DATA_PATH")
    if not compatdata_raw:
        raise ValueError("STEAM_COMPAT_DATA_PATH is required for lifecycle-managed Proton launch")
    config = RunnerConfig(config_path=Path("majestic-runner.conf"))
    return run_with_lifecycle(command, config, Path(compatdata_raw), dry_run=dry_run, logger=logger)


def run_proton_managed(command: ProtonCommand, config: RunnerConfig, compatdata: Path, *, dry_run: bool = False, logger: logging.Logger | None = None) -> int:
    return run_with_lifecycle(command, config, compatdata, dry_run=dry_run, logger=logger)


def _with_dll_override(current: str, override: str) -> str:
    name = override.split("=", 1)[0].lower()
    parts = [part for part in current.split(";") if part and not part.lower().startswith(name + "=")]
    return ";".join([override, *parts])
