from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..core.errors import RunnerError
from ..core.logger import setup_logging
from .commands import cmd_analyze_crash, cmd_clean, cmd_config, cmd_detect, cmd_doctor, cmd_doctor_radio, cmd_env, cmd_install, cmd_patch, cmd_purge_majestic, cmd_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="majestic_linux", description="Majestic RP Linux Proton runner")
    parser.add_argument("--config", default="majestic-runner.conf", help="Path to shell-style runner config")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without changing files or launching Proton")
    sub = parser.add_subparsers(dest="command")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--radio-safe", action="store_true", help="Enable G Radio safe diagnostics for this run")
    run_parser.add_argument("--disable-winegstreamer", action="store_true", help="Disable Wine GStreamer for this run")
    run_parser.add_argument("--gui", action="store_true", help="Use GUI mode for first-run setup tricks")
    for command in ("install", "installer", "patch"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("--gui", action="store_true", help="Use GUI mode for protontricks/winetricks setup")
        if command == "patch":
            command_parser.add_argument("--repair-multiplayer-cache", action="store_true", help="Force Majestic Multiplayer cache repair")
            command_parser.add_argument("--no-repair-multiplayer-cache", action="store_true", help="Skip Majestic Multiplayer cache repair")
    purge_parser = sub.add_parser("purge-majestic")
    purge_parser.add_argument("--include-trash", action="store_true", help="Also remove Majestic entries from the Linux trash")
    purge_parser.add_argument("--include-installers", action="store_true", help="Also remove Majestic installer files from home/download folders")
    purge_parser.add_argument("--include-projects", action="store_true", help="Also remove local majestic-rp-linux project copies/zips")
    for command in ("doctor", "doctor-radio", "analyze-crash", "config", "detect", "env", "dry-run", "clean"):
        sub.add_parser(command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.command = args.command or "run"
    if args.command == "dry-run":
        args.command = "run"
        args.dry_run = True
    os.environ.setdefault("PYTHONUTF8", "1")
    commands = {
        "run": cmd_run,
        "doctor": cmd_doctor,
        "doctor-radio": cmd_doctor_radio,
        "analyze-crash": cmd_analyze_crash,
        "config": cmd_config,
        "detect": cmd_detect,
        "env": cmd_env,
        "install": cmd_install,
        "installer": cmd_install,
        "patch": cmd_patch,
        "clean": cmd_clean,
        "purge-majestic": cmd_purge_majestic,
    }
    try:
        return commands[args.command](args)
    except RunnerError as exc:
        logger = setup_logging(args.debug, Path("logs"))
        logger.error("%s", exc)
        return 2
