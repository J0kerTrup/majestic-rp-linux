from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from ..detection.paths import DetectionResult
from ..runtime.proton import build_proton_command
from ..runtime.fixups import prepare_proton_runtime_fixups
from ..runtime.wine import prepare_wine_mapping
from .checks import CheckResult, audio_stack, dll_override_status, gstreamer_stack, proton_stack, system_info, wine_stack
from .log_analyzer import Cause, LogAnalysis, analyze_logs
from .proton_gstreamer import proton_gstreamer_stack


@dataclass(slots=True)
class RadioReport:
    checks: list[CheckResult]
    logs: LogAnalysis
    report_path: Path


def build_radio_report(config: RunnerConfig, result: DetectionResult, *, dry_run: bool = True) -> RadioReport:
    prefix = result.compatdata_path / "pfx" if result.compatdata_path else None
    if result.proton_path:
        config.runtime_library_paths = prepare_proton_runtime_fixups(result.proton_path, dry_run=False)
    env = _proton_env(config, result)
    logs = analyze_logs(_log_candidates(result, prefix)) if config.radio_collect_logs else analyze_logs([])
    checks = [system_info()]
    if config.radio_analyze_audio_stack:
        checks.append(audio_stack())
    if config.radio_analyze_wine:
        checks.extend([wine_stack(prefix, result.compatdata_path), dll_override_status(prefix)])
    if config.radio_analyze_proton:
        checks.append(proton_stack(result.proton_path, env))
    if config.radio_analyze_codecs:
        checks.extend([gstreamer_stack(), proton_gstreamer_stack(result.proton_path, config.runtime_library_paths or [], env.get("GST_PLUGIN_PATH_1_0", ""))])
    _add_check_causes(logs, checks)
    report_path = write_report(config, result, checks, logs, dry_run=dry_run)
    return RadioReport(checks, logs, report_path)


def radio_safe_env(env: dict[str, str]) -> dict[str, str]:
    safe = env.copy()
    safe.setdefault("PROTON_LOG", "1")
    safe.setdefault("WINEDEBUG", "+timestamp,+pid,+tid,+seh,+loaddll")
    safe.setdefault("GST_DEBUG", "2")
    safe.setdefault("DXVK_LOG_LEVEL", "info")
    safe.setdefault("VKD3D_DEBUG", "warn")
    safe["MAJESTIC_RADIO_SAFE"] = "1"
    return safe


def write_report(config: RunnerConfig, result: DetectionResult, checks: list[CheckResult], logs: LogAnalysis, *, dry_run: bool) -> Path:
    report_dir = Path.home() / ".local" / "share" / "majestic-runner" / "reports"
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = report_dir / f"radio-report-{stamp}.txt"
    if dry_run:
        return path
    report_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(format_report(config, result, checks, logs), encoding="utf-8")
    return path


def format_report(config: RunnerConfig, result: DetectionResult, checks: list[CheckResult], logs: LogAnalysis) -> str:
    lines = ["Majestic Runner G Radio Diagnostics", "=" * 36, ""]
    lines.extend([
        f"config: {config.config_path}",
        f"platform: {result.selected_platform}",
        f"winegstreamer_disabled: {config.radio_disable_winegstreamer}",
        f"steam_root: {result.steam_root or '-'}",
        f"proton: {result.proton_path or '-'}",
        f"compatdata: {result.compatdata_path or '-'}",
        f"gta_path: {result.gta_path or '-'}",
        "",
    ])
    for check in checks:
        lines.append(f"[{check.name}]")
        lines.extend(f"{key}: {value}" for key, value in check.values.items())
        lines.extend(f"warning: {warning}" for warning in check.warnings)
        lines.append("")
    lines.append("[Log analysis]")
    lines.append(f"files: {len(logs.files)}")
    lines.append(f"hits: {len(logs.hits)}")
    for cause in logs.causes:
        lines.append(f"possible cause: {cause.title} ({cause.confidence}%) evidence={', '.join(cause.evidence)}")
    for hit in logs.hits[:80]:
        lines.append(f"{hit.file}:{hit.line}: [{hit.keyword}] {hit.text}")
    if logs.urls:
        lines.append("")
        lines.append("[Network streams found in logs]")
        lines.extend(logs.urls)
    lines.extend(["", "[Recommendations]", *_recommendations(checks, logs)])
    return "\n".join(lines) + "\n"


def format_summary(report: RadioReport) -> str:
    lines = ["G Radio diagnostics summary", ""]
    lines.append(f"report: {report.report_path}")
    for check in report.checks:
        for warning in check.warnings:
            lines.append(f"warning: {check.name}: {warning}")
    lines.append(f"analyzed log files: {len(report.logs.files)}")
    lines.append(f"keyword hits: {len(report.logs.hits)}")
    if report.logs.causes:
        for index, cause in enumerate(report.logs.causes[:5], 1):
            lines.append(f"possible cause #{index}: {cause.title} ({cause.confidence}%)")
            lines.append(f"  evidence: {', '.join(cause.evidence)}")
    else:
        lines.append("possible causes: no strong match in available logs")
    if report.logs.urls:
        lines.append(f"network URLs found in logs: {len(report.logs.urls)}")
    return "\n".join(lines)


def _recommendations(checks: list[CheckResult], logs: LogAnalysis) -> list[str]:
    recs = []
    text = " ".join(c.title for c in logs.causes).lower()
    if "cef" in text:
        recs.append("Test with DISABLE_CEF_GPU=1 and collect Chromium/CEF logs.")
    if "codec" in text or "gstreamer" in text:
        recs.append("Check distro multimedia/GStreamer codec packages, including 32-bit compatibility libraries.")
    for check in checks:
        joined = " ".join([*check.values.values(), *check.warnings]).lower()
        if check.name == "Proton GStreamer" and check.values.get("bundled_or_host_libbz2") == "not found":
            recs.append("Install/restore the distro package that provides libbz2.so.1.0 for Proton GStreamer libav.")
        if check.name == "Proton GStreamer" and any(name in joined for name in ("libavcodec.so.58", "libavformat.so.58", "libavfilter.so.7", "libavutil.so.56")):
            recs.append("Install compatible FFmpeg/libav runtime libraries for Proton GStreamer, or test a Proton/GE build that bundles matching libav libraries.")
    if "override" in text:
        recs.append("Review Wine DLL overrides for winegstreamer, mfplat, quartz, xaudio, and xact.")
    if not recs:
        recs.append("No single cause was obvious; attach this report and recent launcher/game logs to a bug report.")
    return recs


def _add_check_causes(logs: LogAnalysis, checks: list[CheckResult]) -> None:
    text = " ".join(" ".join([check.name, *check.values.values(), *check.warnings]) for check in checks).lower()
    if "libgstlibav" in text and ("not found" in text or "libbz2.so.1.0" in text):
        evidence = [name for name in ("libavfilter.so.7", "libavformat.so.58", "libavcodec.so.58", "libavutil.so.56") if name in text]
        if "bundled_or_host_libbz2: not found" in text:
            evidence.append("libbz2.so.1.0")
        cause = Cause("Proton GStreamer dependency failure", 88, ["libgstlibav", *(evidence or ["missing shared libraries"])])
        logs.causes = _dedupe_causes([cause, *logs.causes])


def _dedupe_causes(causes: list[Cause]) -> list[Cause]:
    merged: dict[str, Cause] = {}
    for cause in causes:
        current = merged.get(cause.title)
        if current is None or cause.confidence > current.confidence:
            merged[cause.title] = cause
        elif current and cause.confidence == current.confidence:
            current.evidence = sorted(set(current.evidence + cause.evidence))
    return sorted(merged.values(), key=lambda item: item.confidence, reverse=True)


def _proton_env(config: RunnerConfig, result: DetectionResult) -> dict[str, str]:
    if not all((result.proton_path, result.compatdata_path, result.gta_path, result.majestic_exe)):
        return {}
    mapping = prepare_wine_mapping(result.compatdata_path, result.gta_path, config.gta_wine_drive, dry_run=True)
    command = build_proton_command(config, result.proton_path, result.compatdata_path, result.steam_root, result.majestic_exe, result.selected_platform, mapping)
    return command.env


def _log_candidates(result: DetectionResult, prefix: Path | None) -> list[Path]:
    roots = [Path("logs")]
    if prefix:
        roots.extend([
            prefix / "drive_c" / "users" / "steamuser" / "AppData" / "Local",
            prefix / "drive_c" / "users" / "steamuser" / "Documents",
        ])
    patterns = ("*.log", "*.txt", "*.dmp", "*.crash")
    files = []
    for root in roots:
        if root.exists():
            files.extend(path for pattern in patterns for path in root.rglob(pattern) if ".majestic-proton-bak" not in str(path))
    if result.gta_path and result.gta_path.exists():
        files.extend(path for pattern in patterns for path in result.gta_path.glob(pattern))
    return sorted(files, key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)[:80]
