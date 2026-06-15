from __future__ import annotations

import logging
import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from ..core.errors import RunnerError
from .tricks import _gui_args, _sanitize_fontconfig_env, select_tricks_tool

EMOJI_FONT_FILENAME = "seguiemj.ttf"
FONT_MAGIC_HEADERS = (b"\x00\x01\x00\x00", b"OTTO", b"ttcf")
SYSTEM_LINK_KEY = r"Software\\Microsoft\\Windows NT\\CurrentVersion\\FontLink\\SystemLink"
FONTS_KEY = r"Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"
FONT_LINK_VALUE = "Segoe UI"
FONT_LINK_DATA = "seguiemj.ttf,Segoe UI Emoji"
FONT_VALUE = "Segoe UI Emoji (TrueType)"
MARKER_NAME = ".majestic-emoji-fonts.done"


@dataclass(frozen=True, slots=True)
class EmojiFontStatus:
    prefix_font: Path
    system_font: Path
    marker: Path
    registry_applied: bool

    @property
    def applied(self) -> bool:
        return _is_valid_font_file(self.prefix_font) and _is_valid_font_file(self.system_font) and self.marker.exists() and self.registry_applied


def apply_emoji_font_fix(config: RunnerConfig, compatdata: Path, platform: str, *, dry_run: bool, logger: logging.Logger | None = None) -> None:
    prefix = compatdata / "pfx"
    prefix_font = prefix / "drive_c" / "windows" / "Fonts" / EMOJI_FONT_FILENAME
    system_font = Path.home() / ".local" / "share" / "fonts" / EMOJI_FONT_FILENAME
    marker = prefix / MARKER_NAME
    if emoji_font_fix_is_applied(compatdata):
        if logger:
            logger.info("Emoji font fix already applied")
        return
    app_id = config.app_id if config.app_id and config.app_id != "0" else "271590"
    _install_font_file(config.emoji_font_url, prefix_font, system_font, dry_run=dry_run, logger=logger)
    _install_corefonts(app_id, config, compatdata, platform, dry_run=dry_run, logger=logger)
    _write_font_registry(prefix, dry_run=dry_run, logger=logger)
    if not dry_run:
        marker.write_text("ok\n", encoding="utf-8")


def emoji_font_fix_is_applied(compatdata: Path) -> bool:
    return emoji_font_status(compatdata).applied


def emoji_font_status(compatdata: Path) -> EmojiFontStatus:
    prefix = compatdata / "pfx"
    prefix_font = prefix / "drive_c" / "windows" / "Fonts" / EMOJI_FONT_FILENAME
    system_font = Path.home() / ".local" / "share" / "fonts" / EMOJI_FONT_FILENAME
    marker = prefix / MARKER_NAME
    return EmojiFontStatus(prefix_font, system_font, marker, _font_registry_is_applied(prefix))


def _install_font_file(url: str, prefix_font: Path, system_font: Path, *, dry_run: bool, logger: logging.Logger | None) -> None:
    if logger:
        logger.info("Installing emoji font into prefix: %s", prefix_font)
        logger.info("Installing emoji font for current Linux user: %s", system_font)
    if dry_run:
        return
    prefix_font.parent.mkdir(parents=True, exist_ok=True)
    system_font.parent.mkdir(parents=True, exist_ok=True)
    if not _is_valid_font_file(prefix_font):
        if prefix_font.exists() and logger:
            logger.warning("Existing emoji font is invalid and will be replaced: %s", prefix_font)
        _download_font(url, prefix_font)
    if not _is_valid_font_file(prefix_font):
        raise RunnerError(f"Downloaded emoji font is not a valid TTF/OTF file: {prefix_font}")
    if not _is_valid_font_file(system_font) or system_font.stat().st_size != prefix_font.stat().st_size:
        shutil.copy2(prefix_font, system_font)
    if not _is_valid_font_file(system_font):
        raise RunnerError(f"Installed user emoji font is not a valid TTF/OTF file: {system_font}")
    fc_cache = shutil.which("fc-cache")
    if fc_cache:
        subprocess.run([fc_cache, "-f", str(system_font.parent)], check=False)


def _download_font(url: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".download")
    try:
        urllib.request.urlretrieve(url, tmp)
        if not _is_valid_font_file(tmp):
            raise RunnerError(f"Emoji font URL did not return a valid TTF/OTF file: {url}")
        tmp.replace(target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _is_valid_font_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return False
    with path.open("rb") as handle:
        header = handle.read(4)
    return header in FONT_MAGIC_HEADERS


def _install_corefonts(app_id: str, config: RunnerConfig, compatdata: Path, platform: str, *, dry_run: bool, logger: logging.Logger | None) -> None:
    tool, reason = select_tricks_tool(platform, config.tricks_tool)
    if tool is None:
        if logger:
            logger.warning("Skipping optional corefonts install: %s", reason)
        return
    env = os.environ.copy()
    _sanitize_fontconfig_env(env)
    if tool == "protontricks":
        argv = ["protontricks", *_gui_args(config), app_id, "corefonts"]
    else:
        env["WINEPREFIX"] = str(compatdata / "pfx")
        argv = ["winetricks", *_gui_args(config), "-q", "corefonts"]
    _run_optional_tricks(argv, config.tricks_timeout, env, dry_run=dry_run, logger=logger, description="Installing corefonts")


def _run_optional_tricks(argv: list[str], timeout: int, env: dict[str, str], *, dry_run: bool, logger: logging.Logger | None, description: str) -> None:
    if logger:
        logger.info("%s via %s", description, " ".join(argv))
    if dry_run:
        return
    result = subprocess.run(argv, env=env, timeout=timeout if timeout > 0 else None, check=False)
    if result.returncode != 0 and logger:
        logger.warning("%s exited with code %s while %s; continuing", argv[0], result.returncode, description.lower())


def _write_font_registry(prefix: Path, *, dry_run: bool, logger: logging.Logger | None) -> None:
    if logger:
        logger.info("Writing emoji font registry into prefix: %s", prefix)
    if dry_run:
        return
    if _write_font_registry_with_wine(prefix, logger=logger):
        return
    system_reg = prefix / "system.reg"
    if logger:
        logger.warning("wine command is not available; writing emoji font registry directly to %s", system_reg)
    _set_registry_value(system_reg, FONTS_KEY, FONT_VALUE, f'"{EMOJI_FONT_FILENAME}"')
    _set_registry_value(system_reg, SYSTEM_LINK_KEY, FONT_LINK_VALUE, _multi_sz(FONT_LINK_DATA))


def _write_font_registry_with_wine(prefix: Path, *, logger: logging.Logger | None) -> bool:
    wine = shutil.which("wine")
    if wine is None:
        return False
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    _sanitize_fontconfig_env(env)
    commands = [
        [wine, "reg", "add", r"HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\Fonts", "/v", FONT_VALUE, "/t", "REG_SZ", "/d", EMOJI_FONT_FILENAME, "/f"],
        [wine, "reg", "add", r"HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink", "/v", FONT_LINK_VALUE, "/t", "REG_MULTI_SZ", "/d", FONT_LINK_DATA, "/f"],
    ]
    for command in commands:
        if logger:
            logger.info("Writing emoji font registry via %s", " ".join(command))
        result = subprocess.run(command, env=env, check=False)
        if result.returncode != 0:
            if logger:
                logger.warning("%s exited with code %s while writing emoji font registry; falling back to direct registry edit", command[0], result.returncode)
            return False
    return True


def _font_registry_is_applied(prefix: Path) -> bool:
    system_reg = prefix / "system.reg"
    if not system_reg.exists():
        return False
    text = system_reg.read_text(encoding="utf-8", errors="ignore")
    font_registered = FONT_VALUE in text and EMOJI_FONT_FILENAME in text
    font_link_registered = FONT_LINK_VALUE in text and (
        _multi_sz(FONT_LINK_DATA) in text or f'"{FONT_LINK_DATA}\\0"' in text or f'"{FONT_LINK_DATA}"' in text
    )
    return font_registered and font_link_registered


def _set_registry_value(system_reg: Path, key: str, value: str, data: str) -> None:
    system_reg.parent.mkdir(parents=True, exist_ok=True)
    lines = system_reg.read_text(encoding="utf-8", errors="ignore").splitlines() if system_reg.exists() else ["WINE REGISTRY Version 2", ""]
    section = f"[{key}]"
    entry = f'"{value}"={data}'
    start = _section_start(lines, section)
    if start is None:
        if lines and lines[-1]:
            lines.append("")
        lines.extend([section, entry])
        system_reg.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    end = _section_end(lines, start)
    for index in range(start + 1, end):
        if lines[index].startswith(f'"{value}"='):
            lines[index] = entry
            break
    else:
        lines.insert(end, entry)
    system_reg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _section_start(lines: list[str], section: str) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() == section:
            return index
    return None


def _section_end(lines: list[str], start: int) -> int:
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("[") and lines[index].endswith("]"):
            return index
    return len(lines)


def _multi_sz(value: str) -> str:
    raw = (value + "\0\0").encode("utf-16le")
    return "hex(7):" + ",".join(f"{byte:02x}" for byte in raw)
