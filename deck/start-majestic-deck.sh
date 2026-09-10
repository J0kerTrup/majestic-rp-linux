#!/usr/bin/env bash
set -euo pipefail

# Directory where deck files and main repo are located
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Strip Steam environment variables injected by Steam Gaming Mode
# This prevents non-Steam GTA V / Rockstar Launcher from failing with LAUNCHER_ERR_STEAM_FAILED
unset SteamAppId SteamGameId SteamOverlayGameId SteamClientLaunch SteamEnv

# Launch Majestic RP Linux Runner
exec ./install-and-run-majestic-proton.sh run "$@"
