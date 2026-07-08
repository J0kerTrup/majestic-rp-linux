from __future__ import annotations

import logging
import os
import shutil
from importlib import resources
from pathlib import Path

from .config_parser import SECTION_PREFIXES
from .keys import CONFIG_KEYS

CONFIG_DIR_NAME = "majestic-runner"
CONFIG_FILE_NAME = "majestic-runner.conf"
EXAMPLE_CONFIG_PATH = Path("examples") / "majestic-runner.example.conf"
RESOURCE_CONFIG_NAME = "majestic-runner.example.conf"


def xdg_config_home() -> Path:
    """Return the base directory for user configuration files."""
    configured = os.environ.get("XDG_CONFIG_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config"


def xdg_cache_home() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".cache"


def default_config_path() -> Path:
    return xdg_config_home() / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def default_log_dir() -> Path:
    return xdg_cache_home() / CONFIG_DIR_NAME


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
        update_config_file(path, logger)
        return False
    legacy = legacy_config_path()
    is_default_path = path.resolve() == default_config_path().resolve()
    is_distinct_legacy = legacy.exists() and legacy.resolve() != path.resolve()
    if is_default_path and is_distinct_legacy:
        if logger:
            logger.info("Migrating legacy config: %s -> %s", legacy, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, path)
        update_config_file(path, logger)
        return True
    example = example_config_path()
    if example.exists() and example.resolve() != path.resolve():
        if logger:
            logger.info("Creating default config from example: %s -> %s", example, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(example, path)
        update_config_file(path, logger)
        return True
    if logger:
        logger.info("Creating default config: %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(default_config_text(), encoding="utf-8")
    return True


def update_config_file(path: Path, logger: logging.Logger | None = None) -> list[str]:
    """Append missing config keys from the current example/template without overwriting user values."""
    if not path.exists():
        return []
    existing_keys = _keys_in_config(path.read_text(encoding="utf-8").splitlines())
    template_entries = _template_entries()
    missing = [entry for entry in template_entries if entry[0] not in existing_keys]
    if not missing:
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    root_missing = [entry for entry in missing if not entry[1]]
    section_missing = [entry for entry in missing if entry[1]]
    if root_missing:
        insert_at = _first_section_index(lines)
        block = ["", "# Added automatically by majestic-linux config updater.", *(line for _key, _section, line in root_missing), ""]
        lines[insert_at:insert_at] = block
    if section_missing:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Added automatically by majestic-linux config updater.")
    current_section: str | None = None
    added_keys: list[str] = []
    for key, section, line in section_missing:
        if section != current_section:
            lines.append("")
            lines.append(f"[{section}]")
            current_section = section
        lines.append(line)
        added_keys.append(key)
    added_keys = [key for key, _section, _line in root_missing] + added_keys
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if logger:
        logger.info("Updated config %s with missing keys: %s", path, ", ".join(added_keys))
    return added_keys


def _template_entries() -> list[tuple[str, str, str]]:
    template = default_config_text()
    entries: list[tuple[str, str, str]] = []
    section = ""
    for raw_line in template.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        key = _line_config_key(raw_line, section)
        if key in CONFIG_KEYS:
            entries.append((key, section, raw_line))
    return entries


def default_config_text() -> str:
    example = example_config_path()
    if example.exists():
        return example.read_text(encoding="utf-8")
    return resources.files("majestic_linux.resources").joinpath(RESOURCE_CONFIG_NAME).read_text(encoding="utf-8")


def _keys_in_config(lines: list[str]) -> set[str]:
    keys: set[str] = set()
    section = ""
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        key = _line_config_key(raw_line, section)
        if key in CONFIG_KEYS:
            keys.add(key)
    return keys


def _first_section_index(lines: list[str]) -> int:
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            return index
    return len(lines)


def _line_config_key(line: str, section: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip().upper()
    return SECTION_PREFIXES.get(section, "") + key if section else key
