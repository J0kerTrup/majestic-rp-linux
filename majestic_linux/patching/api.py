from __future__ import annotations

import logging
from pathlib import Path

from ..core.errors import PatchError
from .common import (
    DIRECT_MARKER,
    INDEX_COMPAT_MARKER,
    LEGACY_ARRAY_RE,
    MARKER,
    SOURCE_MARKER,
    PatchReport,
    PatchStatus,
    fix_legacy_arrays,
    read_text,
    validate_text,
)
from .index import patch_index
from .source_find import patch_source_find_gta, patch_source_revalidate_gta
from .source_runtime import patch_source_game, patch_source_patcher
from .targets import cleanup, extract_asar, find_js_files, repack_asar, resolve_targets
from .worker import patch_worker, worker_adapter


def patch_text(text: str) -> tuple[str, bool]:
    status = PatchStatus(Path("<memory>"))
    next_text = fix_legacy_arrays(text, status)
    if next_text != text and MARKER not in next_text and INDEX_COMPAT_MARKER not in next_text:
        next_text = f"// {MARKER}\n{next_text}"
    validate_text(next_text, Path("<memory>"))
    return next_text, next_text != text


def patch_source_tree(app_root: Path, *, dry_run: bool, permissions: str) -> list[PatchStatus]:
    return [
        patch_source_find_gta(app_root / "src" / "electron" / "main" / "utils" / "findGTA.js", dry_run=dry_run),
        patch_source_revalidate_gta(app_root / "src" / "electron" / "main" / "utils" / "revalidateGTA.js", dry_run=dry_run),
        patch_source_patcher(app_root / "src" / "electron" / "main" / "patcher.js", dry_run=dry_run, permissions=permissions),
        patch_source_game(app_root / "src" / "electron" / "main" / "modules" / "game.js", dry_run=dry_run),
    ]


def patch_js_tree(
    root: Path,
    *,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
    permissions: str = "1",
) -> PatchReport:
    targets = resolve_targets(root)
    statuses: list[PatchStatus] = []
    if logger:
        logger.info("Resolved JS patch target mode=%s app_root=%s", targets.mode, targets.app_root)
    try:
        if targets.mode == "source":
            statuses.extend(patch_source_tree(targets.app_root, dry_run=dry_run, permissions=permissions))
        else:
            extract_asar(targets, dry_run=dry_run, logger=logger)
            index = targets.app_root / "dist" / "electron" / "main" / "index.js"
            worker = targets.unpacked_root / "dist" / "electron" / "main" / "gamePatcher.js"
            statuses.append(patch_index(index, dry_run=dry_run, permissions=permissions))
            statuses.append(patch_worker(worker, dry_run=dry_run, permissions=permissions))
            repack_asar(targets, dry_run=dry_run, logger=logger)
    finally:
        cleanup(targets, logger)
    failures = [error for status in statuses for error in status.errors]
    if failures:
        raise PatchError("; ".join(failures))
    if logger:
        for status in statuses:
            logger.debug("Patch status file=%s changed=%s details=%s", status.file, status.changed, status.details)
    return PatchReport(targets.mode, statuses)


def _state_for_files(files: list[Path]) -> dict[str, object]:
    legacy = [str(file) for file in files if LEGACY_ARRAY_RE.search(read_text(file))]
    markers = {
        "source": any(SOURCE_MARKER in read_text(file) for file in files),
        "index_compat": any(INDEX_COMPAT_MARKER in read_text(file) for file in files),
        "direct": any(DIRECT_MARKER in read_text(file) for file in files),
        "worker": any(MARKER in read_text(file) for file in files),
    }
    steam_ready = [str(file) for file in files if all(token in read_text(file) for token in ("steam", "rgl", "egs"))]
    return {"files": len(files), "legacy_without_steam": legacy, "steam_ready": steam_ready, "markers": markers}


def patch_state(root: Path) -> dict[str, object]:
    try:
        targets = resolve_targets(root)
    except PatchError:
        files = find_js_files(root)
        return {"mode": "unknown", **_state_for_files(files)}
    try:
        sections: dict[str, object] = {}
        if targets.mode == "asar":
            if targets.asar_path and targets.asar_path.exists():
                try:
                    extract_asar(targets, dry_run=False, logger=None)
                    sections["asar"] = _state_for_files(find_js_files(targets.app_root))
                except Exception as exc:  # noqa: BLE001 - diagnostic output should not crash doctor
                    sections["asar_error"] = str(exc)
            if targets.unpacked_root.exists():
                sections["unpacked"] = _state_for_files(find_js_files(targets.unpacked_root))
            return {"mode": targets.mode, **sections}
        return {"mode": targets.mode, **_state_for_files(find_js_files(targets.app_root))}
    finally:
        cleanup(targets)
