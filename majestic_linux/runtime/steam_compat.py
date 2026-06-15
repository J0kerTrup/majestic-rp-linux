from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig

DISABLED_VALUES = {"0", "false", "off", "none", "disabled"}
RUNTIME_DIR_NAMES = (
    "SteamLinuxRuntime_4",
    "SteamLinuxRuntime_sniper",
    "SteamLinuxRuntime_soldier",
    "SteamLinuxRuntime",
)


@dataclass(frozen=True, slots=True)
class SteamCompatLayout:
    steamapps: Path | None
    runtime_entrypoint: Path | None

    @property
    def runtime_root(self) -> Path | None:
        return self.runtime_entrypoint.parent if self.runtime_entrypoint else None


def apply_steam_compat(
    command: list[str],
    env: dict[str, str],
    config: RunnerConfig,
    *,
    app_id: str,
    proton_path: Path,
    steam_root: Path | None,
    gta_path: Path,
) -> list[str]:
    layout = detect_steam_compat_layout(proton_path, steam_root, gta_path)
    apply_steam_compat_environment(env, app_id, proton_path, gta_path, layout)
    return wrap_with_steam_runtime(command, env, config, layout)


def detect_steam_compat_layout(proton_path: Path, steam_root: Path | None, gta_path: Path) -> SteamCompatLayout:
    steamapps = find_steamapps_root(steam_root, gta_path, proton_path)
    return SteamCompatLayout(
        steamapps=steamapps,
        runtime_entrypoint=find_steam_runtime_entrypoint(proton_path, steam_root, steamapps),
    )


def apply_steam_compat_environment(
    env: dict[str, str],
    app_id: str,
    proton_path: Path,
    gta_path: Path,
    layout: SteamCompatLayout,
) -> None:
    env["MAJESTIC_STEAM_COMPAT_STATUS"] = "enabled"
    env.setdefault("SteamAppId", app_id)
    env.setdefault("SteamGameId", app_id)
    env.setdefault("SteamOverlayGameId", app_id)
    env.setdefault("SteamEnv", "1")
    env.setdefault("SteamClientLaunch", "1")
    env.setdefault("STEAM_COMPAT_PROTON", "1")
    env.setdefault("STEAM_COMPAT_FLAGS", "search-cwd")
    env.setdefault("STEAM_COMPAT_INSTALL_PATH", str(gta_path))

    if layout.steamapps:
        env.setdefault("STEAM_COMPAT_LIBRARY_PATHS", str(layout.steamapps))
        shader_path = layout.steamapps / "shadercache" / app_id
        env.setdefault("STEAM_COMPAT_SHADER_PATH", str(shader_path))
        env.setdefault("STEAM_COMPAT_MEDIA_PATH", str(shader_path / "fozmediav1"))
        env.setdefault("STEAM_COMPAT_TRANSCODED_MEDIA_PATH", str(shader_path))
        env.setdefault("DXVK_STATE_CACHE_PATH", str(shader_path / "DXVK_state_cache"))

    if layout.runtime_root:
        tool_paths = [proton_path.parent, layout.runtime_root]
        env.setdefault("STEAM_COMPAT_TOOL_PATHS", ":".join(str(path) for path in tool_paths))
        mounts = _existing_paths(
            [
                layout.steamapps / "common" / "Steamworks Shared" if layout.steamapps else None,
                proton_path.parent,
                layout.runtime_root,
            ]
        )
        if mounts:
            env.setdefault("STEAM_COMPAT_MOUNTS", ":".join(str(path) for path in mounts))


def wrap_with_steam_runtime(command: list[str], env: dict[str, str], config: RunnerConfig, layout: SteamCompatLayout) -> list[str]:
    mode = (getattr(config, "steam_runtime", "auto") or "auto").strip().lower()
    if mode in DISABLED_VALUES:
        env["MAJESTIC_STEAM_RUNTIME_STATUS"] = "disabled"
        return command
    if layout.runtime_entrypoint is None:
        env["MAJESTIC_STEAM_RUNTIME_STATUS"] = "missing"
        return command
    env["MAJESTIC_STEAM_RUNTIME_STATUS"] = "enabled"
    env["MAJESTIC_STEAM_RUNTIME_ENTRYPOINT"] = str(layout.runtime_entrypoint)
    return [str(layout.runtime_entrypoint), "--verb=waitforexitandrun", "--", *command]


def find_steamapps_root(steam_root: Path | None, gta_path: Path, proton_path: Path) -> Path | None:
    candidates: list[Path] = []
    if steam_root:
        candidates.append(steam_root / "steamapps")
    for path in (gta_path, proton_path):
        for parent in path.parents:
            if parent.name == "steamapps":
                candidates.append(parent)
                break
    return _first_existing(candidates) or (candidates[0] if candidates else None)


def find_steam_runtime_entrypoint(proton_path: Path, steam_root: Path | None, steamapps: Path | None = None) -> Path | None:
    common_roots: list[Path] = []
    if proton_path.parent.parent.name == "common":
        common_roots.append(proton_path.parent.parent)
    if steamapps:
        common_roots.append(steamapps / "common")
    if steam_root:
        common_roots.append(steam_root / "steamapps" / "common")

    for common in _unique_paths(common_roots):
        for name in RUNTIME_DIR_NAMES:
            entrypoint = common / name / "_v2-entry-point"
            if entrypoint.is_file():
                return entrypoint
    return None


def _first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in _unique_paths(paths) if path.exists()), None)


def _existing_paths(paths: list[Path | None]) -> list[Path]:
    return [path for path in _unique_optional_paths(paths) if path.exists()]


def _unique_paths(paths: list[Path]) -> list[Path]:
    return list(dict.fromkeys(paths))


def _unique_optional_paths(paths: list[Path | None]) -> list[Path]:
    return list(dict.fromkeys(path for path in paths if path is not None))
