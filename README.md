# Majestic RP Linux Proton Runner

[![Linux](https://img.shields.io/badge/platform-Linux-2ea44f)](#)
[![Steam + Proton](https://img.shields.io/badge/runtime-Steam%20%2B%20Proton-1b2838)](#)
[![GTA V Legacy](https://img.shields.io/badge/game-GTA%20V%20Legacy-blue)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

Run Majestic RP on Linux by using the same Steam Proton prefix as your legal
GTA V Legacy installation.

This project is a helper for Linux users who have GTA V installed through
Steam/Proton and want Majestic Launcher to see the game correctly. It prepares
the Proton environment, patches Majestic Launcher's Electron files for Proton,
maps your real GTA V folder to a Windows drive letter, and starts the launcher
through Proton.

Support Discord: <https://discord.gg/fkNExq39Yg>

> [!IMPORTANT]
> This project is for Linux. You need a legal GTA V Legacy copy. The Steam path
> is the primary supported flow.

## Who This Is For

Use this project if:

- you are on Linux;
- you own GTA V Legacy legally;
- your GTA V is installed in Steam;
- you use Steam Proton, preferably Proton Experimental;
- Majestic Launcher does not correctly find GTA V or cannot patch/start it.

This project can also detect Rockstar Games Launcher and Epic Games Store GTA V
folders in some cases, but Steam is the main target.

## What It Does

`install-and-run-majestic-proton.sh` does the following:

| Step | What happens |
| --- | --- |
| Steam detection | Finds Steam root and Steam library folders. |
| GTA detection | Finds GTA V Legacy by Steam manifests or configured `GTA_PATH`. |
| Prefix detection | Uses the GTA V Proton prefix, usually `steamapps/compatdata/271590`. |
| Launcher install | Downloads/runs Majestic Launcher installer if the launcher is missing. |
| Wine drive mapping | Maps the Linux GTA V folder to a Windows drive like `G:\`. |
| Config patching | Writes GTA `commandline.txt`, patches Majestic runtime config, disables CEF GPU when configured. |
| app.asar patching | Extracts and patches Majestic Launcher's Electron `app.asar`. |
| Proton launch | Starts `Majestic Launcher.exe` through Proton with Steam-compatible environment variables. |

## What Is Not Guaranteed

This project does not guarantee that:

- Majestic RP will work after upstream launcher/game updates;
- every Proton version will work;
- every distro package set is complete out of the box;
- Epic/Rockstar non-Steam installs will behave the same as Steam;
- anti-cheat, DRM, or server-side checks will accept every setup.

It does not patch GTA V executables, multiplayer DLLs, DRM, anti-cheat, or the
network protocol.

## Important Warnings

> [!WARNING]
> Do not run `GTA5.exe` or `GTAV.exe` directly with plain Wine. Steam GTA V needs
> the correct Steam AppID and Proton prefix. Direct Wine launches often lose the
> Steam license context and may trigger activation/key prompts.

> [!CAUTION]
> Do not use `C:` or `Z:` as `GTA_WINE_DRIVE`. `C:` is the Wine prefix drive and
> `Z:` is usually Wine's Linux filesystem bridge. Use `G:`, `E:`, `D:`, etc.

> [!NOTE]
> If GTA V is on another disk, make sure that disk is mounted before running the
> script. Steam can remember old libraries in `libraryfolders.vdf`, but an
> unmounted drive cannot be used.

## Requirements

- Linux.
- Steam installed and logged in.
- Legal Steam GTA V Legacy installed at least once.
- Proton Experimental installed in Steam.
- Node.js 18 or newer.
- `npm`, `perl`, `sed`, `findutils`.
- Vulkan drivers for your GPU.
- 32-bit graphics libraries for Proton.
- Optional but useful: `protontricks`.

The script can install the local `@electron/asar` dependency automatically when
`package.json` and `npm` are available. You can also install dependencies with
`npm install`.

## Distro Dependencies

Package names vary by distro and GPU. The commands below install the basic tools
used by this repository. Install your GPU-specific Vulkan packages too.

### Fedora

```bash
sudo dnf install steam nodejs npm perl sed findutils curl wget vulkan-loader vulkan-loader.i686
```

For Mesa GPUs, also install:

```bash
sudo dnf install mesa-vulkan-drivers mesa-vulkan-drivers.i686
```

For NVIDIA, install the NVIDIA driver and its 32-bit Vulkan/OpenGL userspace
packages from the repository you use on Fedora.

### Arch / Manjaro

Enable `multilib` first if it is not already enabled, then install:

```bash
sudo pacman -S steam nodejs npm perl sed findutils curl wget vulkan-icd-loader lib32-vulkan-icd-loader
```

Mesa example:

```bash
sudo pacman -S mesa vulkan-radeon lib32-mesa lib32-vulkan-radeon
```

NVIDIA example:

```bash
sudo pacman -S nvidia-utils lib32-nvidia-utils
```

### Ubuntu / Debian / Linux Mint

Enable 32-bit packages and install the basics:

```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install steam nodejs npm perl sed findutils curl wget mesa-vulkan-drivers mesa-vulkan-drivers:i386
```

For NVIDIA, install the appropriate NVIDIA driver and 32-bit NVIDIA libraries
from your distro repositories.

## Quick Start

Clone the repository:

```bash
git clone https://github.com/J0kerTrup/majestic-rp-linux.git
cd majestic-rp-linux
```

Install Node dependencies:

```bash
npm install
```

Open Steam and make sure:

- GTA V Legacy is installed;
- GTA V was started at least once through Steam/Proton;
- Proton Experimental is installed.

Run:

```bash
chmod +x install-and-run-majestic-proton.sh
./install-and-run-majestic-proton.sh
```

The script will try to detect Steam, GTA V, Proton, the GTA V prefix, and
Majestic Launcher automatically.

## Manual Installation

You normally do not need to copy scripts into the Windows prefix. Keep this
repository as a normal Linux folder and run:

```bash
./install-and-run-majestic-proton.sh
```

If Majestic Launcher is missing, the script downloads the installer configured
in `majestic-proton.conf` and runs it inside the active GTA V Proton prefix.

## Discord Rich Presence

Wine/Proton applications cannot normally talk to the native Linux Discord IPC
socket directly. To enable Rich Presence, provide a Wine Discord RPC bridge such
as `winediscordipcbridge.exe`.

The runner starts the bridge inside the active GTA V Proton prefix before
Majestic Launcher starts, then stops it after the launcher exits. Use one of
these options:

```bash
# Auto-detected if the file is next to install-and-run-majestic-proton.sh:
DISCORD_BRIDGE_PATH=

# Or set a local executable:
DISCORD_BRIDGE_PATH="/home/you/tools/winediscordipcbridge.exe"

# Or set a direct download URL:
DISCORD_BRIDGE_URL="https://example.com/winediscordipcbridge.exe"
```

Make sure native Discord, Vesktop, or another compatible client is running
before launching Majestic.

If automatic detection fails, edit `majestic-proton.conf` and set the paths
manually:

```bash
STEAM_ROOT="/home/you/.local/share/Steam"
GTA_PATH="/mnt/ssd/SteamLibrary/steamapps/common/Grand Theft Auto V"
STEAM_COMPAT_DATA_PATH="/mnt/ssd/SteamLibrary/steamapps/compatdata/271590"
PROTON_PATH="/home/you/.local/share/Steam/steamapps/common/Proton - Experimental/proton"
```

## Configuration

All main settings live in `majestic-proton.conf`.

| Setting | Meaning |
| --- | --- |
| `GAME_WIDTH`, `GAME_HEIGHT` | Resolution written to GTA startup/config files. |
| `GAME_WINDOWED`, `GAME_BORDERLESS` | Window mode flags written to `commandline.txt`. |
| `DISABLE_CEF_GPU` | Disables Majestic CEF hardware acceleration when set to `1`. |
| `MAJESTIC_LAUNCHER_FLAGS` | Extra Electron flags for the launcher. |
| `MAJESTIC_WINE_DLL_OVERRIDES` | DLL overrides merged into `WINEDLLOVERRIDES`; default is `winegstreamer=d;dcomp=d`. |
| `MAJESTIC_LOCALE` | Locale exported for Proton text input. Default is `ru_RU.UTF-8`. |
| `MAJESTIC_INPUT_METHOD` | Input method variables exported as `XMODIFIERS`, `GTK_IM_MODULE`, and `QT_IM_MODULE`. Default is `xim`. |
| `MAJESTIC_XKB_LAYOUT`, `MAJESTIC_XKB_OPTIONS` | Optional XKB hints for XWayland/Proton. Leave empty to keep the system layout. |
| `MAJESTIC_DISABLE_SUPER_KEYS` | Temporarily disables Super/Win keys with `xmodmap` while the launcher is running. Default is `1`. |
| `MAJESTIC_TRACE_STEPS` | Writes every bash command step to `logs/majestic-proton-steps.log`. Default is `1`. |
| `MAJESTIC_PLATFORM` | `auto`, `steam`, `rgl`, or `egs`. Use `auto` unless debugging. |
| `MAJESTIC_PROTON_NATIVE_PLATFORM` | Optional override for the native patcher platform. Empty is recommended. |
| `GTA_WINE_DRIVE` | Windows drive letter mapped to the real GTA folder. Do not use `C` or `Z`. |
| `MAJESTIC_PERMISSIONS` | Permission bytes written into Majestic multiplayer cache files. |
| `RESET_ROCKSTAR_DOCUMENTS` | Renames Rockstar Documents cache when set to `1`. |
| `PROTONTRICKS_WIN10` | Runs `protontricks <AppID> win10` when set to `1`. |
| `PROTONTRICKS_TIMEOUT` | Timeout for protontricks. `0` keeps unbounded original behavior. |
| `PROTONTRICKS_STOP_PREFIX` | Stops Wine processes in the active prefix before protontricks when set to `1`. |
| `PROTON_VERB` | Proton command verb. `waitforexitandrun` is recommended. |
| `MAJESTIC_INSTALLER_URL` | Majestic installer URL. |
| `MAJESTIC_INSTALLER_PATH` | Optional local installer path/cache path. |
| `MAJESTIC_INSTALLER_ARGS` | Installer arguments, default `/S`. |
| `MAJESTIC_INSTALLER_TIMEOUT` | Timeout for silent installer run. |
| `DISCORD_BRIDGE_PATH` | Optional Discord RPC bridge executable path or direct download URL. If empty, the script auto-uses `winediscordipcbridge.exe` next to the script when present. |
| `DISCORD_BRIDGE_URL` | Optional direct URL used to download the bridge when `DISCORD_BRIDGE_PATH` is empty or points to a missing local file. |
| `DISCORD_BRIDGE_START_DELAY` | Seconds to wait after starting the Discord bridge before launching Majestic. Default is `2`. |
| `APP_ID` | Steam AppID. GTA V Steam is `271590`. Usually auto-detected. |
| `STEAM_ROOT` | Steam root folder. |
| `STEAM_COMPAT_DATA_PATH` | Proton prefix path, usually `steamapps/compatdata/271590`. |
| `GTA_PATH` | Real Linux path to the GTA V folder. |
| `PROTON_PATH` | Path to the Proton executable. |
| `MAJESTIC_EXE` | Optional path to `Majestic Launcher.exe` inside the active prefix. |
| `MAJESTIC_SOURCE_ROOT` | Optional recovered source tree for advanced patching. Usually empty. |

Recommended Steam setup when GTA V is on another disk:

```bash
MAJESTIC_PLATFORM=auto
GTA_WINE_DRIVE=g
GTA_PATH="/mnt/ssd/SteamLibrary/steamapps/common/Grand Theft Auto V"
STEAM_COMPAT_DATA_PATH="/mnt/ssd/SteamLibrary/steamapps/compatdata/271590"
```

## Launch

Run from the repository directory:

```bash
./install-and-run-majestic-proton.sh
```

Or through npm:

```bash
npm start
```

Check scripts without launching:

```bash
npm run check
```

This runs:

```bash
bash -n install-and-run-majestic-proton.sh
node --check majestic-proton-js-patcher.js
```

## Why The Steam Proton Prefix Matters

Steam GTA V is not just a Windows executable. It depends on Steam runtime state,
Steam AppID, Steam license visibility, Rockstar/Social Club state, and the
correct Proton prefix.

The important environment variables are:

| Variable | Why it matters |
| --- | --- |
| `STEAM_COMPAT_DATA_PATH` | Points Proton to the Windows prefix for GTA V, usually `compatdata/271590`. |
| `STEAM_COMPAT_CLIENT_INSTALL_PATH` | Points Proton to the Steam installation root. |
| `STEAM_COMPAT_APP_ID` | Tells Proton/Steam which app is being run. GTA V is `271590`. |
| `SteamAppId` | Exposes the Steam AppID to Windows processes. |
| `SteamGameId` | Another Steam ID variable expected by some launchers/games. |

If Steam GTA V is launched from the wrong prefix, Rockstar may not see the Steam
license and can ask for an activation key. This is why the script tries hard to
use `steamapps/compatdata/271590`.

## Steam vs Rockstar vs Epic

| Platform | Detection marker | Notes |
| --- | --- | --- |
| Steam | `steam_api64.dll` | Main supported flow. Requires AppID `271590` and the correct Steam Proton prefix. |
| Rockstar Games Launcher | `GTAVLauncher.exe` without Steam/Epic markers | Can work, but license/runtime behavior differs from Steam. |
| Epic Games Store | `EOSSDK-Win64-Shipping.dll` | Experimental. The script can create a `GTAVLauncher.exe` symlink to `GTA5.exe` for EGS compatibility. |

Use `MAJESTIC_PLATFORM=auto` unless you have a specific reason to force a
platform.

## Troubleshooting

### GTA V is not found

Check that the game folder contains:

```text
GTA5.exe
x64j.rpf
```

Then set:

```bash
GTA_PATH="/path/to/SteamLibrary/steamapps/common/Grand Theft Auto V"
```

If GTA is on another disk, mount the disk first. The script searches Steam
libraries from `libraryfolders.vdf`, `/mnt/*/SteamLibrary`,
`/run/media/$USER/*/SteamLibrary`, and `~/Games/SteamLibrary`.

### Majestic downloads files again

Majestic may not be using the same prefix/cache as before. Make sure
`STEAM_COMPAT_DATA_PATH` points to the GTA V prefix:

```bash
STEAM_COMPAT_DATA_PATH="/path/to/SteamLibrary/steamapps/compatdata/271590"
```

Also check that `MAJESTIC_EXE`, if set, is inside that same prefix.

### Rockstar asks for an activation key

This usually means Steam license context is missing. Common causes:

- wrong Proton prefix;
- missing `SteamAppId` / `SteamGameId` / `STEAM_COMPAT_APP_ID`;
- launching `GTA5.exe` directly through Wine;
- using a Majestic Launcher installed in a different prefix.

For Steam GTA V, use:

```bash
APP_ID=271590
STEAM_COMPAT_DATA_PATH="/path/to/SteamLibrary/steamapps/compatdata/271590"
MAJESTIC_PLATFORM=auto
```

### EGS does not work

EGS support is experimental. Make sure `GTA_PATH` points to the real EGS GTA V
folder and that `EOSSDK-Win64-Shipping.dll` exists. The script can create a
`GTAVLauncher.exe` symlink to `GTA5.exe`, because EGS installs may not include
Rockstar's `GTAVLauncher.exe`.

### No access to `Z:\root`

Do not use `Z:` as the GTA drive. In Wine, `Z:` usually maps to the Linux root
filesystem. Use:

```bash
GTA_WINE_DRIVE=g
```

The script now automatically replaces reserved `C` or `Z` with `G`.

### `majestic-patcher.node is a Windows PE binary`

This happens when the native Windows patcher is accidentally loaded by Linux
Node.js outside Proton. The script patches Majestic Launcher so the native
patcher is used from the Windows/Proton runtime instead.

Try:

```bash
npm run check
./install-and-run-majestic-proton.sh
```

Do not run Majestic's internal patcher files directly with system Node.js.

### CEF white screen or GPU problems

Keep these enabled:

```bash
DISABLE_CEF_GPU=1
MAJESTIC_LAUNCHER_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu-sandbox"
MAJESTIC_WINE_DLL_OVERRIDES="winegstreamer=d;dcomp=d"
```

Also verify Vulkan and 32-bit graphics libraries are installed.

### Protontricks hangs on `wineserver -w`

`protontricks win10` waits until all Wine processes in the prefix exit. The
script can stop active Wine processes in the prefix first:

```bash
PROTONTRICKS_STOP_PREFIX=1
```

To skip Windows 10 enforcement:

```bash
PROTONTRICKS_WIN10=0
```

To limit how long it can wait:

```bash
PROTONTRICKS_TIMEOUT=30
```

### Wine drive path problems: `Z:`, `G:`, `C:`

- `C:` is the Wine prefix drive. Do not map GTA there.
- `Z:` is Wine's Linux filesystem bridge. Do not map GTA there.
- `G:`, `E:`, or `D:` are safer choices.

Use:

```bash
GTA_WINE_DRIVE=g
```

### Steam library on another disk is ignored

Make sure the disk is mounted and contains:

```text
SteamLibrary/steamapps
SteamLibrary/steamapps/appmanifest_271590.acf
SteamLibrary/steamapps/common/Grand Theft Auto V
SteamLibrary/steamapps/compatdata/271590
```

If Steam remembers a removed disk, the script will log a warning such as
`Steam library root is configured but unavailable`.

## Known Issues

- Majestic Launcher updates can change `app.asar` layout and require patcher
  updates.
- EGS and Rockstar-only flows are less tested than Steam.
- Proton Experimental can change behavior between releases.
- `protontricks win10` can wait on Wine processes unless skipped or timed out.
- If GTA and `compatdata/271590` are on different Steam libraries, Steam license
  visibility can become unreliable.
- Flatpak/Snap Steam paths may need manual `STEAM_ROOT`, `GTA_PATH`, or
  `PROTON_PATH`.

## Project Files

| File | Purpose |
| --- | --- |
| `install-and-run-majestic-proton.sh` | Main script. Detects Steam/GTA/Proton, prepares the prefix, patches Majestic, and launches it. |
| `majestic-proton.conf` | User configuration file loaded by the main script. |
| `majestic-proton-js-patcher.js` | Node.js patcher for Majestic Launcher's Electron `app.asar` files. |
| `uinstall-majescic.sh` | Uninstall/cleanup helper. Dry-run by default; use `--yes` to remove detected Majestic files. |
| `MAJESTIC-PROTON-PATCH-README.md` | Developer notes about earlier platform/patcher fixes. |
| `package.json` | Node package metadata and scripts such as `npm run check`. |
| `LICENSE` | MIT license. |
| `logs/majestic-proton.log` | Runtime log created by the launcher script. This directory appears after running the script. |
| `cache/` | Installer cache directory created when Majestic installer is downloaded. |

## Bug Reports

Please include enough information to understand your Steam library, prefix, and
GTA location.

Checklist:

- [ ] Linux distribution and version.
- [ ] Steam type: native package, Flatpak, or Snap.
- [ ] GPU and driver type.
- [ ] Proton version, for example Proton Experimental.
- [ ] GTA platform: Steam, Rockstar, or Epic.
- [ ] `majestic-proton.conf` with private paths allowed but secrets removed.
- [ ] Full `logs/majestic-proton.log`.
- [ ] Output of:

```bash
npm run check
```

- [ ] Paths to:

```text
Steam root
GTA_PATH
STEAM_COMPAT_DATA_PATH
PROTON_PATH
MAJESTIC_EXE
```

- [ ] Say whether GTA is on another disk and whether that disk is mounted before
      launch.

## Uninstall / Cleanup

Dry-run:

```bash
./uinstall-majescic.sh
```

Remove detected Majestic files and caches:

```bash
./uinstall-majescic.sh --yes
```

Optional cleanup flags:

```bash
./uinstall-majescic.sh --yes --include-trash --include-installers
```

The cleanup script intentionally does not remove GTA V, Steam, Proton, Heroic,
Lutris, or Rockstar Launcher folders.

## Disclaimer

This project is not an official product of Majestic RP, Rockstar Games, Steam,
or Valve.

This project does not bypass licenses, DRM, anti-cheat, or server-side checks.
It only prepares a Linux/Proton environment and patches launcher compatibility
logic so that a legitimate installation can be used more reliably.

You must own a legal copy of GTA V.
