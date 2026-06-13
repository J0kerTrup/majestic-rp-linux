from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tarfile
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import Popen

LOG_FILES = ("steam.log", "proton.log", "wine.log", "launcher.log", "game.log", "system.log", "journal.log", "dxvk.log", "vulkan.log")
MAX_RUN_LOGS = 30


@dataclass(slots=True)
class DebugLogSession:
    root: Path
    run_dir: Path
    started_at: datetime
    app_id: str = "271590"
    proton_log_roots: list[Path] | None = None

    def path(self, name: str) -> Path:
        return self.run_dir / name


def start_debug_log_session(*, logger: logging.Logger | None = None) -> DebugLogSession:
    root = Path("logs").resolve()
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    run_dir = root / now.strftime("%Y-%m-%d_%H-%M-%S")
    suffix = 1
    while run_dir.exists():
        run_dir = root / f"{now.strftime('%Y-%m-%d_%H-%M-%S')}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    for name in LOG_FILES:
        _append(run_dir / name, f"# {name} created {now.isoformat(timespec='seconds')}\n")
    if logger:
        logger.info("Debug log session: %s", run_dir)
    return DebugLogSession(root, run_dir, now)


def prepare_debug_environment(env: dict[str, str], session: DebugLogSession) -> None:
    env["PROTON_LOG"] = "1"
    env["DXVK_LOG_LEVEL"] = "info"
    env["DXVK_LOG_PATH"] = str(session.run_dir)
    env["WINEDEBUG"] = _merge_winedebug(env.get("WINEDEBUG", ""), "+timestamp,+seh,+pid")


def append_system_event(session: DebugLogSession, message: str) -> None:
    _append(session.path("system.log"), f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")


def collect_pre_run_diagnostics(session: DebugLogSession, env: dict[str, str], *, logger: logging.Logger | None = None) -> None:
    for title, command in (("uname -a", ["uname", "-a"]), ("cat /etc/os-release", ["cat", "/etc/os-release"]), ("lspci", ["lspci"]), ("vulkaninfo --summary", ["vulkaninfo", "--summary"]), ("glxinfo -B", ["glxinfo", "-B"]), ("nvidia-smi", ["nvidia-smi"])):
        _run_to_file(session.path("system-info.log"), command, title=title, env=env, append=True, logger=logger)
    _append(session.path("system-info.log"), "\n\n===== env =====\n")
    for key, value in sorted(env.items()):
        _append(session.path("system-info.log"), f"{key}={value}\n")
    _run_to_file(session.path("processes.log"), ["ps", "aux"], title="ps aux", env=env, logger=logger)
    _run_to_file(session.path("vulkan.log"), ["vulkaninfo", "--summary"], title="vulkaninfo --summary", env=env, logger=logger)


def start_process_log_capture(process: Popen, session: DebugLogSession) -> threading.Thread | None:
    if process.stdout is None:
        return None
    targets = [session.path(name) for name in ("steam.log", "proton.log", "wine.log", "launcher.log", "game.log")]

    def worker() -> None:
        handles = [path.open("a", encoding="utf-8", errors="ignore") for path in targets]
        try:
            for line in process.stdout:
                for handle in handles:
                    handle.write(line)
                    handle.flush()
                sys.stdout.write(line)
                sys.stdout.flush()
        finally:
            for handle in handles:
                handle.close()

    thread = threading.Thread(target=worker, name="majestic-debug-log-capture", daemon=True)
    thread.start()
    return thread


def collect_post_run_diagnostics(session: DebugLogSession, env: dict[str, str], *, logger: logging.Logger | None = None) -> None:
    for title, command in (("journalctl --user -b", ["journalctl", "--user", "-b"]), ("journalctl -b", ["journalctl", "-b"]), ("coredumpctl list", ["coredumpctl", "list"])):
        _run_to_file(session.path("journal.log"), command, title=title, env=env, timeout=30, append=True, logger=logger)
    _run_to_file(session.path("processes.log"), ["ps", "aux"], title="ps aux after exit", env=env, append=True, logger=logger)
    copy_proton_log(session, logger=logger)
    collect_dxvk_logs(session, logger=logger)


def write_crash_log(session: DebugLogSession, *, code: int | None = None, signal_number: int | None = None, reason: str = "") -> None:
    _append(session.path("crash.log"), f"timestamp={datetime.now().isoformat(timespec='seconds')}\nreturn_code={code if code is not None else '-'}\nsignal={signal_number if signal_number is not None else '-'}\nreason={reason or '-'}\n")


def copy_proton_log(session: DebugLogSession, *, logger: logging.Logger | None = None) -> None:
    copied = False
    for root in list(dict.fromkeys([*(session.proton_log_roots or []), Path.cwd(), Path.home()])):
        source = root / f"steam-{session.app_id}.log"
        if source.exists():
            shutil.copy2(source, session.run_dir / source.name)
            _append(session.path("proton.log"), source.read_text(encoding="utf-8", errors="ignore"))
            copied = True
    if not copied:
        _append(session.path("proton.log"), "\nNo steam-271590.log was found after Proton exit.\n")


def collect_dxvk_logs(session: DebugLogSession, *, logger: logging.Logger | None = None) -> None:
    matched = [path for path in sorted(session.run_dir.glob("*.log")) if _looks_like_dxvk_log(path)]
    if not matched:
        _append(session.path("dxvk.log"), "\nNo separate DXVK log files were found in DXVK_LOG_PATH.\n")
        return
    for path in matched:
        _append(session.path("dxvk.log"), f"\n===== {path.name} =====\n{path.read_text(encoding='utf-8', errors='ignore')}")


def archive_and_rotate_logs(session: DebugLogSession, *, logger: logging.Logger | None = None) -> Path | None:
    archive = session.root / f"{session.run_dir.name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(session.run_dir, arcname=session.run_dir.name)
    rotate_logs(session.root, logger=logger)
    return archive


def rotate_logs(root: Path, keep: int = MAX_RUN_LOGS, *, logger: logging.Logger | None = None) -> None:
    runs = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)
    for old in runs[keep:]:
        shutil.rmtree(old, ignore_errors=True)
        archive = root / f"{old.name}.tar.gz"
        if archive.exists():
            archive.unlink()


def _run_to_file(path: Path, command: list[str], *, title: str, env: dict[str, str], timeout: int = 15, append: bool = False, logger: logging.Logger | None = None) -> None:
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", errors="ignore") as handle:
        handle.write(f"\n===== {title} =====\n")
        if shutil.which(command[0]) is None:
            handle.write(f"missing utility: {command[0]}\n")
            return
        try:
            result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False, env=env)
            handle.write(result.stdout or "")
            handle.write(f"\nexit_code={result.returncode}\n")
        except subprocess.TimeoutExpired:
            handle.write(f"command timed out after {timeout}s: {' '.join(command)}\n")


def _merge_winedebug(current: str, required: str) -> str:
    parts = [part for part in current.split(",") if part]
    for item in required.split(","):
        if item and item not in parts:
            parts.append(item)
    return ",".join(parts)


def _looks_like_dxvk_log(path: Path) -> bool:
    name = path.name.lower()
    return name not in set(LOG_FILES) | {"system-info.log", "processes.log", "crash.log"} and not name.startswith("steam-") and any(token in name for token in ("dxgi", "d3d9", "d3d10", "d3d11", "d3d12", "dxvk"))


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(text)
