#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/majestic-proton.conf}"
PATCHER_FILE="$SCRIPT_DIR/majestic-proton-js-patcher.js"
PATCHER_REQUIRED_MARKER="MAJESTIC_PROTON_INDEX_COMPAT_V4"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

GAME_WIDTH="${GAME_WIDTH:-1920}"
GAME_HEIGHT="${GAME_HEIGHT:-1080}"
GAME_WINDOWED="${GAME_WINDOWED:-1}"
GAME_BORDERLESS="${GAME_BORDERLESS:-1}"
DISABLE_CEF_GPU="${DISABLE_CEF_GPU:-1}"
MAJESTIC_PLATFORM="${MAJESTIC_PLATFORM:-rgl}"
GTA_WINE_DRIVE="${GTA_WINE_DRIVE:-g}"
MAJESTIC_PERMISSIONS="${MAJESTIC_PERMISSIONS:-1,3,4}"
RESET_ROCKSTAR_DOCUMENTS="${RESET_ROCKSTAR_DOCUMENTS:-0}"


PROTON_VERB="${PROTON_VERB:-waitforexitandrun}"
APP_ID="${APP_ID:-}"

MAJESTIC_LAUNCHER_FLAGS="${MAJESTIC_LAUNCHER_FLAGS:---no-sandbox --disable-dev-shm-usage --disable-gpu-sandbox}"

log() { printf '[majestic-proton] %s\n' "$*"; }
die() { printf '[majestic-proton] ERROR: %s\n' "$*" >&2; exit 1; }

require_command() {
  local name="$1"
  local package_hint="$2"
  command -v "$name" >/dev/null 2>&1 && return 0
  die "Required command '$name' was not found. Install it and rerun. Package hint: $package_hint"
}

check_base_dependencies() {
  require_command node "Ubuntu/Debian: nodejs; Fedora: nodejs; Arch: nodejs"
  require_command perl "Ubuntu/Debian: perl; Fedora: perl; Arch: perl"
  require_command sed "Ubuntu/Debian: sed; Fedora: sed; Arch: sed"
  require_command find "Ubuntu/Debian: findutils; Fedora: findutils; Arch: findutils"
}

validate_proton_verb() {
  case "$PROTON_VERB" in
    run|waitforexitandrun|runinprefix) ;;
    *) die "Unsupported PROTON_VERB='$PROTON_VERB'. Use runinprefix, run or waitforexitandrun." ;;
  esac
}

backup_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  [[ -f "$file.majestic-proton-bak" ]] || cp -a "$file" "$file.majestic-proton-bak"
}

find_steam_root() {
  if [[ -n "${STEAM_ROOT:-}" && -d "${STEAM_ROOT:-}" ]]; then printf '%s\n' "$STEAM_ROOT"; return; fi
  local candidates=(
    "$HOME/.local/share/Steam"
    "$HOME/.steam/root"
    "$HOME/.steam/steam"
    "$HOME/snap/steam/common/.local/share/Steam"
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"
    "$HOME/.var/app/com.valvesoftware.Steam/.steam/root"
  )
  local c
  for c in "${candidates[@]}"; do
    [[ -d "$c/steamapps" ]] && { printf '%s\n' "$c"; return; }
  done
  die "Steam folder was not found. Set STEAM_ROOT in $CONFIG_FILE."
}

get_steam_library_roots() {
  local base="$1"
  printf '%s\n' "$base"
  local vdf="$base/steamapps/libraryfolders.vdf"
  [[ -f "$vdf" ]] || return 0
  while IFS= read -r p; do
    p="${p//\\\\//}"
    [[ -d "$p/steamapps" ]] && printf '%s\n' "$p"
  done < <(sed -nE 's/^[[:space:]]*"path"[[:space:]]*"([^"]+)".*/\1/p' "$vdf")
}

find_compatdata() {
  if [[ -n "${STEAM_COMPAT_DATA_PATH:-}" && -d "${STEAM_COMPAT_DATA_PATH:-}/pfx" ]]; then
    printf '%s\n' "$STEAM_COMPAT_DATA_PATH"
    return
  fi

  local root candidate
  if [[ -n "$APP_ID" ]]; then
    while IFS= read -r root; do
      candidate="$root/steamapps/compatdata/$APP_ID"
      [[ -d "$candidate/pfx" ]] && { printf '%s\n' "$candidate"; return; }
    done < <(get_steam_library_roots "$STEAM_ROOT")
  fi

  while IFS= read -r root; do
    local compat_root="$root/steamapps/compatdata"
    [[ -d "$compat_root" ]] || continue
    while IFS= read -r candidate; do
      if [[ -f "$candidate/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/Majestic Launcher.exe" ]]; then
        printf '%s\n' "$candidate"
        return
      fi
      if [[ -f "$candidate/pfx/drive_c/Program Files/Rockstar Games/Launcher/Launcher.exe" ]] ||
         [[ -d "$candidate/pfx/drive_c/users/steamuser/Documents/Rockstar Games/GTA V" ]]; then
        printf '%s\n' "$candidate"
        return
      fi
    done < <(find "$compat_root" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
  done < <(get_steam_library_roots "$STEAM_ROOT")

  die "GTA V Proton prefix was not found. Start GTA V once through Steam/Proton or set STEAM_COMPAT_DATA_PATH in $CONFIG_FILE."
}

manifest_value() {
  local file="$1"
  local key="$2"
  sed -nE 's/^[[:space:]]*"'"$key"'"[[:space:]]*"([^"]*)".*/\1/p' "$file" | head -n 1
}

find_gta_manifest() {
  local gta_real="$1"
  local root manifest installdir appdir
  gta_real="$(cd "$gta_real" && pwd -P)"
  while IFS= read -r root; do
    for manifest in "$root"/steamapps/appmanifest_*.acf; do
      [[ -f "$manifest" ]] || continue
      installdir="$(manifest_value "$manifest" installdir)"
      [[ -n "$installdir" ]] || continue
      appdir="$root/steamapps/common/$installdir"
      [[ -d "$appdir" ]] || continue
      appdir="$(cd "$appdir" && pwd -P)"
      [[ "$appdir" == "$gta_real" ]] && { printf '%s\n' "$manifest"; return; }
      [[ -f "$appdir/GTA5.exe" && "$installdir" == "Grand Theft Auto V" ]] && { printf '%s\n' "$manifest"; return; }
    done
  done < <(get_steam_library_roots "$STEAM_ROOT")
}

find_gta_path() {
  if [[ -n "${GTA_PATH:-}" && -f "${GTA_PATH:-}/GTA5.exe" ]]; then printf '%s\n' "$GTA_PATH"; return; fi
  local roots=()
  mapfile -t roots < <(get_steam_library_roots "$STEAM_ROOT")
  local root candidate
  for root in "${roots[@]}"; do
    local manifests=("$root"/steamapps/appmanifest_*.acf)
    local manifest installdir
    for manifest in "${manifests[@]}"; do
      [[ -f "$manifest" ]] || continue
      installdir="$(manifest_value "$manifest" installdir)"
      [[ -n "$installdir" ]] || continue
      candidate="$root/steamapps/common/$installdir"
      [[ -f "$candidate/GTA5.exe" && -f "$candidate/x64j.rpf" ]] && { printf '%s\n' "$candidate"; return; }
    done
    candidate="$root/steamapps/common/Grand Theft Auto V"
    [[ -f "$candidate/GTA5.exe" && -f "$candidate/x64j.rpf" ]] && { printf '%s\n' "$candidate"; return; }
  done
  die "GTA V Legacy was not found. Set GTA_PATH in $CONFIG_FILE."
}

find_proton() {
  if [[ -n "${PROTON_PATH:-}" && -x "${PROTON_PATH:-}" ]]; then printf '%s\n' "$PROTON_PATH"; return; fi
  local candidates=()
  local root

  while IFS= read -r root; do
    candidates+=(
      "$root/steamapps/common/Proton - Experimental/proton"
      "$root/steamapps/common/Proton Hotfix/proton"
      "$root/steamapps/common/Proton 10.0/proton"
      "$root/steamapps/common/Proton 9.0/proton"
    )
  done < <(get_steam_library_roots "$STEAM_ROOT")

  candidates+=(
    "$HOME/.steam/root/compatibilitytools.d/GE-Proton10-34/proton"
    "$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton10-34/proton"
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/compatibilitytools.d/GE-Proton10-34/proton"
    "$HOME/snap/steam/common/.local/share/Steam/compatibilitytools.d/GE-Proton10-34/proton"
  )

  local c
  for c in "${candidates[@]}"; do
    [[ -x "$c" ]] && { printf '%s\n' "$c"; return; }
  done

  local found
  found="$(find \
    "$STEAM_ROOT/steamapps/common" \
    "$STEAM_ROOT/compatibilitytools.d" \
    "$HOME/.steam/root/compatibilitytools.d" \
    "$HOME/.local/share/Steam/compatibilitytools.d" \
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/compatibilitytools.d" \
    "$HOME/snap/steam/common/.local/share/Steam/compatibilitytools.d" \
    -maxdepth 2 -type f -name proton -executable 2>/dev/null | sort -Vr | head -n 1 || true)"
  [[ -n "$found" ]] && { printf '%s\n' "$found"; return; }

  die "Proton was not found. Set PROTON_PATH in $CONFIG_FILE."
}

find_majestic_exe() {
  if [[ -n "${MAJESTIC_EXE:-}" && -f "${MAJESTIC_EXE:-}" ]]; then printf '%s\n' "$MAJESTIC_EXE"; return; fi
  if [[ -f "$SCRIPT_DIR/Majestic Launcher.exe" ]]; then printf '%s\n' "$SCRIPT_DIR/Majestic Launcher.exe"; return; fi
  local candidate="$COMPATDATA/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/Majestic Launcher.exe"
  [[ -f "$candidate" ]] && { printf '%s\n' "$candidate"; return; }
  die "Majestic Launcher.exe was not found. Put this script next to it or set MAJESTIC_EXE."
}

patch_json_file() {
  local file="$1"
  local js="$2"
  [[ -f "$file" ]] || return 0
  node -e '
const fs = require("fs");
const file = process.argv[1];
const patch = new Function("config", process.argv[2]);
const config = JSON.parse(fs.readFileSync(file, "utf8"));
const next = patch(config) || config;
fs.writeFileSync(file, JSON.stringify(next, null, 2));
' "$file" "$js"
}

patch_settings_xml() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  backup_file "$file"
  perl -0pi -e '
    s/<ScreenWidth value="[^"]*" \/>/<ScreenWidth value="'"$GAME_WIDTH"'" \/>/g;
    s/<ScreenHeight value="[^"]*" \/>/<ScreenHeight value="'"$GAME_HEIGHT"'" \/>/g;
    s/<Windowed value="[^"]*" \/>/<Windowed value="'"$GAME_WINDOWED"'" \/>/g;
    s/<VSync value="[^"]*" \/>/<VSync value="0" \/>/g;
    s/<PauseOnFocusLoss value="[^"]*" \/>/<PauseOnFocusLoss value="0" \/>/g;
  ' "$file"
}

write_commandline() {
  local file="$GTA_PATH/commandline.txt"
  backup_file "$file"
  {
    [[ "$GAME_WINDOWED" == "1" ]] && printf '%s\n' "-windowed"
    [[ "$GAME_BORDERLESS" == "1" ]] && printf '%s\n' "-borderless"
    printf '%s\n' "-width $GAME_WIDTH"
    printf '%s\n' "-height $GAME_HEIGHT"
    printf '%s\n' "-ignoreDifferentVideoCard"
  } > "$file"
}

patch_runtime_configs() {
  local mp_config="$COMPATDATA/pfx/drive_c/users/steamuser/AppData/Roaming/majestic-launcher/Multiplayer/majestic.json"
  if [[ -f "$mp_config" ]]; then
    backup_file "$mp_config"
    patch_json_file "$mp_config" '
config.debug = false;
config.cefUseHardwareAcceleration = false;
return config;
'
  fi

  local cache_root="$COMPATDATA/pfx/drive_c/users/steamuser/AppData/Roaming/majestic-launcher/Multiplayer/cache"
  if [[ -d "$cache_root" ]]; then
    node -e '
const fs = require("fs");
const path = require("path");
const root = process.argv[1];
const values = process.argv[2].split(",").map((x) => Number.parseInt(x.trim(), 10)).filter((x) => Number.isInteger(x) && x >= 0 && x <= 254);
const data = Buffer.from([...values, 255]);
for (const name of fs.readdirSync(root)) {
  const dir = path.join(root, name);
  if (fs.existsSync(dir) && fs.lstatSync(dir).isDirectory()) {
    fs.writeFileSync(path.join(dir, "permissions"), data);
  }
}
' "$cache_root" "$MAJESTIC_PERMISSIONS"
  fi
}

reset_rockstar_documents() {
  [[ "$RESET_ROCKSTAR_DOCUMENTS" == "1" ]] || return 0
  local docs="$COMPATDATA/pfx/drive_c/users/steamuser/Documents/Rockstar Games"
  [[ -d "$docs" ]] || return 0
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  mv "$docs" "$docs.majestic-proton-bak-$stamp"
  log "Rockstar Documents was renamed to Rockstar Games.majestic-proton-bak-$stamp"
}

find_asar() {
  local candidates=(
    "$SCRIPT_DIR/node_modules/.bin/asar"
    "$HOME/.npm-global/bin/asar"
    "$HOME/.local/bin/asar"
    "$HOME/.npm/bin/asar"
    "/usr/bin/asar"
    "/usr/local/bin/asar"
  )
  local c
  for c in "${candidates[@]}"; do
    [[ -x "$c" ]] && { printf '%s\n' "$c"; return; }
  done
  command -v asar 2>/dev/null || true
}

patch_asar_app() {
  local resources="$MAJESTIC_DIR/resources"
  local app_asar="$resources/app.asar"
  [[ -f "$app_asar" ]] || { log "app.asar not found, skipping launcher JS patch"; return 0; }
  [[ -f "$PATCHER_FILE" ]] || die "JS patcher was not found: $PATCHER_FILE"
  grep -q "$PATCHER_REQUIRED_MARKER" "$PATCHER_FILE" || die "Outdated JS patcher: $PATCHER_FILE. Copy the updated majestic-proton-js-patcher.js next to this script."
  log "JS patcher: $PATCHER_FILE"

  local asar_bin
  asar_bin="$(find_asar)"
  [[ -n "$asar_bin" ]] || {
    log "asar tool not found; install @electron/asar or put asar in PATH, then rerun for full JS patch"
    return 0
  }

  local tmp="$resources/app.asar.majestic-proton-work"
  rm -rf "$tmp"
  mkdir -p "$tmp"
  backup_file "$app_asar"
  "$asar_bin" extract "$app_asar" "$tmp"

  node "$PATCHER_FILE" "$tmp" "$MAJESTIC_PERMISSIONS"

  "$asar_bin" pack "$tmp" "$app_asar"
  rm -rf "$tmp"
}

check_base_dependencies
validate_proton_verb

STEAM_ROOT="$(find_steam_root)"
GTA_PATH="$(find_gta_path)"

GTA_MANIFEST="$(find_gta_manifest "$GTA_PATH" || true)"
if [[ -z "$APP_ID" && -n "$GTA_MANIFEST" ]]; then
  APP_ID="$(manifest_value "$GTA_MANIFEST" appid)"
fi
if [[ -n "$APP_ID" ]]; then
  log "Detected GTA AppID: $APP_ID"
else
  log "GTA AppID was not found in Steam manifest; scanning all compatdata prefixes"
fi

COMPATDATA="$(find_compatdata)"
if [[ -z "$APP_ID" ]]; then
  APP_ID="$(basename "$COMPATDATA")"
  log "Using AppID from detected compatdata folder: $APP_ID"
fi
PROTON="$(find_proton)"
MAJESTIC_EXE="$(find_majestic_exe)"
MAJESTIC_DIR="$(dirname "$MAJESTIC_EXE")"

log "Steam: $STEAM_ROOT"
log "Compatdata: $COMPATDATA"
log "GTA V: $GTA_PATH"
log "Majestic: $MAJESTIC_EXE"
log "Proton: $PROTON"

mkdir -p "$COMPATDATA/pfx/dosdevices"
ln -sfn "$GTA_PATH" "$COMPATDATA/pfx/dosdevices/${GTA_WINE_DRIVE}:"
log "Wine drive ${GTA_WINE_DRIVE^^}: mapped to GTA V"

write_commandline
patch_settings_xml "$COMPATDATA/pfx/drive_c/users/steamuser/Documents/Rockstar Games/GTA V/settings.xml"
patch_runtime_configs
reset_rockstar_documents
patch_asar_app

export STEAM_COMPAT_CLIENT_INSTALL_PATH="${STEAM_COMPAT_CLIENT_INSTALL_PATH:-$STEAM_ROOT}"
export STEAM_COMPAT_DATA_PATH="${STEAM_COMPAT_DATA_PATH:-$COMPATDATA}"
export STEAM_COMPAT_APP_ID="${STEAM_COMPAT_APP_ID:-$APP_ID}"
export SteamAppId="${SteamAppId:-$APP_ID}"
export SteamGameId="${SteamGameId:-$APP_ID}"
export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:-winegstreamer=d}"

export MAJESTIC_PROTON_PLATFORM="$MAJESTIC_PLATFORM"
export MAJESTIC_GTA_WIN_PATH="${GTA_WINE_DRIVE^^}:\\"
export MAJESTIC_DISABLE_CEF_GPU="$DISABLE_CEF_GPU"

export ELECTRON_DISABLE_SANDBOX="${ELECTRON_DISABLE_SANDBOX:-1}"
export ELECTRON_DISABLE_GPU="${ELECTRON_DISABLE_GPU:-1}"

cd "$MAJESTIC_DIR"
log "Starting Majestic Launcher with Proton verb: $PROTON_VERB"
log "Platform: $MAJESTIC_PLATFORM, GTA Path (Win): ${GTA_WINE_DRIVE^^}:\\"

exec "$PROTON" "$PROTON_VERB" "$MAJESTIC_EXE" $MAJESTIC_LAUNCHER_FLAGS
