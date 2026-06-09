from __future__ import annotations

from pathlib import Path

from .common import MARKER, PatchStatus, permissions as parse_permissions, read_text, write_text

def worker_adapter(permissions: str) -> str:
    values = parse_permissions(permissions)
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
    if file.exists() and read_text(file) == text:
        return status
    write_text(file, text, dry_run=dry_run, status=status)
    status.details.append("worker adapter")
    return status
