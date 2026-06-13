from __future__ import annotations

from .actions import cmd_clean, cmd_install, cmd_patch, cmd_purge_majestic, cmd_run
from .diagnostics import cmd_analyze_crash, cmd_config, cmd_detect, cmd_doctor, cmd_env
from .radio import cmd_doctor_radio

__all__ = [
    "cmd_clean",
    "cmd_analyze_crash",
    "cmd_config",
    "cmd_detect",
    "cmd_doctor",
    "cmd_doctor_radio",
    "cmd_env",
    "cmd_install",
    "cmd_patch",
    "cmd_purge_majestic",
    "cmd_run",
]
