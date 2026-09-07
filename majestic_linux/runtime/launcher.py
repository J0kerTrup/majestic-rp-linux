from __future__ import annotations

import hashlib
import logging
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..core.config import RunnerConfig
from ..core.config_file import cache_dir
from ..core.errors import RunnerError
from ..detection.paths import find_majestic_exe


def installer_target() -> Path:
    return cache_dir() / "MajesticLauncherSetup.exe"


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request_headers() -> dict[str, str]:
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}


def _installer_hash_url(installer_url: str) -> str:
    return installer_url + ".sha256"


def _read_local_hash(hash_file: Path) -> str:
    if not hash_file.exists():
        return ""
    match = re.search(r"\b[0-9a-fA-F]{64}\b", hash_file.read_text(encoding="utf-8", errors="replace"))
    return match.group(0).lower() if match else ""


def _fetch_remote_hash(installer_url: str, logger: logging.Logger | None = None) -> str | None:
    url = _installer_hash_url(installer_url)
    req = urllib.request.Request(url, headers=_request_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            text = response.read(4096).decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        if logger:
            logger.warning("Could not fetch installer hash %s: %s", url, exc)
        return None
    match = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    if match:
        return match.group(0).lower()
    if logger:
        logger.warning("Installer hash file has unexpected content: %r", text.strip()[:200])
    return None


def _download_installer(installer_url: str, target: Path, logger: logging.Logger | None = None) -> str:
    if logger:
        logger.info("Downloading Majestic installer: %s -> %s", installer_url, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(installer_url, headers=_request_headers())
    tmp = target.with_suffix(".tmp")
    with urllib.request.urlopen(req) as response, open(tmp, "wb") as out_file:
        out_file.write(response.read())
    new_hash = _hash_file(tmp)
    tmp.replace(target)
    hash_file = Path(str(target) + ".sha256")
    hash_file.write_text(new_hash + "\n", encoding="utf-8")
    return new_hash


def ensure_installer(config: RunnerConfig, *, dry_run: bool, logger: logging.Logger | None = None) -> tuple[Path, bool]:
    target = installer_target()
    hash_file = Path(str(target) + ".sha256")
    if not config.installer_url:
        raise RunnerError("Majestic Launcher.exe is missing and MAJESTIC_INSTALLER_URL is empty")
    if dry_run:
        return target, True
    local_hash = _read_local_hash(hash_file)
    remote_hash = _fetch_remote_hash(config.installer_url, logger=logger)
    if remote_hash is None:
        if logger:
            logger.info("Installer hash file is missing; auto-updating")
        needs_install = True
    elif local_hash != remote_hash:
        if logger:
            logger.info("Installer hash changed (%s -> %s), will reinstall", local_hash or "none", remote_hash)
        needs_install = True
    else:
        needs_install = False
        if target.exists():
            if logger:
                logger.info("Installer hash unchanged; using cached installer")
            return target, False
        if logger:
            logger.info("Installer hash unchanged, but cached installer is missing; downloading")
        _download_installer(config.installer_url, target, logger)
        return target, False
    _download_installer(config.installer_url, target, logger)
    return target, needs_install


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
    installer, needs_install = ensure_installer(config, dry_run=dry_run, logger=logger)
    if not needs_install:
        existing = find_majestic_exe(config, compatdata)
        if existing:
            if logger:
                logger.info("Installer unchanged, Majestic Launcher.exe is up to date")
            return existing
    if not needs_install and logger:
        logger.info("Installer unchanged, but Majestic Launcher.exe is missing — reinstalling")
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
