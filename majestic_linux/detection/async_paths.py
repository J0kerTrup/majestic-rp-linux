from __future__ import annotations

import asyncio
import logging

from ..core.config import RunnerConfig
from .paths import (
    DetectionResult,
    detect_gta_platform,
    find_compatdata,
    find_gta_path,
    find_majestic_exe,
    find_proton,
    find_steam_root,
)
from .platform import select_platform


async def detect_all_async(config: RunnerConfig, logger: logging.Logger | None = None) -> DetectionResult:
    """Detect independent paths concurrently while preserving dependencies."""
    if logger:
        logger.debug("Starting async path detection")
    steam_root = await asyncio.to_thread(find_steam_root, config)
    compat_task = asyncio.to_thread(find_compatdata, config, steam_root)
    gta_task = asyncio.to_thread(find_gta_path, config, steam_root)
    proton_task = asyncio.to_thread(find_proton, config, steam_root)
    compatdata, gta_path, proton_path = await asyncio.gather(compat_task, gta_task, proton_task)
    majestic_exe = await asyncio.to_thread(find_majestic_exe, config, compatdata)
    detected = detect_gta_platform(gta_path)
    selected = select_platform(config.selected_platform, detected, config.platform_explicit, logger)
    result = DetectionResult(steam_root, proton_path, compatdata, gta_path, majestic_exe, detected, selected)
    if logger:
        logger.debug("Async detection result: %s", result)
    return result
