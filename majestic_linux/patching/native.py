from __future__ import annotations

import shutil
import subprocess
import tempfile
import os
from pathlib import Path

from ..core.errors import PatchError
from .common import PatchStatus, read_text, write_text


NATIVE_MARKER = "MAJESTIC_PROTON_NATIVE_PATCH_V1"
MINGW_TARGET = "x86_64-w64-mingw32"


def _compiler_query(compiler: str, argument: str) -> Path | None:
    try:
        result = subprocess.run(
            [compiler, argument],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    if not value or value == argument.removeprefix("-print-file-name="):
        return None
    return Path(value)


def _first_directory_with_file(candidates: list[Path], filename: str) -> Path | None:
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / filename).is_file():
            return candidate
    return None


def _mingw_include_dir(compiler: str) -> Path:
    compiler_path = Path(compiler).resolve()
    sysroot = _compiler_query(compiler, "-print-sysroot")
    candidates = [
        Path("/usr") / MINGW_TARGET / "include",
        Path("/usr") / MINGW_TARGET / "sys-root" / "mingw" / "include",
        compiler_path.parent.parent / MINGW_TARGET / "include",
        compiler_path.parent.parent / MINGW_TARGET / "sys-root" / "mingw" / "include",
    ]
    if sysroot:
        candidates.extend((sysroot / "include", sysroot / "mingw" / "include"))
    include = _first_directory_with_file(candidates, "windows.h")
    if include is None:
        raise PatchError(
            "Cannot find MinGW Windows headers (windows.h). "
            f"Install the headers for the {MINGW_TARGET} cross-compiler."
        )
    return include


def _mingw_runtime_dll(compiler: str, filename: str) -> Path | None:
    queried = _compiler_query(compiler, f"-print-file-name={filename}")
    if queried and queried.is_file():
        return queried
    include = _mingw_include_dir(compiler)
    for root in (include.parent, include.parent.parent):
        for directory in ("bin", "lib"):
            candidate = root / directory / filename
            if candidate.is_file():
                return candidate
    return None


def _node_include_dir() -> Path:
    candidates = [
        Path("/usr/include/node"),
        Path("/usr/local/include/node"),
        Path("/usr/include/nodejs/src"),
    ]
    pkg_config = shutil.which("pkg-config")
    if pkg_config:
        try:
            result = subprocess.run(
                [pkg_config, "--cflags-only-I", "libnode"],
                check=True,
                capture_output=True,
                text=True,
            )
            candidates[:0] = [
                Path(flag[2:])
                for flag in result.stdout.split()
                if flag.startswith("-I") and len(flag) > 2
            ]
        except subprocess.CalledProcessError:
            pass
    include = _first_directory_with_file(candidates, "node.h")
    if include is None:
        raise PatchError("Cannot find Node.js development headers (node.h); install the distro's Node.js development package.")
    return include


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


def build_native_module(package_root: Path, launcher_exe: Path, *, dry_run: bool = False) -> PatchStatus:
    """Cross-build the patched addon; editing its bundled sources alone is a no-op."""
    output = package_root / "build" / "Release" / "majestic-patcher.node"
    status = PatchStatus(output)
    if dry_run:
        status.details.append("would rebuild native Proton addon")
        return status

    tools = {
        name: shutil.which(name)
        for name in ("cmake", "x86_64-w64-mingw32-g++", "x86_64-w64-mingw32-objdump", "x86_64-w64-mingw32-dlltool", "x86_64-w64-mingw32-strip")
    }
    missing = [name for name, path in tools.items() if path is None]
    if missing:
        raise PatchError("Cannot rebuild Launcher 6.x native addon; missing: " + ", ".join(missing))
    if not launcher_exe.is_file():
        raise PatchError(f"Electron executable not found for native addon linking: {launcher_exe}")

    node_api = package_root.parent / "node-addon-api"
    if not node_api.is_dir():
        raise PatchError(f"node-addon-api headers not found: {node_api}")

    # The published source is built by MSVC and contains casing/stdlib assumptions.
    _prepare_mingw_source(package_root)
    compiler = tools["x86_64-w64-mingw32-g++"]
    assert compiler is not None
    mingw_include = _mingw_include_dir(compiler)
    node_include = _node_include_dir()
    with tempfile.TemporaryDirectory(prefix="majestic-native-cmake-") as temp_raw:
        temp = Path(temp_raw)
        include = temp / "include"
        include.mkdir()
        for requested, actual in (("Windows.h", "windows.h"), ("Shlobj.h", "shlobj.h"), ("Shlwapi.h", "shlwapi.h"), ("Psapi.h", "psapi.h"), ("RestartManager.h", "restartmanager.h")):
            target = mingw_include / actual
            if not target.is_file():
                raise PatchError(f"MinGW header missing: {target}")
            (include / requested).symlink_to(target)

        exports = subprocess.run(
            [tools["x86_64-w64-mingw32-objdump"], "-p", str(launcher_exe)],
            check=True, capture_output=True, text=True,
        ).stdout
        names = sorted({line.split()[-1] for line in exports.splitlines() if line.split() and line.split()[-1].startswith("napi_")})
        if not names:
            raise PatchError(f"No N-API exports found in {launcher_exe}")
        definition = temp / "node.def"
        definition.write_text("EXPORTS\n" + "\n".join(names) + "\n", encoding="utf-8")
        node_lib = temp / "libnode.a"
        subprocess.run([tools["x86_64-w64-mingw32-dlltool"], "-d", str(definition), "-l", str(node_lib), "-D", launcher_exe.name], check=True)

        build = temp / "build"
        flags = "-include algorithm -include cmath -include thread -include stdexcept -fpermissive -static-libgcc -static-libstdc++"
        subprocess.run([
            tools["cmake"], "-S", str(package_root), "-B", str(build),
            f"-DCMAKE_TOOLCHAIN_FILE={package_root / 'WineToolchain.cmake'}",
            # RelWithDebInfo avoids the upstream's unconditional MSVC-only /Zi
            # options while still compiling the non-DEBUG production path.
            "-DCMAKE_BUILD_TYPE=RelWithDebInfo", "-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O0 -DNDEBUG",
            f"-DCMAKE_CXX_FLAGS={flags}",
            f"-DCMAKE_JS_INC={node_include};{node_api};{include}",
            f"-DCMAKE_JS_LIB={node_lib}", f"-DNAPI_INCLUDE_HEADERS={node_api}",
        ], check=True)
        jobs = str(min(os.cpu_count() or 4, 16))
        subprocess.run([tools["cmake"], "--build", str(build), "--config", "RelWithDebInfo", f"-j{jobs}"], check=True)
        built = build / "majestic-patcher.node"
        if not built.is_file():
            raise PatchError(f"Native addon build produced no output: {built}")
        subprocess.run([tools["x86_64-w64-mingw32-strip"], "--strip-unneeded", str(built)], check=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, output)

    # libstdc++/libgcc are static, but GCC's std::thread still uses winpthreads.
    pthread = _mingw_runtime_dll(compiler, "libwinpthread-1.dll")
    if pthread is not None:
        shutil.copy2(pthread, output.parent / pthread.name)
    status.changed = True
    status.details.append("rebuilt native Proton addon")
    return status


def _prepare_mingw_source(package_root: Path) -> None:
    replacements = {
        package_root / "src" / "core" / "Launcher.cpp": (
            ("HANDLE_ERRORS(err::handler::run)", "HANDLE_ERRORS()"),
            ("HANDLE_ERRORS(err::handler::main)", "HANDLE_ERRORS()"),
            ('std::locale::global(std::locale("en_US.utf-8"));', 'std::locale::global(std::locale::classic());'),
        ),
        package_root / "src" / "config" / "ConfigBase.cpp": (
            ('std::exception(("Failed to open file" + fileName).c_str())', 'std::runtime_error("Failed to open file" + fileName)'),
        ),
    }
    source_suffixes = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
    for file in (package_root / "src").rglob("*"):
        if not file.is_file() or file.suffix.lower() not in source_suffixes:
            continue
        text = read_text(file)
        text = text.replace('std::exception("', 'std::runtime_error("')
        for old, new in replacements.get(file, ()):
            text = text.replace(old, new)
        file.write_text(text, encoding="utf-8")
    cmake = package_root / "CMakeLists.txt"
    text = read_text(cmake)
    text = text.replace(
        "target_link_libraries(${PROJECT_NAME} PRIVATE ${CMAKE_JS_LIB})",
        "target_link_libraries(${PROJECT_NAME} PRIVATE ${CMAKE_JS_LIB} rstrtmgr version crypt32 dxgi)",
    )
    cmake.write_text(text, encoding="utf-8")
