from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from pathlib import Path

from ..core.config import load_config
from ..core.config_file import ensure_config_file
from ..core.logger import setup_logging
from ..discord.bridge import discord_ipc_sockets, find_discord_bridge
from ..patching.patcher import patch_state
from ..runtime.assets import inspect_launcher_assets
from ..runtime.fixups import prepare_proton_runtime_fixups
from ..runtime.launcher import installer_target
from ..runtime.lifecycle import prefix_processes
from ..runtime.proton import build_proton_command
from ..runtime.tricks import build_win10_plan
from ..runtime.wine import prepare_wine_mapping
from .context import load_context, print_detection

py_platform = importlib.import_module("platform")


def cmd_config(args: argparse.Namespace) -> int:
    logger = setup_logging(args.debug, Path("logs"))
    path = Path(args.config).expanduser()
    created = ensure_config_file(path, logger)
    print(f"Config:  {path}")
    print(f"Created: {'yes' if created else 'no'}")
    print(path.read_text(encoding="utf-8"))
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    context, _logger = load_context(args)
    print_detection(context.result)
    return 0


def cmd_env(args: argparse.Namespace) -> int:
    context, _logger = load_context(args)
    config, result = context.config, context.result
    if not all((result.proton_path, result.compatdata_path, result.gta_path, result.majestic_exe)):
        print_detection(result)
        return 1
    config.runtime_library_paths = prepare_proton_runtime_fixups(result.proton_path, dry_run=True)
    mapping = prepare_wine_mapping(result.compatdata_path, result.gta_path, config.gta_wine_drive, dry_run=True)
    command = build_proton_command(
        config, result.proton_path, result.compatdata_path, result.steam_root, result.majestic_exe, result.selected_platform, mapping
    )
    print("Command:")
    print(" ".join(command.argv))
    print("\nEnvironment:")
    for key in sorted(k for k in command.env if k.startswith(("STEAM_", "MAJESTIC_", "GAME_", "DISABLE_", "GST_")) or k in {"LANG", "LC_ALL", "LC_CTYPE", "LD_LIBRARY_PATH", "WINEDLLOVERRIDES"}):
        print(f"{key}={command.env[key]}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    context, logger = load_context(args)
    config, result = context.config, context.result
    print(f"OS:                {py_platform.platform()}")
    print(f"Python:            {sys.version.split()[0]}")
    print_detection(result)
    print(f"Wine drive:        {config.gta_wine_drive.upper()}:")
    print(f"Locale/Input:      {config.locale} / {config.input_method}")
    print(f"XKB layout:        {config.xkb_layout or '-'} ({config.xkb_options or 'no options'})")
    if result.compatdata_path:
        plan = build_win10_plan(config, result.selected_platform, result.compatdata_path)
        print(f"Tricks tool:       {plan.tool or '-'} ({plan.reason})")
        print(f"Wine prefix:       {result.compatdata_path / 'pfx'}")
        print(f"wineserver:        {shutil.which('wineserver') or '-'}")
        bridge = find_discord_bridge(config, result.compatdata_path, logger)
        print(f"Discord bridge:    {bridge or '-'}")
        sockets = discord_ipc_sockets()
        print(f"Discord IPC:       {sockets[0] if sockets else '-'}")
        processes = prefix_processes(result.compatdata_path / "pfx", result.compatdata_path)
        print(f"Prefix processes:  {len(processes)}")
        for process in processes[:8]:
            print(f"  pid={process.pid} name={process.name}")
    if result.proton_path:
        print(f"Proton executable: {'yes' if result.proton_path.is_file() else 'no'}")
    if result.gta_path:
        for name in ("GTA5.exe", "PlayGTAV.exe", "GTAVLauncher.exe", "steam_api64.dll", "EOSSDK-Win64-Shipping.dll"):
            print(f"{name:22} {'yes' if (result.gta_path / name).exists() else 'no'}")
    patch_root = config.source_root or (result.majestic_exe.parent if result.majestic_exe else None)
    if patch_root:
        print(f"JS patch state:    {patch_state(patch_root)}")
        _print_asset_report(inspect_launcher_assets(patch_root, logger))
    print(f"Shutdown cleanup:  {'enabled' if config.kill_wine_on_exit else 'disabled'}")
    print(f"Xalia warning:     {'ignored on shutdown' if config.ignore_xalia_task_cancelled else 'not ignored'}")
    problems = _doctor_problems(config, result)
    if problems:
        print("\nProblems:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    logger.success("Doctor checks passed")  # type: ignore[attr-defined]
    return 0


def _doctor_problems(config, result) -> list[str]:
    problems = []
    if result.steam_root is None:
        problems.append("Steam root was not found; set STEAM_ROOT if Proton is managed by Steam.")
    if result.proton_path is None:
        problems.append("Proton was not found; set PROTON_PATH.")
    if result.gta_path is None:
        problems.append("GTA V was not found; set GTA_PATH.")
    if result.compatdata_path is None:
        problems.append("Compatdata prefix was not found; set STEAM_COMPAT_DATA_PATH.")
    elif not (result.compatdata_path / "pfx").exists():
        problems.append("Wine prefix does not exist inside compatdata.")
    if result.proton_path is not None and not result.proton_path.is_file():
        problems.append("Proton path exists but is not an executable file.")
    if result.majestic_exe is None:
        installer = installer_target(config, result.compatdata_path) if result.compatdata_path else config.installer_path or "-"
        print(f"Installer path:    {installer}")
        print(f"Installer URL:     {config.installer_url or '-'}")
        problems.append(
            "Majestic Launcher.exe was not found in MajesticLauncher or MajesticLauncherGLOBAL; "
            "run command can install it automatically, or set MAJESTIC_EXE."
        )
    if result.selected_platform == "steam" and result.detected_platform != "steam":
        problems.append(f"Selected steam, but GTA files look like {result.detected_platform}. Check MAJESTIC_PLATFORM.")
    return problems


def _print_asset_report(report) -> None:
    print("Icon/font assets:")
    print(f"  roots:       {len(report.roots)}")
    print(f"  fonts:       {len(report.fonts)}")
    for path in report.fonts[:8]:
        print(f"    font: {path}")
    print(f"  icons:       {len(report.icons)}")
    for path in report.icons[:8]:
        print(f"    icon: {path}")
    print(f"  @font-face:  {len(report.font_faces)}")
    for path in report.font_faces[:8]:
        print(f"    css:  {path}")
    print(f"  broken urls: {len(report.broken_urls)}")
    for item in report.broken_urls[:8]:
        print(f"    missing: {item}")
    for warning in report.warnings:
        print(f"  recommendation: {warning}")
