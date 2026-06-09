from __future__ import annotations

import os
import shlex
from pathlib import Path

from .errors import ConfigError
from .keys import CONFIG_KEYS

SECTION_PREFIXES = {"shutdown": "SHUTDOWN_", "radio": "RADIO_"}


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"Expected integer, got {value!r}") from exc


def parse_path(value: str | None) -> Path | None:
    if value is None or value == "":
        return None
    return Path(value).expanduser()


def parse_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"Expected float, got {value!r}") from exc


def parse_shell_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    section = ""
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = SECTION_PREFIXES.get(section, "") + key.strip().upper() if section else key.strip()
        if key not in CONFIG_KEYS:
            continue
        try:
            parsed = shlex.split(raw_value.strip(), posix=True)
        except ValueError as exc:
            raise ConfigError(f"{path}:{lineno}: cannot parse {key}") from exc
        values[key] = parsed[0] if parsed else ""
    return values


def merged_values(config_path: Path) -> dict[str, str]:
    values = parse_shell_config(config_path)
    for key in CONFIG_KEYS:
        if key in os.environ:
            values[key] = os.environ[key]
    return values
