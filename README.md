# Majestic RP Linux Proton Runner

Python runner for launching Majestic RP on Linux through Proton with GTA V
Legacy. The runner detects Steam, Proton, GTA V, the Proton prefix, Majestic
Launcher, patches Majestic Electron files for Proton, maps the GTA folder to a
Wine drive, and starts the launcher.

Support Discord: <https://discord.gg/fkNExq39Yg>

## Quick Start

```bash
chmod +x install-and-run-majestic-proton.sh
./install-and-run-majestic-proton.sh doctor
./install-and-run-majestic-proton.sh run
```

Without arguments the wrapper runs:

```bash
python3 -m majestic_linux run
```

## Commands

```bash
./install-and-run-majestic-proton.sh run
./install-and-run-majestic-proton.sh doctor
./install-and-run-majestic-proton.sh detect
./install-and-run-majestic-proton.sh patch
./install-and-run-majestic-proton.sh clean
./install-and-run-majestic-proton.sh purge-majestic
```

Useful flags:

```bash
./install-and-run-majestic-proton.sh --dry-run --debug doctor
python3 -m majestic_linux --config examples/majestic-runner.example.conf detect
```

`purge-majestic` removes Majestic Launcher install/cache/shortcut data from the
Proton prefix after confirmation. It does not remove the GTA V installation.
Use `--dry-run purge-majestic` to inspect the list first.

## Layout

The active runtime code lives in `majestic_linux/`. Compatibility files remain
in the repository root so old commands and instructions do not break.

```text
majestic_linux/core/       config, logging, errors
majestic_linux/app/        CLI entry point
majestic_linux/detection/  path and platform detection
majestic_linux/runtime/    Wine, Proton, installer launch
majestic_linux/patching/   app.asar and JS patching
tests/                     unittest tests
docs/                      architecture and migration notes
examples/                  example config files
scripts/                   development helpers
```

More details: `docs/PROJECT_STRUCTURE.md`.

## Configuration

The runner can read an optional shell-style config file. Environment variables
override values from the config file. If no config exists, built-in defaults are
used.

Example config:

```text
examples/majestic-runner.example.conf
```

Important variables:

- `MAJESTIC_PLATFORM=auto|steam|rgl|egs`
- `GTA_PATH`
- `PROTON_PATH`
- `STEAM_ROOT`
- `STEAM_COMPAT_DATA_PATH`
- `GTA_WINE_DRIVE`
- `MAJESTIC_EXE`
- `MAJESTIC_SOURCE_ROOT`
- `GAME_WIDTH`
- `GAME_HEIGHT`
- `GAME_WINDOWED`
- `GAME_BORDERLESS`
- `DISABLE_CEF_GPU`
- `MAJESTIC_PERMISSIONS`
- `DRY_RUN`

## Platform Detection

`MAJESTIC_PLATFORM=auto` uses files in the GTA V folder:

- `EOSSDK-Win64-Shipping.dll` -> `egs`
- `steam_api64.dll` -> `steam`
- `GTAVLauncher.exe` -> `rgl`
- fallback -> `rgl`

Explicit `steam`, `rgl`, or `egs` is respected. Heroic/Epic installs are also
searched in common Heroic locations.

## Python Patcher

The Python patcher in `majestic_linux/patching/patcher.py` patches Majestic
Launcher Electron files directly:

- resolves recovered source trees, extracted app directories, `resources/`, and
  `app.asar`;
- extracts and repacks `app.asar` through `asar`;
- patches `findGTA`, `revalidateGTA`, source `patcher.js`, and `game.js`;
- patches minified `index.js` current and legacy needles;
- fixes the critical `["rgl","egs"]` array so `steam` is included;
- injects native patcher Proton launch config adaptation;
- writes the `gamePatcher.js` Proton worker adapter;
- creates backups and supports `--dry-run`.

## Development

Requires Python 3.14.

