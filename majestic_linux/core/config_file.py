from __future__ import annotations

import logging
from pathlib import Path

from .config_template import DEFAULT_CONFIG_TEXT


def ensure_config_file(path: Path, logger: logging.Logger | None = None) -> bool:
    """Create the runner config with safe defaults when it is missing."""
    if path.exists():
        return False
    if logger:
        logger.info("Creating default config: %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return True
