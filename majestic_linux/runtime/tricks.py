from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from ..core.errors import RunnerError


@dataclass(frozen=True, slots=True)
class TricksPlan:
    tool: str | None
    reason: str
    argv: list[str]
    env: dict[str, str]

POWERSHELL_MARKER_NAME = ".majestic-runner-powershell.done"


def _has_tool(name: str) -> bool:
    return shutil.which(name) is not None


def select_tricks_tool(platform: str, override: str = "auto") -> tuple[str | None, str]:
    override = (override or "auto").lower()
    if override in {"winetricks", "protontricks"}:
        return (override, "forced by TRICKS_TOOL") if _has_tool(override) else (None, f"{override} not installed")
    if platform == "steam":
        return ("protontricks", "Steam uses protontricks") if _has_tool("protontricks") else (None, "protontricks not installed")
    if _has_tool("winetricks"):
        reason = "EGS/Heroic uses winetricks" if platform == "egs" else "Non-Steam platform uses winetricks"
        return "winetricks", reason
    if _has_tool("protontricks"):
        return "protontricks", "winetricks not installed; falling back to protontricks"
    return None, "neither protontricks nor winetricks is installed"


def build_win10_plan(config: RunnerConfig, platform: str, compatdata: Path) -> TricksPlan:
    tool, reason = select_tricks_tool(platform, config.tricks_tool)
    env = os.environ.copy()
    _sanitize_fontconfig_env(env)
    if tool == "protontricks":
        app_id = config.app_id if config.app_id and config.app_id != "0" else "271590"
        return TricksPlan(tool, reason, ["protontricks", *_gui_args(config), app_id, "win10"], env)
    if tool == "winetricks":
        env["WINEPREFIX"] = str(compatdata / "pfx")
        return TricksPlan(tool, reason, ["winetricks", *_gui_args(config), "-q", "win10"], env)
    return TricksPlan(None, reason, [], env)


def build_powershell_plan(config: RunnerConfig, platform: str, compatdata: Path) -> TricksPlan:
    tool, reason = select_tricks_tool(platform, config.tricks_tool)
    env = os.environ.copy()
    _sanitize_fontconfig_env(env)
    if tool == "protontricks":
        app_id = config.app_id if config.app_id and config.app_id != "0" else "271590"
        return TricksPlan(tool, reason, ["protontricks", app_id, "-q", "powershell"], env)
    if tool == "winetricks":
        env["WINEPREFIX"] = str(compatdata / "pfx")
        return TricksPlan(tool, reason, ["winetricks", "-q", "powershell"], env)
    return TricksPlan(None, reason, [], env)


def apply_win10_mode(
    config: RunnerConfig,
    platform: str,
    compatdata: Path,
    *,
    dry_run: bool,
    logger: logging.Logger | None = None,
) -> None:
    if not config.tricks_win10:
        if logger:
            logger.info("Win10 tricks step disabled")
        return
    prefix = compatdata / "pfx"
    if prefix_is_win10(prefix):
        if logger:
            logger.info("Win10 mode already applied in prefix; skipping protontricks/winetricks")
        return
    plan = build_win10_plan(config, platform, compatdata)
    if plan.tool is None:
        raise RunnerError(f"Cannot apply win10 mode: {plan.reason}")
    if logger:
        logger.info("Applying win10 mode via %s: %s", plan.tool, " ".join(plan.argv))
    if dry_run:
        return
    timeout = config.tricks_timeout if config.tricks_timeout > 0 else None
    result = subprocess.run(plan.argv, env=plan.env, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RunnerError(f"{plan.tool} exited with code {result.returncode}")


def apply_powershell(
    config: RunnerConfig,
    platform: str,
    compatdata: Path,
    *,
    dry_run: bool,
    logger: logging.Logger | None = None,
) -> None:
    if not config.tricks_powershell:
        if logger:
            logger.info("PowerShell tricks step disabled")
        return
    if powershell_setup_is_complete(compatdata):
        if logger:
            logger.info("PowerShell already installed by runner; skipping protontricks/winetricks")
        return
    plan = build_powershell_plan(config, platform, compatdata)
    if plan.tool is None:
        raise RunnerError(f"Cannot install PowerShell: {plan.reason}")
    if logger:
        logger.info("Installing PowerShell silently via %s: %s", plan.tool, " ".join(plan.argv))
    if dry_run:
        return
    timeout = config.tricks_timeout if config.tricks_timeout > 0 else None
    result = subprocess.run(plan.argv, env=plan.env, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RunnerError(f"{plan.tool} powershell exited with code {result.returncode}")
    marker = powershell_setup_marker(compatdata)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("ok\n", encoding="utf-8")


def powershell_setup_marker(compatdata: Path) -> Path:
    return compatdata / "pfx" / POWERSHELL_MARKER_NAME


def powershell_setup_is_complete(compatdata: Path) -> bool:
    return powershell_setup_marker(compatdata).exists()


def prefix_is_win10(prefix: Path) -> bool:
    system_reg = prefix / "system.reg"
    if not system_reg.exists():
        return False
    text = system_reg.read_text(encoding="utf-8", errors="ignore")
    return _reg_section_is_win10(text, r"Software\\Microsoft\\Windows NT\\CurrentVersion") and _reg_section_is_win10(
        text, r"Software\\Wow6432Node\\Microsoft\\Windows NT\\CurrentVersion"
    )


def _reg_section_is_win10(text: str, section: str) -> bool:
    marker = f"[{section}]"
    start = text.find(marker)
    if start < 0:
        return False
    next_section = text.find("\n[", start + len(marker))
    block = text[start:] if next_section < 0 else text[start:next_section]
    return '"ProductName"="Microsoft Windows 10"' in block and '"CurrentMajorVersionNumber"=dword:0000000a' in block


def _sanitize_fontconfig_env(env: dict[str, str]) -> None:
    for key in ("FONTCONFIG_FILE", "FONTCONFIG_PATH", "FONTCONFIG_SYSROOT"):
        env.pop(key, None)
    env["FC_FONTATIONS"] = "0"


def _gui_args(config: RunnerConfig) -> list[str]:
    return ["--gui"] if getattr(config, "tricks_gui", False) else []
