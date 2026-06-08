from __future__ import annotations

from .actions import cmd_clean, cmd_patch, cmd_purge_majestic, cmd_run
from .diagnostics import cmd_config, cmd_detect, cmd_doctor, cmd_env
from .radio import cmd_doctor_radio

__all__ = [
    "cmd_clean",
    "cmd_config",
    "cmd_detect",
    "cmd_doctor",
    "cmd_doctor_radio",
    "cmd_env",
    "cmd_patch",
    "cmd_purge_majestic",
    "cmd_run",
]
