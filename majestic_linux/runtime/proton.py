from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import RunnerConfig
from .fixups import apply_library_path
from .lifecycle import run_with_lifecycle
from .wine import WineMapping


@dataclass(slots=True)
class ProtonCommand:
    argv: list[str]
    env: dict[str, str]
    cwd: Path | None = None
    after_start: list[Callable[[subprocess.Popen], None]] = field(default_factory=list)


def build_proton_command(
    config: RunnerConfig,
    proton_path: Path,
    compatdata: Path,
    steam_root: Path | None,
    majestic_exe: Path,
    platform: str,
    wine_mapping: WineMapping,
) -> ProtonCommand:
    app_id = _steam_app_id(config)
    env = os.environ.copy()
    _sanitize_host_launcher_env(env)
    env.update(
        {
            "STEAM_COMPAT_DATA_PATH": str(compatdata),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or ""),
            "STEAM_COMPAT_APP_ID": app_id,
            "MAJESTIC_PLATFORM": platform,
            "MAJESTIC_PROTON_PLATFORM": config.native_platform or platform,
            "MAJESTIC_DISABLE_CEF_GPU": "1" if config.disable_cef_gpu else "0",
            "MAJESTIC_LAUNCHER_FLAGS": config.launcher_flags,
            "GTA_PATH": str(wine_mapping.gta_path),
            "MAJESTIC_GTA_WIN_PATH": wine_mapping.wine_gta_path,
            "DISABLE_CEF_GPU": "1" if config.disable_cef_gpu else "0",
            "PROTON_USE_XALIA": "0",
            "DXVK_STATE_CACHE": "1",
            "GAME_WIDTH": str(config.game_width),
            "GAME_HEIGHT": str(config.game_height),
            "GAME_WINDOWED": "1" if config.game_windowed else "0",
            "GAME_BORDERLESS": "1" if config.game_borderless else "0",
        }
    )
    if platform == "steam":
        env["SteamAppId"] = app_id
        env["SteamGameId"] = app_id
    if config.disable_cef_gpu:
        env.setdefault("CEF_DISABLE_GPU", "1")
    apply_gpu_selection(env, config)
    if config.radio_disable_winegstreamer:
        env["WINEDLLOVERRIDES"] = _with_dll_override(env.get("WINEDLLOVERRIDES", ""), "winegstreamer=d")
    apply_library_path(env, getattr(config, "runtime_library_paths", []))
    argv = [str(proton_path), "waitforexitandrun", str(majestic_exe), *shlex.split(config.launcher_flags)]
    argv = apply_launch_options(argv, env, config.launch_options)
    return ProtonCommand(argv, env, majestic_exe.parent)


def _steam_app_id(config: RunnerConfig) -> str:
    return config.app_id if config.app_id and config.app_id != "0" else "271590"


def _sanitize_host_launcher_env(env: dict[str, str]) -> None:
    for key in list(env):
        if key.startswith(("CODEX_", "VSCODE_", "ELECTRON_")) or key in {"NODE_OPTIONS", "SteamAppId", "SteamGameId"}:
            env.pop(key, None)


def apply_launch_options(command: list[str], env: dict[str, str], launch_options: str) -> list[str]:
    options = shlex.split(launch_options or "")
    if not options:
        return command
    result: list[str] = []
    command_inserted = False
    for item in options:
        if item == "%command%":
            result.extend(command)
            command_inserted = True
            continue
        if not command_inserted and _looks_like_env_assignment(item):
            key, value = item.split("=", 1)
            env[key] = value
            continue
        result.append(item)
    if not command_inserted:
        result.extend(command)
    return result


def _looks_like_env_assignment(value: str) -> bool:
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", value) is not None


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


def apply_gpu_selection(env: dict[str, str], config: RunnerConfig) -> None:
    mode = (config.gpu_mode or "auto").lower()
    if config.gpu_device_name:
        env["DXVK_FILTER_DEVICE_NAME"] = config.gpu_device_name
    if mode in {"prime", "discrete"}:
        env.setdefault("DRI_PRIME", "1")
    if mode == "nvidia":
        env.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
        env.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
        env.setdefault("__VK_LAYER_NV_optimus", "NVIDIA_only")
