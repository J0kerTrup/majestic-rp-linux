from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ..core.config import RunnerConfig
from ..runtime.sidecars import SidecarContext, SidecarHandle, SidecarSpec, configure_remote_debug_sidecar, stop_sidecar

DiscordBridge = SidecarHandle


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
    if not config.discord_bridge_enabled:
        if logger:
            logger.info("Discord RPC bridge is disabled")
        return None
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
    sockets: list[Path] = []
    for root in discord_ipc_roots():
        sockets.extend(root.glob("discord-ipc-*"))
    return [path for path in sockets if path.is_socket()]


def discord_ipc_roots() -> list[Path]:
    temp = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or os.environ.get("TMP") or os.environ.get("TEMP") or "/tmp"
    return [
        Path(temp),
        Path(temp) / "app" / "com.discordapp.Discord",
        Path(temp) / "snap.discord-canary",
        Path(temp) / "snap.discord",
        Path(f"/run/user/{os.getuid()}"),
    ]


def configure_discord_bridge_environment(
    config: RunnerConfig,
    *,
    compatdata: Path,
    proton_path: Path,
    steam_root: Path | None,
    app_id: str,
    env: dict[str, str],
    logger: logging.Logger | None = None,
) -> DiscordBridge:
    if not config.discord_bridge_enabled:
        if logger:
            logger.info("Discord RPC bridge is disabled")
        return DiscordBridge("discord-rpc")
    bridge = find_discord_bridge(config, compatdata, logger)
    if bridge is None:
        if logger:
            logger.debug("Discord RPC bridge is not configured and no local bridge was found")
        return DiscordBridge("discord-rpc")
    sockets = discord_ipc_sockets()
    if logger:
        if sockets:
            logger.info("Discord IPC socket detected: %s", sockets[0])
        else:
            logger.warning("Discord IPC socket was not found; Rich Presence may stay disabled")
        logger.info("Configuring Discord RPC bridge via PROTON_REMOTE_DEBUG_CMD: %s", bridge)
    context = SidecarContext(config, compatdata, proton_path, steam_root, app_id, False, logger)
    return configure_remote_debug_sidecar(
        SidecarSpec(name="discord-rpc", executable=bridge, stop_image="winediscordipcbridge.exe"),
        context,
        env,
        filesystem_paths=sockets[:1],
    )


def stop_discord_bridge(handle: DiscordBridge, *, compatdata: Path, proton_path: Path, app_id: str, logger: logging.Logger | None = None) -> None:
    context = SidecarContext(None, compatdata, proton_path, None, app_id, False, logger)
    stop_sidecar(handle, context)
