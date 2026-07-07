# AI Agent Guidelines for majestic-rp-linux

## Project Overview
This project is a Python-based orchestration runner for launching **Majestic RP (GTA V)** on Linux through **Steam, Proton, and Wine**. 
It automates path detection, prepares Wine prefixes, applies JavaScript patches to the Electron-based Majestic Launcher, handles Discord RPC bridging, and manages lifecycle events (launching, prefix shutdown, log rotation).

## Tech Stack
- **Language:** Python 3.11+ (Strict typing using `from __future__ import annotations`)
- **Dependencies:** **Python Standard Library ONLY**. Do not use or suggest any third-party `pip` packages.
- **Environment:** Linux, Proton, Wine
- **External Tools:** `bash`, `protontricks`, `winetricks`, `asar`, `xdotool`

## Project Structure
The core Python module is located in `majestic_linux/`:
- `app/` - CLI entry points, argument parsing, and command handlers (`run`, `install`, `doctor`, etc.).
- `core/` - Configuration models (`RunnerConfig`), error handling (`RunnerError`), and logging.
- `detection/` - Async path detection for Steam, Proton, GTA V, and platform detection (Steam vs Epic vs Rockstar).
- `discord/` - Discord Rich Presence bridge management via Wine IPC.
- `patching/` - JavaScript AST/regex patching for the Electron app (`app.asar`), modifying the launcher to work under Proton.
- `radio/` - Read-only diagnostic tools for analyzing GStreamer/audio issues and parsing crash logs.
- `runtime/` - Wine prefix setup, Proton invocation, `winetricks`/`protontricks` application, fonts, and cleanup.

## Core Design Principles

1. **Zero External Dependencies:** The project must remain 100% dependency-free outside of the Python Standard Library to ensure trivial packaging (DEB/RPM) and maximum portability across Linux distributions. **Never** import or suggest installing third-party libraries (e.g., `requests`, `psutil`, `pydantic`).
2. **Auto-Detection First:** The runner relies heavily on auto-detecting paths (Steam roots, library folders, Proton binaries). Configuration overrides should be the exception, not the rule.
3. **Idempotency:** Operations like patching (`patching/`) or prefix setup (`runtime/`) must be idempotent. They should safely exit or skip if the target is already patched or set up.
4. **Dry-Run Support:** Almost all state-mutating functions (writing files, running external shell commands, patching) MUST support a `dry_run` boolean flag. When `dry_run=True`, the function should log what *would* happen without actually doing it.
5. **No Hardcoded Paths:** Always use dynamic XDG paths or Steam installation paths. Never hardcode user-specific paths or secrets.
6. **ASCII Paths Priority:** Keep project paths ASCII-only where possible, as Wine and Proton often fail with non-English characters in paths.

## Coding Standards

- **Path Handling:** Always use `pathlib.Path`. Do NOT use `os.path`.
- **Typing:** Use modern Python type hints. Always include `from __future__ import annotations` at the top of new files.
- **External Commands:** Use the `subprocess` module for calling external tools. Always handle timeouts and non-zero exit codes gracefully (often wrapping them in a `RunnerError` or `CommandError`).
- **Logging:** Do not use `print()` for regular output. Use the custom logger instantiated via `core.logger`.
- **String Formatting:** Prefer f-strings for string interpolation.
- **File Encoding:** Always specify `encoding="utf-8"` when reading or writing text files.

## Common Contexts & Objects
- `RunnerConfig`: Contains all configuration variables. Passed down to most runtime functions.
- `DetectionResult`: Contains resolved paths (`compatdata_path`, `proton_path`, etc.).
- `AppContext`: A wrapper containing both the loaded `RunnerConfig` and `DetectionResult`.

## Important Rules for AI
- **Strictly adhere to the Zero External Dependencies rule.** If a task requires HTTP requests, use `urllib`. If it requires JSON parsing, use the built-in `json` module.
- When generating fixes for path issues, always consider Epic Games (Heroic Launcher), Rockstar Launcher, and Steam variants.
- If modifying the JS patcher (`patching/`), ensure regular expressions or string replacements account for minified Electron code.
- If modifying prefix setup, ensure compatibility with both `protontricks` (for Steam) and `winetricks` (for non-Steam).
