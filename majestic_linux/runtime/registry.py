from __future__ import annotations

import logging
import os
import shlex
import subprocess
from pathlib import Path

from ..core.config import RunnerConfig
from ..core.errors import RunnerError
from .tricks import _gui_args, _sanitize_fontconfig_env

MARKER_NAME = ".majestic-wine-registry-fixups.done"
APP_ID_FALLBACK = "271590"
KEYBOARD_LAYOUT_KEY = r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Keyboard Layout"
SCANCODE_MAP_DISABLE_WIN_KEYS = "00000000000000000300000000005BE000005CE000000000"


def apply_wine_registry_fixups(config: RunnerConfig, compatdata: Path, *, dry_run: bool, logger: logging.Logger | None = None) -> None:
    prefix = compatdata / "pfx"
    marker = prefix / MARKER_NAME
    if marker.exists():
        if logger:
            logger.info("Wine registry fixups already applied")
        return
    app_id = config.app_id if config.app_id and config.app_id != "0" else APP_ID_FALLBACK
    for command in _registry_commands():
        _run_protontricks(["protontricks", *_gui_args(config), "-c", shlex.join(["wine", *command]), app_id], config.tricks_timeout, dry_run=dry_run, logger=logger)
    if not dry_run:
        marker.write_text("ok\n", encoding="utf-8")


def _registry_commands() -> list[list[str]]:
    return [
        ["reg", "add", KEYBOARD_LAYOUT_KEY, "/v", "Scancode Map", "/t", "REG_BINARY", "/d", SCANCODE_MAP_DISABLE_WIN_KEYS, "/f"],
    ]


def _run_protontricks(argv: list[str], timeout: int, *, dry_run: bool, logger: logging.Logger | None) -> None:
    if logger:
        logger.info("Applying Wine registry fixup via %s", " ".join(argv))
    if dry_run:
        return
    env = os.environ.copy()
    _sanitize_fontconfig_env(env)
    result = subprocess.run(argv, env=env, timeout=timeout if timeout > 0 else None, check=False)
    if result.returncode != 0:
        raise RunnerError(f"{argv[0]} exited with code {result.returncode} while applying Wine registry fixups")
