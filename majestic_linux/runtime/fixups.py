from __future__ import annotations

import logging
from pathlib import Path


def prepare_proton_runtime_fixups(proton_path: Path, *, dry_run: bool, logger: logging.Logger | None = None) -> list[Path]:
    paths: list[Path] = []
    proton_lib = proton_path.parent / "files" / "lib"
    if _needs_libbz2_alias(proton_lib):
        paths.extend(_prepare_libbz2_aliases(dry_run=dry_run, logger=logger))
    return paths


def apply_library_path(env: dict[str, str], paths: list[Path]) -> None:
    if not paths:
        return
    existing = env.get("LD_LIBRARY_PATH", "")
    prefix = ":".join(str(path.resolve()) for path in paths)
    env["LD_LIBRARY_PATH"] = prefix + (":" + existing if existing else "")


def _needs_libbz2_alias(proton_lib: Path) -> bool:
    for arch in ("x86_64-linux-gnu", "i386-linux-gnu"):
        plugin = proton_lib / arch / "gstreamer-1.0" / "libgstlibav.so"
        if plugin.exists():
            return True
    return False


def _prepare_libbz2_aliases(*, dry_run: bool, logger: logging.Logger | None) -> list[Path]:
    mappings = [
        ("x86_64", ("/usr/lib64/libbz2.so.1", "/usr/lib/x86_64-linux-gnu/libbz2.so.1", "/lib64/libbz2.so.1")),
        ("i386", ("/usr/lib/libbz2.so.1", "/usr/lib/i386-linux-gnu/libbz2.so.1", "/lib/libbz2.so.1")),
    ]
    roots: list[Path] = []
    for arch, candidates in mappings:
        source = next((Path(item) for item in candidates if Path(item).exists()), None)
        if source is None:
            if logger:
                logger.warning("Cannot prepare libbz2.so.1.0 alias for %s: source libbz2.so.1 not found", arch)
            continue
        root = (Path.cwd() / "cache" / "proton-libs" / arch).resolve()
        target = root / "libbz2.so.1.0"
        roots.append(root)
        needs_update = dry_run or not (target.exists() or target.is_symlink()) or target.resolve() != source.resolve()
        if logger and needs_update:
            logger.info("Preparing Proton lib alias %s -> %s", target, source)
        if dry_run:
            continue
        root.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            if target.resolve() == source.resolve():
                continue
            target.unlink()
        target.symlink_to(source)
    return roots
