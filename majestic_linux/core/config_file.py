from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from .config_template import DEFAULT_CONFIG_TEXT

CONFIG_DIR_NAME = "majestic-runner"
CONFIG_FILE_NAME = "majestic-runner.conf"
EXAMPLE_CONFIG_PATH = Path("examples") / "majestic-runner.example.conf"


def xdg_config_home() -> Path:
    """Return the base directory for user configuration files."""
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config"


def default_config_path() -> Path:
    return xdg_config_home() / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def resolve_config_path(path: Path | str | None = None) -> Path:
    if path is None or str(path) == "":
        return default_config_path()
    return Path(path).expanduser()


def legacy_config_path() -> Path:
    return Path.cwd() / CONFIG_FILE_NAME


def example_config_path() -> Path:
    return Path.cwd() / EXAMPLE_CONFIG_PATH


def ensure_config_file(path: Path, logger: logging.Logger | None = None) -> bool:
    """Create the runner config with safe defaults when it is missing."""
    if path.exists():
        return False
    legacy = legacy_config_path()
    is_default_path = path.resolve() == default_config_path().resolve()
    is_distinct_legacy = legacy.exists() and legacy.resolve() != path.resolve()
    if is_default_path and is_distinct_legacy:
        if logger:
            logger.info("Migrating legacy config: %s -> %s", legacy, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, path)
        return True
    example = example_config_path()
    if example.exists() and example.resolve() != path.resolve():
        if logger:
            logger.info("Creating default config from example: %s -> %s", example, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(example, path)
        return True
    if logger:
        logger.info("Creating default config: %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
    return True
