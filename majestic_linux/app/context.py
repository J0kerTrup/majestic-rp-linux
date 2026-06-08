from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig, config_summary, load_config
from ..core.logger import setup_logging
from ..detection.async_paths import detect_all_async
from ..detection.paths import DetectionResult


@dataclass(slots=True)
class AppContext:
    config: RunnerConfig
    result: DetectionResult


def load_context(args: argparse.Namespace) -> tuple[AppContext, object]:
    logger = setup_logging(args.debug, Path("logs"))
    config = load_config(args.config, dry_run=args.dry_run or None)
    logger = setup_logging(args.debug, Path("logs"), config.log_level)
    logger.debug("Config: %s", config_summary(config))
    result = asyncio.run(detect_all_async(config, logger))
    return AppContext(config, result), logger


def print_detection(result: DetectionResult) -> None:
    print(f"Steam root:        {result.steam_root or '-'}")
    print(f"Proton:            {result.proton_path or '-'}")
    print(f"Compatdata:        {result.compatdata_path or '-'}")
    print(f"GTA V:             {result.gta_path or '-'}")
    print(f"Majestic Launcher: {result.majestic_exe or '-'}")
    print(f"Detected platform: {result.detected_platform}")
    print(f"Selected platform: {result.selected_platform}")
