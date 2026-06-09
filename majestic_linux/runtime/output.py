from __future__ import annotations

import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path
from subprocess import Popen


def proton_log_path() -> Path:
    return Path("logs") / "proton-run-latest.log"


def start_output_capture(process: Popen, log_path: Path | None = None) -> threading.Thread | None:
    if process.stdout is None:
        return None
    path = log_path or proton_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    def worker() -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        with path.open("w", encoding="utf-8", errors="ignore") as log:
            log.write(f"# Proton output capture started {timestamp}\n")
            for line in process.stdout:
                log.write(line)
                log.flush()
                sys.stdout.write(line)
                sys.stdout.flush()
        _copy_latest(path)

    thread = threading.Thread(target=worker, name="proton-output-capture", daemon=True)
    thread.start()
    return thread


def _copy_latest(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"proton-run-{stamp}.log")
    try:
        shutil.copy2(path, target)
    except OSError:
        pass
