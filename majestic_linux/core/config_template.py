DEFAULT_CONFIG_TEXT = """# Majestic Runner config.
# Environment variables override values from this file.

# GTA V startup resolution and window mode.
GAME_WIDTH=1920
GAME_HEIGHT=1080
GAME_WINDOWED=1
GAME_BORDERLESS=1

# GPU selection: auto, prime/discrete, nvidia. Leave auto for most systems.
# MAJESTIC_GPU_DEVICE_NAME can force a DXVK/Vulkan device name, e.g. "NVIDIA GeForce RTX 5060".
MAJESTIC_GPU_MODE=auto
MAJESTIC_GPU_DEVICE_NAME=

# Steam Linux Runtime wrapper: auto, 1, 0.
MAJESTIC_STEAM_RUNTIME=auto

# Text input method for Wine/Electron: none, auto, ibus, fcitx.
MAJESTIC_INPUT_METHOD=none

# Proton/Electron launcher flags.
DISABLE_CEF_GPU=1
MAJESTIC_LAUNCH_OPTIONS=
MAJESTIC_LAUNCHER_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu-sandbox --disable-gpu --disable-gpu-compositing --disable-direct-composition --disable-features=DirectComposition,CalculateNativeWinOcclusion"

# auto, steam, rgl, egs. Keep auto unless you need to force one platform.
MAJESTIC_PLATFORM=auto
MAJESTIC_AUTO_DETECT=1
MAJESTIC_PROTON_NATIVE_PLATFORM=

# Wine drive mapped to the real GTA V folder.
GTA_WINE_DRIVE=g

# Optional storage drive for Majestic files. Leave path empty to disable.
MAJESTIC_STORAGE_PATH=
MAJESTIC_STORAGE_WINE_DRIVE=m
MAJESTIC_PERMISSIONS=1

# Optional path to a prebuilt patched majestic-patcher.node. Launcher 6.1+
# ships the native addon without C++ sources, so when no src/ is present the
# patcher copies this binary into the package before repacking app.asar.
# Point it at the patched build from an older launcher, e.g.:
#   .../6.0.13.unpacked/resources/app.asar.unpacked/node_modules/majestic-patcher/build/Release/majestic-patcher.node
MAJESTIC_NATIVE_BINARY=

# Launcher installer, used when Majestic Launcher.exe is missing.
MAJESTIC_INSTALLER_URL="https://majestic-linux.com/MajesticLauncherSetup.repacked.exe"
MAJESTIC_INSTALLER_PATH=
MAJESTIC_INSTALLER_ARGS=
MAJESTIC_INSTALLER_TIMEOUT=30

# Steam -> protontricks. Non-Steam platforms prefer winetricks.
PROTONTRICKS_WIN10=1
TRICKS_POWERSHELL=1
PROTONTRICKS_TIMEOUT=0
TRICKS_TOOL=auto
EMOJI_FONT_URL="https://raw.githubusercontent.com/thedemons/merge_color_emoji_font/main/seguiemj.ttf"

# Optional Discord Rich Presence bridge.
DISCORD_BRIDGE_ENABLED=1
DISCORD_BRIDGE_PATH=
DISCORD_BRIDGE_URL="https://github.com/0e4ef622/wine-discord-ipc-bridge/releases/download/v0.0.3/winediscordipcbridge.exe"

# Experimental Steam Overlay injection. Start Steam first, then set to 1.
MAJESTIC_STEAM_OVERLAY=0

# Optional manual paths. Leave empty for auto-detection.
APP_ID=271590
STEAM_ROOT=
STEAM_COMPAT_DATA_PATH=
GTA_PATH=
PROTON_PATH=
MAJESTIC_EXE=
MAJESTIC_SOURCE_ROOT=

# Logging and dry-run.
MAJESTIC_LOG_LEVEL=INFO
MAJESTIC_LOG_DIRECTORY=
DRY_RUN=0

[shutdown]
graceful_shutdown=true
kill_wine_on_exit=true
kill_timeout_seconds=10
force_kill_timeout_seconds=5
kill_only_current_prefix=true
wait_wineserver=true

[repair]
# patch analyzes recent Multiplayer client logs. If the known wheel drawable
# crash pattern is found, Multiplayer is archived so the launcher redownloads it.
multiplayer_cache_on_patch=true
gta_conflicts_on_patch=true
wheel_error_threshold=25
"""
