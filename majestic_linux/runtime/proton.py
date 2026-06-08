from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from ..core.errors import CommandError
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
    env.update(
        {
            "STEAM_COMPAT_DATA_PATH": str(compatdata),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or ""),
            "STEAM_COMPAT_APP_ID": app_id,
            "SteamAppId": app_id,
            "SteamGameId": app_id,
            "MAJESTIC_PLATFORM": platform,
            "MAJESTIC_PROTON_PLATFORM": config.native_platform or platform,
            "GTA_PATH": str(wine_mapping.gta_path),
            "MAJESTIC_GTA_WIN_PATH": wine_mapping.wine_gta_path,
            "DISABLE_CEF_GPU": "1" if config.disable_cef_gpu else "0",
            "GAME_WIDTH": str(config.game_width),
            "GAME_HEIGHT": str(config.game_height),
            "GAME_WINDOWED": "1" if config.game_windowed else "0",
            "GAME_BORDERLESS": "1" if config.game_borderless else "0",
        }
    )
    argv = [str(proton_path), "waitforexitandrun", str(majestic_exe)]
    return ProtonCommand(argv, env, majestic_exe.parent)


def run_proton(command: ProtonCommand, *, dry_run: bool = False, logger: logging.Logger | None = None) -> int:
    if logger:
        logger.info("Launching Proton: %s", " ".join(command.argv))
    if dry_run:
        if logger:
            logger.success("Dry-run: Proton launch skipped")  # type: ignore[attr-defined]
        return 0
    result = subprocess.run(command.argv, env=command.env, cwd=command.cwd, check=False)
    if result.returncode != 0:
        raise CommandError(f"Proton exited with code {result.returncode}")
    return result.returncode
