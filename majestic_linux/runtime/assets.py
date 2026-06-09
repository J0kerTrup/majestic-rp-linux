from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import PatchError
from ..patching.targets import cleanup, extract_asar, resolve_targets

FONT_EXTS = {".woff", ".woff2", ".ttf", ".otf", ".eot"}
ICON_EXTS = {".svg", ".ico", ".icns"}
STYLE_EXTS = {".css", ".html", ".js"}
URL_RE = re.compile(r"url\((['\"]?)([^)'\"\s]+)\1\)")


@dataclass(slots=True)
class AssetReport:
    roots: list[Path] = field(default_factory=list)
    fonts: list[Path] = field(default_factory=list)
    icons: list[Path] = field(default_factory=list)
    font_faces: list[Path] = field(default_factory=list)
    broken_urls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def inspect_launcher_assets(app_root: Path | None, logger: logging.Logger | None = None) -> AssetReport:
    report = AssetReport()
    if app_root is None:
        report.warnings.append("Majestic Launcher path is unknown; cannot inspect icon/font assets.")
        return report
    roots, cleanup_targets = _asset_roots(app_root, logger)
    report.roots.extend(roots)
    for root in roots:
        _scan_root(root, report)
    for target in cleanup_targets:
        cleanup(target, logger)
    if not report.fonts:
        report.warnings.append("No font files found; icon fonts may render as missing squares.")
    if not report.icons:
        report.warnings.append("No SVG/ICO icon assets found.")
    if report.font_faces and report.broken_urls:
        report.warnings.append("Some CSS url(...) references are broken after extraction/path relocation.")
    return report


def _asset_roots(app_root: Path, logger: logging.Logger | None) -> tuple[list[Path], list]:
    candidates = [app_root]
    if app_root.is_dir():
        candidates.extend([app_root / "resources", app_root / "resources" / "app.asar.unpacked"])
    roots: list[Path] = []
    cleanup_targets = []
    seen_asar: set[Path] = set()
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            targets = resolve_targets(candidate)
        except PatchError:
            if candidate.is_dir():
                roots.append(candidate)
            continue
        if targets.mode == "asar":
            if targets.asar_path and targets.asar_path.resolve() in seen_asar:
                continue
            if targets.asar_path:
                seen_asar.add(targets.asar_path.resolve())
            try:
                extract_asar(targets, dry_run=False, logger=logger)
                roots.append(targets.app_root)
                if targets.unpacked_root.exists():
                    roots.append(targets.unpacked_root)
                cleanup_targets.append(targets)
            except PatchError as exc:
                roots.append(targets.unpacked_root)
                if logger:
                    logger.warning("Cannot extract app.asar for asset inspection: %s", exc)
        else:
            roots.append(targets.app_root)
    return list(dict.fromkeys(root for root in roots if root.exists())), cleanup_targets


def _scan_root(root: Path, report: AssetReport) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in FONT_EXTS:
            report.fonts.append(path)
        if suffix in ICON_EXTS:
            report.icons.append(path)
        if suffix in STYLE_EXTS:
            _scan_text_asset(root, path, report)


def _scan_text_asset(root: Path, path: Path, report: AssetReport) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "@font-face" in text:
        report.font_faces.append(path)
    if path.suffix.lower() == ".js":
        return
    for match in URL_RE.finditer(text):
        ref = match.group(2).split("?", 1)[0].split("#", 1)[0]
        if not ref or ref.startswith(("#", "%23", "data:", "http:", "https:", "file:", "blob:")):
            continue
        target = _resolve_url(root, path, ref)
        if target is not None and not target.exists():
            report.broken_urls.append(f"{path}: {ref}")


def _resolve_url(root: Path, source: Path, ref: str) -> Path | None:
    if ref.startswith("/"):
        return root / ref.lstrip("/")
    if ref.startswith("..") or ref.startswith("."):
        return (source.parent / ref).resolve()
    return source.parent / ref
