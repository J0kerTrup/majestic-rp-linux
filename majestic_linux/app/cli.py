from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

from ..core.config import config_summary, load_config
from ..core.errors import RunnerError
from ..core.logger import setup_logging
from ..detection.paths import DetectionResult, detect_all, looks_like_gta
from ..patching.patcher import patch_js_tree, patch_state
from ..runtime.launcher import install_majestic_launcher, installer_target
from ..runtime.cleanup import delete_cleanup_candidates, find_majestic_cleanup_candidates
from ..runtime.proton import build_proton_command, run_proton
from ..runtime.wine import ensure_egs_launcher_symlink, prepare_wine_mapping

py_platform = importlib.import_module("platform")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="majestic_linux", description="Majestic RP Linux Proton runner")
    parser.add_argument("--config", default="majestic-runner.conf", help="Path to optional shell-style runner config")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without changing files or launching Proton")
    sub = parser.add_subparsers(dest="command")
    for command in ("run", "doctor", "detect", "patch", "clean", "purge-majestic"):
        sub.add_parser(command)
    return parser


def _print_detection(result: DetectionResult) -> None:
    print(f"Steam root:        {result.steam_root or '-'}")
    print(f"Proton:            {result.proton_path or '-'}")
    print(f"Compatdata:        {result.compatdata_path or '-'}")
    print(f"GTA V:             {result.gta_path or '-'}")
    print(f"Majestic Launcher: {result.majestic_exe or '-'}")
    print(f"Detected platform: {result.detected_platform}")
    print(f"Selected platform: {result.selected_platform}")


def cmd_detect(args: argparse.Namespace) -> int:
    logger = setup_logging(args.debug, Path("logs"))
    config = load_config(args.config, dry_run=args.dry_run or None)
    logger.debug("Config: %s", config_summary(config))
    _print_detection(detect_all(config, logger))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    logger = setup_logging(args.debug, Path("logs"))
    config = load_config(args.config, dry_run=args.dry_run or None)
    result = detect_all(config, logger)
    print(f"OS:                {py_platform.platform()}")
    print(f"Python:            {sys.version.split()[0]}")
    _print_detection(result)
    print(f"Wine drive:        {config.gta_wine_drive.upper()}:")
    if result.gta_path:
        for name in ("GTA5.exe", "PlayGTAV.exe", "GTAVLauncher.exe", "steam_api64.dll", "EOSSDK-Win64-Shipping.dll"):
            print(f"{name:22} {'yes' if (result.gta_path / name).exists() else 'no'}")
    patch_root = config.source_root or (result.majestic_exe.parent if result.majestic_exe else None)
    if patch_root:
        print(f"JS patch state:    {patch_state(patch_root)}")
    problems = []
    if result.steam_root is None:
        problems.append("Steam root was not found; set STEAM_ROOT if Proton is managed by Steam.")
    if result.proton_path is None:
        problems.append("Proton was not found; set PROTON_PATH.")
    if result.gta_path is None or not looks_like_gta(result.gta_path):
        problems.append("GTA V was not found; set GTA_PATH.")
    if result.compatdata_path is None:
        problems.append("Compatdata prefix was not found; set STEAM_COMPAT_DATA_PATH.")
    if result.majestic_exe is None:
        print(f"Installer path:    {installer_target(config, result.compatdata_path) if result.compatdata_path else config.installer_path or '-'}")
        print(f"Installer URL:     {config.installer_url or '-'}")
        problems.append("Majestic Launcher.exe was not found; run command can install it automatically, or set MAJESTIC_EXE.")
    if problems:
        print("\nProblems:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    logger.success("Doctor checks passed")  # type: ignore[attr-defined]
    return 0


def _patch_root(config, result: DetectionResult) -> Path:
    if config.source_root:
        return config.source_root
    if result.majestic_exe:
        return result.majestic_exe.parent
    raise RunnerError("Cannot patch: MAJESTIC_SOURCE_ROOT or MAJESTIC_EXE is required")


def cmd_patch(args: argparse.Namespace) -> int:
    logger = setup_logging(args.debug, Path("logs"))
    config = load_config(args.config, dry_run=args.dry_run or None)
    result = detect_all(config, logger)
    report = patch_js_tree(_patch_root(config, result), dry_run=config.dry_run, logger=logger, permissions=config.majestic_permissions)
    logger.success("Patch completed, changed=%s, files=%s", report.changed, len(report.statuses))  # type: ignore[attr-defined]
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    logger = setup_logging(args.debug, Path("logs"))
    config = load_config(args.config, dry_run=args.dry_run or None)
    result = detect_all(config, logger)
    roots = [Path(".")]
    if result.majestic_exe:
        roots.append(result.majestic_exe.parent)
    patterns = ("*.majestic-python-bak", "*.majestic-proton-bak", "*.majestic-proton-bak-*", "app.asar.bak")
    backups = sorted({path for root in roots for pattern in patterns for path in root.rglob(pattern)})
    if not backups:
        print("No patch backups found.")
        return 0
    for path in backups:
        print(path)
    if args.dry_run:
        return 0
    answer = input("Delete these backups? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled.")
        return 0
    for path in backups:
        path.unlink()
    print(f"Deleted {len(backups)} backup files.")
    return 0


def cmd_purge_majestic(args: argparse.Namespace) -> int:
    logger = setup_logging(args.debug, Path("logs"))
    config = load_config(args.config, dry_run=args.dry_run or None)
    result = detect_all(config, logger)
    if result.compatdata_path is None:
        raise RunnerError("Cannot purge Majestic data: STEAM_COMPAT_DATA_PATH was not found")
    candidates = find_majestic_cleanup_candidates(result.compatdata_path, result.gta_path)
    if not candidates:
        print("No Majestic launcher/cache files found.")
        return 0
    print("Majestic files/directories selected for removal:")
    for candidate in candidates:
        print(f"- {candidate.path}  [{candidate.reason}]")
    print("\nProtected: GTA V install path is never removed by this command.")
    if args.dry_run:
        return 0
    answer = input('\nType "DELETE" to remove these Majestic files: ').strip()
    if answer != "DELETE":
        print("Cancelled.")
        return 0
    deleted = delete_cleanup_candidates(candidates)
    print(f"Deleted {deleted} Majestic files/directories.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    logger = setup_logging(args.debug, Path("logs"))
    config = load_config(args.config, dry_run=args.dry_run or None)
    result = detect_all(config, logger)
    missing = []
    if result.proton_path is None:
        missing.append("PROTON_PATH")
    if result.compatdata_path is None:
        missing.append("STEAM_COMPAT_DATA_PATH")
    if result.gta_path is None:
        missing.append("GTA_PATH")
    if missing:
        raise RunnerError("Missing required paths: " + ", ".join(missing))
    if result.majestic_exe is None:
        result.majestic_exe = install_majestic_launcher(
            config,
            proton_path=result.proton_path,
            compatdata=result.compatdata_path,
            steam_root=result.steam_root,
            dry_run=config.dry_run,
            logger=logger,
        )
    if result.majestic_exe is None:
        raise RunnerError("Majestic Launcher.exe is still missing after installer step")
    if result.selected_platform == "egs":
        ensure_egs_launcher_symlink(result.gta_path, dry_run=config.dry_run, logger=logger)
    mapping = prepare_wine_mapping(result.compatdata_path, result.gta_path, config.gta_wine_drive, dry_run=config.dry_run, logger=logger)
    try:
        patch_js_tree(_patch_root(config, result), dry_run=config.dry_run, logger=logger, permissions=config.majestic_permissions)
    except RunnerError as exc:
        logger.warning("JS patch skipped/failed before launch: %s", exc)
    command = build_proton_command(config, result.proton_path, result.compatdata_path, result.steam_root, result.majestic_exe, result.selected_platform, mapping)
    return run_proton(command, dry_run=config.dry_run, logger=logger)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.command = args.command or "run"
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        return {
            "run": cmd_run,
            "doctor": cmd_doctor,
            "detect": cmd_detect,
            "patch": cmd_patch,
            "clean": cmd_clean,
            "purge-majestic": cmd_purge_majestic,
        }[args.command](args)
    except RunnerError as exc:
        logger = setup_logging(args.debug, Path("logs"))
        logger.error("%s", exc)
        return 2
