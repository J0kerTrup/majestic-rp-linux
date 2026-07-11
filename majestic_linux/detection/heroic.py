from __future__ import annotations

import json
from pathlib import Path


def heroic_roots(home: Path | None = None) -> list[Path]:
    home = home or Path.home()
    return [
        home / "Games" / "Heroic",
        home / ".var" / "app" / "com.heroicgameslauncher.hgl" / "data" / "heroic",
        home / ".config" / "heroic",
    ]


def heroic_gta_candidates(home: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    for root in heroic_roots(home):
        candidates.extend(
            [
                root / "Grand Theft Auto V",
                root / "GTAV",
                root / "Games" / "Grand Theft Auto V",
                root / "legendaryConfig" / "legendary" / "Grand Theft Auto V",
            ]
        )
    for cfg in (home or Path.home()).glob(".config/heroic/**/*.json"):
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for value in data.values() if isinstance(data, dict) else []:
            if isinstance(value, str) and "Grand Theft Auto" in value:
                candidates.append(Path(value).expanduser())
    return list(dict.fromkeys(candidates))


def legendary_gta_candidates(home: Path | None = None) -> list[Path]:
    home = home or Path.home()
    candidates: list[Path] = []
    manifests = [
        home / ".config" / "legendary" / "installed.json",
        home / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "legendary" / "installed.json",
        home / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "legendaryConfig" / "legendary" / "installed.json",
    ]
    for manifest in manifests:
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for app_name, value in data.items() if isinstance(data, dict) else []:
            if not isinstance(value, dict):
                continue
            title = " ".join(str(value.get(key, "")) for key in ("title", "app_name", "app_title"))
            install_path = value.get("install_path") or value.get("installPath")
            if install_path and ("grand theft auto" in title.lower() or str(app_name).lower() in {"9d2d0eb64d5c44529cece33fe2a46482", "gta5"}):
                candidates.append(Path(str(install_path)).expanduser())
    return list(dict.fromkeys(candidates))
