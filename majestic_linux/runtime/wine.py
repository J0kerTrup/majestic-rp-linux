from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class WineMapping:
    prefix: Path
    dosdevices: Path
    drive_letter: str
    gta_path: Path
    wine_gta_path: str


def wine_path_for(path: Path, drive_letter: str) -> str:
    letter = drive_letter.upper()[0]
    return letter + ":\\"


def prepare_wine_mapping(
    compatdata: Path,
    gta_path: Path,
    drive_letter: str,
    *,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> WineMapping:
    prefix = compatdata / "pfx"
    dosdevices = prefix / "dosdevices"
    link = dosdevices / f"{drive_letter.lower()}:"
    mapping = WineMapping(prefix, dosdevices, drive_letter.lower()[0], gta_path, wine_path_for(gta_path, drive_letter))
    if logger:
        logger.info("Preparing Wine drive %s -> %s", link, gta_path)
    if not dry_run:
        dosdevices.mkdir(parents=True, exist_ok=True)
        if link.exists() or link.is_symlink():
            if link.resolve() != gta_path.resolve():
                link.unlink()
        if not link.exists():
            link.symlink_to(gta_path.resolve())
    return mapping


def ensure_egs_launcher_symlink(gta_path: Path, *, dry_run: bool = False, logger: logging.Logger | None = None) -> None:
    target = gta_path / "GTA5.exe"
    link = gta_path / "GTAVLauncher.exe"
    if not target.exists():
        if logger:
            logger.warning("Cannot create EGS launcher symlink, GTA5.exe is missing: %s", target)
        return
    if link.exists():
        return
    if logger:
        logger.info("Creating EGS compatibility symlink %s -> %s", link, target.name)
    if not dry_run:
        link.symlink_to(target.name)
