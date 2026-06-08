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


def _has_tool(name: str) -> bool:
    return shutil.which(name) is not None


def select_tricks_tool(platform: str, override: str = "auto") -> tuple[str | None, str]:
    override = (override or "auto").lower()
    if override in {"winetricks", "protontricks"}:
        return (override, "forced by TRICKS_TOOL") if _has_tool(override) else (None, f"{override} not installed")
    if platform == "steam":
        return ("protontricks", "Steam uses protontricks") if _has_tool("protontricks") else (None, "protontricks not installed")
    if platform == "egs":
        return ("winetricks", "EGS/Heroic uses winetricks") if _has_tool("winetricks") else (None, "winetricks not installed")
    if _has_tool("protontricks"):
        return "protontricks", "RGL uses available protontricks"
    if _has_tool("winetricks"):
        return "winetricks", "RGL fallback to available winetricks"
    return None, "neither protontricks nor winetricks is installed"


def build_win10_plan(config: RunnerConfig, platform: str, compatdata: Path) -> TricksPlan:
    tool, reason = select_tricks_tool(platform, config.tricks_tool)
    env = os.environ.copy()
    if tool == "protontricks":
        app_id = config.app_id if config.app_id and config.app_id != "0" else "271590"
        return TricksPlan(tool, reason, ["protontricks", app_id, "win10"], env)
    if tool == "winetricks":
        env["WINEPREFIX"] = str(compatdata / "pfx")
        return TricksPlan(tool, reason, ["winetricks", "-q", "win10"], env)
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
