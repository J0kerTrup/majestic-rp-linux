from __future__ import annotations

import curses
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.config import load_config
from ..core.config_parser import SECTION_PREFIXES
from ..detection.paths import (
    DetectionResult,
    detect_gta_platform,
    find_compatdata,
    find_majestic_exe,
    find_proton,
    find_steam_root,
    gta_path_candidates,
    proton_path_candidates,
)
from ..detection.platform import select_platform


@dataclass(slots=True)
class ConfiguratorState:
    config_path: Path
    result: DetectionResult
    gta_candidates: list[Path]
    resolution: tuple[int, int] | None


def run_configurator(config_path: Path, logger) -> int:
    state = _build_config_state(config_path, logger)
    _menu_loop(state, logger)
    return 0


def _build_config_state(config_path: Path, logger) -> ConfiguratorState:
    config = load_config(config_path)
    gta_path = config.gta_path if config.gta_path and config.gta_path.exists() else None
    detected = detect_gta_platform(gta_path)
    selected = select_platform(config.selected_platform, detected, config.platform_explicit, logger)
    result = DetectionResult(
        config.steam_root,
        config.proton_path,
        config.compatdata_path,
        gta_path,
        config.majestic_exe,
        detected,
        selected,
    )
    resolution = (config.game_width, config.game_height)
    return ConfiguratorState(config_path, result, [], resolution)


def _build_state(config_path: Path, logger) -> ConfiguratorState:
    config = load_config(config_path)
    steam_root = find_steam_root(config)
    candidates = gta_path_candidates(steam_root)
    compatdata = find_compatdata(config, steam_root)
    if config.gta_path and config.gta_path.exists():
        gta_path = config.gta_path
    else:
        gta_path = candidates[0] if len(candidates) == 1 else None
    proton_path = find_proton(config, steam_root)
    majestic_exe = find_majestic_exe(config, compatdata)
    detected = detect_gta_platform(gta_path)
    selected = select_platform(config.selected_platform, detected, config.platform_explicit, logger)
    result = DetectionResult(steam_root, proton_path, compatdata, gta_path, majestic_exe, detected, selected)
    return ConfiguratorState(config_path, result, candidates, detect_screen_resolution())


def _smart_default_updates(state: ConfiguratorState, logger) -> dict[str, str]:
    config = load_config(state.config_path)
    updates: dict[str, str] = {"MAJESTIC_AUTO_DETECT": "1"}
    if state.resolution:
        width, height = state.resolution
        updates["GAME_WIDTH"] = str(width)
        updates["GAME_HEIGHT"] = str(height)
    if state.result.steam_root:
        updates["STEAM_ROOT"] = str(state.result.steam_root)
    if state.result.compatdata_path:
        updates["STEAM_COMPAT_DATA_PATH"] = str(state.result.compatdata_path)
    if state.result.proton_path:
        updates["PROTON_PATH"] = str(state.result.proton_path)
    if state.result.majestic_exe:
        updates["MAJESTIC_EXE"] = str(state.result.majestic_exe)
    if len(state.gta_candidates) == 1:
        gta_path = state.gta_candidates[0]
        updates["GTA_PATH"] = str(gta_path)
        updates["MAJESTIC_PLATFORM"] = select_platform("auto", detect_gta_platform(gta_path), False, logger)
    elif config.gta_path and config.gta_path.exists():
        updates["GTA_PATH"] = str(config.gta_path)
        updates["MAJESTIC_PLATFORM"] = state.result.selected_platform
    return updates


def _menu_loop(state: ConfiguratorState, logger) -> None:
    try:
        curses.wrapper(_curses_menu_loop, state, logger)
    except curses.error:
        _plain_menu_loop(state, logger)


def _curses_menu_loop(stdscr, state: ConfiguratorState, logger) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    _init_curses_colors()
    message = "Menu loaded. Run smart autodetect when you want to scan paths."
    while True:
        state = _build_config_state(state.config_path, logger)
        choice = _main_menu(stdscr, state, message)
        if choice is None or choice == "exit":
            return
        if choice == "detect":
            _status_screen(stdscr, "Detecting paths...")
            state = _build_state(state.config_path, logger)
            update_config_values(state.config_path, _smart_default_updates(state, logger))
            if len(state.gta_candidates) > 1 and not state.result.gta_path:
                message = "Multiple GTA V installs found. Select the GTA V path from the menu."
            else:
                message = "Smart defaults applied."
        elif choice == "gta":
            message = _select_gta_path_curses(stdscr, state, logger)
        elif choice == "resolution":
            message = _set_resolution_curses(stdscr, state)
        elif choice == "window":
            message = _toggle_window_mode(state)
        elif choice == "autopatch":
            message = _toggle_bool_value(state, "MAJESTIC_AUTO_PATCH_LAUNCHER", "Launcher auto-patch")
        elif choice == "platform":
            message = _select_platform_curses(stdscr, state)
        elif choice == "proton":
            message = _select_proton_path_curses(stdscr, state)
        elif choice == "compatdata":
            message = _set_path_value_curses(stdscr, state, "STEAM_COMPAT_DATA_PATH", "Path to compatdata directory")
        elif choice == "logdir":
            message = _set_path_value_curses(stdscr, state, "MAJESTIC_LOG_DIR", "Directory for runner logs")
        elif choice == "show":
            _text_view(stdscr, "Config file", state.config_path.read_text(encoding="utf-8").splitlines())
            message = ""


def _main_menu(stdscr, state: ConfiguratorState, message: str) -> str | None:
    items = [
        ("detect", "Apply smart defaults", "Detect resolution and common game/runtime paths"),
        ("gta", "Select GTA V path", "Choose Steam, Epic/Rockstar prefix, manual path, or deep scan"),
        ("resolution", "Set screen resolution", "Write GAME_WIDTH and GAME_HEIGHT"),
        ("window", "Toggle window mode", "Switch GAME_WINDOWED on/off"),
        ("autopatch", "Toggle launcher auto-patch", "Patch launcher again after launcher updates"),
        ("platform", "Select platform", "auto, steam, egs, or rgl"),
        ("proton", "Select Proton/Wine path", "Choose Steam Proton, GE-Proton, Wine-GE, or manual path"),
        ("compatdata", "Set compatdata prefix", "Manual STEAM_COMPAT_DATA_PATH override"),
        ("logdir", "Set logs directory", "Where runner logs and debug archives are saved"),
        ("show", "Show config file", "Open the raw config in a scrollable view"),
        ("exit", "Exit", "Return to shell"),
    ]
    selected = 0
    while True:
        _draw_main_screen(stdscr, state, message, items, selected)
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(items)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(items)
        elif key in (curses.KEY_ENTER, 10, 13):
            return items[selected][0]
        elif key in (27, ord("q")):
            return None


def _draw_main_screen(stdscr, state: ConfiguratorState, message: str, items: list[tuple[str, str, str]], selected: int) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    _paint_background(stdscr)
    box_h = min(height - 2, 24)
    box_w = min(width - 4, 92)
    top = max(0, (height - box_h) // 2)
    left = max(0, (width - box_w) // 2)
    _draw_box(stdscr, top, left, box_h, box_w, "Majestic Linux Configurator")

    info = [
        ("Config", str(state.config_path)),
        ("Resolution", _format_resolution(state.resolution)),
        ("Steam root", str(state.result.steam_root or "-")),
        ("Proton", str(state.result.proton_path or "-")),
        ("Compatdata", str(state.result.compatdata_path or "-")),
        ("GTA V", str(state.result.gta_path or "-")),
        ("Majestic Launcher", str(state.result.majestic_exe or "-")),
        ("Platform", f"{state.result.selected_platform} (detected: {state.result.detected_platform})"),
        ("Auto-patch", "enabled" if load_config(state.config_path).auto_patch_launcher else "disabled"),
        ("Logs", str(load_config(state.config_path).log_dir)),
    ]
    y = top + 2
    for label, value in info:
        _addstr(stdscr, y, left + 3, f"{label:17}", curses.color_pair(3) | curses.A_BOLD)
        _addstr(stdscr, y, left + 22, _truncate(value, box_w - 25), curses.color_pair(2))
        y += 1
    if message:
        y += 1
        _addstr(stdscr, y, left + 3, _truncate(message, box_w - 6), curses.color_pair(4))
        y += 1
    y += 1
    visible_rows = max(1, top + box_h - y - 2)
    start = max(0, selected - visible_rows + 1)
    for index, (_action, label, desc) in enumerate(items[start : start + visible_rows], start):
        attr = curses.color_pair(5) | curses.A_BOLD if index == selected else curses.color_pair(2)
        marker = ">" if index == selected else " "
        row = y + index - start
        line = _truncate(f"{marker} {label:<24} {desc}", box_w - 6)
        _addstr(stdscr, row, left + 3, line.ljust(box_w - 6), attr)
    _addstr(stdscr, top + box_h - 2, left + 3, "Up/Down: move  Enter: select  q/Esc: exit", curses.color_pair(6))
    stdscr.refresh()


def _select_gta_path_curses(stdscr, state: ConfiguratorState, logger) -> str:
    _status_screen(stdscr, "Scanning common GTA paths...")
    config = load_config(state.config_path)
    candidates = gta_path_candidates(find_steam_root(config))
    selected = 0
    while True:
        selected = min(selected, max(0, len(candidates) + 2))
        choice, selected = _select_gta_dialog(stdscr, candidates, selected)
        if choice is None or choice == "back":
            return "Selection cancelled."
        if choice == "deep":
            _status_screen(stdscr, "Deep scanning home and mounted drives...")
            candidates = gta_path_candidates(find_steam_root(config), deep_scan=True)
            selected = 0
            continue
        if choice == "manual":
            raw = _prompt(stdscr, "Manual GTA V path", "Path", "")
            if raw is None:
                return "Selection cancelled."
            path = Path(raw).expanduser()
        else:
            path = candidates[int(choice.split(":", 1)[1])]
        if not path.exists():
            return f"Path does not exist: {path}"
        platform = select_platform("auto", detect_gta_platform(path), False, logger)
        update_config_values(state.config_path, {"GTA_PATH": str(path), "MAJESTIC_PLATFORM": platform})
        return f"GTA V path saved: {path}"


def _select_proton_path_curses(stdscr, state: ConfiguratorState) -> str:
    _status_screen(stdscr, "Scanning Proton and Wine runners...")
    config = load_config(state.config_path)
    candidates = proton_path_candidates(find_steam_root(config), include_wine=True)
    selected = 0
    while True:
        selected = min(selected, max(0, len(candidates) + 1))
        choice, selected = _select_runner_dialog(stdscr, "Select Proton/Wine path", candidates, selected)
        if choice is None or choice == "back":
            return "Selection cancelled."
        if choice == "manual":
            raw = _prompt(stdscr, "Manual Proton/Wine path", "Path to proton or wine executable", "")
            if raw is None:
                return "Selection cancelled."
            path = Path(raw).expanduser()
        else:
            path = candidates[int(choice.split(":", 1)[1])]
        if not path.exists():
            return f"Path does not exist: {path}"
        update_config_values(state.config_path, {"PROTON_PATH": str(path)})
        return f"PROTON_PATH saved: {path}"


def _select_runner_dialog(stdscr, title: str, candidates: list[Path], selected: int) -> tuple[str | None, int]:
    actions = [("manual", "Manual path", "Type a custom runner executable"), ("back", "Back", "Return to main menu")]
    while True:
        rows: list[tuple[str, str, str, Path | None]] = []
        for index, path in enumerate(candidates):
            rows.append((f"path:{index}", _runner_label(path), _runner_description(path), path))
        rows.extend((value, label, desc, None) for value, label, desc in actions)
        selected = min(selected, max(0, len(rows) - 1))

        stdscr.erase()
        _paint_background(stdscr)
        height, width = stdscr.getmaxyx()
        detail_height = 5 if height >= 18 else 0
        box_h = min(height - 2, max(12, min(len(rows) + detail_height + 7, height - 2)))
        box_w = min(width - 4, 96)
        top = max(0, (height - box_h) // 2)
        left = max(0, (width - box_w) // 2)
        _draw_box(stdscr, top, left, box_h, box_w, title)

        list_top = top + 3
        detail_top = top + box_h - detail_height - 1 if detail_height else top + box_h - 2
        list_bottom = max(list_top, detail_top - 1)
        visible = max(1, list_bottom - list_top)
        action_header_index = len(candidates)
        if candidates:
            _addstr(stdscr, top + 2, left + 3, "Detected runners", curses.color_pair(3) | curses.A_BOLD)
        else:
            _addstr(stdscr, top + 2, left + 3, "No detected runners", curses.color_pair(4) | curses.A_BOLD)
        start = max(0, selected - visible + 1)
        row = list_top
        for index in range(start, min(len(rows), start + visible)):
            if index == action_header_index:
                if row < list_bottom:
                    _addstr(stdscr, row, left + 3, "Actions", curses.color_pair(3) | curses.A_BOLD)
                    row += 1
                if row >= list_bottom:
                    break
            _value, label, desc, _path = rows[index]
            attr = curses.color_pair(5) | curses.A_BOLD if index == selected else curses.color_pair(2)
            marker = ">" if index == selected else " "
            line = _truncate(f"{marker} {label:<40} {desc}", box_w - 6)
            _addstr(stdscr, row, left + 3, line.ljust(box_w - 6), attr)
            row += 1

        if detail_height:
            _addstr(stdscr, detail_top, left + 3, "Selected", curses.color_pair(3) | curses.A_BOLD)
            _addstr(stdscr, detail_top + 1, left + 3, "-" * (box_w - 6), curses.color_pair(6))
            _value, label, desc, path = rows[selected]
            selected_text = f"{path}  {desc}" if path else f"{label}  {desc}"
            detail_lines = _wrap_text(selected_text, box_w - 6, detail_height - 3)
            for index in range(detail_height - 3):
                _addstr(stdscr, detail_top + 2 + index, left + 3, " " * (box_w - 6), curses.color_pair(2))
            for index, line in enumerate(detail_lines):
                _addstr(stdscr, detail_top + 2 + index, left + 3, line, curses.color_pair(2))

        _addstr(stdscr, top + box_h - 2, left + 3, "Up/Down: move  Enter: select  Esc: back", curses.color_pair(6))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(rows)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(rows)
        elif key in (curses.KEY_ENTER, 10, 13):
            return rows[selected][0], selected
        elif key in (27, ord("q")):
            return None, selected


def _select_gta_dialog(
    stdscr,
    candidates: list[Path],
    selected: int,
) -> tuple[str | None, int]:
    actions = [
        ("deep", "Deep scan", "Search home and mounted drives"),
        ("manual", "Manual path", "Type a custom GTA V directory"),
        ("back", "Back", "Return to main menu"),
    ]
    while True:
        rows: list[tuple[str, str, str, Path | None]] = []
        for index, path in enumerate(candidates):
            rows.append((f"path:{index}", _compact_path_label(str(path)), detect_gta_platform(path), path))
        rows.extend((value, label, desc, None) for value, label, desc in actions)
        selected = min(selected, max(0, len(rows) - 1))

        stdscr.erase()
        _paint_background(stdscr)
        height, width = stdscr.getmaxyx()
        detail_height = 5 if height >= 18 else 0
        box_h = min(height - 2, max(12, min(len(rows) + detail_height + 7, height - 2)))
        box_w = min(width - 4, 92)
        top = max(0, (height - box_h) // 2)
        left = max(0, (width - box_w) // 2)
        _draw_box(stdscr, top, left, box_h, box_w, "Select GTA V path")

        list_top = top + 3
        detail_top = top + box_h - detail_height - 1 if detail_height else top + box_h - 2
        list_bottom = max(list_top, detail_top - 1)
        visible = max(1, list_bottom - list_top)
        action_header_index = len(candidates)
        start = max(0, selected - visible + 1)
        if candidates:
            _addstr(stdscr, top + 2, left + 3, "Detected installs", curses.color_pair(3) | curses.A_BOLD)
        else:
            _addstr(stdscr, top + 2, left + 3, "No detected installs", curses.color_pair(4) | curses.A_BOLD)
        row = list_top
        for index in range(start, min(len(rows), start + visible)):
            if index == action_header_index:
                if row < list_bottom:
                    _addstr(stdscr, row, left + 3, "Actions", curses.color_pair(3) | curses.A_BOLD)
                    row += 1
                if row >= list_bottom:
                    break
            value, label, desc, _path = rows[index]
            attr = curses.color_pair(5) | curses.A_BOLD if index == selected else curses.color_pair(2)
            marker = ">" if index == selected else " "
            line = _truncate(f"{marker} {label:<38} {desc}", box_w - 6)
            _addstr(stdscr, row, left + 3, line.ljust(box_w - 6), attr)
            row += 1

        if detail_height:
            _addstr(stdscr, detail_top, left + 3, "Selected", curses.color_pair(3) | curses.A_BOLD)
            _addstr(stdscr, detail_top + 1, left + 3, "-" * (box_w - 6), curses.color_pair(6))
            value, label, desc, path = rows[selected]
            selected_text = f"{path}  {desc}" if path else f"{label}  {desc}"
            detail_lines = _wrap_text(selected_text, box_w - 6, detail_height - 3)
            for index in range(detail_height - 3):
                _addstr(stdscr, detail_top + 2 + index, left + 3, " " * (box_w - 6), curses.color_pair(2))
            for index, line in enumerate(detail_lines):
                _addstr(stdscr, detail_top + 2 + index, left + 3, line, curses.color_pair(2))

        _addstr(stdscr, top + box_h - 2, left + 3, "Up/Down: move  Enter: select  Esc: back", curses.color_pair(6))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(rows)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(rows)
        elif key in (curses.KEY_ENTER, 10, 13):
            return rows[selected][0], selected
        elif key in (27, ord("q")):
            return None, selected


def _set_resolution_curses(stdscr, state: ConfiguratorState) -> str:
    raw = _prompt(stdscr, "Screen resolution", "Resolution (WIDTHxHEIGHT)", _format_resolution(state.resolution))
    if raw is None:
        return "Resolution was not changed."
    match = re.fullmatch(r"(\d{3,5})\s*x\s*(\d{3,5})", raw.strip().lower())
    if not match:
        return "Resolution was not changed."
    width, height = int(match.group(1)), int(match.group(2))
    update_config_values(state.config_path, {"GAME_WIDTH": str(width), "GAME_HEIGHT": str(height)})
    return f"Resolution saved: {width}x{height}"


def _select_platform_curses(stdscr, state: ConfiguratorState) -> str:
    options = [("auto", "auto", "Let the runner decide"), ("steam", "steam", "Force Steam"), ("egs", "egs", "Force Epic Games"), ("rgl", "rgl", "Force Rockstar Games Launcher")]
    choice = _select_dialog(stdscr, "Platform", options, 0)
    if choice is None:
        return "Platform was not changed."
    update_config_values(state.config_path, {"MAJESTIC_PLATFORM": choice})
    return f"Platform saved: {choice}"


def _set_path_value_curses(stdscr, state: ConfiguratorState, key: str, prompt: str) -> str:
    raw = _prompt(stdscr, key, prompt, "")
    if raw is None:
        return f"{key} was not changed."
    if not raw.strip():
        update_config_values(state.config_path, {key: ""})
        return f"{key} cleared."
    path = Path(raw.strip()).expanduser()
    if not path.exists():
        confirm = _select_dialog(stdscr, "Path does not exist", [("no", "No", "Do not save"), ("yes", "Yes", "Save anyway")], 0)
        if confirm != "yes":
            return f"{key} was not changed."
    update_config_values(state.config_path, {key: str(path)})
    return f"{key} saved."


def _select_dialog(stdscr, title: str, items: list[tuple[str, str, str]], selected: int = 0) -> str | None:
    if not items:
        return None
    while True:
        stdscr.erase()
        _paint_background(stdscr)
        height, width = stdscr.getmaxyx()
        detail_height = 5 if height >= 18 else 0
        box_h = min(height - 2, max(9, min(len(items) + detail_height + 5, height - 2)))
        box_w = min(width - 4, 88)
        top = max(0, (height - box_h) // 2)
        left = max(0, (width - box_w) // 2)
        _draw_box(stdscr, top, left, box_h, box_w, title)
        visible = max(1, box_h - detail_height - 4)
        start = max(0, selected - visible + 1)
        for index, (_value, label, desc) in enumerate(items[start : start + visible], start):
            attr = curses.color_pair(5) | curses.A_BOLD if index == selected else curses.color_pair(2)
            marker = ">" if index == selected else " "
            row = top + 2 + index - start
            display_label = _compact_path_label(label) if "/" in label else label
            line = _truncate(f"{marker} {display_label:<34} {desc}", box_w - 6)
            _addstr(stdscr, row, left + 3, line.ljust(box_w - 6), attr)
        if detail_height:
            detail_top = top + box_h - detail_height - 1
            _addstr(stdscr, detail_top, left + 3, "Selected", curses.color_pair(3) | curses.A_BOLD)
            _addstr(stdscr, detail_top + 1, left + 3, "-" * (box_w - 6), curses.color_pair(6))
            _value, label, desc = items[selected]
            detail_lines = _wrap_text(f"{label}  {desc}".strip(), box_w - 6, detail_height - 3)
            for index in range(detail_height - 3):
                _addstr(stdscr, detail_top + 2 + index, left + 3, " " * (box_w - 6), curses.color_pair(2))
            for index, line in enumerate(detail_lines):
                _addstr(stdscr, detail_top + 2 + index, left + 3, line, curses.color_pair(2))
        _addstr(stdscr, top + box_h - 2, left + 3, "Up/Down: move  Enter: select  Esc: back", curses.color_pair(6))
        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(items)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(items)
        elif key in (curses.KEY_ENTER, 10, 13):
            return items[selected][0]
        elif key in (27, ord("q")):
            return None


def _prompt(stdscr, title: str, prompt: str, initial: str = "") -> str | None:
    curses.curs_set(1)
    curses.echo()
    try:
        stdscr.erase()
        _paint_background(stdscr)
        height, width = stdscr.getmaxyx()
        box_h, box_w = 8, min(width - 4, 76)
        top = max(0, (height - box_h) // 2)
        left = max(0, (width - box_w) // 2)
        _draw_box(stdscr, top, left, box_h, box_w, title)
        _addstr(stdscr, top + 2, left + 3, _truncate(prompt, box_w - 6), curses.color_pair(2))
        _addstr(stdscr, top + 4, left + 3, _truncate(initial, box_w - 6).ljust(box_w - 6), curses.color_pair(7))
        _addstr(stdscr, top + box_h - 2, left + 3, "Enter value, leave empty to cancel", curses.color_pair(6))
        stdscr.move(top + 4, left + 3 + min(len(initial), box_w - 6))
        stdscr.refresh()
        raw = stdscr.getstr(top + 4, left + 3, box_w - 6).decode("utf-8", errors="ignore").strip()
        return raw or None
    finally:
        curses.noecho()
        curses.curs_set(0)


def _text_view(stdscr, title: str, lines: list[str]) -> None:
    offset = 0
    while True:
        stdscr.erase()
        _paint_background(stdscr)
        height, width = stdscr.getmaxyx()
        box_h = height - 2
        box_w = width - 4
        top, left = 1, 2
        _draw_box(stdscr, top, left, box_h, box_w, title)
        visible = max(1, box_h - 4)
        offset = min(offset, max(0, len(lines) - visible))
        for index, line in enumerate(lines[offset : offset + visible]):
            _addstr(stdscr, top + 2 + index, left + 3, _truncate(line, box_w - 6), curses.color_pair(2))
        _addstr(stdscr, top + box_h - 2, left + 3, "Up/Down/PgUp/PgDn: scroll  Esc/q: back", curses.color_pair(6))
        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            offset = max(0, offset - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            offset = min(max(0, len(lines) - visible), offset + 1)
        elif key == curses.KEY_PPAGE:
            offset = max(0, offset - visible)
        elif key == curses.KEY_NPAGE:
            offset = min(max(0, len(lines) - visible), offset + visible)
        elif key in (27, ord("q")):
            return


def _message_box(stdscr, title: str, lines: list[str]) -> None:
    _status_screen(stdscr, title, lines)
    stdscr.getch()


def _status_screen(stdscr, title: str, lines: list[str] | None = None) -> None:
    stdscr.erase()
    _paint_background(stdscr)
    height, width = stdscr.getmaxyx()
    box_h, box_w = 7, min(width - 4, 70)
    top = max(0, (height - box_h) // 2)
    left = max(0, (width - box_w) // 2)
    _draw_box(stdscr, top, left, box_h, box_w, title)
    for index, line in enumerate(lines or ["Please wait..."]):
        _addstr(stdscr, top + 2 + index, left + 3, _truncate(line, box_w - 6), curses.color_pair(2))
    stdscr.refresh()


def _init_curses_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_WHITE)


def _paint_background(stdscr) -> None:
    stdscr.bkgd(" ", curses.color_pair(1))


def _draw_box(stdscr, top: int, left: int, height: int, width: int, title: str) -> None:
    win = stdscr.derwin(height, width, top, left)
    win.bkgd(" ", curses.color_pair(2))
    win.attron(curses.color_pair(3))
    win.box()
    win.attroff(curses.color_pair(3))
    if title:
        win.addstr(0, 2, f" {title} ", curses.color_pair(3) | curses.A_BOLD)


def _addstr(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = stdscr.getmaxyx()
    if y < 0 or y >= height or x < 0 or x >= width:
        return
    stdscr.addstr(y, x, text[: max(0, width - x - 1)], attr)


def _truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _compact_path_label(text: str) -> str:
    path = Path(text)
    name = path.name or text
    parent = path.parent.name
    return f"{parent}/{name}" if parent and parent != "." else name


def _runner_label(path: Path) -> str:
    parent = path.parent.name
    grandparent = path.parent.parent.name if path.parent.parent != path.parent else ""
    if path.name.startswith("wine") and parent == "bin":
        if str(path).startswith(("/usr/bin", "/bin")):
            return path.name
        return grandparent or path.name
    return parent if path.name == "proton" else _compact_path_label(str(path))


def _runner_description(path: Path) -> str:
    text = str(path).lower()
    if path.name.startswith("wine"):
        if "wine-ge" in text or "wine_ge" in text:
            return "wine-ge"
        if "lutris" in text:
            return "lutris wine"
        if str(path).startswith(("/usr/bin", "/bin")):
            return "system wine"
        return "wine"
    if "ge-proton" in text or "proton-ge" in text:
        return "proton-ge"
    if "compatibilitytools.d" in text:
        return "custom proton"
    if "steamapps/common" in text:
        return "steam proton"
    return "proton"


def _wrap_text(text: str, width: int, max_lines: int) -> list[str]:
    if width <= 0 or max_lines <= 0:
        return []
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        chunks = [word[index : index + width] for index in range(0, len(word), width)] or [word]
        for chunk in chunks:
            candidate = chunk if not current else f"{current} {chunk}"
            if len(candidate) <= width:
                current = candidate
                continue
            lines.append(current)
            current = chunk
            if len(lines) >= max_lines:
                return _ellipsize_last_line(lines, width)
    if current and len(lines) < max_lines:
        lines.append(current)
    return _ellipsize_last_line(lines[:max_lines], width) if len(lines) >= max_lines and words else lines


def _ellipsize_last_line(lines: list[str], width: int) -> list[str]:
    if not lines:
        return lines
    if len(lines[-1]) >= width and width > 3:
        lines[-1] = lines[-1][: width - 3] + "..."
    return lines


def _plain_menu_loop(state: ConfiguratorState, logger) -> None:
    message = "Menu loaded. Run smart autodetect when you want to scan paths."
    while True:
        _clear_screen()
        state = _build_config_state(state.config_path, logger)
        print("Majestic Linux Configurator")
        print("=" * 28)
        print(f"Config:            {state.config_path}")
        print(f"Resolution:        {_format_resolution(state.resolution)}")
        print(f"Steam root:        {state.result.steam_root or '-'}")
        print(f"Proton:            {state.result.proton_path or '-'}")
        print(f"Compatdata:        {state.result.compatdata_path or '-'}")
        print(f"GTA V:             {state.result.gta_path or '-'}")
        print(f"Majestic Launcher: {state.result.majestic_exe or '-'}")
        print(f"Platform:          {state.result.selected_platform} (detected: {state.result.detected_platform})")
        print(f"Auto-patch:        {'enabled' if load_config(state.config_path).auto_patch_launcher else 'disabled'}")
        print(f"Logs:              {load_config(state.config_path).log_dir}")
        print()
        if message:
            print(message)
            print()
        print("1. Apply smart defaults again")
        print("2. Select GTA V path")
        print("3. Set screen resolution")
        print("4. Toggle window mode")
        print("5. Toggle launcher auto-patch")
        print("6. Select platform")
        print("7. Set Proton path")
        print("8. Set compatdata prefix")
        print("9. Set logs directory")
        print("10. Show config file")
        print("0. Exit")
        choice = input("> ").strip().lower()
        if choice == "1":
            print("Detecting...")
            state = _build_state(state.config_path, logger)
            update_config_values(state.config_path, _smart_default_updates(state, logger))
            if len(state.gta_candidates) > 1 and not state.result.gta_path:
                message = "Multiple GTA V installs found. Select the GTA V path from the menu."
            else:
                message = "Smart defaults applied."
        elif choice == "2":
            message = _select_gta_path(state, logger)
        elif choice == "3":
            message = _set_resolution(state)
        elif choice == "4":
            message = _toggle_window_mode(state)
        elif choice == "5":
            message = _toggle_bool_value(state, "MAJESTIC_AUTO_PATCH_LAUNCHER", "Launcher auto-patch")
        elif choice == "6":
            message = _select_platform(state)
        elif choice == "7":
            message = _set_path_value(state, "PROTON_PATH", "Path to proton executable")
        elif choice == "8":
            message = _set_path_value(state, "STEAM_COMPAT_DATA_PATH", "Path to compatdata directory")
        elif choice == "9":
            message = _set_path_value(state, "MAJESTIC_LOG_DIR", "Directory for runner logs")
        elif choice == "10":
            _show_config(state.config_path)
            message = ""
        elif choice in {"0", "q", "quit", "exit"}:
            return
        else:
            message = "Unknown menu item."


def _select_gta_path(state: ConfiguratorState, logger) -> str:
    config = load_config(state.config_path)
    candidates = gta_path_candidates(find_steam_root(config))
    while True:
        _clear_screen()
        print("Select GTA V path")
        print("=" * 17)
        if candidates:
            for index, path in enumerate(candidates, 1):
                platform = detect_gta_platform(path)
                print(f"{index}. {path} [{platform}]")
        else:
            print("No GTA V candidates were found automatically.")
        print("d. Deep scan home and mounted drives")
        print("m. Enter path manually")
        print("0. Back")
        choice = input("> ").strip().lower()
        if choice == "d":
            print("Scanning...")
            config = load_config(state.config_path)
            candidates = gta_path_candidates(find_steam_root(config), deep_scan=True)
            continue
        break
    if choice == "0":
        return "Selection cancelled."
    if choice == "m":
        raw = input("GTA V path: ").strip()
        path = Path(raw).expanduser()
    else:
        try:
            path = candidates[int(choice) - 1]
        except (ValueError, IndexError):
            return "Invalid GTA V selection."
    if not path.exists():
        return f"Path does not exist: {path}"
    platform = select_platform("auto", detect_gta_platform(path), False, logger)
    update_config_values(state.config_path, {"GTA_PATH": str(path), "MAJESTIC_PLATFORM": platform})
    return f"GTA V path saved: {path}"


def _set_resolution(state: ConfiguratorState) -> str:
    detected = _format_resolution(state.resolution)
    print(f"Detected resolution: {detected}")
    raw = input("Resolution (WIDTHxHEIGHT): ").strip().lower()
    match = re.fullmatch(r"(\d{3,5})\s*x\s*(\d{3,5})", raw)
    if not match:
        return "Resolution was not changed."
    width, height = int(match.group(1)), int(match.group(2))
    update_config_values(state.config_path, {"GAME_WIDTH": str(width), "GAME_HEIGHT": str(height)})
    return f"Resolution saved: {width}x{height}"


def _toggle_window_mode(state: ConfiguratorState) -> str:
    config = load_config(state.config_path)
    windowed = not config.game_windowed
    updates = {"GAME_WINDOWED": _bool_value(windowed)}
    if not windowed:
        updates["GAME_BORDERLESS"] = "0"
    else:
        updates["GAME_BORDERLESS"] = _bool_value(config.game_borderless)
    update_config_values(state.config_path, updates)
    return f"Windowed mode: {'enabled' if windowed else 'disabled'}"


def _toggle_bool_value(state: ConfiguratorState, key: str, label: str) -> str:
    config = load_config(state.config_path)
    current = config.auto_patch_launcher if key == "MAJESTIC_AUTO_PATCH_LAUNCHER" else False
    enabled = not current
    update_config_values(state.config_path, {key: _bool_value(enabled)})
    return f"{label}: {'enabled' if enabled else 'disabled'}"


def _select_platform(state: ConfiguratorState) -> str:
    options = ["auto", "steam", "egs", "rgl"]
    print("Platform:")
    for index, option in enumerate(options, 1):
        print(f"{index}. {option}")
    choice = input("> ").strip().lower()
    if choice in options:
        platform = choice
    else:
        try:
            platform = options[int(choice) - 1]
        except (ValueError, IndexError):
            return "Platform was not changed."
    update_config_values(state.config_path, {"MAJESTIC_PLATFORM": platform})
    return f"Platform saved: {platform}"


def _set_path_value(state: ConfiguratorState, key: str, prompt: str) -> str:
    raw = input(f"{prompt}: ").strip()
    if not raw:
        update_config_values(state.config_path, {key: ""})
        return f"{key} cleared."
    path = Path(raw).expanduser()
    if not path.exists():
        confirm = input(f"Path does not exist: {path}\nSave anyway? [y/N] ").strip().lower()
        if confirm not in {"y", "yes"}:
            return f"{key} was not changed."
    update_config_values(state.config_path, {key: str(path)})
    return f"{key} saved."


def _show_config(path: Path) -> None:
    _clear_screen()
    print(path.read_text(encoding="utf-8"))
    input("\nPress Enter to return to menu.")


def detect_screen_resolution() -> tuple[int, int] | None:
    for env_width, env_height in (("GAMESCOPE_WIDTH", "GAMESCOPE_HEIGHT"), ("GAME_WIDTH", "GAME_HEIGHT")):
        width = _int_env(env_width)
        height = _int_env(env_height)
        if width and height:
            return width, height
    xrandr = shutil.which("xrandr")
    if xrandr:
        try:
            proc = subprocess.run([xrandr, "--current"], check=False, capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            proc = None
        if proc and proc.returncode == 0:
            for line in proc.stdout.splitlines():
                match = re.search(r"\b(\d{3,5})x(\d{3,5})\b[^\n]*\*", line)
                if match:
                    return int(match.group(1)), int(match.group(2))
    return None


def update_config_values(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    section = ""
    output: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
            output.append(raw_line)
            continue
        key = _line_config_key(raw_line, section)
        if key in remaining:
            output.append(f"{_line_key_name(raw_line)}={_quote_config_value(remaining.pop(key))}")
        else:
            output.append(raw_line)
    if remaining:
        if output and output[-1].strip():
            output.append("")
        output.append("# Values written by majestic-linux config.")
        for key, value in remaining.items():
            output.append(f"{key}={_quote_config_value(value)}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _line_config_key(line: str, section: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    return SECTION_PREFIXES.get(section, "") + key.upper() if section else key.upper()


def _line_key_name(line: str) -> str:
    return line.split("=", 1)[0].strip()


def _quote_config_value(value: str) -> str:
    if value == "":
        return ""
    if re.search(r"\s|#|\"|'", value):
        return shlex.quote(value)
    return value


def _format_resolution(resolution: tuple[int, int] | None) -> str:
    return f"{resolution[0]}x{resolution[1]}" if resolution else "not detected"


def _int_env(name: str) -> int | None:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bool_value(value: bool) -> str:
    return "1" if value else "0"


def _clear_screen() -> None:
    if os.environ.get("TERM"):
        print("\033[2J\033[H", end="")
