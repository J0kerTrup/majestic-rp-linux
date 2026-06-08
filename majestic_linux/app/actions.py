from __future__ import annotations

import argparse
from pathlib import Path

from ..core.errors import RunnerError
from ..detection.paths import DetectionResult
from ..discord.bridge import start_discord_bridge, stop_discord_bridge
from ..patching.patcher import patch_js_tree
from ..runtime.cleanup import delete_cleanup_candidates, find_majestic_cleanup_candidates
from ..runtime.input import apply_xkb_layout
from ..runtime.fixups import prepare_proton_runtime_fixups
from ..runtime.launcher import install_majestic_launcher
from ..runtime.proton import build_proton_command, run_proton_managed
from ..runtime.tricks import apply_win10_mode
from ..runtime.wine import ensure_egs_launcher_symlink, prepare_wine_mapping
from ..radio.doctor import build_radio_report, radio_safe_env
from .context import load_context


def _patch_root(config, result: DetectionResult) -> Path:
    if config.source_root:
        return config.source_root
    if result.majestic_exe:
        return result.majestic_exe.parent
    raise RunnerError("Cannot patch: MAJESTIC_SOURCE_ROOT or MAJESTIC_EXE is required")


def cmd_patch(args: argparse.Namespace) -> int:
    context, logger = load_context(args)
    config, result = context.config, context.result
    report = patch_js_tree(_patch_root(config, result), dry_run=config.dry_run, logger=logger, permissions=config.majestic_permissions)
    logger.success("Patch completed, changed=%s, files=%s", report.changed, len(report.statuses))  # type: ignore[attr-defined]
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    context, _logger = load_context(args)
    roots = [Path(".")]
    if context.result.majestic_exe:
        roots.append(context.result.majestic_exe.parent)
    patterns = ("*.majestic-python-bak", "*.majestic-proton-bak", "*.majestic-proton-bak-*", "app.asar.bak")
    backups = sorted({path for root in roots for pattern in patterns for path in root.rglob(pattern)})
    if not backups:
        print("No patch backups found.")
        return 0
    for path in backups:
        print(path)
    if args.dry_run:
        return 0
    if input("Delete these backups? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return 0
    for path in backups:
        path.unlink()
    print(f"Deleted {len(backups)} backup files.")
    return 0


def cmd_purge_majestic(args: argparse.Namespace) -> int:
    context, _logger = load_context(args)
    result = context.result
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
    if input('\nType "DELETE" to remove these Majestic files: ').strip() != "DELETE":
        print("Cancelled.")
        return 0
    print(f"Deleted {delete_cleanup_candidates(candidates)} Majestic files/directories.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    context, logger = load_context(args)
    config, result = context.config, context.result
    if getattr(args, "disable_winegstreamer", False):
        config.radio_disable_winegstreamer = True
    if config.radio_disable_winegstreamer:
        logger.warning("Wine GStreamer is disabled for this run: WINEDLLOVERRIDES=winegstreamer=d")
    missing = [name for name, value in (("PROTON_PATH", result.proton_path), ("STEAM_COMPAT_DATA_PATH", result.compatdata_path), ("GTA_PATH", result.gta_path)) if value is None]
    if missing:
        raise RunnerError("Missing required paths: " + ", ".join(missing))
    if result.majestic_exe is None:
        result.majestic_exe = install_majestic_launcher(
            config, proton_path=result.proton_path, compatdata=result.compatdata_path, steam_root=result.steam_root, dry_run=config.dry_run, logger=logger
        )
    if result.majestic_exe is None:
        raise RunnerError("Majestic Launcher.exe is still missing after installer step")
    if result.selected_platform == "egs":
        ensure_egs_launcher_symlink(result.gta_path, dry_run=config.dry_run, logger=logger)
    config.runtime_library_paths = prepare_proton_runtime_fixups(result.proton_path, dry_run=config.dry_run, logger=logger)
    mapping = prepare_wine_mapping(result.compatdata_path, result.gta_path, config.gta_wine_drive, dry_run=config.dry_run, logger=logger)
    apply_xkb_layout(config, dry_run=config.dry_run, logger=logger)
    apply_win10_mode(config, result.selected_platform, result.compatdata_path, dry_run=config.dry_run, logger=logger)
    discord = start_discord_bridge(
        config,
        compatdata=result.compatdata_path,
        proton_path=result.proton_path,
        steam_root=result.steam_root,
        app_id=config.app_id,
        dry_run=config.dry_run,
        logger=logger,
    )
    try:
        patch_js_tree(_patch_root(config, result), dry_run=config.dry_run, logger=logger, permissions=config.majestic_permissions)
    except RunnerError as exc:
        logger.warning("JS patch skipped/failed before launch: %s", exc)
    command = build_proton_command(config, result.proton_path, result.compatdata_path, result.steam_root, result.majestic_exe, result.selected_platform, mapping)
    if getattr(args, "radio_safe", False) or config.radio_safe_mode:
        logger.info("G Radio safe mode enabled: collecting report and enabling extra Proton/Wine logs")
        report = build_radio_report(config, result, dry_run=config.dry_run)
        logger.info("G Radio diagnostic report: %s", report.report_path)
        command.env = radio_safe_env(command.env)
    try:
        return run_proton_managed(command, config, result.compatdata_path, dry_run=config.dry_run, logger=logger)
    finally:
        stop_discord_bridge(discord, compatdata=result.compatdata_path, proton_path=result.proton_path, app_id=config.app_id, logger=logger)
