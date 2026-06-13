from __future__ import annotations

import argparse
from pathlib import Path

from ..core.errors import RunnerError
from ..detection.paths import DetectionResult, find_majestic_exes
from ..discord.bridge import configure_discord_bridge_environment, stop_discord_bridge
from ..patching.patcher import patch_js_tree
from ..runtime.cleanup import UninstallCleanupOptions, delete_cleanup_candidates, find_majestic_cleanup_candidates, find_majestic_uninstall_candidates
from ..runtime.fonts import apply_emoji_font_fix, emoji_font_fix_is_applied
from ..runtime.input import clear_caps_lock
from ..runtime.fixups import prepare_proton_runtime_fixups
from ..runtime.launcher import install_majestic_launcher
from ..runtime.multiplayer_repair import latest_repair_time, repair_gta_conflicts, repair_multiplayer_cache
from ..runtime.proton import build_proton_command, run_proton_managed
from ..runtime.registry import apply_wine_registry_fixups
from ..runtime.tricks import apply_powershell, apply_win10_mode, powershell_setup_is_complete
from ..runtime.win_blocker import configure_win_blocker_sidecar, stop_win_blocker
from ..runtime.wine import ensure_egs_launcher_symlink, prepare_optional_storage_drive, prepare_wine_mapping
from ..radio.doctor import build_radio_report, radio_safe_env
from .context import load_context

SETUP_MARKER_NAME = ".majestic-runner-setup.done"


def _patch_root(config, result: DetectionResult) -> Path:
    if config.source_root:
        return config.source_root
    if result.majestic_exe:
        return result.majestic_exe.parent
    raise RunnerError("Cannot patch: MAJESTIC_SOURCE_ROOT or MAJESTIC_EXE is required")


def _setup_marker(compatdata: Path) -> Path:
    return compatdata / "pfx" / SETUP_MARKER_NAME


def _setup_is_complete(config, result: DetectionResult) -> bool:
    return (
        result.compatdata_path is not None
        and result.majestic_exe is not None
        and _setup_marker(result.compatdata_path).exists()
        and emoji_font_fix_is_applied(result.compatdata_path)
        and (not config.tricks_powershell or powershell_setup_is_complete(result.compatdata_path))
    )


def _require_launch_paths(result: DetectionResult) -> None:
    missing = [name for name, value in (("PROTON_PATH", result.proton_path), ("STEAM_COMPAT_DATA_PATH", result.compatdata_path), ("GTA_PATH", result.gta_path)) if value is None]
    if missing:
        raise RunnerError("Missing required paths: " + ", ".join(missing))


def _ensure_majestic_launcher(config, result: DetectionResult, logger) -> None:
    if result.majestic_exe is not None:
        return
    result.majestic_exe = install_majestic_launcher(
        config, proton_path=result.proton_path, compatdata=result.compatdata_path, steam_root=result.steam_root, dry_run=config.dry_run, logger=logger
    )
    if result.majestic_exe is None:
        raise RunnerError("Majestic Launcher.exe is still missing after installer step in MajesticLauncher or MajesticLauncherGLOBAL")


def _prepare_wine_drives(config, result: DetectionResult, logger):
    mapping = prepare_wine_mapping(result.compatdata_path, result.gta_path, config.gta_wine_drive, dry_run=config.dry_run, logger=logger)
    prepare_optional_storage_drive(
        result.compatdata_path,
        config.majestic_storage_path,
        config.majestic_storage_wine_drive,
        reserved_letters={config.gta_wine_drive.lower()},
        dry_run=config.dry_run,
        logger=logger,
    )
    return mapping


def _prepare_prefix_and_launcher(context, logger, *, force: bool = False) -> None:
    config, result = context.config, context.result
    _require_launch_paths(result)
    _prepare_wine_drives(config, result, logger)
    if not force and _setup_is_complete(config, result):
        logger.info("One-time setup already completed; skipping patch/setup steps")
        return
    _ensure_majestic_launcher(config, result, logger)
    config.runtime_library_paths = prepare_proton_runtime_fixups(result.proton_path, dry_run=config.dry_run, logger=logger)
    if result.selected_platform == "egs":
        ensure_egs_launcher_symlink(result.gta_path, dry_run=config.dry_run, logger=logger)
    apply_win10_mode(config, result.selected_platform, result.compatdata_path, dry_run=config.dry_run, logger=logger)
    apply_powershell(config, result.selected_platform, result.compatdata_path, dry_run=config.dry_run, logger=logger)
    apply_wine_registry_fixups(config, result.compatdata_path, dry_run=config.dry_run, logger=logger)
    apply_emoji_font_fix(config, result.compatdata_path, dry_run=config.dry_run, logger=logger)
    report = patch_js_tree(_patch_root(config, result), dry_run=config.dry_run, logger=logger, permissions=config.majestic_permissions)
    if not config.dry_run:
        marker = _setup_marker(result.compatdata_path)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("ok\n", encoding="utf-8")
    logger.success("Setup completed, patch changed=%s, files=%s", report.changed, len(report.statuses))  # type: ignore[attr-defined]


def _apply_cli_modes(config, args: argparse.Namespace) -> None:
    if getattr(args, "gui", False):
        config.tricks_gui = True


def cmd_patch(args: argparse.Namespace) -> int:
    context, logger = load_context(args)
    _apply_cli_modes(context.config, args)
    _prepare_prefix_and_launcher(context, logger, force=True)
    _repair_multiplayer_if_needed(context, logger, args)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    context, logger = load_context(args)
    _apply_cli_modes(context.config, args)
    _prepare_prefix_and_launcher(context, logger)
    return 0


def _repair_multiplayer_if_needed(context, logger, args: argparse.Namespace) -> None:
    config, result = context.config, context.result
    if result.compatdata_path is None:
        return
    if getattr(args, "no_repair_multiplayer_cache", False):
        logger.info("Majestic Multiplayer cache repair skipped by CLI flag")
        return
    force = getattr(args, "repair_multiplayer_cache", False)
    if not force and not config.repair_multiplayer_cache_on_patch:
        logger.info("Majestic Multiplayer cache repair disabled in config")
        return
    reports = repair_multiplayer_cache(
        result.compatdata_path,
        threshold=config.repair_wheel_error_threshold,
        force=force,
        dry_run=config.dry_run,
        logger=logger,
        min_mtime=latest_repair_time(result.compatdata_path, result.gta_path),
    )
    if config.repair_gta_conflicts_on_patch and result.gta_path is not None:
        reports = repair_gta_conflicts(result.gta_path, reports, dry_run=config.dry_run, logger=logger)
    if not reports:
        logger.info("Majestic Multiplayer cache was not found; repair skipped")
        return
    repaired = [report for report in reports if report.repaired]
    if repaired:
        for report in repaired:
            action = "Would archive" if report.dry_run else "Archived"
            if report.backup_path:
                logger.warning("%s Majestic Multiplayer cache to %s", action, report.backup_path)
            if report.gta_root_backup_path:
                logger.warning("%s stale GTA root Majestic files to %s", action, report.gta_root_backup_path)
            if report.gen9_backup_path:
                logger.warning("%s GTA Gen9/Enhanced DLC folders to %s", action, report.gen9_backup_path)
        if any(report.backup_path or report.gta_root_backup_path for report in repaired):
            logger.warning("Majestic will redownload/reinject repaired files on next launch")


def cmd_clean(args: argparse.Namespace) -> int:
    context, _logger = load_context(args)
    roots = [Path(".")]
    if context.result.compatdata_path:
        roots.extend(path.parent for path in find_majestic_exes(context.config, context.result.compatdata_path))
    if context.result.majestic_exe:
        roots.append(context.result.majestic_exe.parent)
    roots = list(dict.fromkeys(roots))
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
    options = UninstallCleanupOptions(
        include_trash=getattr(args, "include_trash", False),
        include_installers=getattr(args, "include_installers", False),
        include_projects=getattr(args, "include_projects", False),
    )
    candidates = find_majestic_uninstall_candidates(
        compatdata=result.compatdata_path,
        gta_path=result.gta_path,
        steam_root=result.steam_root,
        majestic_exe=result.majestic_exe,
        options=options,
    )
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
    _apply_cli_modes(config, args)
    _require_launch_paths(result)
    if not _setup_is_complete(config, result):
        _prepare_prefix_and_launcher(context, logger)
    _ensure_majestic_launcher(config, result, logger)
    config.runtime_library_paths = prepare_proton_runtime_fixups(result.proton_path, dry_run=config.dry_run, logger=logger)
    mapping = _prepare_wine_drives(config, result, logger)
    clear_caps_lock(dry_run=config.dry_run, logger=logger)
    command = build_proton_command(config, result.proton_path, result.compatdata_path, result.steam_root, result.majestic_exe, result.selected_platform, mapping)
    discord = configure_discord_bridge_environment(
        config,
        compatdata=result.compatdata_path,
        proton_path=result.proton_path,
        steam_root=result.steam_root,
        app_id=config.app_id,
        env=command.env,
        logger=logger,
    )
    win_blocker = configure_win_blocker_sidecar(
        config,
        command,
        compatdata=result.compatdata_path,
        proton_path=result.proton_path,
        steam_root=result.steam_root,
        logger=logger,
    )
    if getattr(args, "radio_safe", False):
        logger.info("G Radio safe mode enabled: collecting report and enabling extra Proton/Wine logs")
        report = build_radio_report(config, result, dry_run=config.dry_run)
        logger.info("G Radio diagnostic report: %s", report.report_path)
        command.env = radio_safe_env(command.env)
    try:
        return run_proton_managed(command, config, result.compatdata_path, dry_run=config.dry_run, logger=logger)
    finally:
        stop_win_blocker(
            win_blocker,
            compatdata=result.compatdata_path,
            proton_path=result.proton_path,
            steam_root=result.steam_root,
            app_id=config.app_id,
            logger=logger,
        )
        stop_discord_bridge(discord, compatdata=result.compatdata_path, proton_path=result.proton_path, app_id=config.app_id, logger=logger)
