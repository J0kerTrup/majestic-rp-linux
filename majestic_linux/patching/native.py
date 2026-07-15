from __future__ import annotations

from pathlib import Path

from ..core.errors import PatchError
from .common import PatchStatus, read_text, write_text


NATIVE_MARKER = "MAJESTIC_PROTON_NATIVE_PATCH_V1"


def _replace_once(source: str, old: str, new: str, file: Path) -> str:
    if old not in source:
        raise PatchError(f"{file}: native patch anchor was not found")
    return source.replace(old, new, 1)


def _patch_config_hpp(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    source = read_text(file)
    if NATIVE_MARKER in source:
        return status
    source = _replace_once(
        source,
        '\tstd::string gamePlatform;\n',
        '\tstd::string gamePlatform;\n\n'
        f'\t// {NATIVE_MARKER}: values supplied by majestic-rp-linux.\n'
        '\tbool protonRuntime = false;\n'
        '\tstd::filesystem::path protonLauncherPath;\n',
        file,
    )
    write_text(file, source, dry_run=dry_run, status=status)
    status.details.append("native Proton config fields")
    return status


def _patch_config_cpp(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    source = read_text(file)
    if NATIVE_MARKER in source:
        return status
    source = _replace_once(
        source,
        '\tgamePlatform = ReadString("gtaPlatform");\n',
        '\tgamePlatform = ReadString("gtaPlatform");\n\n'
        f'\t// {NATIVE_MARKER}: preserve the store and add a direct Proton launcher.\n'
        '\tprotonRuntime = ReadBool("protonRuntime", false);\n'
        '\tprotonLauncherPath = PathFromUtf8(ReadString("protonLauncherPath"));\n',
        file,
    )
    write_text(file, source, dry_run=dry_run, status=status)
    status.details.append("load native Proton config")
    return status


def _patch_game_cpp(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    source = read_text(file)
    if NATIVE_MARKER in source:
        return status
    old = '    platform->Start(cfg.gamePath);\n    MJ_VMP_END();\n'
    new = f'''\t// {NATIVE_MARKER}: protocol launchers escape the active Wine prefix.
\t// Keep gamePlatform as the real store for validation and backup staging,
\t// but start GTAVLauncher.exe directly inside the current Proton prefix.
\tif (cfg.protonRuntime)
\t{{
\t\tconst auto launcherPath = cfg.protonLauncherPath.empty()
\t\t\t? cfg.gamePath / "GTAVLauncher.exe"
\t\t\t: cfg.protonLauncherPath;

\t\tif (!std::filesystem::is_regular_file(launcherPath))
\t\t{{
\t\t\tMJ_PRINT_ERROR("Proton launcher does not exist: {{}}", launcherPath.string());
\t\t\tLauncher::SetPatcherError(L"ERR_FAILED_TO_LAUNCH_PLATFORM");
\t\t\tthrow std::exception("ERR_FAILED_TO_LAUNCH_PLATFORM");
\t\t}}

\t\tSTARTUPINFOW startup{{}};
\t\tPROCESS_INFORMATION process{{}};
\t\tstartup.cb = sizeof(startup);
\t\tstd::wstring commandLine = L"\\\"" + launcherPath.wstring() + L"\\\" -nobattleye";
\t\tconst auto workingDirectory = cfg.gamePath.wstring();
\t\tif (!CreateProcessW(launcherPath.c_str(), commandLine.data(), nullptr, nullptr, FALSE,
\t\t\t0, nullptr, workingDirectory.c_str(), &startup, &process))
\t\t{{
\t\t\tMJ_PRINT_ERROR("Failed to start Proton GTA launcher: {{}}", GetLastError());
\t\t\tLauncher::SetPatcherError(L"ERR_FAILED_TO_LAUNCH_PLATFORM");
\t\t\tthrow std::exception("ERR_FAILED_TO_LAUNCH_PLATFORM");
\t\t}}
\t\tCloseHandle(process.hThread);
\t\tCloseHandle(process.hProcess);
\t}}
\telse
\t{{
\t\tplatform->Start(cfg.gamePath);
\t}}
\tMJ_VMP_END();
'''
    source = _replace_once(source, old, new, file)
    write_text(file, source, dry_run=dry_run, status=status)
    status.details.append("direct Proton GTAVLauncher start")
    return status


def _patch_rockstar_cpp(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    source = read_text(file)
    if NATIVE_MARKER in source:
        return status
    old = '''\tWCHAR* mpPathGta5 = const_cast<WCHAR*>((Config::Instance().multiplayerPath / "backup" / Config::Instance().gtaExe).c_str());

\tMJ_PRINT_INFO("GTA backup file location: " + String::FromWString(mpPathGta5));

\tsize_t strSize = _wcslen(mpPathGta5) * 2;
\tsize_t allocateBuffer = strSize + sizeof(zero);
'''
    new = f'''\t// {NATIVE_MARKER}: never retain c_str() from a temporary path.
\t// The former pointer was dangling before WriteProcessMemory used it.
\tconst auto gtaBackupPath = Config::Instance().multiplayerPath / "backup" / Config::Instance().gtaExe;
\tconst std::wstring mpPathGta5 = gtaBackupPath.wstring();

\tif (!std::filesystem::is_regular_file(gtaBackupPath))
\t{{
\t\tMJ_PRINT_CRITICAL("GTA backup file is missing: {{}}", gtaBackupPath.string());
\t\tLauncher::SetPatcherError(L"ERR_FAILED_TO_PATCH_LAUNCHER");
\t\treturn FALSE;
\t}}

\tMJ_PRINT_INFO("GTA backup file location: " + String::FromWString(mpPathGta5));

\tconst size_t strSize = (mpPathGta5.size() + 1) * sizeof(wchar_t);
\tconst size_t allocateBuffer = strSize;
'''
    source = _replace_once(source, old, new, file)
    source = _replace_once(
        source,
        '\tWriteProcessMemory(process, gtaBackupAlloc, mpPathGta5, strSize, NULL);\n'
        '\tWriteProcessMemory(process, (PVOID)((uint64_t)gtaBackupAlloc + strSize), zero, sizeof(zero), NULL);\n',
        '\tSIZE_T bytesWritten = 0;\n'
        '\tif (!WriteProcessMemory(process, gtaBackupAlloc, mpPathGta5.c_str(), strSize, &bytesWritten) || bytesWritten != strSize)\n'
        '\t{\n'
        '\t\tMJ_PRINT_CRITICAL("Failed to write GTA backup path: {}", GetLastError());\n'
        '\t\tVirtualFreeEx(process, gtaBackupAlloc, 0, MEM_RELEASE);\n'
        '\t\treturn FALSE;\n'
        '\t}\n',
        file,
    )
    write_text(file, source, dry_run=dry_run, status=status)
    status.details.append("stable checked GTA backup path")
    return status


def patch_native_source_tree(package_root: Path, *, dry_run: bool = False) -> list[PatchStatus]:
    src = package_root / "src"
    required = (src / "core" / "Config.hpp", src / "core" / "Config.cpp", src / "core" / "Game.cpp", src / "inject" / "RockstarPatch.cpp")
    if not all(file.is_file() for file in required):
        return []
    return [
        _patch_config_hpp(required[0], dry_run=dry_run),
        _patch_config_cpp(required[1], dry_run=dry_run),
        _patch_game_cpp(required[2], dry_run=dry_run),
        _patch_rockstar_cpp(required[3], dry_run=dry_run),
    ]
