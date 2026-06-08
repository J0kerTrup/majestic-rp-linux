from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import PatchError

MARKER = "MAJESTIC_PROTON_PATCH_V2"
INDEX_COMPAT_MARKER = "MAJESTIC_PROTON_INDEX_COMPAT_V6"
DIRECT_MARKER = "MAJESTIC_PROTON_DIRECT_PATCH_V4"
DIRECT_MARKER_V3 = "MAJESTIC_PROTON_DIRECT_PATCH_V3"
DIRECT_MARKER_V2 = "MAJESTIC_PROTON_DIRECT_PATCH_V2"
DIRECT_MARKER_V1 = "MAJESTIC_PROTON_DIRECT_PATCH_V1"
SOURCE_MARKER = "MAJESTIC_PROTON_SOURCE_PATCH_V1"
PY_BACKUP_SUFFIX = ".majestic-python-bak"
FULL_ARRAY = '["steam","rgl","egs"]'
LEGACY_ARRAY_RE = re.compile(r"\[\s*(['\"])rgl\1\s*,\s*(['\"])egs\2\s*\]")


@dataclass(slots=True)
class PatchTargets:
    mode: str
    app_root: Path
    resources_dir: Path
    asar_path: Path | None
    unpacked_root: Path
    cleanup_root: Path | None = None


@dataclass(slots=True)
class PatchStatus:
    file: Path
    changed: bool = False
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PatchReport:
    mode: str
    statuses: list[PatchStatus]

    @property
    def changed(self) -> bool:
        return any(status.changed for status in self.statuses)


def _permissions(values: str) -> list[int]:
    parsed: list[int] = []
    for item in values.split(","):
        try:
            number = int(item.strip())
        except ValueError:
            continue
        if 0 <= number <= 254:
            parsed.append(number)
    return parsed or [1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _backup(path: Path) -> None:
    backup = path.with_suffix(path.suffix + PY_BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(path, backup)


def _write(path: Path, text: str, *, dry_run: bool, status: PatchStatus) -> None:
    status.changed = True
    if dry_run:
        status.details.append("dry-run write skipped")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _backup(path)
    path.write_text(text, encoding="utf-8")


def _replace_once(src: str, needle: str, replacement: str, status: PatchStatus, name: str) -> str:
    if needle not in src:
        return src
    status.details.append(name)
    return src.replace(needle, replacement, 1)


def resolve_targets(input_path: Path) -> PatchTargets:
    root = input_path.expanduser().resolve()
    app_asar_from_root = root / "app.asar"
    app_asar_from_resources = root / "resources" / "app.asar"
    sibling_app_asar = root.parent / "app.asar"
    extracted_index = root / "dist" / "electron" / "main" / "index.js"
    source_files = [
        root / "src" / "electron" / "main" / "utils" / "findGTA.js",
        root / "src" / "electron" / "main" / "utils" / "revalidateGTA.js",
        root / "src" / "electron" / "main" / "patcher.js",
        root / "src" / "electron" / "main" / "modules" / "game.js",
    ]
    if all(path.is_file() for path in source_files):
        return PatchTargets("source", root, root.parent, None, root)
    if root.is_file() and root.name == "app.asar":
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, root.parent, root, root.parent / "app.asar.unpacked", temp)
    if root.is_dir() and app_asar_from_root.is_file():
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, root, app_asar_from_root, root / "app.asar.unpacked", temp)
    if root.is_dir() and app_asar_from_resources.is_file():
        resources = root / "resources"
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, resources, app_asar_from_resources, resources / "app.asar.unpacked", temp)
    if root.is_dir() and root.name == "app.asar.unpacked" and sibling_app_asar.is_file():
        temp = Path(tempfile.mkdtemp(prefix="majestic-app-asar-"))
        return PatchTargets("asar", temp, root.parent, sibling_app_asar, root, temp)
    if extracted_index.is_file():
        return PatchTargets("extracted", root, root.parent, None, root)
    raise PatchError(
        "Could not locate Majestic app files. Pass resources/, resources/app.asar, "
        "resources/app.asar.unpacked, extracted app root, or recovered source root."
    )


def _run(command: list[str], *, dry_run: bool, logger: logging.Logger | None) -> None:
    if logger:
        logger.info("Executing: %s", " ".join(command))
    if dry_run:
        return
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise PatchError(f"Command failed with code {result.returncode}: {' '.join(command)}")


def _extract_asar(targets: PatchTargets, *, dry_run: bool, logger: logging.Logger | None) -> None:
    if targets.mode != "asar" or targets.asar_path is None:
        return
    asar = os.environ.get("ASAR_BIN", "asar")
    _run([asar, "extract", str(targets.asar_path), str(targets.app_root)], dry_run=dry_run, logger=logger)


def _repack_asar(targets: PatchTargets, *, dry_run: bool, logger: logging.Logger | None) -> None:
    if targets.mode != "asar" or targets.asar_path is None:
        return
    if not dry_run:
        backup = targets.asar_path.with_suffix(targets.asar_path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(targets.asar_path, backup)
    asar = os.environ.get("ASAR_BIN", "asar")
    _run([asar, "pack", str(targets.app_root), str(targets.asar_path)], dry_run=dry_run, logger=logger)


def _cleanup(targets: PatchTargets, logger: logging.Logger | None = None) -> None:
    if targets.cleanup_root and targets.cleanup_root.exists():
        if logger:
            logger.debug("Removing temporary extraction directory %s", targets.cleanup_root)
        shutil.rmtree(targets.cleanup_root, ignore_errors=True)


def _ensure_source_imports(src: str) -> str:
    next_src = src
    if "import fs from 'fs';" not in next_src and 'import fs from "fs";' not in next_src:
        next_src = "import fs from 'fs';\n" + next_src
    if "import path from 'path';" not in next_src and 'import path from "path";' not in next_src:
        next_src = "import path from 'path';\n" + next_src
    if "import childProcess from 'child_process';" not in next_src and 'import childProcess from "child_process";' not in next_src:
        next_src = "import childProcess from 'child_process';\n" + next_src
    return next_src


def patch_source_find_gta(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    src = _read(file)
    if SOURCE_MARKER in src or ("MAJESTIC_GTA_WIN_PATH" in src and "MAJESTIC_PROTON_PLATFORM" in src):
        return status
    find_needle = "export const findGTA = async () => {"
    platform_needle = "export const findValidGTAPlatform = (gtaPath, potentialPlatform) => {"
    if find_needle not in src or platform_needle not in src:
        raise PatchError(f"{file}: could not find source findGTA anchors")
    src = src.replace(
        find_needle,
        f"""{find_needle}
    const JO_ENV_GTA = process.env.MAJESTIC_GTA_WIN_PATH;
    const JO_ENV_PLATFORM = process.env.MAJESTIC_PROTON_PLATFORM;
    if (JO_ENV_GTA && ['steam', 'rgl', 'egs'].includes(JO_ENV_PLATFORM) && checkForValidGTAPath(JO_ENV_GTA)) {{
        log.info('[findGTA] using forced Proton GTA path', JO_ENV_GTA, JO_ENV_PLATFORM);
        return [JO_ENV_GTA, JO_ENV_PLATFORM];
    }}""",
        1,
    )
    src = src.replace(
        platform_needle,
        f"""{platform_needle}
    const JO_FORCED_PLATFORM = process.env.MAJESTIC_PROTON_PLATFORM;
    if (['steam', 'rgl', 'egs'].includes(JO_FORCED_PLATFORM)) return JO_FORCED_PLATFORM;""",
        1,
    )
    src = f"/* {SOURCE_MARKER}: force configured Proton GTA path and platform in recovered source tree. */\n{src}"
    _write(file, src, dry_run=dry_run, status=status)
    return status


def patch_source_revalidate_gta(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    src = _read(file)
    marker = "MAJESTIC_PROTON_SOURCE_REVALIDATE_PATCH_V1"
    if marker in src:
        return status
    import_needle = "import { game } from '../modules/game';"
    if "const JO_normalizePlatform = (platform) => {" not in src:
        if import_needle not in src:
            raise PatchError(f"{file}: could not find revalidate import anchor")
        src = src.replace(
            import_needle,
            import_needle
            + """

const JO_normalizePlatform = (platform) => {
    const normalized = platform?.toLowerCase();
    if (normalized === 'epic') return 'egs';
    return ['steam', 'rgl', 'egs'].includes(normalized) ? normalized : null;
};""",
            1,
        )
    log_needle = "log.info('[REVALIDATE GTA] Checking if GTA V is installed...', gtaPath);"
    if "const JO_FORCED_PROTON_PATH = process.env.MAJESTIC_GTA_WIN_PATH;" not in src:
        if log_needle not in src:
            raise PatchError(f"{file}: could not find revalidate env anchor")
        src = src.replace(
            log_needle,
            log_needle
            + """

    const JO_FORCED_PROTON_PATH = process.env.MAJESTIC_GTA_WIN_PATH;
    const JO_FORCED_PROTON_PLATFORM = JO_normalizePlatform(process.env.MAJESTIC_PROTON_PLATFORM);
    if (JO_FORCED_PROTON_PATH?.length && JO_FORCED_PROTON_PLATFORM && checkForValidGTAPath(JO_FORCED_PROTON_PATH)) {
        gtaPath = JO_FORCED_PROTON_PATH.replace('GTA5.exe', '');
        gtaPlatform = JO_FORCED_PROTON_PLATFORM;
        await Promise.all([
            game.set('path', gtaPath.replaceAll('/', '\\\\')),
            game.set('platform', gtaPlatform),
        ]);
        return { gta_path: gtaPath, gta_platform: gtaPlatform, valid: true };
    }""",
            1,
        )
    src = src.replace(
        "const validPlatform = findValidGTAPlatform(detectedPath, detectedPlatform);",
        "const validPlatform = findValidGTAPlatform(detectedPath, detectedPlatform) ?? JO_normalizePlatform(detectedPlatform);",
    )
    src = src.replace(
        "gtaPlatform = findValidGTAPlatform(gtaPath);\n        game.set('platform', gtaPlatform);",
        "gtaPlatform = findValidGTAPlatform(gtaPath, game.get('platform')) ?? JO_normalizePlatform(game.get('platform'));\n        if (gtaPlatform) await game.set('platform', gtaPlatform);",
    )
    src = f"/* {marker}: prefer Proton GTA path/platform and preserve Steam platform in recovered source tree. */\n{src}"
    _write(file, src, dry_run=dry_run, status=status)
    return status


def _source_patcher_helper(permissions: str) -> str:
    values = _permissions(permissions)
    return f"""/* {SOURCE_MARKER}: adapt Majestic native patcher launch config under Proton. */
const JO_PROTON_PERMISSIONS = {values};
const JO_PROTON_GTA_PATH = process.env.MAJESTIC_GTA_WIN_PATH || 'G:\\\\';
const JO_PROTON_PLATFORM = process.env.MAJESTIC_PROTON_PLATFORM || 'rgl';
const JO_PROTON_NATIVE_PLATFORM = process.env.MAJESTIC_PROTON_NATIVE_PLATFORM || (JO_PROTON_PLATFORM === 'steam' ? 'rgl' : JO_PROTON_PLATFORM);
const JO_PROTON_DISABLE_CEF_GPU = process.env.MAJESTIC_DISABLE_CEF_GPU !== '0';

function JO_isProtonRuntime() {{
    return process.platform === 'win32' && Boolean(process.env.STEAM_COMPAT_DATA_PATH || process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH || process.env.MAJESTIC_PROTON_PLATFORM || process.env.WINEPREFIX);
}}

function JO_patchJsonFile(filePath, patcherFn) {{
    if (!filePath || !fs.existsSync(filePath)) return false;
    try {{
        const config = JSON.parse(fs.readFileSync(filePath, 'utf8'));
        const nextConfig = patcherFn(config);
        if (!nextConfig) return false;
        fs.writeFileSync(filePath, JSON.stringify(nextConfig, null, 2));
        return true;
    }} catch (error) {{
        console.log('[LINUX-PROTON DEBUG] failed to patch json', {{ filePath, error }});
        return false;
    }}
}}

function JO_patchPermissionCache(multiplayerPath) {{
    const cacheRoot = path.join(multiplayerPath || '', 'cache');
    if (!fs.existsSync(cacheRoot)) return;
    const data = Buffer.from([...JO_PROTON_PERMISSIONS, 255]);
    for (const name of fs.readdirSync(cacheRoot)) {{
        const dir = path.join(cacheRoot, name);
        if (fs.existsSync(dir) && fs.lstatSync(dir).isDirectory()) fs.writeFileSync(path.join(dir, 'permissions'), data);
    }}
}}

function JO_adaptLaunchConfigForProton(launchOptionsPath) {{
    if (!JO_isProtonRuntime()) return;
    let multiplayerConfigPath = '';
    const changed = JO_patchJsonFile(launchOptionsPath, (config) => {{
        let changed = false;
        if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== JO_PROTON_GTA_PATH) {{ config.gtaPath = JO_PROTON_GTA_PATH; changed = true; }}
        if (['steam', 'rgl', 'egs'].includes(JO_PROTON_NATIVE_PLATFORM) && config.gtaPlatform !== JO_PROTON_NATIVE_PLATFORM) {{ config.gtaPlatform = JO_PROTON_NATIVE_PLATFORM; changed = true; }}
        if (config.debug !== false) {{ config.debug = false; changed = true; }}
        if (JO_PROTON_DISABLE_CEF_GPU && config.cefUseHardwareAcceleration !== false) {{ config.cefUseHardwareAcceleration = false; changed = true; }}
        if (config.multiplayerPath && config.configFileName) {{ multiplayerConfigPath = path.join(config.multiplayerPath, config.configFileName); JO_patchPermissionCache(config.multiplayerPath); }}
        return changed ? config : null;
    }});
    if (changed) console.log('[LINUX-PROTON DEBUG] launch config adapted for Proton');
    if (multiplayerConfigPath) JO_patchJsonFile(multiplayerConfigPath, (config) => {{
        let changed = false;
        if (String(config.gtapath || '').startsWith('Z:\\\\') || String(config.gtapath || '') !== JO_PROTON_GTA_PATH) {{ config.gtapath = JO_PROTON_GTA_PATH; changed = true; }}
        if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== JO_PROTON_GTA_PATH) {{ config.gtaPath = JO_PROTON_GTA_PATH; changed = true; }}
        if (config.debug !== false) {{ config.debug = false; changed = true; }}
        if (JO_PROTON_DISABLE_CEF_GPU && config.cefUseHardwareAcceleration !== false) {{ config.cefUseHardwareAcceleration = false; changed = true; }}
        return changed ? config : null;
    }});
}}
"""


def patch_source_patcher(file: Path, *, dry_run: bool, permissions: str) -> PatchStatus:
    status = PatchStatus(file)
    src = _read(file)
    if SOURCE_MARKER in src or "JO_adaptLaunchConfigForProton" in src:
        return status
    call_needle = "const result = await patcher.patchMultiplayerWithProgress(launchConfigPath, (event) => {"
    insert_needle = "export const requestPatcherCancel = () => {"
    if call_needle not in src or insert_needle not in src:
        raise PatchError(f"{file}: could not find source patcher anchors")
    src = _ensure_source_imports(src)
    src = src.replace(insert_needle, _source_patcher_helper(permissions) + insert_needle, 1)
    src = src.replace(call_needle, f"JO_adaptLaunchConfigForProton(launchConfigPath);\n        {call_needle}", 1)
    _write(file, src, dry_run=dry_run, status=status)
    return status


def patch_source_game(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    src = _read(file)
    marker = "MAJESTIC_PROTON_SOURCE_GAME_PATCH_V1"
    if marker in src:
        return status
    next_src = src.replace("    async init() {\n        this.#platform;", "    async init() {\n        this.#platform = await regeditStore.get('gta_v_platform');")
    next_src = next_src.replace("const launchConfigSaved = saveLaunchConfig(launchConfig, tempPath);", "const launchConfigSaved = await saveLaunchConfig(launchConfig, tempPath);")
    if next_src != src:
        next_src = f"/* {marker}: keep GTA platform in memory and await launch config writes. */\n{next_src}"
        _write(file, next_src, dry_run=dry_run, status=status)
    return status


def _fix_legacy_arrays(src: str, status: PatchStatus) -> str:
    next_src, count = LEGACY_ARRAY_RE.subn(FULL_ARRAY, src)
    if count:
        status.details.append(f"fixed legacy platform arrays: {count}")
    return next_src


def _index_direct_helper(permissions: str) -> str:
    values = _permissions(permissions)
    return f'''/* {DIRECT_MARKER}: adapt Majestic native patcher launch config under Proton. */
const JO_PROTON_PERMISSIONS={values},JO_PROTON_GTA_PATH=process.env.MAJESTIC_GTA_WIN_PATH||"G:\\\\",JO_PROTON_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM||"rgl",JO_PROTON_NATIVE_PLATFORM=process.env.MAJESTIC_PROTON_NATIVE_PLATFORM||(JO_PROTON_PLATFORM==="steam"?"rgl":JO_PROTON_PLATFORM),JO_PROTON_DISABLE_CEF_GPU=process.env.MAJESTIC_DISABLE_CEF_GPU!=="0";
function JO_isProtonRuntime(){{return process.platform==="win32"&&!!(process.env.STEAM_COMPAT_DATA_PATH||process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH||process.env.MAJESTIC_PROTON_PLATFORM||process.env.WINEPREFIX)}}
function JO_patchJsonFile(e,t){{if(!e||!ue.existsSync(e))return!1;try{{const n=JSON.parse(ue.readFileSync(e,"utf8")),r=t(n);return r?(ue.writeFileSync(e,JSON.stringify(r,null,2)),!0):!1}}catch(n){{return P.log("[LINUX-PROTON DEBUG] failed to patch json",{{filePath:e,error:n}}),!1}}}}
function JO_patchPermissionCache(e){{const t=ae.join(e||"","cache");if(ue.existsSync(t)){{const n=Buffer.from([...JO_PROTON_PERMISSIONS,255]);for(const r of ue.readdirSync(t)){{const i=ae.join(t,r);ue.existsSync(i)&&ue.lstatSync(i).isDirectory()&&ue.writeFileSync(ae.join(i,"permissions"),n)}}}}}}
function JO_adaptLaunchConfigForProton(e){{if(!JO_isProtonRuntime())return;let t="";const n=JO_patchJsonFile(e,r=>{{let i=!1;return(String(r.gtaPath||"").startsWith("Z:\\\\")||String(r.gtaPath||"")!==JO_PROTON_GTA_PATH)&&(r.gtaPath=JO_PROTON_GTA_PATH,i=!0),["steam","rgl","egs"].includes(JO_PROTON_NATIVE_PLATFORM)&&r.gtaPlatform!==JO_PROTON_NATIVE_PLATFORM&&(r.gtaPlatform=JO_PROTON_NATIVE_PLATFORM,i=!0),r.debug!==!1&&(r.debug=!1),JO_PROTON_DISABLE_CEF_GPU&&r.cefUseHardwareAcceleration!==!1&&(r.cefUseHardwareAcceleration=!1,i=!0),r.multiplayerPath&&r.configFileName&&(t=ae.join(r.multiplayerPath,r.configFileName),JO_patchPermissionCache(r.multiplayerPath)),i?r:null}});n&&P.info("[LINUX-PROTON DEBUG] launch config adapted for Proton");t&&JO_patchJsonFile(t,r=>{{let i=!1;return(String(r.gtapath||"").startsWith("Z:\\\\")||String(r.gtapath||"")!==JO_PROTON_GTA_PATH)&&(r.gtapath=JO_PROTON_GTA_PATH,i=!0),((String(r.gtaPath||"").startsWith("Z:\\\\")||String(r.gtaPath||"")!==JO_PROTON_GTA_PATH)&&(r.gtaPath=JO_PROTON_GTA_PATH,i=!0)),r.debug!==!1&&(r.debug=!1,i=!0),JO_PROTON_DISABLE_CEF_GPU&&r.cefUseHardwareAcceleration!==!1&&(r.cefUseHardwareAcceleration=!1,i=!0),i?r:null}})}}
async function JO_patchMultiplayerWithProgress(e,t){{JO_adaptLaunchConfigForProton(e);return Ic.patchMultiplayerWithProgress(e,t)}}
'''


def patch_index(file: Path, *, dry_run: bool, permissions: str) -> PatchStatus:
    status = PatchStatus(file)
    if not file.exists():
        raise PatchError(f"index.js not found: {file}")
    src = _read(file)
    original = src
    src = _fix_legacy_arrays(src, status)

    if INDEX_COMPAT_MARKER not in src:
        compat = False
        needles = {
            'dB=async()=>{ft.info("[findGTA] Looking for Steam...");': 'dB=async()=>{const JO_ENV_GTA=process.env.MAJESTIC_GTA_WIN_PATH,JO_ENV_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(JO_ENV_GTA&&["steam","rgl","egs"].includes(JO_ENV_PLATFORM)&&dn(JO_ENV_GTA))return ft.info("[findGTA] using forced Proton GTA path",JO_ENV_GTA,JO_ENV_PLATFORM),[JO_ENV_GTA,JO_ENV_PLATFORM];ft.info("[findGTA] Looking for Steam...");',
            'EO=async()=>{ht.info("[findGTA] Looking for Steam...");': 'EO=async()=>{const JO_ENV_GTA=process.env.MAJESTIC_GTA_WIN_PATH,JO_ENV_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(JO_ENV_GTA&&["steam","rgl","egs"].includes(JO_ENV_PLATFORM)&&dn(JO_ENV_GTA))return ht.info("[findGTA] using forced Proton GTA path",JO_ENV_GTA,JO_ENV_PLATFORM),[JO_ENV_GTA,JO_ENV_PLATFORM];ht.info("[findGTA] Looking for Steam...");',
            'Nf=(e,t)=>{const n=e?.replace("GTA5.exe","");': 'Nf=(e,t)=>{const JO_FORCED_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(["steam","rgl","egs"].includes(JO_FORCED_PLATFORM))return JO_FORCED_PLATFORM;const n=e?.replace("GTA5.exe","");',
            'tf=(e,t)=>{const n=e?.replace("GTA5.exe","");': 'tf=(e,t)=>{const JO_FORCED_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(["steam","rgl","egs"].includes(JO_FORCED_PLATFORM))return JO_FORCED_PLATFORM;const n=e?.replace("GTA5.exe","");',
        }
        for needle, replacement in needles.items():
            if needle in src:
                src = src.replace(needle, replacement, 1)
                compat = True
                status.details.append("index compatibility needle")
        fallback_patterns = [
            r'JO_fallbackPlayGTAV=e=>new Promise\(t=>\{try\{if\(process\.env\.MAJESTIC_PROTON_PLATFORM!=="steam"\).*?const n=e,r=oe\.join\(n,"PlayGTAV\.exe"\),i=\{.*?\};',
            r'JO_fallbackPlayGTAV=e=>new Promise\(t=>\{try\{const n=e,r=oe\.join\(n,"PlayGTAV\.exe"\),i=\{.*?\};',
        ]
        for pattern in fallback_patterns:
            src, count = re.subn(
                pattern,
                'JO_fallbackPlayGTAV=e=>new Promise(t=>{try{return P.warn(JO_DBG,"Steam PlayGTAV fallback disabled to avoid launching vanilla GTA",{platform:process.env.MAJESTIC_PROTON_PLATFORM}),t(!1);const n=e,r=oe.join(n,"PlayGTAV.exe"),i={...process.env,SteamAppId:"271590",SteamGameId:"271590",STEAM_COMPAT_APP_ID:"271590"};',
                src,
                count=1,
            )
            if count:
                compat = True
                status.details.append("disabled PlayGTAV fallback")
        if compat:
            src = f"/* {INDEX_COMPAT_MARKER}: force configured GTA platform and disable PlayGTAV fallback. */\n{src}"

    direct_v4 = "async function JO_patchMultiplayerWithProgress(e,t){JO_adaptLaunchConfigForProton(e);return Ic.patchMultiplayerWithProgress(e,t)}"
    direct_v1 = "function JO_patchMultiplayerWithProgress(e,t){return JO_adaptLaunchConfigForProton(e),Ic.patchMultiplayerWithProgress(e,t)}"
    if DIRECT_MARKER not in src and DIRECT_MARKER_V1 in src and direct_v1 in src:
        src = src.replace(direct_v1, direct_v4, 1)
        src = f"/* {DIRECT_MARKER}: native patcher uses Proton-compatible platform; Steam fallback disabled. */\n{src}"
    if DIRECT_MARKER not in src and DIRECT_MARKER_V3 in src:
        src = src.replace(
            'JO_PROTON_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM||"rgl",JO_PROTON_DISABLE_CEF_GPU=process.env.MAJESTIC_DISABLE_CEF_GPU!=="0"',
            'JO_PROTON_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM||"rgl",JO_PROTON_NATIVE_PLATFORM=process.env.MAJESTIC_PROTON_NATIVE_PLATFORM||(JO_PROTON_PLATFORM==="steam"?"rgl":JO_PROTON_PLATFORM),JO_PROTON_DISABLE_CEF_GPU=process.env.MAJESTIC_DISABLE_CEF_GPU!=="0"',
        )
        src = src.replace(
            '["steam","rgl","egs"].includes(JO_PROTON_PLATFORM)&&r.gtaPlatform!==JO_PROTON_PLATFORM',
            '["steam","rgl","egs"].includes(JO_PROTON_NATIVE_PLATFORM)&&r.gtaPlatform!==JO_PROTON_NATIVE_PLATFORM',
        )
        src = f"/* {DIRECT_MARKER}: Steam Proton keeps AppID 271590 but native patcher uses rgl unless overridden. */\n{src}"

    if DIRECT_MARKER not in src and MARKER not in src:
        direct_needle = 'Ic.patchMultiplayerWithProgress(e,n=>{re("patcher_setPhase",n)})'
        if direct_needle in src:
            anchor = "let Lc=!1,uf=!1;"
            if anchor not in src:
                raise PatchError(f"{file}: could not find patcher state anchor")
            src = src.replace(anchor, _index_direct_helper(permissions) + anchor, 1)
            src = src.replace(direct_needle, 'JO_patchMultiplayerWithProgress(e,n=>{re("patcher_setPhase",n)})', 1)
            status.details.append("direct native patcher hook")
        elif "app.asar.unpacked" in src and "gamePatcher.js" in src:
            src = f"/* {MARKER}: existing worker path redirect was accepted. */\n{src}"
        elif "gamePatcher.js" in src:
            src = _patch_worker_reference(src, status)

    if src != original:
        _validate_text(src, file)
        _write(file, src, dry_run=dry_run, status=status)
    return status


def _patch_worker_reference(src: str, status: PatchStatus) -> str:
    worker_needle = "gamePatcher.js"
    pos = src.find(worker_needle)
    while pos != -1:
        before = src.rfind("new ", 0, pos)
        worker_call = src.find(".Worker(", before)
        if before != -1 and worker_call != -1 and worker_call < pos:
            arg_start = worker_call + len(".Worker(")
            depth = 1
            quote = ""
            i = arg_start
            while i < len(src):
                ch = src[i]
                prev = src[i - 1] if i > 0 else ""
                if quote:
                    if ch == quote and prev != "\\":
                        quote = ""
                    i += 1
                    continue
                if ch in "\"'`":
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            original_arg = src[arg_start:i]
            if worker_needle in original_arg:
                replacement = '(()=>{const p=require("path"),f=require("fs"),q=p.join(process.resourcesPath,"app.asar.unpacked","dist","electron","main","gamePatcher.js");return f.existsSync(q)?q:p.resolve(__dirname,"gamePatcher.js")})()'
                status.details.append("worker path redirect")
                return f"/* {MARKER}: worker path redirects to app.asar.unpacked under Proton. */\n{src[:arg_start]}{replacement}{src[i:]}"
        pos = src.find(worker_needle, pos + len(worker_needle))
    raise PatchError("Could not find Worker(...gamePatcher.js...) in index.js")


def worker_adapter(permissions: str) -> str:
    values = _permissions(permissions)
    return f"""/* {MARKER}: Proton adapter for Majestic native patcher. */
import {{ parentPort }} from 'worker_threads';
import fs from 'fs';
import path from 'path';
import patcher from 'majestic-patcher';

const protonGtaPath = process.env.MAJESTIC_GTA_WIN_PATH || 'G:\\\\';
const protonPlatform = process.env.MAJESTIC_PROTON_PLATFORM || 'rgl';
const nativePlatform = process.env.MAJESTIC_PROTON_NATIVE_PLATFORM || (protonPlatform === 'steam' ? 'rgl' : protonPlatform);
const disableCefGpu = process.env.MAJESTIC_DISABLE_CEF_GPU !== '0';
const permissions = {values};

function isProtonRuntime() {{
  return process.platform === 'win32' && Boolean(process.env.STEAM_COMPAT_DATA_PATH || process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH || process.env.MAJESTIC_PROTON_PLATFORM || process.env.WINEPREFIX);
}}

function patchJsonFile(filePath, patcherFn) {{
  if (!filePath || !fs.existsSync(filePath)) return false;
  try {{
    const config = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    const nextConfig = patcherFn(config);
    if (!nextConfig) return false;
    fs.writeFileSync(filePath, JSON.stringify(nextConfig, null, 2));
    return true;
  }} catch (error) {{
    console.log('[LINUX-PROTON DEBUG] failed to patch json', {{ filePath, error }});
    return false;
  }}
}}

function patchPermissionCache(multiplayerPath) {{
  const cacheRoot = path.join(multiplayerPath || '', 'cache');
  if (!fs.existsSync(cacheRoot)) return;
  const data = Buffer.from([...permissions, 255]);
  for (const name of fs.readdirSync(cacheRoot)) {{
    const dir = path.join(cacheRoot, name);
    if (fs.existsSync(dir) && fs.lstatSync(dir).isDirectory()) fs.writeFileSync(path.join(dir, 'permissions'), data);
  }}
}}

function adaptLaunchConfigForProton(launchOptionsPath) {{
  if (!isProtonRuntime()) return;
  let multiplayerConfigPath = '';
  patchJsonFile(launchOptionsPath, (config) => {{
    let changed = false;
    if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== protonGtaPath) {{ config.gtaPath = protonGtaPath; changed = true; }}
    if (['steam', 'rgl', 'egs'].includes(nativePlatform) && config.gtaPlatform !== nativePlatform) {{ config.gtaPlatform = nativePlatform; changed = true; }}
    if (config.debug !== false) {{ config.debug = false; changed = true; }}
    if (disableCefGpu && config.cefUseHardwareAcceleration !== false) {{ config.cefUseHardwareAcceleration = false; changed = true; }}
    if (config.multiplayerPath && config.configFileName) {{ multiplayerConfigPath = path.join(config.multiplayerPath, config.configFileName); patchPermissionCache(config.multiplayerPath); }}
    return changed ? config : null;
  }});
  if (multiplayerConfigPath) patchJsonFile(multiplayerConfigPath, (config) => {{
    let changed = false;
    if (String(config.gtapath || '').startsWith('Z:\\\\') || String(config.gtapath || '') !== protonGtaPath) {{ config.gtapath = protonGtaPath; changed = true; }}
    if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== protonGtaPath) {{ config.gtaPath = protonGtaPath; changed = true; }}
    if (config.debug !== false) {{ config.debug = false; changed = true; }}
    if (disableCefGpu && config.cefUseHardwareAcceleration !== false) {{ config.cefUseHardwareAcceleration = false; changed = true; }}
    return changed ? config : null;
  }});
}}

parentPort.on('message', async (launchOptionsPath) => {{
  try {{
    adaptLaunchConfigForProton(launchOptionsPath);
    parentPort.postMessage(patcher.patchMultiplayer(launchOptionsPath));
  }} catch (error) {{
    parentPort.postMessage({{ success: false, error }});
  }}
}});
"""


def patch_worker(file: Path, *, dry_run: bool, permissions: str) -> PatchStatus:
    status = PatchStatus(file)
    text = worker_adapter(permissions)
    if file.exists() and _read(file) == text:
        return status
    _write(file, text, dry_run=dry_run, status=status)
    status.details.append("worker adapter")
    return status


def _validate_text(text: str, file: Path) -> None:
    if LEGACY_ARRAY_RE.search(text):
        raise PatchError(f"{file}: legacy platform array still lacks steam")
    if '"rgl","egs"' in text and '"steam","rgl","egs"' not in text:
        raise PatchError(f"{file}: old rgl/egs array remains without steam")


def patch_text(text: str) -> tuple[str, bool]:
    status = PatchStatus(Path("<memory>"))
    next_text = _fix_legacy_arrays(text, status)
    if next_text != text and MARKER not in next_text and INDEX_COMPAT_MARKER not in next_text:
        next_text = f"// {MARKER}\n{next_text}"
    _validate_text(next_text, Path("<memory>"))
    return next_text, next_text != text


def find_js_files(root: Path) -> list[Path]:
    root = root.expanduser()
    if root.is_file() and root.suffix.lower() == ".js":
        return [root]
    if not root.exists():
        return []
    ignored = {".git", "node_modules"}
    return sorted(path for path in root.rglob("*.js") if not any(part in ignored for part in path.parts))


def patch_source_tree(app_root: Path, *, dry_run: bool, permissions: str) -> list[PatchStatus]:
    return [
        patch_source_find_gta(app_root / "src" / "electron" / "main" / "utils" / "findGTA.js", dry_run=dry_run),
        patch_source_revalidate_gta(app_root / "src" / "electron" / "main" / "utils" / "revalidateGTA.js", dry_run=dry_run),
        patch_source_patcher(app_root / "src" / "electron" / "main" / "patcher.js", dry_run=dry_run, permissions=permissions),
        patch_source_game(app_root / "src" / "electron" / "main" / "modules" / "game.js", dry_run=dry_run),
    ]


def patch_js_tree(
    root: Path,
    *,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
    permissions: str = "1",
) -> PatchReport:
    targets = resolve_targets(root)
    statuses: list[PatchStatus] = []
    if logger:
        logger.info("Resolved JS patch target mode=%s app_root=%s", targets.mode, targets.app_root)
    try:
        if targets.mode == "source":
            statuses.extend(patch_source_tree(targets.app_root, dry_run=dry_run, permissions=permissions))
        else:
            _extract_asar(targets, dry_run=dry_run, logger=logger)
            index = targets.app_root / "dist" / "electron" / "main" / "index.js"
            worker = targets.unpacked_root / "dist" / "electron" / "main" / "gamePatcher.js"
            statuses.append(patch_index(index, dry_run=dry_run, permissions=permissions))
            statuses.append(patch_worker(worker, dry_run=dry_run, permissions=permissions))
            _repack_asar(targets, dry_run=dry_run, logger=logger)
    finally:
        _cleanup(targets, logger)
    failures = [error for status in statuses for error in status.errors]
    if failures:
        raise PatchError("; ".join(failures))
    if logger:
        for status in statuses:
            logger.debug("Patch status file=%s changed=%s details=%s", status.file, status.changed, status.details)
    return PatchReport(targets.mode, statuses)


def _state_for_files(files: list[Path]) -> dict[str, object]:
    legacy = [str(file) for file in files if LEGACY_ARRAY_RE.search(_read(file))]
    markers = {
        "source": any(SOURCE_MARKER in _read(file) for file in files),
        "index_compat": any(INDEX_COMPAT_MARKER in _read(file) for file in files),
        "direct": any(DIRECT_MARKER in _read(file) for file in files),
        "worker": any(MARKER in _read(file) for file in files),
    }
    steam_ready = [str(file) for file in files if all(token in _read(file) for token in ("steam", "rgl", "egs"))]
    return {"files": len(files), "legacy_without_steam": legacy, "steam_ready": steam_ready, "markers": markers}


def patch_state(root: Path) -> dict[str, object]:
    try:
        targets = resolve_targets(root)
    except PatchError:
        files = find_js_files(root)
        return {"mode": "unknown", **_state_for_files(files)}
    try:
        sections: dict[str, object] = {}
        if targets.mode == "asar":
            if targets.asar_path and targets.asar_path.exists():
                try:
                    _extract_asar(targets, dry_run=False, logger=None)
                    sections["asar"] = _state_for_files(find_js_files(targets.app_root))
                except Exception as exc:  # noqa: BLE001 - diagnostic output should not crash doctor
                    sections["asar_error"] = str(exc)
            if targets.unpacked_root.exists():
                sections["unpacked"] = _state_for_files(find_js_files(targets.unpacked_root))
            return {"mode": targets.mode, **sections}
        return {"mode": targets.mode, **_state_for_files(find_js_files(targets.app_root))}
    finally:
        _cleanup(targets)
