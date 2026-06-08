from __future__ import annotations

import logging
from pathlib import Path

VALID_PLATFORMS = {"steam", "rgl", "egs"}


def detect_gta_platform(gta_path: Path | None) -> str:
    if gta_path is None:
        return "rgl"
    root = Path(gta_path)
    if (root / "EOSSDK-Win64-Shipping.dll").exists():
        return "egs"
    if (root / "steam_api64.dll").exists():
        return "steam"
    if (root / "GTAVLauncher.exe").exists():
        return "rgl"
    return "rgl"


def select_platform(selected: str, detected: str, explicit: bool, logger: logging.Logger | None = None) -> str:
    selected = (selected or "auto").strip().lower()
    detected = detected if detected in VALID_PLATFORMS else "rgl"
    if selected in {"", "auto"}:
        return detected
    if selected not in VALID_PLATFORMS:
        if logger:
            logger.warning("Unknown MAJESTIC_PLATFORM=%s, falling back to rgl", selected)
        return "rgl"
    if explicit:
        return selected
    return detected if detected in {"steam", "egs"} else selected
