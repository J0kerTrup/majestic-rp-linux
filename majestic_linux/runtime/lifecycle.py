from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ..core.config import RunnerConfig
from ..core.errors import CommandError
from .debug_logs import (
    append_system_event,
    archive_and_rotate_logs,
    collect_post_run_diagnostics,
    collect_pre_run_diagnostics,
    prepare_debug_environment,
    start_debug_log_session,
    start_process_log_capture,
    write_crash_log,
)

WATCH_NAMES = ("wine", "wine64", "wineserver", "proton", "Xalia", "Launcher.exe", "GTA5.exe", "PlayGTAV.exe", "GTAVLauncher.exe", "RockstarService.exe")


@dataclass(slots=True)
class PrefixProcess:
    pid: int
    name: str
    cmdline: str


def prefix_processes(prefix: Path, compatdata: Path | None = None) -> list[PrefixProcess]:
    needles = [str(prefix.resolve())]
    if compatdata:
        needles.append(str(compatdata.resolve()))
    found: list[PrefixProcess] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        item = _process_for_prefix(proc, needles)
        if item:
            found.append(item)
    return found


def shutdown_prefix(config: RunnerConfig, prefix: Path, compatdata: Path | None, logger: logging.Logger | None = None) -> None:
    if not config.kill_wine_on_exit:
        return
    if config.wait_wineserver:
        _run_wineserver(prefix, "-w", config.kill_timeout_seconds, logger)
    _run_wineserver(prefix, "-k", config.force_kill_timeout_seconds, logger)
    processes = prefix_processes(prefix, compatdata) if config.kill_only_current_prefix else []
    if not processes:
        if logger:
            logger.debug("No Wine/Proton processes found for prefix %s", prefix)
        return
    _signal_processes(processes, signal.SIGTERM, logger)
    _wait_gone([p.pid for p in processes], config.kill_timeout_seconds)
    remaining = [p for p in prefix_processes(prefix, compatdata) if p.pid in {old.pid for old in processes}]
    if remaining:
        _signal_processes(remaining, signal.SIGKILL, logger)
        _wait_gone([p.pid for p in remaining], config.force_kill_timeout_seconds)


def run_with_lifecycle(command, config: RunnerConfig, compatdata: Path, *, dry_run: bool, logger: logging.Logger | None = None) -> int:
    prefix = compatdata / "pfx"
    log_session = start_debug_log_session(logger=logger)
    log_session.proton_log_roots = [path for path in (command.cwd, Path.cwd()) if path is not None]
    prepare_debug_environment(command.env, log_session)
    append_system_event(log_session, f"compatdata={compatdata}")
    append_system_event(log_session, f"prefix={prefix}")
    append_system_event(log_session, f"cwd={command.cwd or Path.cwd()}")
    append_system_event(log_session, "argv=" + " ".join(command.argv))
    collect_pre_run_diagnostics(log_session, command.env, logger=logger)
    if logger:
        logger.info("Launching Proton: %s", " ".join(command.argv))
    if dry_run:
        append_system_event(log_session, "dry-run: Proton launch skipped")
        if logger:
            logger.success("Dry-run: Proton launch skipped")  # type: ignore[attr-defined]
        archive = archive_and_rotate_logs(log_session, logger=logger)
        if logger and archive:
            logger.info("Debug log archive: %s", archive)
        return 0
    process = subprocess.Popen(command.argv, env=command.env, cwd=command.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="ignore")
    _run_after_start(getattr(command, "after_start", ()), process, logger)
    output_thread = start_process_log_capture(process, log_session)
    interrupted = {"signal": None}
    previous = _install_signal_handlers(process, interrupted, logger)
    code: int | None = None
    try:
        code = process.wait()
        append_system_event(log_session, f"Proton process exited with code {code}")
    finally:
        _restore_signal_handlers(previous)
        if output_thread:
            output_thread.join(timeout=2)
        if config.graceful_shutdown:
            shutdown_prefix(config, prefix, compatdata, logger)
        collect_post_run_diagnostics(log_session, command.env, logger=logger)
        signal_number = int(interrupted["signal"]) if interrupted["signal"] else None
        if signal_number or (code is not None and code != 0):
            write_crash_log(log_session, code=code, signal_number=signal_number, reason="Proton process did not exit cleanly")
        archive = archive_and_rotate_logs(log_session, logger=logger)
        if logger and archive:
            logger.info("Debug log archive: %s", archive)
    if interrupted["signal"]:
        return 128 + int(interrupted["signal"])
    if code != 0:
        raise CommandError(f"Proton exited with code {code}")
    return code


def _process_for_prefix(proc: Path, needles: Iterable[str]) -> PrefixProcess | None:
    try:
        cmdline = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore")
        environ = (proc / "environ").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore")
        name = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return None
    haystack = f"{cmdline} {environ}"
    if not any(needle in haystack for needle in needles):
        return None
    if not any(watched.lower() in f"{name} {cmdline}".lower() for watched in WATCH_NAMES):
        return None
    return PrefixProcess(int(proc.name), name, cmdline)


def _run_wineserver(prefix: Path, flag: str, timeout: int, logger: logging.Logger | None) -> None:
    wineserver = shutil.which("wineserver")
    if not wineserver:
        if logger:
            logger.warning("wineserver was not found; skipping wineserver %s", flag)
        return
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    if logger:
        logger.info("Running wineserver %s for prefix %s", flag, prefix)
    try:
        subprocess.run([wineserver, flag], env=env, timeout=max(timeout, 1), check=False)
    except subprocess.TimeoutExpired:
        if logger:
            logger.warning("wineserver %s timed out for prefix %s", flag, prefix)


def _signal_processes(processes: list[PrefixProcess], sig: signal.Signals, logger: logging.Logger | None) -> None:
    for process in processes:
        if logger:
            logger.warning("Sending %s to pid=%s name=%s", sig.name, process.pid, process.name)
        try:
            os.kill(process.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            if logger:
                logger.warning("No permission to signal pid=%s", process.pid)


def _wait_gone(pids: list[int], timeout: int) -> None:
    deadline = time.monotonic() + max(timeout, 0)
    while time.monotonic() < deadline and any((Path("/proc") / str(pid)).exists() for pid in pids):
        time.sleep(0.2)


def _install_signal_handlers(process: subprocess.Popen, interrupted: dict, logger: logging.Logger | None) -> dict[int, object]:
    signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    previous = {sig: signal.getsignal(sig) for sig in signals}

    def handler(signum, _frame):
        interrupted["signal"] = signum
        if logger:
            logger.warning("Received signal %s; stopping Proton process", signal.Signals(signum).name)
        if process.poll() is None:
            process.terminate()

    for sig in signals:
        signal.signal(sig, handler)
    return previous


def _restore_signal_handlers(previous: dict[int, object]) -> None:
    for sig, handler in previous.items():
        signal.signal(sig, handler)


def _run_after_start(hooks, process: subprocess.Popen, logger: logging.Logger | None) -> None:
    for hook in hooks:
        try:
            hook(process)
        except Exception as exc:
            if logger:
                logger.warning("After-start hook failed: %s", exc)
