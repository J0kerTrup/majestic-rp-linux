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
    return candidates
