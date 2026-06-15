from __future__ import annotations

import logging
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


WHEEL_ERROR = "Invalid vehicle wheel drawable index"
MODEL_HASH_RE = re.compile(r"Model hash:\s*(\d+)")
MOD_SLOT_48 = "Mod slot: 48"
DATAFILE_ERROR = "CDataFileMgr::FindDataFile() -> Failed to find"
CATEGORY_ERROR = 'Can\'t load asset file "categories.dat22.rel"'
DUPLICATE_WEAPON_ERROR = "Duplicate weapon item:"
SKIPPED_G9EC_RE = re.compile(r"Skipping game DLC:\s+dlcpacks:/([^/]*g9ec[^/]*)/", re.IGNORECASE)
DATAFILE_DLC_RE = re.compile(r"\s([A-Za-z0-9_]+):/")
MAJESTIC_GTA_ROOT_FILES = (
    "majestic-client.dll",
    "libtox.dll",
    "fvad.dll",
    "opus.dll",
    "opusenc.dll",
    "zlib1.dll",
)


@dataclass(frozen=True, slots=True)
class MultiplayerRepairReport:
    multiplayer_path: Path | None
    analyzed_logs: tuple[Path, ...]
    invalid_wheel_errors: int
    mod_slot_48_errors: int
    model_hashes: dict[str, int]
    datafile_errors: int = 0
    missing_dlc: dict[str, int] | None = None
    duplicate_weapon_errors: int = 0
    category_asset_errors: int = 0
    skipped_gen9_dlc: tuple[str, ...] = ()
    backup_path: Path | None = None
    gta_root_backup_path: Path | None = None
    gen9_backup_path: Path | None = None
    repaired: bool = False
    dry_run: bool = False

    @property
    def detected(self) -> bool:
        return self.invalid_wheel_errors > 0


def multiplayer_roaming_paths(compatdata: Path) -> list[Path]:
    users = compatdata / "pfx" / "drive_c" / "users"
    return sorted(
        path
        for path in users.glob("*/AppData/Roaming/majestic-launcher/Multiplayer")
        if path.exists() and path.is_dir()
    )


def analyze_multiplayer_logs(multiplayer_path: Path, *, max_logs: int = 5, min_mtime: float | None = None) -> MultiplayerRepairReport:
    logs_dir = multiplayer_path / "logs"
    logs = _client_logs(logs_dir, max_logs=max_logs, min_mtime=min_mtime)
    invalid_wheel_errors = 0
    mod_slot_48_errors = 0
    datafile_errors = 0
    duplicate_weapon_errors = 0
    category_asset_errors = 0
    model_hashes: Counter[str] = Counter()
    missing_dlc: Counter[str] = Counter()
    skipped_gen9_dlc: set[str] = set()
    for log in logs:
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            if WHEEL_ERROR in line:
                invalid_wheel_errors += 1
            if MOD_SLOT_48 in line:
                mod_slot_48_errors += 1
            if DATAFILE_ERROR in line:
                datafile_errors += 1
                dlc_match = DATAFILE_DLC_RE.search(line)
                if dlc_match:
                    missing_dlc[dlc_match.group(1)] += 1
            if CATEGORY_ERROR in line:
                category_asset_errors += 1
            if DUPLICATE_WEAPON_ERROR in line:
                duplicate_weapon_errors += 1
            skipped_match = SKIPPED_G9EC_RE.search(line)
            if skipped_match:
                skipped_gen9_dlc.add(skipped_match.group(1))
            match = MODEL_HASH_RE.search(line)
            if match:
                model_hashes[match.group(1)] += 1
    return MultiplayerRepairReport(
        multiplayer_path=multiplayer_path,
        analyzed_logs=tuple(logs),
        invalid_wheel_errors=invalid_wheel_errors,
        mod_slot_48_errors=mod_slot_48_errors,
        model_hashes=dict(model_hashes),
        datafile_errors=datafile_errors,
        missing_dlc=dict(missing_dlc),
        duplicate_weapon_errors=duplicate_weapon_errors,
        category_asset_errors=category_asset_errors,
        skipped_gen9_dlc=tuple(sorted(skipped_gen9_dlc, key=str.lower)),
    )


def _client_logs(logs_dir: Path, *, max_logs: int, min_mtime: float | None = None) -> list[Path]:
    if not logs_dir.exists():
        return []
    logs = sorted(logs_dir.glob("client_*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    if min_mtime is not None:
        logs = [path for path in logs if path.stat().st_mtime > min_mtime]
    return logs[:max_logs]


def repair_multiplayer_cache(
    compatdata: Path,
    *,
    threshold: int,
    force: bool = False,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
    min_mtime: float | None = None,
) -> list[MultiplayerRepairReport]:
    reports: list[MultiplayerRepairReport] = []
    for multiplayer_path in multiplayer_roaming_paths(compatdata):
        report = analyze_multiplayer_logs(multiplayer_path, min_mtime=min_mtime)
        should_repair = force or report.invalid_wheel_errors >= threshold
        if logger:
            logger.info(
                "Majestic multiplayer log analysis: path=%s invalid_wheel_errors=%s mod_slot_48=%s datafile_errors=%s category_asset_errors=%s duplicate_weapon_errors=%s skipped_gen9_dlc=%s model_hashes=%s missing_dlc=%s",
                multiplayer_path,
                report.invalid_wheel_errors,
                report.mod_slot_48_errors,
                report.datafile_errors,
                report.category_asset_errors,
                report.duplicate_weapon_errors,
                report.skipped_gen9_dlc,
                report.model_hashes,
                report.missing_dlc,
            )
        if not should_repair:
            reports.append(report)
            continue
        backup_path = _backup_path(multiplayer_path)
        if logger:
            logger.warning("Repairing Majestic Multiplayer cache by archiving %s -> %s", multiplayer_path, backup_path)
        if not dry_run:
            shutil.move(str(multiplayer_path), str(backup_path))
        reports.append(
            MultiplayerRepairReport(
                multiplayer_path=multiplayer_path,
                analyzed_logs=report.analyzed_logs,
                invalid_wheel_errors=report.invalid_wheel_errors,
                mod_slot_48_errors=report.mod_slot_48_errors,
                model_hashes=report.model_hashes,
                datafile_errors=report.datafile_errors,
                missing_dlc=report.missing_dlc,
                duplicate_weapon_errors=report.duplicate_weapon_errors,
                category_asset_errors=report.category_asset_errors,
                skipped_gen9_dlc=report.skipped_gen9_dlc,
                backup_path=backup_path,
                repaired=True,
                dry_run=dry_run,
            )
        )
    return reports


def latest_repair_time(compatdata: Path, gta_path: Path | None = None) -> float | None:
    candidates: list[Path] = []
    roaming = compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "majestic-launcher"
    candidates.extend(roaming.glob("Multiplayer.repair-backup-*"))
    if gta_path:
        candidates.extend(gta_path.glob("*.repair-backup-*"))
        candidates.extend((gta_path / "update" / "x64" / "dlcpacks").glob("*.repair-backup-*"))
    times = [path.stat().st_mtime for path in candidates if path.exists()]
    return max(times) if times else None


def repair_gta_conflicts(
    gta_path: Path,
    reports: list[MultiplayerRepairReport],
    *,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> list[MultiplayerRepairReport]:
    if not any(_has_gta_data_conflict(report) for report in reports):
        return reports
    gta_root_backup = _backup_path(gta_path / "majestic-root-injected")
    gen9_backup = _backup_path(gta_path / "update" / "x64" / "dlcpacks" / "gen9-dlc")
    moved_root = _archive_gta_root_files(gta_path, gta_root_backup, dry_run=dry_run, logger=logger)
    moved_gen9 = _archive_gen9_dlc(gta_path, gen9_backup, dry_run=dry_run, logger=logger)
    if not moved_root and not moved_gen9:
        return reports
    next_reports: list[MultiplayerRepairReport] = []
    for report in reports:
        next_reports.append(
            MultiplayerRepairReport(
                multiplayer_path=report.multiplayer_path,
                analyzed_logs=report.analyzed_logs,
                invalid_wheel_errors=report.invalid_wheel_errors,
                mod_slot_48_errors=report.mod_slot_48_errors,
                model_hashes=report.model_hashes,
                datafile_errors=report.datafile_errors,
                missing_dlc=report.missing_dlc,
                duplicate_weapon_errors=report.duplicate_weapon_errors,
                category_asset_errors=report.category_asset_errors,
                skipped_gen9_dlc=report.skipped_gen9_dlc,
                backup_path=report.backup_path,
                gta_root_backup_path=gta_root_backup if moved_root else None,
                gen9_backup_path=gen9_backup if moved_gen9 else None,
                repaired=report.repaired or moved_root or moved_gen9,
                dry_run=dry_run,
            )
        )
    return next_reports


def _has_gta_data_conflict(report: MultiplayerRepairReport) -> bool:
    return report.datafile_errors > 0 or report.category_asset_errors > 0 or report.duplicate_weapon_errors > 0 or bool(report.skipped_gen9_dlc)


def _archive_gta_root_files(gta_path: Path, backup_dir: Path, *, dry_run: bool, logger: logging.Logger | None) -> bool:
    candidates = [gta_path / name for name in MAJESTIC_GTA_ROOT_FILES if (gta_path / name).exists()]
    if not candidates:
        return False
    if logger:
        logger.warning("Archiving stale Majestic GTA root injected files to %s", backup_dir)
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for path in candidates:
            shutil.move(str(path), str(backup_dir / path.name))
    return True


def _archive_gen9_dlc(gta_path: Path, backup_dir: Path, *, dry_run: bool, logger: logging.Logger | None) -> bool:
    dlcpacks = gta_path / "update" / "x64" / "dlcpacks"
    candidates = sorted(path for path in dlcpacks.glob("*") if path.is_dir() and "g9ec" in path.name.lower())
    if not candidates:
        return False
    if logger:
        logger.warning("Archiving GTA Gen9/Enhanced DLC folders to %s", backup_dir)
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for path in candidates:
            shutil.move(str(path), str(backup_dir / path.name))
    return True


def _backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.repair-backup-{stamp}")
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.repair-backup-{stamp}-{index}")
        index += 1
    return candidate
