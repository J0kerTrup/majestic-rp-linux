from __future__ import annotations

import logging
import shlex
import subprocess
import urllib.request
from pathlib import Path

from ..core.config import RunnerConfig
from ..core.errors import RunnerError
from ..detection.paths import find_majestic_exe


def installer_target(config: RunnerConfig, compatdata: Path) -> Path:
    if config.installer_path:
        return config.installer_path
    return compatdata / "pfx" / "drive_c" / "MajesticLauncherSetup.exe"


def ensure_installer(config: RunnerConfig, compatdata: Path, *, dry_run: bool, logger: logging.Logger | None = None) -> Path:
    target = installer_target(config, compatdata)
    if target.exists():
        if logger:
            logger.info("Using existing Majestic installer: %s", target)
        return target
    if not config.installer_url:
        raise RunnerError("Majestic Launcher.exe is missing and MAJESTIC_INSTALLER_URL is empty")
    if logger:
        logger.info("Downloading Majestic installer: %s -> %s", config.installer_url, target)
    if dry_run:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(config.installer_url, target)
    return target


def install_majestic_launcher(
    config: RunnerConfig,
    *,
    proton_path: Path,
    compatdata: Path,
    steam_root: Path | None,
    dry_run: bool,
    logger: logging.Logger | None = None,
) -> Path | None:
    existing = find_majestic_exe(config, compatdata)
    if existing:
        return existing
    installer = ensure_installer(config, compatdata, dry_run=dry_run, logger=logger)
    env = {
        **__import__("os").environ.copy(),
        "STEAM_COMPAT_DATA_PATH": str(compatdata),
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or ""),
        "STEAM_COMPAT_APP_ID": config.app_id or "271590",
        "SteamAppId": config.app_id or "271590",
        "SteamGameId": config.app_id or "271590",
    }
    argv = [str(proton_path), "waitforexitandrun", str(installer), *shlex.split(config.installer_args)]
    if logger:
        logger.info("Running Majestic installer through Proton: %s", " ".join(argv))
    if dry_run:
        return None
    try:
        result = subprocess.run(argv, env=env, timeout=config.installer_timeout if config.installer_timeout > 0 else None, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(f"Majestic installer timed out after {config.installer_timeout}s") from exc
    if result.returncode != 0:
        raise RunnerError(f"Majestic installer exited with code {result.returncode}")
    return find_majestic_exe(config, compatdata)
