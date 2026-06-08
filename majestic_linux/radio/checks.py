from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CheckResult:
    name: str
    values: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def system_info() -> CheckResult:
    values = {"kernel": platform.platform(), "python": platform.python_version(), **_os_release()}
    return CheckResult("System", values)


def audio_stack() -> CheckResult:
    procs = _process_names()
    values = {
        "pipewire": _present("pipewire", procs),
        "wireplumber": _present("wireplumber", procs),
        "pulseaudio": _present("pulseaudio", procs),
        "alsa_devices": _cmd(["aplay", "-l"]),
        "pactl": _cmd(["pactl", "info"]),
        "pw_cli": _cmd(["pw-cli", "info", "0"]),
    }
    warnings = []
    if values["pipewire"] == "yes" and values["pulseaudio"] == "yes":
        warnings.append("PipeWire and PulseAudio processes are both present; verify compatibility layer is intentional.")
    if values["pactl"].startswith("missing"):
        warnings.append("pactl is missing; PulseAudio/PipeWire-Pulse diagnostics are limited.")
    return CheckResult("Audio stack", values, warnings)


def wine_stack(prefix: Path | None, compatdata: Path | None) -> CheckResult:
    values = {
        "wine": _version("wine"),
        "wine64": _version("wine64"),
        "wineserver": _version("wineserver"),
        "WINEPREFIX": str(prefix or ""),
        "STEAM_COMPAT_DATA_PATH": str(compatdata or ""),
        "dll_overrides": _registry_overrides(prefix),
    }
    warnings = []
    if values["wineserver"].startswith("missing"):
        warnings.append("wineserver is missing from PATH; Proton may still have its bundled wineserver.")
    return CheckResult("Wine", values, warnings)


def proton_stack(proton: Path | None, env: dict[str, str]) -> CheckResult:
    values = {"path": str(proton or ""), "kind": _proton_kind(proton), "version": _proton_version(proton)}
    for key in ("PROTON_LOG", "WINEDEBUG", "GST_DEBUG", "DISABLE_CEF_GPU", "MAJESTIC_PLATFORM"):
        values[key] = env.get(key, "")
    return CheckResult("Proton", values)


def gstreamer_stack() -> CheckResult:
    values = {
        "gst-inspect-1.0": _version("gst-inspect-1.0"),
        "plugins": _cmd(["gst-inspect-1.0"]),
        "lib64": _find_libs(("/usr/lib64", "/usr/lib/x86_64-linux-gnu", "/run/current-system/sw/lib"), "libgst"),
        "lib32": _find_libs(("/usr/lib", "/usr/lib32", "/usr/lib/i386-linux-gnu"), "libgst"),
    }
    warnings = []
    if values["gst-inspect-1.0"].startswith("missing"):
        warnings.append("GStreamer tools are missing from PATH; codec diagnostics are limited.")
    return CheckResult("GStreamer", values, warnings)


def dll_override_status(prefix: Path | None) -> CheckResult:
    overrides = _registry_overrides(prefix).lower()
    values = {}
    for name in ("winegstreamer", "xaudio", "xact", "mfplat", "quartz"):
        values[name] = "mentioned" if name in overrides else "not found"
    return CheckResult("DLL overrides", values)


def _cmd(command: list[str], timeout: int = 3) -> str:
    if shutil.which(command[0]) is None:
        return f"missing: {command[0]}"
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    except Exception as exc:  # noqa: BLE001 - diagnostics should not crash
        return f"error: {exc}"
    return (result.stdout or result.stderr).strip().replace("\n", " | ")[:800]


def _version(binary: str) -> str:
    return _cmd([binary, "--version"])


def _process_names() -> set[str]:
    names = set()
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit():
            try:
                names.add((proc / "comm").read_text(encoding="utf-8", errors="ignore").strip().lower())
            except OSError:
                pass
    return names


def _present(name: str, procs: set[str]) -> str:
    return "yes" if any(name in proc for proc in procs) else "no"


def _os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {"distribution": "unknown"}
    values = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.lower()] = value.strip('"')
    return {"distribution": values.get("pretty_name", values.get("id", "unknown"))}


def _registry_overrides(prefix: Path | None) -> str:
    if prefix is None:
        return ""
    chunks = []
    for name in ("user.reg", "system.reg"):
        path = prefix / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            chunks.extend(line for line in text.splitlines() if "DllOverrides" in line or "Software\\\\Wine\\\\DllOverrides" in line)
    return " | ".join(chunks)[:1200]


def _proton_kind(proton: Path | None) -> str:
    if proton is None:
        return "unknown"
    text = str(proton).lower()
    if "ge-proton" in text:
        return "GE-Proton"
    if "experimental" in text:
        return "Proton Experimental"
    return "Valve/Custom Proton"


def _proton_version(proton: Path | None) -> str:
    if proton is None:
        return ""
    version_file = proton.parent / "version"
    return version_file.read_text(encoding="utf-8", errors="ignore").strip()[:200] if version_file.exists() else ""


def _find_libs(roots: tuple[str, ...], prefix: str) -> str:
    hits = []
    for root in roots:
        base = Path(root)
        if base.exists():
            hits.extend(str(path) for path in list(base.glob(f"{prefix}*.so*"))[:8])
    return ", ".join(hits[:12]) or "not found"
