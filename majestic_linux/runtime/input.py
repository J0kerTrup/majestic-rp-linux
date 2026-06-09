from __future__ import annotations

import logging
import os
import shutil
import subprocess

from ..core.config import RunnerConfig


def input_env(config: RunnerConfig) -> dict[str, str]:
    env = {
        "LANG": config.locale,
        "LC_ALL": config.locale,
        "LC_CTYPE": config.locale,
        "XKB_DEFAULT_LAYOUT": config.xkb_layout,
    }
    if config.xkb_options:
        env["XKB_DEFAULT_OPTIONS"] = config.xkb_options
    method = config.input_method
    if method == "ibus":
        env.update({"GTK_IM_MODULE": "ibus", "QT_IM_MODULE": "ibus", "XMODIFIERS": "@im=ibus"})
    elif method == "fcitx":
        env.update({"GTK_IM_MODULE": "fcitx", "QT_IM_MODULE": "fcitx", "XMODIFIERS": "@im=fcitx"})
    else:
        env.update({"GTK_IM_MODULE": "xim", "QT_IM_MODULE": "xim", "XMODIFIERS": "@im=none"})
    return {key: value for key, value in env.items() if value}


def apply_xkb_layout(config: RunnerConfig, *, dry_run: bool, logger: logging.Logger | None = None) -> None:
    if not config.xkb_layout or "DISPLAY" not in os.environ:
        return
    setxkbmap = shutil.which("setxkbmap")
    if setxkbmap is None:
        if logger:
            logger.warning("setxkbmap not found; XKB layout will be passed only through environment")
        return
    command = [setxkbmap, "-layout", config.xkb_layout]
    if config.xkb_options:
        command.extend(["-option", config.xkb_options])
    if logger:
        logger.info("Applying XKB layout for Proton session: %s", " ".join(command))
    if dry_run:
        return
    subprocess.run(command, check=False)
