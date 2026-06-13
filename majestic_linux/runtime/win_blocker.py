from __future__ import annotations

import logging
import shutil
import filecmp
import os
import subprocess
import threading
import time
from pathlib import Path

from ..core.config import RunnerConfig
from .lifecycle import prefix_processes
from .proton import ProtonCommand
from .sidecars import SidecarHandle

BUNDLED_BLOCKER = Path("helpers") / "win-blocker" / "block_win.exe"
BLOCKER_IMAGE = "block_win.exe"
GAME_PROCESS_NAMES = ("GTA5.exe", "PlayGTAV.exe", "GTAVLauncher.exe")


def find_win_blocker(config: RunnerConfig, logger: logging.Logger | None = None) -> Path | None:
    if config.win_blocker_path:
        configured = config.win_blocker_path.expanduser()
        if configured.exists() and configured.stat().st_size > 0:
            return configured
        if logger:
            logger.warning("Configured Win blocker was not found: %s", configured)
        return None
    bundled = BUNDLED_BLOCKER
    if bundled.exists() and bundled.stat().st_size > 0:
        return bundled
    if logger:
        logger.warning("Bundled Win blocker was not found: %s", bundled)
    return None


def configure_win_blocker_sidecar(
    config: RunnerConfig,
    command: ProtonCommand,
    *,
    compatdata: Path,
    proton_path: Path,
    steam_root: Path | None,
    logger: logging.Logger | None = None,
) -> SidecarHandle:
    if not config.win_blocker_enabled:
        if logger:
            logger.info("Win blocker sidecar is disabled")
        return SidecarHandle("win-blocker")
    blocker = find_win_blocker(config, logger)
    if blocker is None:
        return SidecarHandle("win-blocker")
    prefix = compatdata / "pfx"
    prefix_blocker = _install_blocker(blocker, prefix)
    app_id = command.env.get("STEAM_COMPAT_APP_ID") or config.app_id or "271590"
    ready_marker = config.win_blocker_ready_marker.strip()
    ready_delay = max(config.win_blocker_ready_delay, 0.0)
    handle = SidecarHandle("win-blocker", None, prefix_blocker, windows=True, stop_image=BLOCKER_IMAGE)

    command.after_start.append(
        lambda main_process: _start_game_watcher(
            main_process,
            handle,
            prefix_blocker,
            proton_path,
            compatdata,
            steam_root,
            app_id,
            ready_marker,
            ready_delay,
            logger,
        )
    )
    if logger:
        logger.info("Win blocker will launch when Majestic client is ready: %s", prefix_blocker)
    return handle


def stop_win_blocker(
    handle: SidecarHandle,
    *,
    compatdata: Path,
    proton_path: Path,
    steam_root: Path | None,
    app_id: str,
    logger: logging.Logger | None = None,
) -> None:
    if not handle.executable:
        return
    _stop_blocker(handle, proton_path, compatdata, steam_root, app_id, logger)


def _install_blocker(source: Path, prefix: Path) -> Path:
    target_dir = prefix / "drive_c" / "majestic-sidecars" / "win-blocker"
    target = target_dir / BLOCKER_IMAGE
    target_dir.mkdir(parents=True, exist_ok=True)
    if not target.exists() or not filecmp.cmp(source, target, shallow=False):
        shutil.copy2(source, target)
    return target


def _start_with_proton(
    executable: Path,
    proton_path: Path,
    compatdata: Path,
    steam_root: Path | None,
    app_id: str,
    logger: logging.Logger | None,
) -> subprocess.Popen:
    env = _proton_sidecar_env(compatdata, steam_root, app_id)
    command = [str(proton_path), "run", str(executable)]
    if logger:
        logger.info("Starting Win blocker via Proton: %s", " ".join(command))
    return subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _start_game_watcher(
    main_process: subprocess.Popen,
    handle: SidecarHandle,
    blocker: Path,
    proton_path: Path,
    compatdata: Path,
    steam_root: Path | None,
    app_id: str,
    ready_marker: str,
    ready_delay: float,
    logger: logging.Logger | None,
) -> None:
    def run() -> None:
        prefix = compatdata / "pfx"
        deadline = time.monotonic() + 600
        started_at = time.time()
        game_seen = False
        main_exited_logged = False
        if logger:
            logger.info("Waiting for Majestic client marker before starting Win blocker: %s", ready_marker)
        while time.monotonic() < deadline:
            if main_process.poll() is not None and not game_seen and not main_exited_logged:
                main_exited_logged = True
                if logger:
                    logger.debug("Main Proton exited before Majestic client marker appeared; continuing to wait")
            game_running = _game_process_running(prefix, compatdata)
            if game_running:
                game_seen = True
                if _client_log_ready(prefix, ready_marker, started_at, logger):
                    if ready_delay > 0:
                        if logger:
                            logger.info("Majestic client marker detected; delaying Win blocker for %.1fs", ready_delay)
                        time.sleep(ready_delay)
                    if logger:
                        logger.info("Majestic client is ready; starting Win blocker")
                    _watch_blocker_until_game_exits(handle, blocker, proton_path, compatdata, steam_root, app_id, logger)
                    return
            if game_seen:
                game_seen = game_running
            time.sleep(1.0)
        if logger:
            logger.warning("Timed out waiting for Majestic client marker; Win blocker was not started")

    thread = threading.Thread(target=run, name="majestic-win-blocker-watcher", daemon=True)
    thread.start()


def _watch_blocker_until_game_exits(
    handle: SidecarHandle,
    blocker: Path,
    proton_path: Path,
    compatdata: Path,
    steam_root: Path | None,
    app_id: str,
    logger: logging.Logger | None,
) -> None:
    prefix = compatdata / "pfx"
    while _game_process_running(prefix, compatdata):
        if handle.process is None or handle.process.poll() is not None:
            handle.process = _start_with_proton(blocker, proton_path, compatdata, steam_root, app_id, logger)
        time.sleep(3.0)
    _stop_blocker(handle, proton_path, compatdata, steam_root, app_id, logger)
    if logger:
        logger.info("GTA process exited; Win blocker watcher is stopping")


def _stop_blocker(
    handle: SidecarHandle,
    proton_path: Path,
    compatdata: Path,
    steam_root: Path | None,
    app_id: str,
    logger: logging.Logger | None,
) -> None:
    env = _proton_sidecar_env(compatdata, steam_root, app_id or "271590")
    command = [str(proton_path), "run", "taskkill", "/F", "/IM", BLOCKER_IMAGE]
    if logger:
        logger.info("Stopping Win blocker via Proton taskkill")
    try:
        subprocess.run(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    except subprocess.TimeoutExpired:
        if logger:
            logger.warning("Timed out while stopping Win blocker")
    if handle.process and handle.process.poll() is None:
        handle.process.terminate()
        try:
            handle.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            handle.process.kill()


def _game_process_running(prefix: Path, compatdata: Path) -> bool:
    processes = prefix_processes(prefix, compatdata)
    return any(_contains_game_name(process.name) or _contains_game_name(process.cmdline) for process in processes)


def _contains_game_name(value: str) -> bool:
    lower = value.lower()
    return any(name.lower() in lower for name in GAME_PROCESS_NAMES)


def _client_log_ready(prefix: Path, marker: str, started_at: float, logger: logging.Logger | None) -> bool:
    if not marker:
        return True
    log = _latest_client_log(prefix, started_at)
    if log is None:
        return False
    try:
        text = log.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        if logger:
            logger.debug("Could not read Majestic client log %s: %s", log, exc)
        return False
    if marker in text:
        if logger:
            logger.info("Majestic client marker found in %s: %s", log, marker)
        return True
    return False


def _latest_client_log(prefix: Path, started_at: float) -> Path | None:
    logs_dir = prefix / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "majestic-launcher" / "Multiplayer" / "logs"
    try:
        candidates = [
            path
            for path in logs_dir.glob("client_*.log")
            if path.is_file() and path.stat().st_mtime >= started_at - 5
        ]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _proton_sidecar_env(compatdata: Path, steam_root: Path | None, app_id: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "WINEPREFIX": str(compatdata / "pfx"),
            "STEAM_COMPAT_DATA_PATH": str(compatdata),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or ""),
            "STEAM_COMPAT_APP_ID": app_id,
            "WINEDEBUG": "-all",
        }
    )
    return env
