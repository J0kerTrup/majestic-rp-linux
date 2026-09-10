#!/usr/bin/env python3
"""
Automatically adds Majestic RP as a Non-Steam Game to Steam with Proton Experimental.
Detects active Steam user, updates shortcuts.vdf, copies grid icon, and configures config.vdf.
"""
import os
import sys
import glob
import struct
import binascii
import shutil
from pathlib import Path
import subprocess
from setup_rockstar_prefix import atomic_write
from majestic_linux.core.config import RunnerConfig
from majestic_linux.core.config_file import default_config_path
from majestic_linux.core.config_parser import parse_shell_config
from majestic_linux.detection.paths import find_steam_root

def parse_vdf_dict(data, offset=0):
    res = {}
    while offset < len(data):
        type_byte = data[offset]
        offset += 1
        if type_byte == 8:
            break
        null_pos = data.find(b"\x00", offset)
        if null_pos < 0:
            raise ValueError("Truncated VDF key")
        key = data[offset:null_pos].decode("utf-8", errors="ignore")
        offset = null_pos + 1
        if type_byte == 0:
            val, offset = parse_vdf_dict(data, offset)
            res[key] = val
        elif type_byte == 1:
            null_pos = data.find(b"\x00", offset)
            if null_pos < 0:
                raise ValueError("Truncated VDF string")
            val = data[offset:null_pos].decode("utf-8", errors="ignore")
            offset = null_pos + 1
            res[key] = val
        elif type_byte == 2:
            val = struct.unpack("<i", data[offset:offset+4])[0]
            offset += 4
            res[key] = val
        else:
            raise ValueError(f"Unknown type {type_byte} at {offset}")
    if offset == len(data) and (not data or data[-1] != 8):
        raise ValueError("Unterminated VDF object")
    return res, offset

def serialize_vdf_dict(d):
    buf = bytearray()
    for k, v in d.items():
        if isinstance(v, dict):
            buf.append(0)
            buf.extend(k.encode("utf-8") + b"\x00")
            buf.extend(serialize_vdf_dict(v))
            buf.append(8)
        elif isinstance(v, str):
            buf.append(1)
            buf.extend(k.encode("utf-8") + b"\x00")
            buf.extend(v.encode("utf-8") + b"\x00")
        elif isinstance(v, int):
            buf.append(2)
            buf.extend(k.encode("utf-8") + b"\x00")
            buf.extend(struct.pack("<i", v))
    return bytes(buf)

def add_shortcut():
    if subprocess.run(['pgrep', '-x', 'steam'], capture_output=True).returncode == 0:
        raise ValueError('Закройте Steam перед изменением ярлыков.')
    config_path = default_config_path()
    values = parse_shell_config(config_path)
    cfg = RunnerConfig(config_path=config_path)
    if values.get('STEAM_ROOT'):
        cfg.steam_root = Path(values['STEAM_ROOT'])
    steam_root = find_steam_root(cfg)
    if steam_root is None:
        raise ValueError('Steam не найден.')
    userdata_root = steam_root / "userdata"
    if not userdata_root.exists():
        print(f"Error: Steam userdata not found at {userdata_root}")
        return False

    repo_root = Path(__file__).resolve().parent.parent.parent
    exe = f'"{repo_root / "start-majestic-deck.sh"}"'
    start_dir = f'"{repo_root}/"'
    appname = "Majestic RP"
    key = exe + appname
    crc = binascii.crc32(key.encode("utf-8")) | 0x80000000
    signed_appid = struct.unpack("<i", struct.pack("<I", crc))[0]
    unsigned_appid = str(crc & 0xFFFFFFFF)

    # Find all user directories
    user_dirs = [p for p in userdata_root.iterdir() if p.is_dir() and p.name != "0"]
    if not user_dirs:
        print("No Steam users found.")
        return False

    icon_src = Path.home() / ".steam/steam/steamapps/compatdata/271590/pfx/drive_c/proton_shortcuts/icons/256x256/apps/5CB8_Majestic Launcher.0.png"

    for udir in user_dirs:
        config_dir = udir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        grid_dir = config_dir / "grid"
        grid_dir.mkdir(parents=True, exist_ok=True)

        grid_icon_dst = grid_dir / f"{unsigned_appid}_icon.png"
        if icon_src.exists():
            shutil.copy2(icon_src, grid_icon_dst)

        shortcuts_file = config_dir / "shortcuts.vdf"
        if shortcuts_file.exists():
            with open(shortcuts_file, "rb") as f:
                root, _ = parse_vdf_dict(f.read())
        else:
            root = {}

        shortcuts = root.get("shortcuts", {})
        idx_to_use = None
        for k, v in shortcuts.items():
            if v.get("AppName") == appname:
                idx_to_use = k
                break

        if idx_to_use is None:
            idx_to_use = str(max((int(k) for k in shortcuts if k.isdigit()), default=-1) + 1)

        entry = {
            "appid": signed_appid,
            "AppName": appname,
            "Exe": exe,
            "StartDir": start_dir,
            "icon": str(grid_icon_dst),
            "ShortcutPath": "",
            "LaunchOptions": "",
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "OpenVR": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "DevkitOverrideAppID": 0,
            "LastPlayTime": 0,
            "FlatpakAppID": "",
            "sortas": "",
            "tags": {}
        }
        shortcuts[idx_to_use] = entry
        root["shortcuts"] = shortcuts

        atomic_write(shortcuts_file, serialize_vdf_dict(root) + b"\x08")
        print(f"Added Steam shortcut to {shortcuts_file} (AppID: {unsigned_appid})")

    # Remove forced Proton from config.vdf if present for this native script
    config_vdf_path = steam_root / "config" / "config.vdf"
    if config_vdf_path.exists():
        text = config_vdf_path.read_text(encoding="utf-8", errors="ignore")
        # Remove any old mapping for unsigned_appid
        import re
        text = re.sub(rf'\n\s*"{unsigned_appid}"\s*\{{[^}}]*\}}', '', text)
        # Also clean any old shortcut appid mapping for majestic
        text = re.sub(r'\n\s*"2636208061"\s*\{{[^}}]*\}}', '', text)
        atomic_write(config_vdf_path, text)
        print(f"Cleaned CompatToolMapping for native script in {config_vdf_path}")

    return True


if __name__ == "__main__":
    try:
        if not add_shortcut():
            sys.exit(1)
        print("Steam shortcut configuration completed successfully!")
    except (OSError, ValueError, struct.error) as exc:
        print(f"Ошибка добавления ярлыка: {exc}", file=sys.stderr)
        sys.exit(1)
