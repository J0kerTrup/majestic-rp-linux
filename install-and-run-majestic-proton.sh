#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/majestic-proton.conf}"
PATCHER_FILE="$SCRIPT_DIR/majestic-proton-js-patcher.js"
PATCHER_REQUIRED_MARKER="MAJESTIC_PROTON_INDEX_COMPAT_V4"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/majestic-proton.log"
LOG_MAX_BYTES=$((10 * 1024 * 1024))
LOG_MAX_FILES=10
LOG_MODULE="Launcher"

init_logging() {
  mkdir -p "$LOG_DIR"
  if [[ -f "$LOG_FILE" ]]; then
    local size
    size="$(wc -c < "$LOG_FILE" 2>/dev/null | tr -d ' \t' || printf '0')"
    if (( size >= LOG_MAX_BYTES )); then
      rm -f "$LOG_FILE.$((LOG_MAX_FILES - 1))"
      local i
      for ((i = LOG_MAX_FILES - 2; i >= 1; i--)); do
        [[ -f "$LOG_FILE.$i" ]] && mv "$LOG_FILE.$i" "$LOG_FILE.$((i + 1))"
      done
      mv "$LOG_FILE" "$LOG_FILE.1"
    fi
  fi
  touch "$LOG_FILE"
}

log_color() {
  case "$1" in
    INFO) printf '\033[34m' ;;
    DEBUG) printf '\033[90m' ;;
    SUCCESS) printf '\033[32m' ;;
    WARN) printf '\033[33m' ;;
    ERROR) printf '\033[31m' ;;
    *) printf '' ;;
  esac
}

log_event() {
  local level="$1"
  local module="$2"
  local message="$3"
  shift 3 || true
  local timestamp line details reset color
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  details="$*"
  line="[$timestamp] [$level] [$module] $message"
  [[ -n "$details" ]] && line="$line | $details"
  printf '%s\n' "$line" >> "$LOG_FILE"
  if [[ -t 2 ]]; then
    color="$(log_color "$level")"
    reset=$'\033[0m'
    printf '%b%s%b\n' "$color" "$line" "$reset" >&2
  else
    printf '%s\n' "$line" >&2
  fi
}

log_info() { log_event INFO "${2:-$LOG_MODULE}" "$1" "${3:-}"; }
log_debug() { log_event DEBUG "${2:-$LOG_MODULE}" "$1" "${3:-}"; }
log_warn() { log_event WARN "${2:-$LOG_MODULE}" "$1" "${3:-}"; }
log_error() { log_event ERROR "${2:-$LOG_MODULE}" "$1" "${3:-}"; }
log_success() { log_event SUCCESS "${2:-$LOG_MODULE}" "$1" "${3:-}"; }
log() { log_info "$1" "${2:-$LOG_MODULE}" "${3:-}"; }
die() {
  local message="$1"
  local code="${2:-1}"
  log_error "$message" "$LOG_MODULE" "exit_code=$code"
  exit "$code"
}

on_error() {
  local code=$?
  local command="${BASH_COMMAND:-unknown}"
  log_error "Command failed" "$LOG_MODULE" "exit_code=$code line=${BASH_LINENO[0]:-unknown} command=$command"
  exit "$code"
}

init_logging
trap on_error ERR
log_info "Starting Majestic Proton Launcher" "$LOG_MODULE" "script_dir=$SCRIPT_DIR log_file=$LOG_FILE"

if [[ -f "$CONFIG_FILE" ]]; then
  log_info "Loading configuration file" "Environment" "CONFIG_FILE=$CONFIG_FILE"
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
else
  log_warn "Configuration file not found; using defaults and environment" "Environment" "CONFIG_FILE=$CONFIG_FILE"
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

require_command() {
  local name="$1"
  local package_hint="$2"
  log_debug "Checking required command" "Dependencies" "command=$name"
  if command -v "$name" >/dev/null 2>&1; then
    local command_path version_output
    command_path="$(command -v "$name")"
    version_output="$("$name" --version 2>&1 | head -n 1 || true)"
    log_debug "Required command found" "Dependencies" "command=$name path=$command_path version=${version_output:-unknown}"
    return 0
  fi
  die "Required command '$name' was not found. Install it and rerun. Package hint: $package_hint"
}

check_base_dependencies() {
  log_info "Checking base dependencies" "Dependencies"
  require_command node "Ubuntu/Debian: nodejs; Fedora: nodejs; Arch: nodejs"
  require_command perl "Ubuntu/Debian: perl; Fedora: perl; Arch: perl"
  require_command sed "Ubuntu/Debian: sed; Fedora: sed; Arch: sed"
  require_command find "Ubuntu/Debian: findutils; Fedora: findutils; Arch: findutils"
  log_success "Base dependencies are available" "Dependencies"
}

validate_proton_verb() {
  log_debug "Validating Proton verb" "Proton" "PROTON_VERB=$PROTON_VERB"
  case "$PROTON_VERB" in
    run|waitforexitandrun|runinprefix) log_success "Proton verb is supported" "Proton" "PROTON_VERB=$PROTON_VERB" ;;
    *) die "Unsupported PROTON_VERB='$PROTON_VERB'. Use runinprefix, run or waitforexitandrun." ;;
  esac
}

backup_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    log_debug "Backup skipped because file does not exist" "Files" "file=$file"
    return 0
  fi
  if [[ -f "$file.majestic-proton-bak" ]]; then
    log_debug "Backup already exists" "Files" "backup=$file.majestic-proton-bak"
    return 0
  fi
  log_info "Creating file backup" "Files" "source=$file backup=$file.majestic-proton-bak"
  cp -a "$file" "$file.majestic-proton-bak"
  log_success "File backup created" "Files" "backup=$file.majestic-proton-bak"
}

find_steam_root() {
  log_info "Checking Steam installation" "Steam" "STEAM_ROOT=${STEAM_ROOT:-}"
  if [[ -n "${STEAM_ROOT:-}" && -d "${STEAM_ROOT:-}" ]]; then
    log_success "Using configured Steam root" "Steam" "STEAM_ROOT=$STEAM_ROOT"
    printf '%s\n' "$STEAM_ROOT"
    return
  fi
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
    log_debug "Checking Steam root candidate" "Steam" "candidate=$c"
    [[ -d "$c/steamapps" ]] && {
      log_success "Steam root detected" "Steam" "STEAM_ROOT=$c"
      printf '%s\n' "$c"
      return
    }
  done
  die "Steam folder was not found. Set STEAM_ROOT in $CONFIG_FILE."
}

get_steam_library_roots() {
  local base="$1"
  log_debug "Adding Steam library root" "Steam" "root=$base"
  printf '%s\n' "$base"
  local vdf="$base/steamapps/libraryfolders.vdf"
  if [[ ! -f "$vdf" ]]; then
    log_debug "Steam libraryfolders.vdf not found" "Steam" "file=$vdf"
    return 0
  fi
  log_debug "Reading Steam library folders" "Steam" "file=$vdf"
  while IFS= read -r p; do
    p="${p//\\\\//}"
    if [[ -d "$p/steamapps" ]]; then
      log_debug "Adding Steam library root from VDF" "Steam" "root=$p"
      printf '%s\n' "$p"
    else
      log_debug "Ignoring invalid Steam library root from VDF" "Steam" "root=$p"
    fi
  done < <(sed -nE 's/^[[:space:]]*"path"[[:space:]]*"([^"]+)".*/\1/p' "$vdf")
}

find_compatdata() {
  log_info "Checking Proton compatdata prefix" "Environment" "STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-} APP_ID=$APP_ID"
  if [[ -n "${STEAM_COMPAT_DATA_PATH:-}" && -d "${STEAM_COMPAT_DATA_PATH:-}/pfx" ]]; then
    log_success "Using configured Proton compatdata prefix" "Environment" "COMPATDATA=$STEAM_COMPAT_DATA_PATH"
    printf '%s\n' "$STEAM_COMPAT_DATA_PATH"
    return
  fi

  local root candidate
  if [[ -n "$APP_ID" ]]; then
    while IFS= read -r root; do
      candidate="$root/steamapps/compatdata/$APP_ID"
      log_debug "Checking compatdata candidate by AppID" "Environment" "candidate=$candidate"
      [[ -d "$candidate/pfx" ]] && {
        log_success "Compatdata prefix found by AppID" "Environment" "COMPATDATA=$candidate"
        printf '%s\n' "$candidate"
        return
      }
    done < <(get_steam_library_roots "$STEAM_ROOT")
  fi

  while IFS= read -r root; do
    local compat_root="$root/steamapps/compatdata"
    if [[ ! -d "$compat_root" ]]; then
      log_debug "Compatdata root missing" "Environment" "root=$compat_root"
      continue
    fi
    log_debug "Scanning compatdata root" "Environment" "root=$compat_root"
    while IFS= read -r candidate; do
      log_debug "Inspecting compatdata candidate" "Environment" "candidate=$candidate"
      if [[ -f "$candidate/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/Majestic Launcher.exe" ]]; then
        log_success "Compatdata prefix found by Majestic Launcher marker" "Environment" "COMPATDATA=$candidate"
        printf '%s\n' "$candidate"
        return
      fi
      if [[ -f "$candidate/pfx/drive_c/Program Files/Rockstar Games/Launcher/Launcher.exe" ]] ||
         [[ -d "$candidate/pfx/drive_c/users/steamuser/Documents/Rockstar Games/GTA V" ]]; then
        log_success "Compatdata prefix found by Rockstar/GTA marker" "Environment" "COMPATDATA=$candidate"
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
  log_info "Searching GTA V Steam manifest" "GTA" "GTA_PATH=$gta_real"
  gta_real="$(cd "$gta_real" && pwd -P)"
  while IFS= read -r root; do
    for manifest in "$root"/steamapps/appmanifest_*.acf; do
      [[ -f "$manifest" ]] || continue
      installdir="$(manifest_value "$manifest" installdir)"
      [[ -n "$installdir" ]] || continue
      appdir="$root/steamapps/common/$installdir"
      [[ -d "$appdir" ]] || continue
      appdir="$(cd "$appdir" && pwd -P)"
      log_debug "Checking Steam manifest" "GTA" "manifest=$manifest installdir=$installdir appdir=$appdir"
      [[ "$appdir" == "$gta_real" ]] && {
        log_success "GTA V Steam manifest found by path match" "GTA" "manifest=$manifest"
        printf '%s\n' "$manifest"
        return
      }
      [[ -f "$appdir/GTA5.exe" && "$installdir" == "Grand Theft Auto V" ]] && {
        log_success "GTA V Steam manifest found by executable marker" "GTA" "manifest=$manifest"
        printf '%s\n' "$manifest"
        return
      }
    done
  done < <(get_steam_library_roots "$STEAM_ROOT")
  log_warn "GTA V Steam manifest was not found" "GTA" "GTA_PATH=$gta_real"
}

find_gta_path() {
  log_info "Checking GTA V installation" "GTA" "GTA_PATH=${GTA_PATH:-}"
  if [[ -n "${GTA_PATH:-}" && -f "${GTA_PATH:-}/GTA5.exe" ]]; then
    log_success "Using configured GTA V path" "GTA" "GTA_PATH=$GTA_PATH"
    printf '%s\n' "$GTA_PATH"
    return
  fi
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
      log_debug "Checking GTA V candidate from manifest" "GTA" "manifest=$manifest candidate=$candidate"
      [[ -f "$candidate/GTA5.exe" && -f "$candidate/x64j.rpf" ]] && {
        log_success "GTA V path detected from Steam manifest" "GTA" "GTA_PATH=$candidate"
        printf '%s\n' "$candidate"
        return
      }
    done
    candidate="$root/steamapps/common/Grand Theft Auto V"
    log_debug "Checking default GTA V candidate" "GTA" "candidate=$candidate"
    [[ -f "$candidate/GTA5.exe" && -f "$candidate/x64j.rpf" ]] && {
      log_success "GTA V path detected from default Steam directory" "GTA" "GTA_PATH=$candidate"
      printf '%s\n' "$candidate"
      return
    }
  done

  # Heroic Launcher / Lutris fallback (EGS and RGL outside Steam)
  local heroic_candidates=(
    "$HOME/Games/Grand Theft Auto V"
    "$HOME/Games/GTA V"
    "$HOME/Games/Heroic/Grand Theft Auto V"
    "$HOME/.var/app/com.heroicgameslauncher.hgl/config/heroic/Games/Grand Theft Auto V"
    "$HOME/Games/grand-theft-auto-v"
    "$HOME/heroic/Grand Theft Auto V"
  )
  local c
  for c in "${heroic_candidates[@]}"; do
    log_debug "Checking Heroic/Lutris GTA V candidate" "GTA" "candidate=$c"
    [[ -f "$c/GTA5.exe" && -f "$c/x64j.rpf" ]] && {
      log_success "GTA V path detected from Heroic/Lutris directory" "GTA" "GTA_PATH=$c"
      printf '%s\n' "$c"
      return
    }
  done

  die "GTA V Legacy was not found. Set GTA_PATH in $CONFIG_FILE."
}

detect_gta_platform() {
  local gta="$1"
  # EGS: only EGS ships EOSSDK; check first since GTAVLauncher.exe exists in Steam too
  if [[ -f "$gta/EOSSDK-Win64-Shipping.dll" ]]; then printf 'egs\n'; return; fi
  # Steam: steam_api64.dll without EOSSDK = Steam
  if [[ -f "$gta/steam_api64.dll" ]]; then printf 'steam\n'; return; fi
  # RGL: GTAVLauncher.exe without steam_api64.dll = RGL
  if [[ -f "$gta/GTAVLauncher.exe" ]]; then printf 'rgl\n'; return; fi
  printf 'rgl\n'
}

ensure_gta_launcher_for_egs() {
  local gta="$1"
  # EGS GTA V does not ship GTAVLauncher.exe; create a symlink so the launcher
  # can invoke it and Wine will transparently execute GTA5.exe instead.
  if [[ ! -f "$gta/GTAVLauncher.exe" && -f "$gta/GTA5.exe" ]]; then
    log_info "GTAVLauncher.exe not found (EGS install); creating GTA5.exe symlink" "GTA" "target=$gta/GTAVLauncher.exe"
    ln -sfn "$gta/GTA5.exe" "$gta/GTAVLauncher.exe"
    log_success "GTAVLauncher.exe → GTA5.exe symlink created for EGS compatibility" "GTA"
  fi
}

find_proton() {
  log_info "Checking Proton installation" "Proton" "PROTON_PATH=${PROTON_PATH:-}"
  if [[ -n "${PROTON_PATH:-}" && -x "${PROTON_PATH:-}" ]]; then
    log_success "Using configured Proton executable" "Proton" "PROTON=$PROTON_PATH"
    printf '%s\n' "$PROTON_PATH"
    return
  fi
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
    log_debug "Checking Proton candidate" "Proton" "candidate=$c"
    [[ -x "$c" ]] && {
      log_success "Proton executable detected" "Proton" "PROTON=$c"
      printf '%s\n' "$c"
      return
    }
  done

  local found
  log_debug "Running fallback Proton search" "Proton" "STEAM_ROOT=$STEAM_ROOT"
  found="$(find \
    "$STEAM_ROOT/steamapps/common" \
    "$STEAM_ROOT/compatibilitytools.d" \
    "$HOME/.steam/root/compatibilitytools.d" \
    "$HOME/.local/share/Steam/compatibilitytools.d" \
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/compatibilitytools.d" \
    "$HOME/snap/steam/common/.local/share/Steam/compatibilitytools.d" \
    -maxdepth 2 -type f -name proton -executable 2>/dev/null | sort -Vr | head -n 1 || true)"
  log_debug "Fallback Proton search result" "Proton" "found=$found"
  [[ -n "$found" ]] && {
    log_success "Proton executable detected by fallback search" "Proton" "PROTON=$found"
    printf '%s\n' "$found"
    return
  }

  die "Proton was not found. Set PROTON_PATH in $CONFIG_FILE."
}

find_majestic_exe() {
  log_info "Searching Majestic Launcher executable" "Majestic" "MAJESTIC_EXE=${MAJESTIC_EXE:-}"
  if [[ -n "${MAJESTIC_EXE:-}" && -f "${MAJESTIC_EXE:-}" ]]; then
    log_success "Using configured Majestic Launcher executable" "Majestic" "MAJESTIC_EXE=$MAJESTIC_EXE"
    printf '%s\n' "$MAJESTIC_EXE"
    return
  fi
  if [[ -f "$SCRIPT_DIR/Majestic Launcher.exe" ]]; then
    log_success "Majestic Launcher executable found next to script" "Majestic" "MAJESTIC_EXE=$SCRIPT_DIR/Majestic Launcher.exe"
    printf '%s\n' "$SCRIPT_DIR/Majestic Launcher.exe"
    return
  fi
  local candidate="$COMPATDATA/pfx/drive_c/users/steamuser/AppData/Local/MajesticLauncher/Majestic Launcher.exe"
  log_debug "Checking Majestic Launcher in Proton prefix" "Majestic" "candidate=$candidate"
  [[ -f "$candidate" ]] && {
    log_success "Majestic Launcher executable found in Proton prefix" "Majestic" "MAJESTIC_EXE=$candidate"
    printf '%s\n' "$candidate"
    return
  }
  die "Majestic Launcher.exe was not found. Put this script next to it or set MAJESTIC_EXE."
}

patch_json_file() {
  local file="$1"
  local js="$2"
  if [[ ! -f "$file" ]]; then
    log_debug "JSON patch skipped because file does not exist" "Files" "file=$file"
    return 0
  fi
  log_info "Patching JSON file" "Files" "file=$file"
  node -e '
const fs = require("fs");
const file = process.argv[1];
const patch = new Function("config", process.argv[2]);
const config = JSON.parse(fs.readFileSync(file, "utf8"));
const next = patch(config) || config;
fs.writeFileSync(file, JSON.stringify(next, null, 2));
' "$file" "$js"
  log_success "JSON file patched" "Files" "file=$file"
}

patch_settings_xml() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    log_warn "GTA settings.xml not found; settings patch skipped" "GTA" "file=$file"
    return 0
  fi
  log_info "Patching GTA settings.xml" "GTA" "file=$file width=$GAME_WIDTH height=$GAME_HEIGHT windowed=$GAME_WINDOWED"
  backup_file "$file"
  perl -0pi -e '
    s/<ScreenWidth value="[^"]*" \/>/<ScreenWidth value="'"$GAME_WIDTH"'" \/>/g;
    s/<ScreenHeight value="[^"]*" \/>/<ScreenHeight value="'"$GAME_HEIGHT"'" \/>/g;
    s/<Windowed value="[^"]*" \/>/<Windowed value="'"$GAME_WINDOWED"'" \/>/g;
    s/<VSync value="[^"]*" \/>/<VSync value="0" \/>/g;
    s/<PauseOnFocusLoss value="[^"]*" \/>/<PauseOnFocusLoss value="0" \/>/g;
  ' "$file"
  log_success "GTA settings.xml patched" "GTA" "file=$file"
}

write_commandline() {
  local file="$GTA_PATH/commandline.txt"
  log_info "Writing GTA commandline.txt" "GTA" "file=$file"
  backup_file "$file"
  {
    [[ "$GAME_WINDOWED" == "1" ]] && printf '%s\n' "-windowed"
    [[ "$GAME_BORDERLESS" == "1" ]] && printf '%s\n' "-borderless"
    printf '%s\n' "-width $GAME_WIDTH"
    printf '%s\n' "-height $GAME_HEIGHT"
    printf '%s\n' "-ignoreDifferentVideoCard"
  } > "$file"
  log_success "GTA commandline.txt written" "GTA" "file=$file width=$GAME_WIDTH height=$GAME_HEIGHT windowed=$GAME_WINDOWED borderless=$GAME_BORDERLESS"
}

patch_runtime_configs() {
  log_info "Checking Majestic runtime configuration files" "Majestic"
  local mp_config="$COMPATDATA/pfx/drive_c/users/steamuser/AppData/Roaming/majestic-launcher/Multiplayer/majestic.json"
  if [[ -f "$mp_config" ]]; then
    log_info "Patching Majestic multiplayer configuration" "Majestic" "file=$mp_config"
    backup_file "$mp_config"
    patch_json_file "$mp_config" '
config.debug = false;
config.cefUseHardwareAcceleration = false;
return config;
'
  else
    log_debug "Majestic multiplayer configuration not found" "Majestic" "file=$mp_config"
  fi

  local cache_root="$COMPATDATA/pfx/drive_c/users/steamuser/AppData/Roaming/majestic-launcher/Multiplayer/cache"
  if [[ -d "$cache_root" ]]; then
    log_info "Writing Majestic permission cache files" "Majestic" "cache_root=$cache_root permissions=$MAJESTIC_PERMISSIONS"
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
    log_success "Majestic permission cache files written" "Majestic" "cache_root=$cache_root"
  else
    log_debug "Majestic permission cache root not found" "Majestic" "cache_root=$cache_root"
  fi
}

reset_rockstar_documents() {
  if [[ "$RESET_ROCKSTAR_DOCUMENTS" != "1" ]]; then
    log_debug "Rockstar Documents reset disabled" "Rockstar" "RESET_ROCKSTAR_DOCUMENTS=$RESET_ROCKSTAR_DOCUMENTS"
    return 0
  fi
  local docs="$COMPATDATA/pfx/drive_c/users/steamuser/Documents/Rockstar Games"
  if [[ ! -d "$docs" ]]; then
    log_warn "Rockstar Documents directory not found; reset skipped" "Rockstar" "directory=$docs"
    return 0
  fi
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  log_info "Renaming Rockstar Documents directory" "Rockstar" "source=$docs target=$docs.majestic-proton-bak-$stamp"
  mv "$docs" "$docs.majestic-proton-bak-$stamp"
  log_success "Rockstar Documents directory renamed" "Rockstar" "target=$docs.majestic-proton-bak-$stamp"
}

find_asar() {
  log_info "Searching asar tool" "Patcher"
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
    log_debug "Checking asar candidate" "Patcher" "candidate=$c"
    [[ -x "$c" ]] && {
      log_success "asar tool found" "Patcher" "asar=$c"
      printf '%s\n' "$c"
      return
    }
  done
  local found
  found="$(command -v asar 2>/dev/null || true)"
  log_debug "PATH asar lookup result" "Patcher" "asar=$found"
  [[ -n "$found" ]] && log_success "asar tool found in PATH" "Patcher" "asar=$found"
  printf '%s\n' "$found"
}

patch_asar_app() {
  local resources="$MAJESTIC_DIR/resources"
  local app_asar="$resources/app.asar"
  log_info "Checking Majestic Electron resources" "Patcher" "resources=$resources app_asar=$app_asar"
  [[ -f "$app_asar" ]] || {
    log_warn "app.asar not found; launcher JS patch skipped" "Patcher" "app_asar=$app_asar"
    return 0
  }
  [[ -f "$PATCHER_FILE" ]] || die "JS patcher was not found: $PATCHER_FILE"
  grep -q "$PATCHER_REQUIRED_MARKER" "$PATCHER_FILE" || die "Outdated JS patcher: $PATCHER_FILE. Copy the updated majestic-proton-js-patcher.js next to this script."
  log_info "JS patcher verified" "Patcher" "patcher=$PATCHER_FILE required_marker=$PATCHER_REQUIRED_MARKER"

  local asar_bin
  asar_bin="$(find_asar)"
  [[ -n "$asar_bin" ]] || {
    log_warn "asar tool not found; install @electron/asar or put asar in PATH, then rerun for full JS patch" "Patcher"
    return 0
  }

  local tmp="$resources/app.asar.majestic-proton-work"
  log_info "Preparing temporary app.asar workspace" "Patcher" "tmp=$tmp"
  log_debug "Removing previous temporary workspace" "Files" "command=rm -rf $tmp"
  rm -rf "$tmp"
  log_debug "Creating temporary workspace" "Files" "command=mkdir -p $tmp"
  mkdir -p "$tmp"
  backup_file "$app_asar"
  log_info "Extracting app.asar" "Patcher" "command=$asar_bin extract $app_asar $tmp"
  "$asar_bin" extract "$app_asar" "$tmp"

  log_info "Executing Majestic Proton JS patcher" "Patcher" "command=node $PATCHER_FILE $tmp $MAJESTIC_PERMISSIONS"
  node "$PATCHER_FILE" "$tmp" "$MAJESTIC_PERMISSIONS"

  log_info "Packing patched app.asar" "Patcher" "command=$asar_bin pack $tmp $app_asar"
  "$asar_bin" pack "$tmp" "$app_asar"
  log_debug "Removing temporary workspace" "Files" "command=rm -rf $tmp"
  rm -rf "$tmp"
  log_success "Majestic Launcher JS patch completed" "Patcher" "app_asar=$app_asar"
}

log_debug "Resolved configuration values" "Environment" "GAME_WIDTH=$GAME_WIDTH GAME_HEIGHT=$GAME_HEIGHT GAME_WINDOWED=$GAME_WINDOWED GAME_BORDERLESS=$GAME_BORDERLESS DISABLE_CEF_GPU=$DISABLE_CEF_GPU MAJESTIC_PLATFORM=$MAJESTIC_PLATFORM GTA_WINE_DRIVE=$GTA_WINE_DRIVE MAJESTIC_PERMISSIONS=$MAJESTIC_PERMISSIONS RESET_ROCKSTAR_DOCUMENTS=$RESET_ROCKSTAR_DOCUMENTS PROTON_VERB=$PROTON_VERB APP_ID=$APP_ID MAJESTIC_LAUNCHER_FLAGS=$MAJESTIC_LAUNCHER_FLAGS"
check_base_dependencies
validate_proton_verb

STEAM_ROOT="$(find_steam_root)"
GTA_PATH="$(find_gta_path)"

# Auto-detect real GTA V platform and warn if conf value differs
DETECTED_GTA_PLATFORM="$(detect_gta_platform "$GTA_PATH")"
log_info "Detected GTA V platform from files" "GTA" "detected=$DETECTED_GTA_PLATFORM configured=$MAJESTIC_PLATFORM GTA_PATH=$GTA_PATH"
if [[ "$MAJESTIC_PLATFORM" = "rgl" && "$DETECTED_GTA_PLATFORM" != "rgl" ]]; then
  log_warn "MAJESTIC_PLATFORM=rgl in conf but detected platform is '$DETECTED_GTA_PLATFORM'. Consider setting MAJESTIC_PLATFORM=$DETECTED_GTA_PLATFORM in $CONFIG_FILE." "GTA"
  MAJESTIC_PLATFORM="$DETECTED_GTA_PLATFORM"
  log_info "Auto-corrected MAJESTIC_PLATFORM to '$MAJESTIC_PLATFORM'" "GTA"
fi

# For EGS: create GTAVLauncher.exe → GTA5.exe symlink so the launcher can invoke it via Wine
if [[ "$MAJESTIC_PLATFORM" = "egs" ]]; then
  ensure_gta_launcher_for_egs "$GTA_PATH"
fi

GTA_MANIFEST="$(find_gta_manifest "$GTA_PATH" || true)"
if [[ -z "$APP_ID" && -n "$GTA_MANIFEST" ]]; then
  APP_ID="$(manifest_value "$GTA_MANIFEST" appid)"
  log_debug "Read AppID from GTA manifest" "GTA" "manifest=$GTA_MANIFEST APP_ID=$APP_ID"
fi
if [[ -n "$APP_ID" ]]; then
  log_info "Detected GTA AppID" "GTA" "APP_ID=$APP_ID"
else
  log_warn "GTA AppID was not found in Steam manifest; scanning all compatdata prefixes" "GTA"
fi

COMPATDATA="$(find_compatdata)"
if [[ -z "$APP_ID" ]]; then
  APP_ID="$(basename "$COMPATDATA")"
  log_info "Using AppID from detected compatdata folder" "Environment" "APP_ID=$APP_ID COMPATDATA=$COMPATDATA"
fi

if command -v protontricks >/dev/null 2>&1; then
  log_info "Forcing Windows 10 for Proton prefix" "Proton" "APP_ID=$APP_ID"
  protontricks "$APP_ID" win10 || log_debug "protontricks win10 returned non-zero, continuing..." "Proton"
else
  log_debug "protontricks not found, skipping Windows 10 enforcement" "Proton"
fi

PROTON="$(find_proton)"
MAJESTIC_EXE="$(find_majestic_exe)"
MAJESTIC_DIR="$(dirname "$MAJESTIC_EXE")"

log_debug "Resolved launch paths" "Environment" "STEAM_ROOT=$STEAM_ROOT COMPATDATA=$COMPATDATA GTA_PATH=$GTA_PATH MAJESTIC_EXE=$MAJESTIC_EXE MAJESTIC_DIR=$MAJESTIC_DIR PROTON=$PROTON"

log_info "Creating Wine dosdevices directory" "Wine" "directory=$COMPATDATA/pfx/dosdevices"
mkdir -p "$COMPATDATA/pfx/dosdevices"
log_info "Mapping Wine drive to GTA V" "Wine" "command=ln -sfn $GTA_PATH $COMPATDATA/pfx/dosdevices/${GTA_WINE_DRIVE}:"
ln -sfn "$GTA_PATH" "$COMPATDATA/pfx/dosdevices/${GTA_WINE_DRIVE}:"
log_success "Wine drive mapped to GTA V" "Wine" "drive=${GTA_WINE_DRIVE^^}: target=$GTA_PATH"

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

log_debug "Exported Proton and Majestic environment" "Environment" "STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAM_COMPAT_CLIENT_INSTALL_PATH STEAM_COMPAT_DATA_PATH=$STEAM_COMPAT_DATA_PATH STEAM_COMPAT_APP_ID=$STEAM_COMPAT_APP_ID SteamAppId=$SteamAppId SteamGameId=$SteamGameId WINEDLLOVERRIDES=$WINEDLLOVERRIDES MAJESTIC_PROTON_PLATFORM=$MAJESTIC_PROTON_PLATFORM MAJESTIC_GTA_WIN_PATH=$MAJESTIC_GTA_WIN_PATH MAJESTIC_DISABLE_CEF_GPU=$MAJESTIC_DISABLE_CEF_GPU ELECTRON_DISABLE_SANDBOX=$ELECTRON_DISABLE_SANDBOX ELECTRON_DISABLE_GPU=$ELECTRON_DISABLE_GPU"
log_info "Changing working directory to Majestic Launcher directory" "Launcher" "directory=$MAJESTIC_DIR"
cd "$MAJESTIC_DIR"
log_info "Starting Majestic Launcher with Proton" "Launcher" "PROTON_VERB=$PROTON_VERB"
log_debug "Majestic launch command" "Launcher" "command=$PROTON $PROTON_VERB $MAJESTIC_EXE $MAJESTIC_LAUNCHER_FLAGS platform=$MAJESTIC_PLATFORM gta_win_path=${GTA_WINE_DRIVE^^}:\\"
log_success "Launcher preparation completed; handing control to Proton" "Launcher"

exec "$PROTON" "$PROTON_VERB" "$MAJESTIC_EXE" $MAJESTIC_LAUNCHER_FLAGS
