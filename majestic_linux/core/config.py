from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config_file import ensure_config_file
from .config_parser import merged_values, parse_bool, parse_float, parse_int, parse_path, parse_shell_config


@dataclass(slots=True)
class RunnerConfig:
    config_path: Path
    game_width: int = 1920
    game_height: int = 1080
    game_windowed: bool = True
    game_borderless: bool = True
    disable_cef_gpu: bool = True
    launcher_flags: str = "--no-sandbox --disable-dev-shm-usage --disable-gpu-sandbox --disable-gpu --disable-gpu-compositing --disable-direct-composition --disable-features=DirectComposition,CalculateNativeWinOcclusion"
    selected_platform: str = "auto"
    platform_explicit: bool = False
    native_platform: str = ""
    gta_wine_drive: str = "g"
    majestic_permissions: str = "1"
    steam_root: Path | None = None
    compatdata_path: Path | None = None
    gta_path: Path | None = None
    proton_path: Path | None = None
    majestic_exe: Path | None = None
    source_root: Path | None = None
    installer_url: str = "https://cdn.majestic-files.net/launcher/cis/MajesticLauncherSetup.exe"
    installer_path: Path | None = None
    installer_args: str = "/S"
    installer_timeout: int = 30
    tricks_win10: bool = True
    tricks_timeout: int = 0
    tricks_tool: str = "auto"
    discord_bridge_path: str = ""
    discord_bridge_url: str = ""
    discord_bridge_start_delay: float = 2.0
    locale: str = "ru_RU.UTF-8"
    input_method: str = "xim"
    xkb_layout: str = "us,ru"
    xkb_options: str = "grp:alt_shift_toggle"
    app_id: str = "271590"
    dry_run: bool = False
    auto_detect: bool = True
    log_level: str = "INFO"
    graceful_shutdown: bool = True
    kill_wine_on_exit: bool = True
    kill_timeout_seconds: int = 10
    force_kill_timeout_seconds: int = 5
    kill_only_current_prefix: bool = True
    wait_wineserver: bool = True
    ignore_xalia_task_cancelled: bool = True
    radio_enabled: bool = True
    radio_diagnostics: bool = True
    radio_safe_mode: bool = False
    radio_disable_winegstreamer: bool = False
    radio_collect_logs: bool = True
    radio_analyze_audio_stack: bool = True
    radio_analyze_cef: bool = True
    radio_analyze_codecs: bool = True
    radio_analyze_network_streams: bool = True
    radio_analyze_proton: bool = True
    radio_analyze_wine: bool = True
    runtime_library_paths: list[Path] | None = None

def load_config(config_path: Path | str = "majestic-runner.conf", *, dry_run: bool | None = None) -> RunnerConfig:
    path = Path(config_path).expanduser()
    ensure_config_file(path)
    values = merged_values(path)
    platform_raw = values.get("MAJESTIC_PLATFORM", "auto").strip().lower()
    platform_explicit = "MAJESTIC_PLATFORM" in values and platform_raw not in {"", "auto"}

    cfg = RunnerConfig(
        config_path=path,
        game_width=parse_int(values.get("GAME_WIDTH"), 1920),
        game_height=parse_int(values.get("GAME_HEIGHT"), 1080),
        game_windowed=parse_bool(values.get("GAME_WINDOWED"), True),
        game_borderless=parse_bool(values.get("GAME_BORDERLESS"), True),
        disable_cef_gpu=parse_bool(values.get("DISABLE_CEF_GPU"), True),
        launcher_flags=values.get("MAJESTIC_LAUNCHER_FLAGS", RunnerConfig.launcher_flags),
        selected_platform=platform_raw or "rgl",
        platform_explicit=platform_explicit,
        native_platform=values.get("MAJESTIC_PROTON_NATIVE_PLATFORM", ""),
        gta_wine_drive=(values.get("GTA_WINE_DRIVE", "g") or "g").lower()[0],
        majestic_permissions=values.get("MAJESTIC_PERMISSIONS", "1"),
        steam_root=parse_path(values.get("STEAM_ROOT")),
        compatdata_path=parse_path(values.get("STEAM_COMPAT_DATA_PATH")),
        gta_path=parse_path(values.get("GTA_PATH")),
        proton_path=parse_path(values.get("PROTON_PATH")),
        majestic_exe=parse_path(values.get("MAJESTIC_EXE")),
        source_root=parse_path(values.get("MAJESTIC_SOURCE_ROOT")),
        installer_url=values.get("MAJESTIC_INSTALLER_URL", RunnerConfig.installer_url),
        installer_path=parse_path(values.get("MAJESTIC_INSTALLER_PATH")),
        installer_args=values.get("MAJESTIC_INSTALLER_ARGS", "/S"),
        installer_timeout=parse_int(values.get("MAJESTIC_INSTALLER_TIMEOUT"), 30),
        tricks_win10=parse_bool(values.get("PROTONTRICKS_WIN10"), True),
        tricks_timeout=parse_int(values.get("PROTONTRICKS_TIMEOUT"), 0),
        tricks_tool=values.get("TRICKS_TOOL", "auto").strip().lower() or "auto",
        discord_bridge_path=values.get("DISCORD_BRIDGE_PATH", ""),
        discord_bridge_url=values.get("DISCORD_BRIDGE_URL", ""),
        discord_bridge_start_delay=parse_float(values.get("DISCORD_BRIDGE_START_DELAY"), 2.0),
        locale=values.get("MAJESTIC_LOCALE", "ru_RU.UTF-8"),
        input_method=values.get("MAJESTIC_INPUT_METHOD", "xim").strip().lower() or "xim",
        xkb_layout=values.get("MAJESTIC_XKB_LAYOUT", "us,ru"),
        xkb_options=values.get("MAJESTIC_XKB_OPTIONS", "grp:alt_shift_toggle"),
        app_id=values.get("APP_ID") or "271590",
        dry_run=parse_bool(values.get("DRY_RUN"), False),
        auto_detect=parse_bool(values.get("MAJESTIC_AUTO_DETECT"), True),
        log_level=values.get("MAJESTIC_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        graceful_shutdown=parse_bool(values.get("SHUTDOWN_GRACEFUL_SHUTDOWN"), True),
        kill_wine_on_exit=parse_bool(values.get("SHUTDOWN_KILL_WINE_ON_EXIT"), True),
        kill_timeout_seconds=parse_int(values.get("SHUTDOWN_KILL_TIMEOUT_SECONDS"), 10),
        force_kill_timeout_seconds=parse_int(values.get("SHUTDOWN_FORCE_KILL_TIMEOUT_SECONDS"), 5),
        kill_only_current_prefix=parse_bool(values.get("SHUTDOWN_KILL_ONLY_CURRENT_PREFIX"), True),
        wait_wineserver=parse_bool(values.get("SHUTDOWN_WAIT_WINESERVER"), True),
        ignore_xalia_task_cancelled=parse_bool(values.get("SHUTDOWN_IGNORE_XALIA_TASK_CANCELLED"), True),
        radio_enabled=parse_bool(values.get("RADIO_ENABLED"), True),
        radio_diagnostics=parse_bool(values.get("RADIO_DIAGNOSTICS"), True),
        radio_safe_mode=parse_bool(values.get("RADIO_SAFE_MODE"), False),
        radio_disable_winegstreamer=parse_bool(values.get("RADIO_DISABLE_WINEGSTREAMER"), False),
        radio_collect_logs=parse_bool(values.get("RADIO_COLLECT_LOGS"), True),
        radio_analyze_audio_stack=parse_bool(values.get("RADIO_ANALYZE_AUDIO_STACK"), True),
        radio_analyze_cef=parse_bool(values.get("RADIO_ANALYZE_CEF"), True),
        radio_analyze_codecs=parse_bool(values.get("RADIO_ANALYZE_CODECS"), True),
        radio_analyze_network_streams=parse_bool(values.get("RADIO_ANALYZE_NETWORK_STREAMS"), True),
        radio_analyze_proton=parse_bool(values.get("RADIO_ANALYZE_PROTON"), True),
        radio_analyze_wine=parse_bool(values.get("RADIO_ANALYZE_WINE"), True),
    )
    if dry_run is not None:
        cfg.dry_run = dry_run
    return cfg

def config_summary(config: RunnerConfig) -> dict[str, object]:
    return {
        "config": str(config.config_path),
        "platform": config.selected_platform,
        "platform_explicit": config.platform_explicit,
        "dry_run": config.dry_run,
        "auto_detect": config.auto_detect,
        "log_level": config.log_level,
        "kill_wine_on_exit": config.kill_wine_on_exit,
        "steam_root": str(config.steam_root) if config.steam_root else "",
        "compatdata": str(config.compatdata_path) if config.compatdata_path else "",
        "gta_path": str(config.gta_path) if config.gta_path else "",
        "proton_path": str(config.proton_path) if config.proton_path else "",
        "majestic_exe": str(config.majestic_exe) if config.majestic_exe else "",
        "installer_path": str(config.installer_path) if config.installer_path else "",
        "installer_url": config.installer_url,
        "locale": config.locale,
        "input_method": config.input_method,
    }
