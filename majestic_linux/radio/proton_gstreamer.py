from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .checks import CheckResult


def proton_gstreamer_stack(proton: Path | None, library_paths: list[Path] | None = None, gst_plugin_path: str = "") -> CheckResult:
    values: dict[str, str] = {}
    warnings: list[str] = []
    if proton is None:
        return CheckResult("Proton GStreamer", {"path": ""}, ["Proton path is unknown."])
    values["runtime_GST_PLUGIN_PATH_1_0"] = gst_plugin_path
    if gst_plugin_path:
        warnings.append("Host GStreamer plugin path is set; this can break Proton because plugin/core ABIs may differ.")
    root = proton.parent / "files" / "lib"
    for arch in ("x86_64-linux-gnu", "i386-linux-gnu"):
        plugin = root / arch / "gstreamer-1.0" / "libgstlibav.so"
        values[f"{arch}:libgstlibav"] = str(plugin) if plugin.exists() else "missing"
        if plugin.exists():
            ldd = _ldd(plugin, library_paths or [])
            values[f"{arch}:ldd"] = ldd
            if "not found" in ldd:
                warnings.append(f"{arch} libgstlibav missing: {', '.join(_missing_libs(ldd))}")
            if "wrong ELF class" in ldd or "not a dynamic executable" in ldd:
                warnings.append(f"{arch} libgstlibav cannot be inspected by host ldd cleanly.")
    bz2 = _find_libbz2(root, library_paths or [])
    values["bundled_or_host_libbz2"] = bz2 or "not found"
    if not bz2:
        warnings.append("libbz2.so.1.0 was not found near Proton or common host library paths.")
    return CheckResult("Proton GStreamer", values, warnings)


def _ldd(path: Path, library_paths: list[Path]) -> str:
    if shutil.which("ldd") is None:
        return "missing: ldd"
    env = None
    if library_paths:
        env = {"LD_LIBRARY_PATH": ":".join(str(path) for path in library_paths)}
    try:
        result = subprocess.run(["ldd", str(path)], text=True, capture_output=True, timeout=5, check=False, env=env)
    except Exception as exc:  # noqa: BLE001 - diagnostics should not crash
        return f"error: {exc}"
    return (result.stdout + result.stderr).strip().replace("\n", " | ")[:1200]


def _find_libbz2(root: Path, library_paths: list[Path]) -> str:
    candidates = [
        *root.glob("**/libbz2.so.1.0"),
        *(path / "libbz2.so.1.0" for path in library_paths if (path / "libbz2.so.1.0").exists()),
        *Path("/usr/lib64").glob("libbz2.so.1.0"),
        *Path("/usr/lib").glob("libbz2.so.1.0"),
        *Path("/usr/lib/x86_64-linux-gnu").glob("libbz2.so.1.0"),
        *Path("/usr/lib/i386-linux-gnu").glob("libbz2.so.1.0"),
    ]
    return ", ".join(str(path) for path in candidates[:8])


def _missing_libs(ldd: str) -> list[str]:
    missing = []
    for part in ldd.split("|"):
        if "=> not found" in part:
            missing.append(part.split("=>", 1)[0].strip())
    return missing or ["unknown"]
