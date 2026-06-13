from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import RunnerConfig


@dataclass(frozen=True, slots=True)
class SidecarContext:
    config: RunnerConfig | None
    compatdata: Path
    proton_path: Path
    steam_root: Path | None
    app_id: str
    dry_run: bool = False
    logger: logging.Logger | None = None

    @property
    def prefix(self) -> Path:
        return self.compatdata / "pfx"


@dataclass(frozen=True, slots=True)
class SidecarSpec:
    name: str
    executable: Path
    args: tuple[str, ...] = ()
    windows: bool | None = None
    hidden: bool = True
    start_delay: float = 0.0
    stop_image: str | None = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SidecarHandle:
    name: str
    process: subprocess.Popen | None = None
    executable: Path | None = None
    windows: bool = False
    stop_image: str | None = None
    remote_debug: bool = False


def start_sidecar(spec: SidecarSpec, context: SidecarContext) -> SidecarHandle:
    executable = spec.executable.expanduser().resolve()
    windows = _is_windows_executable(executable) if spec.windows is None else spec.windows
    if context.logger:
        context.logger.info("Starting sidecar %s: %s", spec.name, executable)
    if context.dry_run:
        return SidecarHandle(spec.name, None, executable, windows, spec.stop_image)
    if spec.start_delay > 0:
        time.sleep(spec.start_delay)
    if windows:
        process = _start_windows_sidecar(spec, executable, context)
    else:
        process = _start_native_sidecar(spec, executable, context)
    return SidecarHandle(spec.name, process, executable, windows, spec.stop_image)


def stop_sidecar(handle: SidecarHandle, context: SidecarContext) -> None:
    if handle.process is None:
        if handle.windows and handle.stop_image and not handle.remote_debug:
            _taskkill_windows_image(handle.stop_image, context)
        return
    if context.logger:
        context.logger.info("Stopping sidecar %s", handle.name)
    if handle.windows and handle.stop_image:
        _taskkill_windows_image(handle.stop_image, context)
    _terminate_process(handle.process)


def stop_sidecars(handles: list[SidecarHandle], context: SidecarContext) -> None:
    for handle in reversed(handles):
        stop_sidecar(handle, context)


def configure_remote_debug_sidecar(
    spec: SidecarSpec,
    context: SidecarContext,
    env: dict[str, str],
    *,
    filesystem_paths: list[Path] | None = None,
) -> SidecarHandle:
    executable = spec.executable.expanduser().resolve()
    if context.logger:
        context.logger.info("Configuring remote-debug sidecar %s: %s", spec.name, executable)
    env["PROTON_REMOTE_DEBUG_CMD"] = str(executable)
    _append_pressure_vessel_paths(env, [executable, *(filesystem_paths or [])])
    windows = _is_windows_executable(executable) if spec.windows is None else spec.windows
    return SidecarHandle(spec.name, None, executable, windows, spec.stop_image, remote_debug=True)


def sidecar_env(context: SidecarContext, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "WINEPREFIX": str(context.prefix),
            "STEAM_COMPAT_DATA_PATH": str(context.compatdata),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(context.steam_root or ""),
            "STEAM_COMPAT_APP_ID": context.app_id,
            "SteamAppId": context.app_id,
            "SteamGameId": context.app_id,
        }
    )
    if extra:
        env.update(extra)
    return env


def _append_pressure_vessel_paths(env: dict[str, str], paths: list[Path]) -> None:
    existing = [item for item in env.get("PRESSURE_VESSEL_FILESYSTEMS_RW", "").split(":") if item]
    seen = set(existing)
    merged = [*existing]
    for path in paths:
        value = str(path)
        if value and value not in seen:
            merged.append(value)
            seen.add(value)
    if merged:
        env["PRESSURE_VESSEL_FILESYSTEMS_RW"] = ":".join(merged)


def _start_native_sidecar(spec: SidecarSpec, executable: Path, context: SidecarContext) -> subprocess.Popen:
    executable.chmod(executable.stat().st_mode | 0o111)
    return subprocess.Popen(
        [str(executable), *spec.args],
        env=sidecar_env(context, spec.env),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _start_windows_sidecar(spec: SidecarSpec, executable: Path, context: SidecarContext) -> subprocess.Popen:
    prefix_executable = _install_windows_sidecar(spec.name, executable, context.prefix)
    env = sidecar_env(context, {"WINEDEBUG": "-all", **spec.env})
    if spec.hidden:
        command = _hidden_windows_command(spec, prefix_executable, context)
    else:
        command = [str(context.proton_path), "run", _windows_path(prefix_executable), *spec.args]
    return subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _install_windows_sidecar(name: str, executable: Path, prefix: Path) -> Path:
    target_dir = prefix / "drive_c" / "majestic-sidecars" / _safe_name(name)
    target = target_dir / executable.name
    target_dir.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size != executable.stat().st_size:
        shutil.copy2(executable, target)
    return target


def _hidden_windows_command(spec: SidecarSpec, prefix_executable: Path, context: SidecarContext) -> list[str]:
    vbs = context.prefix / "drive_c" / "majestic-sidecars" / f"run-{_safe_name(spec.name)}.vbs"
    vbs.write_text(
        'Set objShell = WScript.CreateObject("WScript.Shell")\n'
        f"objShell.Run {_vbs_command_expr(_windows_path(prefix_executable), spec.args)}, 0, False\n",
        encoding="utf-8",
    )
    return [str(context.proton_path), "run", "wscript.exe", _windows_path(vbs)]


def _taskkill_windows_image(image: str, context: SidecarContext) -> None:
    subprocess.run(
        [str(context.proton_path), "run", "taskkill", "/F", "/IM", image],
        env=sidecar_env(context),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()


def _is_windows_executable(path: Path) -> bool:
    return path.name.lower().endswith((".exe", ".bat", ".cmd"))


def _safe_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in "-_." else "-" for char in name.strip().lower()) or "sidecar"


def _windows_path(path: Path) -> str:
    parts = path.parts
    try:
        index = parts.index("drive_c")
    except ValueError:
        return str(path)
    return "C:\\" + "\\".join(parts[index + 1 :])


def _vbs_command_expr(executable: str, args: tuple[str, ...]) -> str:
    parts = [executable, *args]
    quoted = [f'Chr(34) & "{part.replace(chr(34), chr(34) + chr(34))}" & Chr(34)' for part in parts]
    return ' & " " & '.join(quoted)
