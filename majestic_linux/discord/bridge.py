from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..core.config import RunnerConfig


@dataclass(slots=True)
class DiscordBridge:
    process: subprocess.Popen | None = None
    bridge_path: Path | None = None


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def cache_path_for_url(url: str, cache_dir: Path = Path("cache")) -> Path:
    name = Path(urlparse(url).path).name or "discord-rpc-bridge.exe"
    return cache_dir / name


def download_bridge(url: str, output: Path, logger: logging.Logger | None = None) -> Path:
    if logger:
        logger.info("Downloading Discord RPC bridge: %s -> %s", url, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, output)
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(f"Discord RPC bridge download failed: {output}")
    output.chmod(output.stat().st_mode | 0o111)
    return output


def find_discord_bridge(config: RunnerConfig, compatdata: Path, logger: logging.Logger | None = None) -> Path | None:
    configured = config.discord_bridge_path.strip()
    url = config.discord_bridge_url
    if configured and is_url(configured):
        url = configured
        configured = None
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.exists() and configured_path.stat().st_size > 0:
            return configured_path
        if url:
            return download_bridge(url, configured_path, logger)
        if logger:
            logger.warning("Configured Discord RPC bridge was not found: %s", configured_path)
        return None
    if url:
        target = cache_path_for_url(url)
        return target if target.exists() and target.stat().st_size > 0 else download_bridge(url, target, logger)
    candidates = [
        Path("winediscordipcbridge.exe"),
        Path("winediscordipcbridge.exe.so"),
        Path("bridge.exe"),
        Path("rpc-bridge.exe"),
        Path("cache/winediscordipcbridge.exe"),
        Path("cache/bridge.exe"),
        compatdata / "pfx" / "drive_c" / "winediscordipcbridge.exe",
        compatdata / "pfx" / "drive_c" / "bridge.exe",
    ]
    return next((path for path in candidates if path.exists() and path.stat().st_size > 0), None)


def discord_ipc_sockets() -> list[Path]:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    sockets = list(runtime.glob("discord-ipc-*"))
    sockets.extend((runtime / "app" / "com.discordapp.Discord").glob("discord-ipc-*"))
    return sockets


def start_discord_bridge(
    config: RunnerConfig,
    *,
    compatdata: Path,
    proton_path: Path,
    steam_root: Path | None,
    app_id: str,
    dry_run: bool,
    logger: logging.Logger | None = None,
) -> DiscordBridge:
    bridge = find_discord_bridge(config, compatdata, logger)
    if bridge is None:
        if logger:
            logger.debug("Discord RPC bridge is not configured and no local bridge was found")
        return DiscordBridge()
    sockets = discord_ipc_sockets()
    if logger:
        if sockets:
            logger.info("Discord IPC socket detected: %s", sockets[0])
        else:
            logger.warning("Discord IPC socket was not found; Rich Presence may stay disabled")
        logger.info("Starting Discord RPC bridge: %s", bridge)
    if dry_run:
        return DiscordBridge(None, bridge)
    delay = max(config.discord_bridge_start_delay, 0)
    suffix = bridge.name.lower()
    if suffix.endswith((".exe", ".bat", ".cmd")):
        return _start_windows_bridge(bridge, compatdata, proton_path, steam_root, app_id, delay)
    return _start_native_bridge(bridge, compatdata, steam_root, delay)


def _start_windows_bridge(bridge: Path, compatdata: Path, proton_path: Path, steam_root: Path | None, app_id: str, delay: float) -> DiscordBridge:
    prefix_bridge = compatdata / "pfx" / "drive_c" / "winediscordipcbridge.exe"
    vbs = compatdata / "pfx" / "drive_c" / "run_bridge_hidden.vbs"
    prefix_bridge.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bridge, prefix_bridge)
    vbs.write_text('Set objShell = WScript.CreateObject("WScript.Shell")\nobjShell.Run "C:\\winediscordipcbridge.exe", 0, False\n', encoding="utf-8")
    env = os.environ.copy()
    env.update({"STEAM_COMPAT_DATA_PATH": str(compatdata), "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or ""), "STEAM_COMPAT_APP_ID": app_id, "SteamAppId": app_id, "SteamGameId": app_id, "WINEDEBUG": "-all"})
    command = [str(proton_path), "run", "wscript.exe", "C:\\run_bridge_hidden.vbs"]
    process = subprocess.Popen(["bash", "-c", f"sleep {delay}; exec \"$@\"", "discord-delay", *command], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return DiscordBridge(process, bridge)


def _start_native_bridge(bridge: Path, compatdata: Path, steam_root: Path | None, delay: float) -> DiscordBridge:
    bridge.chmod(bridge.stat().st_mode | 0o111)
    env = os.environ.copy()
    env.update({"WINEPREFIX": str(compatdata / "pfx"), "STEAM_COMPAT_DATA_PATH": str(compatdata), "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam_root or "")})
    process = subprocess.Popen([str(bridge)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if delay:
        time.sleep(delay)
    return DiscordBridge(process, bridge)


def stop_discord_bridge(handle: DiscordBridge, *, compatdata: Path, proton_path: Path, app_id: str, logger: logging.Logger | None = None) -> None:
    if handle.process is None:
        return
    if logger:
        logger.info("Stopping Discord RPC bridge")
    env = os.environ.copy()
    env.update({"STEAM_COMPAT_DATA_PATH": str(compatdata), "STEAM_COMPAT_APP_ID": app_id})
    subprocess.run([str(proton_path), "run", "taskkill", "/F", "/IM", "winediscordipcbridge.exe"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if handle.process.poll() is None:
        handle.process.terminate()
        try:
            handle.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            handle.process.kill()
