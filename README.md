# Majestic RP Linux Runner

Installation guide: [INSTALL.md](INSTALL.md)

Python runner for launching Majestic RP on Linux through Proton. It detects
Steam, Proton, GTA V, compatdata/prefix, and Majestic Launcher, prepares the
Wine prefix, applies launcher/runtime fixes, configures optional sidecars, and
then launches Majestic through Proton.

Support Discord: <https://discord.gg/fkNExq39Yg>

## Requirements

- Python 3.11 or newer.
- Steam GTA V with a Proton prefix, or an explicitly configured Proton/GTA path.
- `protontricks` or `winetricks` for first-run prefix setup.
- `asar` for launcher `app.asar` patching.
- Optional: `xdotool` for Caps Lock cleanup before launch.

Keep the project path ASCII-only. Proton, Wine, and some shell tools still get
unhappy around non-English project paths.

## Quick Start

```bash
python3 --version
chmod +x install-and-run-majestic-proton.sh
./install-and-run-majestic-proton.sh config
./install-and-run-majestic-proton.sh doctor
./install-and-run-majestic-proton.sh install
./install-and-run-majestic-proton.sh run
```

The shell wrapper is intentionally small. It only calls:

```bash
python3 -m majestic_linux <command>
```

You can also run the module directly:

```bash
python3 -m majestic_linux detect
python3 -m majestic_linux --config /path/to/majestic-runner.conf detect
```

If installed as a Python package, the console entry point is also available:

```bash
majestic-linux detect
majestic-linux run
```

## Commands

```bash
./install-and-run-majestic-proton.sh run
./install-and-run-majestic-proton.sh doctor
./install-and-run-majestic-proton.sh doctor-radio
./install-and-run-majestic-proton.sh analyze-crash
./install-and-run-majestic-proton.sh config
./install-and-run-majestic-proton.sh detect
./install-and-run-majestic-proton.sh env
./install-and-run-majestic-proton.sh dry-run
./install-and-run-majestic-proton.sh install
./install-and-run-majestic-proton.sh installer
./install-and-run-majestic-proton.sh patch
./install-and-run-majestic-proton.sh clean
./install-and-run-majestic-proton.sh purge-majestic
```

Useful flags:

```bash
./install-and-run-majestic-proton.sh --debug doctor
./install-and-run-majestic-proton.sh --dry-run run
./install-and-run-majestic-proton.sh run --gui
./install-and-run-majestic-proton.sh run --radio-safe
./install-and-run-majestic-proton.sh run --disable-winegstreamer
./install-and-run-majestic-proton.sh install --gui
./install-and-run-majestic-proton.sh patch --repair-multiplayer-cache
./install-and-run-majestic-proton.sh patch --no-repair-multiplayer-cache
./install-and-run-majestic-proton.sh purge-majestic --include-trash --include-installers
```

## Configuration

The active config is `$XDG_CONFIG_HOME/majestic-runner/majestic-runner.conf`.
If `XDG_CONFIG_HOME` is unset, the runner uses
`~/.config/majestic-runner/majestic-runner.conf`. If the file is missing,
`config` creates it from `examples/majestic-runner.example.conf`, falling back
to the built-in template when the example file is not available. Environment
variables override values from the file.

On first run after upgrading, an existing `majestic-runner.conf` in the current
project directory is copied to the XDG config path.

An example lives at:

```text
examples/majestic-runner.example.conf
```

Most users should leave paths empty and let auto-detection do the work:

```ini
MAJESTIC_PLATFORM=auto
MAJESTIC_AUTO_DETECT=1
MAJESTIC_PROTON_NATIVE_PLATFORM=
APP_ID=271590
STEAM_ROOT=
STEAM_COMPAT_DATA_PATH=
GTA_PATH=
PROTON_PATH=
MAJESTIC_EXE=
MAJESTIC_SOURCE_ROOT=
```

Common runtime settings:

```ini
GAME_WIDTH=1920
GAME_HEIGHT=1080
GAME_WINDOWED=1
GAME_BORDERLESS=1
MAJESTIC_GPU_MODE=auto
MAJESTIC_GPU_DEVICE_NAME=
MAJESTIC_STEAM_RUNTIME=auto
MAJESTIC_INPUT_METHOD=none
DISABLE_CEF_GPU=1
MAJESTIC_LAUNCH_OPTIONS=
MAJESTIC_LAUNCHER_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu-sandbox --disable-gpu --disable-gpu-compositing --disable-direct-composition --disable-features=DirectComposition,CalculateNativeWinOcclusion"
GTA_WINE_DRIVE=g
MAJESTIC_STORAGE_PATH=
MAJESTIC_STORAGE_WINE_DRIVE=m
MAJESTIC_PERMISSIONS=1
MAJESTIC_LOG_LEVEL=INFO
DRY_RUN=0
```

Prefix setup and installer settings:

```ini
MAJESTIC_INSTALLER_URL="https://cdn.majestic-files.net/launcher/cis/MajesticLauncherSetup.exe"
MAJESTIC_INSTALLER_PATH=
MAJESTIC_INSTALLER_ARGS=
MAJESTIC_INSTALLER_TIMEOUT=30
PROTONTRICKS_WIN10=1
TRICKS_POWERSHELL=1
PROTONTRICKS_TIMEOUT=0
TRICKS_TOOL=auto
EMOJI_FONT_URL="https://raw.githubusercontent.com/thedemons/merge_color_emoji_font/main/seguiemj.ttf"
```

Sidecar helpers:

```ini
DISCORD_BRIDGE_ENABLED=1
DISCORD_BRIDGE_PATH=
DISCORD_BRIDGE_URL="https://github.com/0e4ef622/wine-discord-ipc-bridge/releases/download/v0.0.3/winediscordipcbridge.exe"
MAJESTIC_STEAM_OVERLAY=0
```

Shutdown and repair settings use INI sections:

```ini
[shutdown]
graceful_shutdown=true
kill_wine_on_exit=true
kill_timeout_seconds=10
force_kill_timeout_seconds=5
kill_only_current_prefix=true
wait_wineserver=true

[repair]
multiplayer_cache_on_patch=true
gta_conflicts_on_patch=true
wheel_error_threshold=25
```

There is no persistent `[radio]` config anymore. Radio tooling is diagnostic and
is enabled only by `doctor-radio`, `run --radio-safe`, or
`run --disable-winegstreamer`.

## Launch Flow

`run` does this in order:

1. Loads config and applies environment overrides.
2. Detects Steam root, Proton, GTA V, compatdata, Majestic Launcher, and platform.
3. Maps the real GTA V directory into the Wine prefix, usually as `G:`.
4. Optionally maps a custom Majestic storage directory into the prefix.
5. Runs first-launch setup if the setup marker is missing.
6. Applies launcher patching when setup is needed.
7. Prepares fonts, Caps Lock cleanup, and helper sidecars.
8. Launches Majestic Launcher through Proton.
9. Cleans only the current prefix on exit.

Detection scans Steam libraries from `libraryfolders.vdf` and common
Heroic/Epic locations. Platform detection checks GTA files:

- `EOSSDK-Win64-Shipping.dll` -> `egs`
- `steam_api64.dll` -> `steam`
- `GTAVLauncher.exe` -> `rgl`
- fallback -> `rgl`

## Proton, Wine, And Tricks

Win10 compatibility mode is selected by platform:

- Steam uses `protontricks`.
- EGS/Heroic uses `winetricks`.
- RGL and other non-Steam launches prefer `winetricks`.

`install` performs the one-time setup. `patch` forces setup/patching again.
First `run` also performs setup automatically when the marker is missing. Use
`--gui` with `run`, `install`, or `patch` when protontricks/winetricks needs GUI
diagnostics.

`installer` is an alias for `install`.

The setup path installs Majestic Launcher when missing, prepares the prefix,
applies Win10/corefonts/emoji font fixes, installs PowerShell for Electron disk
detection, and patches the Majestic launcher JavaScript inside `app.asar` or
unpacked app files.

PowerShell is installed silently through `protontricks`/`winetricks` when
`TRICKS_POWERSHELL=1`. This fixes Majestic Launcher crashes like
`All disk info providers failed` from `node-disk-info`, because the launcher can
then use its PowerShell fallback to read mounted drives inside the Wine prefix.

The runner launches Proton from the Majestic executable directory. This avoids a
class of Wine/Proton issues around spaces and non-trivial paths.

## Launch Options

`MAJESTIC_LAUNCH_OPTIONS` uses Steam-like `%command%` syntax. The runner builds
the real Proton command first, then replaces `%command%` with it.

Examples:

```ini
MAJESTIC_LAUNCH_OPTIONS="gamescope -W 1920 -H 1080 -r 144 -f -- %command%"
MAJESTIC_LAUNCH_OPTIONS="mangohud %command%"
MAJESTIC_LAUNCH_OPTIONS="gamemoderun mangohud %command%"
MAJESTIC_LAUNCH_OPTIONS="MANGOHUD=1 DXVK_HUD=fps %command%"
MAJESTIC_LAUNCH_OPTIONS="~/.local/bin/game-wrapper gamescope -W 1920 -H 1080 -r 144 -f --force-grab-cursor -- %command%"
```

Environment assignments before `%command%` are applied to the launch
environment. The runner also accepts `export KEY=VALUE`, `env KEY=VALUE`,
`&&`/`;` separators before `%command%`, and `~` at the start of wrapper paths.
It does not run launch options through a shell. If `%command%` is omitted, the
runner appends the Proton command to the end of the option list.

## Steam Overlay

By default, the runner starts Majestic Launcher directly through Proton instead
of asking Steam to launch the game. That means Steam's `Shift+Tab` overlay may
not be injected, even when the Steam GTA V prefix and app id are used.

For a best-effort overlay injection, start the Steam client first and set:

```ini
MAJESTIC_STEAM_OVERLAY=1
```

When enabled, the runner looks for Steam's 32-bit and 64-bit
`gameoverlayrenderer.so` files, prepends them to `LD_PRELOAD`, enables Steam's
Vulkan overlay layer flag, and exports the Steam app/game ids for the Proton
process. This is experimental and depends on the local Steam runtime; if the
overlay renderer is missing, the launch continues without overlay injection.
Check `./install-and-run-majestic-proton.sh env` for
`MAJESTIC_STEAM_OVERLAY_STATUS`, `MAJESTIC_STEAM_OVERLAY_RENDERERS`, and
`LD_PRELOAD`.

## Custom Storage Drive

Majestic Launcher can install its multiplayer files to any visible Windows
drive. To store those files outside the Proton prefix, configure a host folder
and a Wine drive letter:

```ini
MAJESTIC_STORAGE_PATH=/home/user/Games/MajesticFiles
MAJESTIC_STORAGE_WINE_DRIVE=m
```

The folder from `MAJESTIC_STORAGE_PATH` is mounted inside the Wine/Proton prefix
as the drive letter from `MAJESTIC_STORAGE_WINE_DRIVE`. The default letter is
`M:`, so the example above makes `/home/user/Games/MajesticFiles` appear in
Majestic Launcher as drive `M:`.

When the launcher asks where to install Majestic files, choose that mounted
drive letter. The runner creates the host folder when missing and keeps the
mapping updated on every launch. Leave `MAJESTIC_STORAGE_PATH` empty to disable
this extra drive. Do not use the same letter as `GTA_WINE_DRIVE`.

## Troubleshooting

### Random actions when pressing Win

If pressing the Windows key causes random actions, broken input, or weird
keyboard behavior in game, disable Rockstar Games Launcher's own Win key
blocking option:

```text
Rockstar Games Launcher -> Settings -> Block Win Key -> Off
```

After changing the option, close Rockstar Games Launcher completely and start
the runner again.

## Discord RPC

Discord Rich Presence is handled as a Proton remote-debug sidecar. Use the
stable GitHub release URL, not the temporary `release-assets.githubusercontent`
redirect:

```ini
DISCORD_BRIDGE_ENABLED=1
DISCORD_BRIDGE_URL="https://github.com/0e4ef622/wine-discord-ipc-bridge/releases/download/v0.0.3/winediscordipcbridge.exe"
```

Or point to a local build:

```ini
DISCORD_BRIDGE_PATH=/path/to/winediscordipcbridge.exe
```

Disable it completely with:

```ini
DISCORD_BRIDGE_ENABLED=0
```

When configured by URL, the runner downloads the bridge into `cache/`. It also
adds the bridge and the first detected `discord-ipc-*` socket to
`PRESSURE_VESSEL_FILESYSTEMS_RW`, matching the behavior of the original bridge
wrapper script.

## Steam Linux Runtime

Steam launches Proton through `SteamLinuxRuntime_4/_v2-entry-point` and adds a
larger `STEAM_COMPAT_*` environment than a direct Proton launch. The runner can
mirror that path without asking Steam to start the game:

```ini
MAJESTIC_STEAM_RUNTIME=auto
```

`auto` uses the runtime when it is found next to the selected Proton install.
Set `MAJESTIC_STEAM_RUNTIME=0` to skip only the runtime wrapper. The Steam-like
compatibility environment is still applied because Proton expects those
`STEAM_COMPAT_*` values.

## Text Input

The runner can optionally export input method variables for Wine/Electron. The
Steam environment captured during debugging did not include these variables, so
this shim is disabled by default.

Default:

```ini
MAJESTIC_INPUT_METHOD=none
```

Use `MAJESTIC_INPUT_METHOD=auto`, `ibus`, or `fcitx` to enable it.

## Fonts And Icons

The runner installs only the emoji/icon font it needs by default:

```text
seguiemj.ttf
```

It downloads the font from `EMOJI_FONT_URL`, installs it into the GTA V Proton
prefix, installs it for the current Linux user in `~/.local/share/fonts`,
refreshes fontconfig when `fc-cache` exists, and writes Wine font registry
entries directly into the current prefix.

If launcher icons disappear, run:

```bash
./install-and-run-majestic-proton.sh doctor
```

`doctor` checks Majestic assets, font files, icon files, `@font-face` usage,
broken relative `url(...)` references, JS patch state, and missing launcher
resources.

## Crash And Repair

`patch` analyzes recent Majestic Multiplayer client logs for known crash
patterns. If the `Invalid vehicle wheel drawable index` pattern crosses the
configured threshold, it archives the active `Multiplayer` directory to:

```text
Multiplayer.repair-backup-*
```

Majestic then redownloads clean multiplayer files on the next launch.

`analyze-crash` summarizes recent Multiplayer logs and reports:

- wheel drawable crashes;
- missing GTA datafile/DLC references;
- duplicate weapon metadata;
- Gen9/Enhanced `_g9ec` DLC folders seen by the client.

When GTA datafile conflicts are detected, `patch` can archive stale
Majestic-injected files from the GTA root and move `_g9ec` DLC folders to
`*.repair-backup-*` so the next launch starts from a cleaner Legacy layout.

## Debug Logs

Every `run` creates an isolated log directory:

```text
logs/YYYY-MM-DD_HH-MM-SS/
```

The runner writes launch output and diagnostics into files such as:

```text
steam.log
proton.log
wine.log
launcher.log
game.log
system.log
journal.log
dxvk.log
vulkan.log
system-info.log
processes.log
crash.log
```

Proton is launched with `PROTON_LOG=1`, DXVK with `DXVK_LOG_LEVEL=info`, and
Wine with `WINEDEBUG=+timestamp,+seh,+pid`. Missing utilities like `vulkaninfo`,
`glxinfo`, or `nvidia-smi` are recorded in logs instead of stopping the launch.

After exit, the runner copies `steam-271590.log` when Proton creates it, writes
post-run process/journal diagnostics, archives the session to:

```text
logs/YYYY-MM-DD_HH-MM-SS.tar.gz
```

Only the newest 30 log sessions are kept.

## G Radio Diagnostics

Radio tooling is diagnostic. It does not install packages, does not run
winetricks, does not modify the prefix, and does not kill processes.

```bash
./install-and-run-majestic-proton.sh doctor-radio
```

The report is written to:

```text
~/.local/share/majestic-runner/reports/
```

For a diagnostic launch:

```bash
./install-and-run-majestic-proton.sh run --radio-safe
```

This writes a radio report before launch and enables extra Proton/Wine/GStreamer
logging for that run.

As a last-resort one-run test:

```bash
./install-and-run-majestic-proton.sh run --disable-winegstreamer
```

This sets `WINEDLLOVERRIDES=winegstreamer=d`. It does not delete files or
change the prefix, but media/radio playback may stop working if the game or
launcher requires Wine GStreamer.

## Diagnostics

```bash
./install-and-run-majestic-proton.sh doctor
./install-and-run-majestic-proton.sh env
```

`doctor` prints OS, Python, Steam root, Proton, compatdata, GTA V, Majestic
Launcher, selected platform, tricks tool, Discord bridge, required GTA files,
JS patch state, icon/font assets, Wine processes for the current prefix,
shutdown settings, and concrete problems to fix.

`env` prints the Proton command and important environment variables without
launching the game.

## Cleanup

```bash
./install-and-run-majestic-proton.sh purge-majestic
./install-and-run-majestic-proton.sh purge-majestic --include-trash --include-installers
./install-and-run-majestic-proton.sh purge-majestic --include-projects
```

`purge-majestic` replaces the old shell uninstaller. It removes detected
Majestic Launcher install/cache/shortcut data from Proton prefixes and native
Linux Majestic cache/config directories after confirmation.

Protected paths are not removed: GTA V installation, Steam roots, home
directory, and the current project directory.

Optional cleanup flags:

```text
--include-trash       also remove Majestic entries from ~/.local/share/Trash
--include-installers  also remove Majestic installer files from home/download folders
--include-projects    also remove local majestic-rp-linux project copies/zips
```

## Project Layout

```text
majestic_linux/app/        CLI commands and command context
majestic_linux/core/       config, config template, logging, errors
majestic_linux/detection/  async path detection and platform detection
majestic_linux/runtime/    Proton, Wine, lifecycle, sidecars, fonts, cleanup
majestic_linux/patching/   app.asar and JS patching
majestic_linux/discord/    Discord RPC bridge support
majestic_linux/radio/      read-only radio diagnostics
examples/                  example config
```
