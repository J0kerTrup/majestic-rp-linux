from __future__ import annotations

import logging
import shlex
import subprocess
import time
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


def wait_for_majestic_exe(config: RunnerConfig, compatdata: Path, *, timeout: int, logger: logging.Logger | None = None) -> Path | None:
    deadline = time.monotonic() + max(timeout, 0)
    while True:
        existing = find_majestic_exe(config, compatdata)
        if existing:
            return existing
        if time.monotonic() >= deadline:
            return None
        if logger:
            logger.debug("Waiting for Majestic Launcher.exe to appear in prefix")
        time.sleep(1)


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
    app_id = _steam_app_id(config)
    env = {
        **__import__("os").environ.copy(),
        "STEAM_COMPAT_DATA_PATH": str(compatdata),
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or ""),
        "STEAM_COMPAT_APP_ID": app_id,
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
    installed = wait_for_majestic_exe(config, compatdata, timeout=config.installer_timeout, logger=logger)
    if installed:
        return installed
    hint = "Clear MAJESTIC_INSTALLER_ARGS to run the installer interactively"
    if not config.installer_args:
        hint = "Complete the interactive installer, delete the cached installer if it is broken, or set MAJESTIC_EXE"
    raise RunnerError(
        "Majestic installer finished, but Majestic Launcher.exe was not found in the prefix. "
        f"{hint}."
    )


def _steam_app_id(config: RunnerConfig) -> str:
    return config.app_id if config.app_id and config.app_id != "0" else "271590"
