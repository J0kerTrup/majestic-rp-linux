# Majestic RP Linux Runner

Python 3.14 runner for launching Majestic RP on Linux through Proton. It detects
Steam, Proton, GTA V, compatdata/prefix, and Majestic Launcher, prepares Wine
paths, applies Proton-friendly launcher patches, starts Discord RPC bridge when
configured, and launches Majestic through Proton.

Support Discord: <https://discord.gg/fkNExq39Yg>

## Install

```bash
python3 --version
chmod +x install-and-run-majestic-proton.sh
./install-and-run-majestic-proton.sh config
```

The wrapper is intentionally small and only calls:

```bash
python3 -m majestic_linux <command>
```

## Commands

```bash
./install-and-run-majestic-proton.sh run
./install-and-run-majestic-proton.sh doctor
./install-and-run-majestic-proton.sh doctor-radio
./install-and-run-majestic-proton.sh config
./install-and-run-majestic-proton.sh detect
./install-and-run-majestic-proton.sh env
./install-and-run-majestic-proton.sh dry-run
./install-and-run-majestic-proton.sh patch
./install-and-run-majestic-proton.sh clean
./install-and-run-majestic-proton.sh purge-majestic
```

Useful flags:

```bash
./install-and-run-majestic-proton.sh --debug doctor
./install-and-run-majestic-proton.sh --dry-run run
./install-and-run-majestic-proton.sh run --radio-safe
python3 -m majestic_linux --config majestic-runner.conf detect
```

## Configuration

The active config is strictly `majestic-runner.conf`. If it is missing, the
runner creates it automatically with safe defaults. Environment variables
override values from the file.

An example lives at:

```text
examples/majestic-runner.example.conf
```

Important settings:

- `MAJESTIC_PLATFORM=auto|steam|rgl|egs`
- `MAJESTIC_AUTO_DETECT=1`
- `STEAM_ROOT`
- `PROTON_PATH`
- `STEAM_COMPAT_DATA_PATH`
- `GTA_PATH`
- `MAJESTIC_EXE`
- `APP_ID=271590`
- `GAME_WIDTH`, `GAME_HEIGHT`
- `GAME_WINDOWED`, `GAME_BORDERLESS`
- `DISABLE_CEF_GPU`
- `MAJESTIC_LOG_LEVEL=INFO`
- `DRY_RUN=0`

Leave paths empty when auto-detection should be used. Set explicit paths only
when detection finds the wrong Steam library, Proton build, GTA install, or
launcher.

Shutdown settings are stored in the same file:

```ini
[shutdown]
graceful_shutdown=true
kill_wine_on_exit=true
kill_timeout_seconds=10
force_kill_timeout_seconds=5
kill_only_current_prefix=true
wait_wineserver=true
ignore_xalia_task_cancelled=true
```

G Radio diagnostics are configured in the same `majestic-runner.conf`:

```ini
[radio]
enabled=true
diagnostics=true
safe_mode=false
disable_winegstreamer=false
collect_logs=true
analyze_audio_stack=true
analyze_cef=true
analyze_codecs=true
analyze_network_streams=true
analyze_proton=true
analyze_wine=true
```

## Auto-Detect

Detection is async where it helps startup time: after Steam root is found, the
runner checks compatdata, GTA V, and Proton in parallel, then searches Majestic
Launcher inside the detected prefix.

Platform detection checks GTA V files:

- `EOSSDK-Win64-Shipping.dll` -> `egs`
- `steam_api64.dll` -> `steam`
- `GTAVLauncher.exe` -> `rgl`
- fallback -> `rgl`

Heroic/Epic installs are searched in common Heroic locations. Steam libraries
from `libraryfolders.vdf` are scanned, so GTA V may live outside the default
Steam directory.

## Proton, Wine, And Tricks

The runner maps the real GTA V directory to a Wine drive such as `G:` and passes
that Windows path to Majestic. Paths with spaces and Cyrillic desktop folders
are handled by launching Proton from the Majestic executable directory.

Win10 compatibility mode is selected by platform:

- Steam uses `protontricks`.
- EGS/Heroic uses `winetricks`.
- RGL uses `protontricks` if installed, otherwise `winetricks`.

Russian input defaults are configured through:

```text
MAJESTIC_LOCALE=ru_RU.UTF-8
MAJESTIC_INPUT_METHOD=xim
MAJESTIC_XKB_LAYOUT=us,ru
MAJESTIC_XKB_OPTIONS=grp:alt_shift_toggle
```

## Shutdown Lifecycle

The runner launches Proton through a lifecycle manager. On normal exit,
Launcher close, game close, `SIGINT`, `SIGTERM`, or `SIGHUP`, it tries to clean
only the current GTA V/Majestic prefix:

- wait for the main Proton process;
- run `wineserver -w` when enabled;
- run `wineserver -k` for the current `WINEPREFIX`;
- find remaining `/proc` processes that mention the current prefix/compatdata;
- send `SIGTERM`, wait, then send `SIGKILL` only to those matching processes.

It intentionally avoids global commands like `pkill wine`, because those can
kill another game or Wine application.

If `wineserver` remains after exit, run:

```bash
./install-and-run-majestic-proton.sh doctor
```

Check `Prefix processes:` and confirm the stuck process belongs to the current
`STEAM_COMPAT_DATA_PATH`.

Xalia messages like `System.Threading.Tasks.TaskCanceledException: A task was
canceled` during shutdown are treated as known shutdown warnings when
`ignore_xalia_task_cancelled=true`. They are not hidden as real fatal errors;
the runner only downgrades that specific Xalia/task-cancel pattern.

## Missing Icons

If launcher icons disappear, run:

```bash
./install-and-run-majestic-proton.sh doctor
```

The doctor now inspects Majestic assets and prints:

- font files such as `.woff`, `.woff2`, `.ttf`, `.otf`;
- SVG/ICO icon assets;
- CSS/HTML/JS files containing `@font-face`;
- broken relative `url(...)` references;
- recommendations when fonts or icon files are missing.

Most icon issues come from broken Vite/Electron relative paths, missing
`app.asar.unpacked` assets, or an incomplete launcher transfer into the Proton
prefix.

## G Radio Troubleshooting

If GTA V or Majestic RP crashes while using G Radio, run:

```bash
./install-and-run-majestic-proton.sh doctor-radio
```

The command does not install packages, does not run winetricks, does not change
Wine/Proton prefixes, and does not kill processes. It only analyzes and writes a
report to:

```text
~/.local/share/majestic-runner/reports/
```

The report includes:

- `/etc/os-release`, kernel, Python;
- PipeWire, PulseAudio, ALSA state;
- Wine, wine64, wineserver versions;
- current `WINEPREFIX` and `STEAM_COMPAT_DATA_PATH`;
- Proton kind, path, version and relevant env;
- DLL override mentions for `winegstreamer`, `xaudio`, `xact`, `mfplat`, `quartz`;
- GStreamer tools, plugin visibility, 32-bit/64-bit library hints;
- Proton-bundled GStreamer plugin dependency checks such as `libgstlibav.so`;
- recent GTA/Majestic/launcher logs;
- detected radio/audio/CEF/GStreamer/Media Foundation crash keywords;
- ranked possible causes with confidence and evidence.

For a safer diagnostic launch:

```bash
./install-and-run-majestic-proton.sh run --radio-safe
```

This enables extra Proton/Wine/GStreamer logging and writes a radio report before
launch. It still avoids risky automatic fixes. Attach the generated
`radio-report-*.txt` when opening a bug report.

During normal runs the runner also captures Proton stdout/stderr into:

```text
logs/proton-run-latest.log
logs/proton-run-YYYYMMDD-HHMMSS.log
```

If logs contain a line like:

```text
Failed to load plugin ... libgstlibav.so: libbz2.so.1.0: cannot open shared object file
```

then `doctor-radio` should report `Proton GStreamer dependency failure`. The
runner prepares safe local compatibility aliases in `cache/proton-libs/` and
prepends them through `LD_LIBRARY_PATH`; it does not modify Proton or system
libraries.

Do not point Proton at host GStreamer plugin directories such as
`/usr/lib64/gstreamer-1.0`: host plugins can fail with `undefined symbol` when
loaded by Proton's bundled GStreamer core. If Proton's bundled `libgstlibav.so`
reports missing FFmpeg ABI libraries such as `libavcodec.so.58`,
`libavformat.so.58`, `libavfilter.so.7`, or `libavutil.so.56`, test a Proton/GE
build that bundles matching libav libraries or install distribution
compatibility packages that provide those exact ABI versions.

As a last-resort test you can cut Wine GStreamer out of the current launch:

```bash
./install-and-run-majestic-proton.sh run --disable-winegstreamer
```

or persist it in `majestic-runner.conf`:

```ini
[radio]
disable_winegstreamer=true
```

This sets `WINEDLLOVERRIDES=winegstreamer=d`. It does not delete files or modify
the prefix, but media/radio playback may stop working if the launcher/game
strictly requires Wine GStreamer.

## Discord RPC

Discord Rich Presence can use `winediscordipcbridge.exe` or a compatible native
bridge. Put the bridge next to the runner, in `cache/`, in the prefix `drive_c`,
or configure:

```text
DISCORD_BRIDGE_PATH=
DISCORD_BRIDGE_URL=
DISCORD_BRIDGE_START_DELAY=2
```

## Diagnostics

Run:

```bash
./install-and-run-majestic-proton.sh doctor
./install-and-run-majestic-proton.sh env
```

`doctor` prints OS, Python, Steam root, Proton, compatdata, GTA V, Majestic
Launcher, selected platform, tricks tool, Discord bridge, required GTA files,
JS patch state, icon/font assets, current-prefix Wine processes, shutdown
settings, and concrete problems to fix.

`env` prints the Proton command and the important environment variables without
launching the game.

## Cleanup

```bash
./install-and-run-majestic-proton.sh purge-majestic
```

This removes Majestic Launcher install/cache/shortcut data from the prefix after
confirmation. The GTA V installation path is protected and is not removed.

## Development

```bash
./scripts/check.sh
```

## Docker

Docker is intended for development checks and lightweight diagnostics. Running
GTA V/Proton itself inside Docker is not the normal path because Steam Runtime,
GPU, X11/Wayland, controller devices, and the Proton prefix are host-sensitive.

Build the image:

```bash
docker build -t majestic-linux-runner:dev .
```

Run the test suite:

```bash
docker compose run --rm test
```

Open a development shell:

```bash
docker compose --profile dev run --rm shell
```

Host diagnostics can be run with read-only Steam mounts:

```bash
docker compose --profile host-diagnostics run --rm doctor
docker compose --profile host-diagnostics run --rm doctor-radio
```

If your Steam library lives outside `~/.steam` or `~/.local/share/Steam`, add
that path to `docker-compose.yml` before using the diagnostic profile.

Architecture:

```text
majestic_linux/app/        CLI commands and command context
majestic_linux/core/       config, config template, logging, errors
majestic_linux/detection/  async path detection and platform detection
majestic_linux/runtime/    Wine, Proton, tricks, input, installer launch
majestic_linux/patching/   app.asar and JS patching
majestic_linux/discord/    Discord RPC bridge support
tests/                     unittest tests
examples/                  example config
scripts/                   development helpers
```
