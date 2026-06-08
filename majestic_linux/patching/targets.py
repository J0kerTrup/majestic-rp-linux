from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..core.errors import PatchError
from .common import PatchTargets

def resolve_targets(input_path: Path) -> PatchTargets:
    root = input_path.expanduser().resolve()
    app_asar_from_root = root / "app.asar"
    app_asar_from_resources = root / "resources" / "app.asar"
    sibling_app_asar = root.parent / "app.asar"
    extracted_index = root / "dist" / "electron" / "main" / "index.js"
    source_files = [
        root / "src" / "electron" / "main" / "utils" / "findGTA.js",
        root / "src" / "electron" / "main" / "utils" / "revalidateGTA.js",
        root / "src" / "electron" / "main" / "patcher.js",
        root / "src" / "electron" / "main" / "modules" / "game.js",
    ]
    if all(path.is_file() for path in source_files):
        return PatchTargets("source", root, root.parent, None, root)
    if root.is_file() and root.name == "app.asar":
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, root.parent, root, root.parent / "app.asar.unpacked", temp)
    if root.is_dir() and app_asar_from_root.is_file():
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, root, app_asar_from_root, root / "app.asar.unpacked", temp)
    if root.is_dir() and app_asar_from_resources.is_file():
        resources = root / "resources"
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, resources, app_asar_from_resources, resources / "app.asar.unpacked", temp)
    if root.is_dir() and root.name == "app.asar.unpacked" and sibling_app_asar.is_file():
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, root.parent, sibling_app_asar, root, temp)
    if extracted_index.is_file():
        return PatchTargets("extracted", root, root.parent, None, root)
    raise PatchError(
        "Could not locate Majestic app files. Pass resources/, resources/app.asar, "
        "resources/app.asar.unpacked, extracted app root, or recovered source root."
    )


def run_command(command: list[str], *, dry_run: bool, logger: logging.Logger | None) -> None:
    if dry_run:
        if logger:
            logger.info("Dry-run: command skipped: %s", " ".join(command))
        return
    if logger:
        logger.info("Executing: %s", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise PatchError(f"Command failed with code {result.returncode}: {' '.join(command)}")


def extract_asar(targets: PatchTargets, *, dry_run: bool, logger: logging.Logger | None) -> None:
    if targets.mode != "asar" or targets.asar_path is None:
        return
    asar = os.environ.get("ASAR_BIN", "asar")
    run_command([asar, "extract", str(targets.asar_path), str(targets.app_root)], dry_run=False, logger=logger)


def repack_asar(targets: PatchTargets, *, dry_run: bool, logger: logging.Logger | None) -> None:
    if targets.mode != "asar" or targets.asar_path is None:
        return
    if not dry_run:
        backup = targets.asar_path.with_suffix(targets.asar_path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(targets.asar_path, backup)
    asar = os.environ.get("ASAR_BIN", "asar")
    run_command([asar, "pack", str(targets.app_root), str(targets.asar_path)], dry_run=dry_run, logger=logger)


def cleanup(targets: PatchTargets, logger: logging.Logger | None = None) -> None:
    if targets.cleanup_root and targets.cleanup_root.exists():
        if logger:
            logger.debug("Removing temporary extraction directory %s", targets.cleanup_root)
        shutil.rmtree(targets.cleanup_root, ignore_errors=True)



def find_js_files(root: Path) -> list[Path]:
    root = root.expanduser()
    if root.is_file() and root.suffix.lower() == ".js":
        return [root]
    if not root.exists():
        return []
    ignored = {".git", "node_modules"}
    return sorted(path for path in root.rglob("*.js") if not any(part in ignored for part in path.parts))
