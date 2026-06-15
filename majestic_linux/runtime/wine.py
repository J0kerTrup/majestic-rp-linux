from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import RunnerError


@dataclass(slots=True)
class WineMapping:
    prefix: Path
    dosdevices: Path
    drive_letter: str
    gta_path: Path
    wine_gta_path: str


def wine_path_for(path: Path, drive_letter: str) -> str:
    letter = normalize_drive_letter(drive_letter).upper()
    return letter + ":\\"


def normalize_drive_letter(drive_letter: str) -> str:
    letter = (drive_letter or "").strip().lower()[:1]
    if not letter.isalpha():
        raise RunnerError(f"Invalid Wine drive letter: {drive_letter!r}")
    return letter


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
    letter = normalize_drive_letter(drive_letter)
    mapping = WineMapping(prefix, dosdevices, letter, gta_path, wine_path_for(gta_path, letter))
    prepare_wine_drive(compatdata, gta_path, letter, dry_run=dry_run, logger=logger)
    return mapping


def prepare_optional_storage_drive(
    compatdata: Path,
    storage_path: Path | None,
    drive_letter: str,
    *,
    reserved_letters: set[str] | None = None,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> None:
    if storage_path is None:
        return
    letter = normalize_drive_letter(drive_letter)
    if letter in (reserved_letters or set()):
        raise RunnerError(f"Wine drive {letter.upper()}: is already reserved")
    prepare_wine_drive(compatdata, storage_path, letter, create_target=True, dry_run=dry_run, logger=logger)


def prepare_wine_drive(
    compatdata: Path,
    host_path: Path,
    drive_letter: str,
    *,
    create_target: bool = False,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> Path:
    prefix = compatdata / "pfx"
    dosdevices = prefix / "dosdevices"
    letter = normalize_drive_letter(drive_letter)
    link = dosdevices / f"{letter}:"
    target = host_path.expanduser().resolve()
    if logger:
        logger.info("Preparing Wine drive %s -> %s", link, target)
    if dry_run:
        return link
    if create_target:
        target.mkdir(parents=True, exist_ok=True)
    dosdevices.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        if link.resolve() != target:
            link.unlink()
    if not link.exists():
        link.symlink_to(target)
    return link


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
