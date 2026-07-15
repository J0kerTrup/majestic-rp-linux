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
    if (config.protonRuntime !== true) {{ config.protonRuntime = true; changed = true; }}
    const protonLauncherPath = path.win32.join(protonGtaPath, 'GTAVLauncher.exe');
    if (config.protonLauncherPath !== protonLauncherPath) {{ config.protonLauncherPath = protonLauncherPath; changed = true; }}
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


def modern_worker_adapter(permissions: str) -> str:
    values = parse_permissions(permissions)
    return f"""/* {MARKER}: Proton adapter for Majestic utility-process native patcher. */
import {{ createRequire }} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const requireFromHere = createRequire(import.meta.url);
const parentPort = process.parentPort;
const protonGtaPath = process.env.MAJESTIC_GTA_WIN_PATH || 'G:\\\\';
const requestedPlatform = process.env.MAJESTIC_PROTON_PLATFORM || 'rgl';
const nativePlatform = process.env.MAJESTIC_PROTON_NATIVE_PLATFORM || (requestedPlatform === 'steam' ? 'rgl' : requestedPlatform);
const permissions = {values};

function patchJsonFile(filePath, patcherFn) {{
  if (!filePath || !fs.existsSync(filePath)) return false;
  const config = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  patcherFn(config);
  fs.writeFileSync(filePath, JSON.stringify(config, null, 2));
  return true;
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

function adaptLaunchConfigForProton(launchConfigPath) {{
  patchJsonFile(launchConfigPath, (config) => {{
    config.gtaPath = protonGtaPath;
    config.protonRuntime = true;
    config.protonLauncherPath = path.win32.join(protonGtaPath, 'GTAVLauncher.exe');
    // A rebuilt native patcher uses the fields above and retains the store.
    // Released binaries need the legacy platform fallback.
    if (!process.env.MAJESTIC_NATIVE_CPP_PATCHED && ['steam', 'rgl', 'egs'].includes(nativePlatform)) config.gtaPlatform = nativePlatform;
    config.debug = false;
    if (process.env.MAJESTIC_DISABLE_CEF_GPU !== '0') config.cefUseHardwareAcceleration = false;
    if (config.multiplayerPath) patchPermissionCache(config.multiplayerPath);
  }});
}}

if (!parentPort) {{
  process.stderr.write('patcherWorker: process.parentPort missing, exiting\\n');
  process.exit(2);
}}

parentPort.on('message', (event) => {{
  try {{
    const message = event.data;
    if (typeof message !== 'object' || message === null || typeof message.launchConfigPath !== 'string') {{
      parentPort.postMessage({{ success: false, error: 'ERR_WORKER_BAD_INPUT' }});
      return;
    }}
    adaptLaunchConfigForProton(message.launchConfigPath);
    const result = requireFromHere('majestic-patcher').patchMultiplayer(message.launchConfigPath);
    parentPort.postMessage({{
      success: Boolean(result?.success),
      error: typeof result?.error === 'string' ? result.error : '',
    }});
  }} catch (error) {{
    parentPort.postMessage({{ success: false, error: error instanceof Error ? error.message : String(error) }});
  }} finally {{
    setImmediate(() => process.exit(0));
  }}
}});
"""


def patch_worker(file: Path, *, dry_run: bool, permissions: str) -> PatchStatus:
    status = PatchStatus(file)
    current = read_text(file) if file.exists() else ""
    modern = file.name == "patcherWorker.js" or "process.parentPort" in current or "utility-process" in current
    text = modern_worker_adapter(permissions) if modern else worker_adapter(permissions)
    if file.exists() and read_text(file) == text:
        return status
    write_text(file, text, dry_run=dry_run, status=status)
    status.details.append("utility-process worker adapter" if modern else "worker adapter")
    return status
