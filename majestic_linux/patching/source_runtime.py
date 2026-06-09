from __future__ import annotations

from pathlib import Path

from ..core.errors import PatchError
from .common import SOURCE_MARKER, PatchStatus, permissions as parse_permissions, read_text, write_text


def _ensure_source_imports(src: str) -> str:
    next_src = src
    if "import fs from 'fs';" not in next_src and 'import fs from "fs";' not in next_src:
        next_src = "import fs from 'fs';\n" + next_src
    if "import path from 'path';" not in next_src and 'import path from "path";' not in next_src:
        next_src = "import path from 'path';\n" + next_src
    if "import childProcess from 'child_process';" not in next_src and 'import childProcess from "child_process";' not in next_src:
        next_src = "import childProcess from 'child_process';\n" + next_src
    return next_src

def _source_patcher_helper(permissions: str) -> str:
    values = parse_permissions(permissions)
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
    src = read_text(file)
    if SOURCE_MARKER in src or "JO_adaptLaunchConfigForProton" in src:
        return status
    call_needle = "const result = await patcher.patchMultiplayerWithProgress(launchConfigPath, (event) => {"
    insert_needle = "export const requestPatcherCancel = () => {"
    if call_needle not in src or insert_needle not in src:
        raise PatchError(f"{file}: could not find source patcher anchors")
    src = _ensure_source_imports(src)
    src = src.replace(insert_needle, _source_patcher_helper(permissions) + insert_needle, 1)
    src = src.replace(call_needle, f"JO_adaptLaunchConfigForProton(launchConfigPath);\n        {call_needle}", 1)
    write_text(file, src, dry_run=dry_run, status=status)
    return status


def patch_source_game(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    src = read_text(file)
    marker = "MAJESTIC_PROTON_SOURCE_GAME_PATCH_V1"
    if marker in src:
        return status
    next_src = src.replace("    async init() {\n        this.#platform;", "    async init() {\n        this.#platform = await regeditStore.get('gta_v_platform');")
    next_src = next_src.replace("const launchConfigSaved = saveLaunchConfig(launchConfig, tempPath);", "const launchConfigSaved = await saveLaunchConfig(launchConfig, tempPath);")
    if next_src != src:
        next_src = f"/* {marker}: keep GTA platform in memory and await launch config writes. */\n{next_src}"
        write_text(file, next_src, dry_run=dry_run, status=status)
    return status
