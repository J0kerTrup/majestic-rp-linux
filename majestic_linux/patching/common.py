from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import PatchError

MARKER = "MAJESTIC_PROTON_PATCH_V2"
INDEX_COMPAT_MARKER = "MAJESTIC_PROTON_INDEX_COMPAT_V6"
DIRECT_MARKER = "MAJESTIC_PROTON_DIRECT_PATCH_V4"
DIRECT_MARKER_V3 = "MAJESTIC_PROTON_DIRECT_PATCH_V3"
DIRECT_MARKER_V2 = "MAJESTIC_PROTON_DIRECT_PATCH_V2"
DIRECT_MARKER_V1 = "MAJESTIC_PROTON_DIRECT_PATCH_V1"
SOURCE_MARKER = "MAJESTIC_PROTON_SOURCE_PATCH_V1"
PY_BACKUP_SUFFIX = ".majestic-python-bak"
FULL_ARRAY = '["steam","rgl","egs"]'
LEGACY_ARRAY_RE = re.compile(r"\[\s*(['\"])rgl\1\s*,\s*(['\"])egs\2\s*\]")


@dataclass(slots=True)
class PatchTargets:
    mode: str
    app_root: Path
    resources_dir: Path
    asar_path: Path | None
    unpacked_root: Path
    cleanup_root: Path | None = None


@dataclass(slots=True)
class PatchStatus:
    file: Path
    changed: bool = False
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PatchReport:
    mode: str
    statuses: list[PatchStatus]

    @property
    def changed(self) -> bool:
        return any(status.changed for status in self.statuses)


def permissions(values: str) -> list[int]:
    parsed: list[int] = []
    for item in values.split(","):
        try:
            number = int(item.strip())
        except ValueError:
            continue
        if 0 <= number <= 254:
            parsed.append(number)
    return parsed or [1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str, *, dry_run: bool, status: PatchStatus) -> None:
    status.changed = True
    if dry_run:
        status.details.append("dry-run write skipped")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + PY_BACKUP_SUFFIX)
        if not backup.exists():
            shutil.copy2(path, backup)
    path.write_text(text, encoding="utf-8")


def fix_legacy_arrays(src: str, status: PatchStatus) -> str:
    next_src, count = LEGACY_ARRAY_RE.subn(FULL_ARRAY, src)
    if count:
        status.details.append(f"fixed legacy platform arrays: {count}")
    return next_src


def validate_text(text: str, file: Path) -> None:
    if LEGACY_ARRAY_RE.search(text):
        raise PatchError(f"{file}: legacy platform array still lacks steam")
    if '"rgl","egs"' in text and '"steam","rgl","egs"' not in text:
        raise PatchError(f"{file}: old rgl/egs array remains without steam")
