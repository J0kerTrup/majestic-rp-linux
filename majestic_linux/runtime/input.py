from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess


def clear_caps_lock(*, dry_run: bool, logger: logging.Logger | None = None) -> None:
    if "DISPLAY" not in os.environ:
        return
    xset = shutil.which("xset")
    if xset is None:
        return
    try:
        state = subprocess.run([xset, "q"], text=True, capture_output=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return
    if state.returncode != 0 or not _caps_lock_is_on(state.stdout):
        return
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        if logger:
            logger.warning("Caps Lock is enabled before launch, but xdotool is not installed; disable Caps Lock manually if input behaves incorrectly")
        return
    if logger:
        logger.info("Caps Lock is enabled before launch; turning it off for Proton input")
    if not dry_run:
        subprocess.run([xdotool, "key", "Caps_Lock"], check=False)


def _caps_lock_is_on(xset_output: str) -> bool:
    return re.search(r"Caps Lock:\s+on\b", xset_output) is not None
