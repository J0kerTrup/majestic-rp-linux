#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/majestic-proton.conf}"
DRY_RUN=1
INCLUDE_TRASH=0
INCLUDE_INSTALLERS=0
INCLUDE_PROJECTS=0

usage() {
  cat <<'EOF'
Usage:
  ./uinstall-majescic.sh            # dry-run: show what would be removed
  ./uinstall-majescic.sh --yes      # remove detected Majestic Launcher files/caches

Options:
  --yes                 actually remove files and directories
  --include-trash       also remove Majestic entries from ~/.local/share/Trash
  --include-installers  also remove Majestic installers from Downloads/home/cache
  --include-projects    also remove local majestic-rp-linux project copies/zips
  -h, --help            show this help

This script removes Majestic Launcher installs, Proton cache, native Linux
cache and MAJESTIC_GTA multiplayer folders. It intentionally does not remove
GTA V, Steam, Proton, Heroic, Lutris or Rockstar Launcher folders.
EOF
}

while (($#)); do
  case "$1" in
    --yes) DRY_RUN=0 ;;
    --include-trash) INCLUDE_TRASH=1 ;;
    --include-installers) INCLUDE_INSTALLERS=1 ;;
    --include-projects) INCLUDE_PROJECTS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

log() { printf '[%s] %s\n' "$1" "$2"; }
info() { log INFO "$1"; }
warn() { log WARN "$1"; }
remove_note() {
  if ((DRY_RUN)); then
    log DRY-RUN "would remove: $1"
  else
    log REMOVE "$1"
  fi
}

declare -a TARGETS=()
declare -A SEEN=()
GTA_PATH="${GTA_PATH:-}"
STEAM_ROOT="${STEAM_ROOT:-}"
STEAM_COMPAT_DATA_PATH="${STEAM_COMPAT_DATA_PATH:-}"
MAJESTIC_EXE="${MAJESTIC_EXE:-}"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

add_target() {
  local target="${1:-}"
  [[ -n "$target" && -e "$target" ]] || return 0
  target="$(realpath -m "$target")"
  [[ -n "${SEEN[$target]:-}" ]] && return 0
  SEEN["$target"]=1
  TARGETS+=("$target")
}

add_glob() {
  local pattern="$1"
  local match
  shopt -s nullglob
  for match in $pattern; do
    add_target "$match"
  done
  shopt -u nullglob
}

find_steam_roots() {
  local candidates=(
    "${STEAM_ROOT:-}"
    "$HOME/.local/share/Steam"
    "$HOME/.steam/root"
    "$HOME/.steam/steam"
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"
    "$HOME/.var/app/com.valvesoftware.Steam/.steam/root"
    "$HOME/snap/steam/common/.local/share/Steam"
  )
  local root
  declare -A roots_seen=()
  for root in "${candidates[@]}"; do
    [[ -n "$root" && -d "$root/steamapps" ]] || continue
    root="$(realpath -m "$root")"
    [[ -n "${roots_seen[$root]:-}" ]] && continue
    roots_seen["$root"]=1
    printf '%s\n' "$root"
  done
}

add_windows_user_targets() {
  local user_dir="$1"
  add_target "$user_dir/AppData/Local/MajesticLauncher"
  add_target "$user_dir/AppData/Local/majestic-launcher"
  add_target "$user_dir/AppData/Local/majestic-launcher-updater"
  add_target "$user_dir/AppData/Local/Programs/Majestic Launcher"
  add_target "$user_dir/AppData/Local/Programs/majestic-launcher"
  add_target "$user_dir/AppData/Roaming/majestic-launcher"
  add_target "$user_dir/AppData/Roaming/MajesticLauncher"
  add_target "$user_dir/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Majestic Launcher"
  add_target "$user_dir/Desktop/Majestic Launcher.lnk"
}

add_compatdata_targets() {
  local compat="$1"
  [[ -d "$compat/pfx" ]] || return 0
  add_target "$compat/pfx/drive_c/Games/MAJESTIC_GTA"
  add_target "$compat/pfx/drive_c/proton_shortcuts/Majestic Launcher.desktop"
  add_target "$compat/pfx/drive_c/users/steamuser/Documents/Majestic Launcher"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Local/MajesticLauncher"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Local/majestic-launcher"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Local/majestic-launcher-updater"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Local/Programs/Majestic Launcher"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Local/Programs/majestic-launcher"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Roaming/majestic-launcher"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Roaming/MajesticLauncher"
  add_glob "$compat/pfx/drive_c/users/*/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Majestic Launcher"
  add_glob "$compat/pfx/drive_c/users/*/Desktop/Majestic Launcher.lnk"
}

collect_targets() {
  local root compat_dir compat

  add_target "$HOME/.config/majestic-launcher"
  add_target "$HOME/.config/MajesticLauncher"
  add_target "$HOME/.config/majestic-linux-runner"
  add_target "$HOME/.cache/majestic-launcher"
  add_target "$HOME/.cache/MajesticLauncher"
  add_target "$HOME/.local/share/majestic-launcher"
  add_target "$HOME/.local/share/MajesticLauncher"
  add_target "$HOME/.Majestic"
  add_target "$HOME/.majestic"

  if [[ -n "${MAJESTIC_EXE:-}" && -f "${MAJESTIC_EXE:-}" ]]; then
    add_target "$(dirname "$MAJESTIC_EXE")"
    if [[ "$MAJESTIC_EXE" == */pfx/drive_c/users/*/* ]]; then
      local user_dir="${MAJESTIC_EXE%%/AppData/*}"
      add_windows_user_targets "$user_dir"
    fi
  fi

  if [[ -n "${STEAM_COMPAT_DATA_PATH:-}" ]]; then
    add_compatdata_targets "$STEAM_COMPAT_DATA_PATH"
  fi

  while IFS= read -r root; do
    compat_dir="$root/steamapps/compatdata"
    [[ -d "$compat_dir" ]] || continue
    while IFS= read -r compat; do
      if [[ -e "$compat/pfx/drive_c/Games/MAJESTIC_GTA" ]] ||
         [[ -e "$compat/pfx/drive_c/proton_shortcuts/Majestic Launcher.desktop" ]] ||
         find "$compat/pfx/drive_c/users" -maxdepth 6 \( -iname '*Majestic*' -o -iname 'majestic-launcher' \) -print -quit 2>/dev/null | grep -q .; then
        add_compatdata_targets "$compat"
      fi
    done < <(find "$compat_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
  done < <(find_steam_roots)

  while IFS= read -r installer_cache; do
    add_target "$installer_cache"
  done < <(find "$HOME/.cache" -maxdepth 4 \( \
    -path '*/$R0/Uninstall Majestic Launcher.exe' -o \
    -path '*/$PLUGINSDIR/app-64/Majestic Launcher.exe' \
  \) -print 2>/dev/null)

  if ((INCLUDE_INSTALLERS)); then
    add_glob "$HOME/MajesticLauncherSetup*.exe"
    add_glob "$HOME/Downloads/MajesticLauncherSetup*.exe"
    add_glob "$HOME/Загрузки/MajesticLauncherSetup*.exe"
    add_glob "$HOME/Downloads/*Majestic*.exe"
    add_glob "$HOME/Загрузки/*Majestic*.exe"
  fi

  if ((INCLUDE_TRASH)); then
    add_glob "$HOME/.local/share/Trash/files/*majestic*"
    add_glob "$HOME/.local/share/Trash/files/*Majestic*"
    add_glob "$HOME/.local/share/Trash/info/*majestic*"
    add_glob "$HOME/.local/share/Trash/info/*Majestic*"
  fi

  if ((INCLUDE_PROJECTS)); then
    add_glob "$HOME/Рабочий стол/majescit/git/majestic-rp-linux"
    add_glob "$HOME/Рабочий стол/majescit/git/majestic-rp-linux.zip"
    add_glob "$HOME/Загрузки/majestic-rp-linux*.zip"
    add_glob "$HOME/Downloads/majestic-rp-linux*.zip"
  fi
}

is_dangerous_target() {
  local target="$1"
  case "$target" in
    "/"|"$HOME"|"$HOME/"|"$SCRIPT_DIR"|"$SCRIPT_DIR/"|\
    "$HOME/.local/share/Steam"|"$HOME/.steam"|"$HOME/.steam/root")
      return 0
      ;;
  esac
  if [[ -n "${GTA_PATH:-}" && "$(realpath -m "$target")" == "$(realpath -m "$GTA_PATH")" ]]; then
    return 0
  fi
  case "$target" in
    *"/Grand Theft Auto V"|*"/GTA V"|*"/GTA5.exe"|*"/steamapps/common"*)
      return 0
      ;;
  esac
  return 1
}

remove_target() {
  local target="$1"
  if is_dangerous_target "$target"; then
    warn "skip protected target: $target"
    return 0
  fi
  remove_note "$target"
  ((DRY_RUN)) || rm -rf -- "$target"
}

collect_targets

if ((${#TARGETS[@]} == 0)); then
  info "No Majestic Launcher files or caches were detected."
  exit 0
fi

if ((DRY_RUN)); then
  info "Dry-run mode. Nothing will be removed. Rerun with --yes to delete."
else
  warn "Real delete mode enabled."
fi

for target in "${TARGETS[@]}"; do
  remove_target "$target"
done

if ((DRY_RUN)); then
  info "Dry-run completed. Add --yes to remove the listed paths."
else
  info "Majestic uninstall cleanup completed."
fi

