from __future__ import annotations

import logging
from pathlib import Path

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


def success(self: logging.Logger, message: str, *args: object, **kwargs: object) -> None:
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)


logging.Logger.success = success  # type: ignore[attr-defined]


def setup_logging(debug: bool = False, log_dir: Path | None = None) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger("majestic_linux")
    root.handlers.clear()
    root.setLevel(level)
    root.propagate = False

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "majestic-python-runner.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    return root
