from __future__ import annotations

import argparse

from ..radio.doctor import build_radio_report, format_summary
from .context import load_context


def cmd_doctor_radio(args: argparse.Namespace) -> int:
    context, _logger = load_context(args)
    config, result = context.config, context.result
    report = build_radio_report(config, result, dry_run=False)
    print(format_summary(report))
    return 0
