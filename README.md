# Majestic RP Linux Runner

Python runner for launching Majestic RP on Linux through Proton. It detects
Steam, Proton, GTA V, compatdata/prefix, and Majestic Launcher, prepares the
Wine prefix, applies launcher/runtime fixes, starts optional helper executables,
and then launches Majestic through Proton.

Support Discord: <https://discord.gg/fkNExq39Yg>

## Requirements

- Python 3.14 or newer.
- Steam GTA V with a Proton prefix, or an explicitly configured Proton/GTA path.
- `protontricks` or `winetricks` for first-run prefix setup.
- `asar` for launcher `app.asar` patching.
- Optional: `xdotool` for Caps Lock cleanup before launch.
- Optional: `x86_64-w64-mingw32-gcc` only when rebuilding the bundled Win key helper.

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
python3 -m majestic_linux --config majestic-runner.conf detect
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

The active config is `majestic-runner.conf`. If it is missing, `config` creates
it from the built-in template. Environment variables override values from the
file.

An example lives at:

```text
examples/majestic-runner.example.conf
```

Most users should leave paths empty and let auto-detection do the work:

```ini
MAJESTIC_PLATFORM=auto
MAJESTIC_AUTO_DETECT=1
APP_ID=271590
STEAM_ROOT=
STEAM_COMPAT_DATA_PATH=
GTA_PATH=
PROTON_PATH=
MAJESTIC_EXE=
```

Common runtime settings:

```ini
GAME_WIDTH=1920
GAME_HEIGHT=1080
GAME_WINDOWED=1
GAME_BORDERLESS=1
MAJESTIC_GPU_MODE=auto
DISABLE_CEF_GPU=1
GTA_WINE_DRIVE=g
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
PROTONTRICKS_TIMEOUT=0
TRICKS_TOOL=auto
EMOJI_FONT_URL="https://raw.githubusercontent.com/thedemons/merge_color_emoji_font/main/seguiemj.ttf"
```

Sidecar helpers:

```ini
DISCORD_BRIDGE_ENABLED=1
DISCORD_BRIDGE_PATH=
DISCORD_BRIDGE_URL="https://github.com/0e4ef622/wine-discord-ipc-bridge/releases/download/v0.0.3/winediscordipcbridge.exe"

WIN_BLOCKER_ENABLED=1
WIN_BLOCKER_PATH=
WIN_BLOCKER_READY_MARKER="Connection complete!"
WIN_BLOCKER_READY_DELAY=0
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
4. Runs first-launch setup if the setup marker is missing.
5. Applies launcher patching and repair checks.
6. Prepares fonts, registry tweaks, Caps Lock cleanup, and helper sidecars.
7. Launches Majestic Launcher through Proton.
8. Cleans only the current prefix on exit.

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
- RGL uses `protontricks` if available, otherwise `winetricks`.

`install` performs the one-time setup. `patch` forces setup/patching again.
First `run` also performs setup automatically when the marker is missing. Use
`--gui` with `run`, `install`, or `patch` when protontricks/winetricks needs GUI
diagnostics.

The setup path installs Majestic Launcher when missing, prepares the prefix,
applies Win10/corefonts/emoji font fixes, applies Wine registry tweaks, and
patches the Majestic launcher JavaScript inside `app.asar` or unpacked app
files.

The runner launches Proton from the Majestic executable directory. This avoids a
class of Wine/Proton issues around spaces and non-trivial paths.

## Win Key Blocker

Majestic/GTA has an input bug around the Windows key. The runner ships a small
Windows helper:

```text
helpers/win-blocker/block_win.exe
helpers/win-blocker/block_win.c
```

At runtime it is copied into the prefix:

```text
drive_c/majestic-sidecars/win-blocker/block_win.exe
```

The helper is not started with the launcher. The watcher waits until GTA is
running and the fresh Majestic client log contains:

```text
Connection complete!
```

Only then it starts `block_win.exe` through the same Proton prefix. If the
helper exits while GTA is still running, the watcher starts it again. When GTA
exits, the watcher stops it with `taskkill` in the same prefix.

Disable or tune it with:

```ini
WIN_BLOCKER_ENABLED=0
WIN_BLOCKER_PATH=/path/to/custom/block_win.exe
WIN_BLOCKER_READY_MARKER="Connection complete!"
WIN_BLOCKER_READY_DELAY=0
```

Rebuild the bundled helper with:

```bash
x86_64-w64-mingw32-gcc -O2 -mwindows helpers/win-blocker/block_win.c -o helpers/win-blocker/block_win.exe
```

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
helpers/                   bundled helper sources and binaries
examples/                  example config
```
