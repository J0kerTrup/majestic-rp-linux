#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const root = process.argv[2];
const permissions = process.argv[3] || "1,3,4";
if (!root) {
  console.error("Usage: majestic-proton-js-patcher.js <extracted-app-dir> [permissions]");
  process.exit(2);
}

const mainDir = path.join(root, "dist", "electron", "main");
const indexPath = path.join(mainDir, "index.js");
const workerPath = path.join(mainDir, "gamePatcher.js");
const marker = "MAJESTIC_PROTON_PATCH_V2";
const workerHookMarker = "MAJESTIC_PROTON_WORKER_HOOK_V3";

function read(file) {
  return fs.readFileSync(file, "utf8");
}

function write(file, data) {
  fs.writeFileSync(file, data);
}

function patchIndex() {
  if (!fs.existsSync(indexPath)) {
    throw new Error(`index.js not found: ${indexPath}`);
  }

  let src = read(indexPath);
  if (src.includes(marker) || src.includes(workerHookMarker)) {
    return;
  }

  const workerHook = `/* ${marker}: ${workerHookMarker}; redirect gamePatcher.js workers to app.asar.unpacked under Proton. */
(() => {
  try {
    const path = require("path");
    const fs = require("fs");
    const workerThreads = require("worker_threads");
    if (!workerThreads || !workerThreads.Worker || workerThreads.Worker.__majesticProtonPatched) return;
    const OriginalWorker = workerThreads.Worker;
    const unpackedWorker = path.join(process.resourcesPath, "app.asar.unpacked", "dist", "electron", "main", "gamePatcher.js");
    const fallbackWorker = path.resolve(__dirname, "gamePatcher.js");
    const redirectWorker = (filename) => {
      const value = filename && filename.href ? filename.href : String(filename || "");
      if (!/gamePatcher\\.js(?:$|[?#])/.test(value)) return filename;
      return fs.existsSync(unpackedWorker) ? unpackedWorker : fallbackWorker;
    };
    class MajesticProtonWorker extends OriginalWorker {
      constructor(filename, options) {
        super(redirectWorker(filename), options);
      }
    }
    Object.defineProperty(MajesticProtonWorker, "__majesticProtonPatched", { value: true });
    workerThreads.Worker = MajesticProtonWorker;
  } catch (error) {
    console.log("[majestic-proton] worker redirect hook was not installed", error);
  }
})();
`;

  if (src.includes("app.asar.unpacked") && src.includes("gamePatcher.js")) {
    src = workerHook + src;
    write(indexPath, src);
    return;
  }

  let patched = false;
  const workerNeedle = "gamePatcher.js";
  let pos = src.indexOf(workerNeedle);
  while (pos !== -1) {
    const before = src.lastIndexOf("new ", pos);
    const workerCall = src.indexOf(".Worker(", before);
    if (before !== -1 && workerCall !== -1 && workerCall < pos) {
      const argStart = workerCall + ".Worker(".length;
      let depth = 1;
      let i = argStart;
      let quote = "";
      for (; i < src.length; i++) {
        const ch = src[i];
        const prev = src[i - 1];
        if (quote) {
          if (ch === quote && prev !== "\\") quote = "";
          continue;
        }
        if (ch === "\"" || ch === "'" || ch === "`") {
          quote = ch;
          continue;
        }
        if (ch === "(") depth++;
        if (ch === ")") depth--;
        if (depth === 0) break;
      }
      const originalArg = src.slice(argStart, i);
      if (originalArg.includes(workerNeedle)) {
        const replacement = `(()=>{const p=require("path"),f=require("fs"),q=p.join(process.resourcesPath,"app.asar.unpacked","dist","electron","main","gamePatcher.js");return f.existsSync(q)?q:p.resolve(__dirname,"gamePatcher.js")})()`;
        src = src.slice(0, argStart) + replacement + src.slice(i);
        patched = true;
        break;
      }
    }
    pos = src.indexOf(workerNeedle, pos + workerNeedle.length);
  }

  if (!patched) {
    src = workerHook + src;
    write(indexPath, src);
    console.warn("Could not rewrite Worker(...gamePatcher.js...) directly; installed runtime Worker redirect hook instead");
    return;
  }

  src = workerHook + src;
  write(indexPath, src);
}

function patchWorker() {
  fs.mkdirSync(mainDir, { recursive: true });
  const permissionValues = permissions
    .split(",")
    .map((x) => Number.parseInt(x.trim(), 10))
    .filter((x) => Number.isInteger(x) && x >= 0 && x <= 254);

  const worker = `/* ${marker}: Proton adapter for Majestic native patcher. */
import { parentPort } from 'worker_threads';
import fs from 'fs';
import path from 'path';
import patcher from 'majestic-patcher';

const protonGtaPath = process.env.MAJESTIC_GTA_WIN_PATH || 'G:\\\\';
const protonPlatform = process.env.MAJESTIC_PROTON_PLATFORM || 'rgl';
const disableCefGpu = process.env.MAJESTIC_DISABLE_CEF_GPU !== '0';
const permissions = ${JSON.stringify(permissionValues)};

function isProtonRuntime() {
  return process.platform === 'win32' && Boolean(
    process.env.STEAM_COMPAT_DATA_PATH ||
    process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH ||
    process.env.MAJESTIC_PROTON_PLATFORM ||
    process.env.WINEPREFIX
  );
}

function patchJsonFile(filePath, patcherFn) {
  if (!filePath || !fs.existsSync(filePath)) return false;
  try {
    const config = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    const nextConfig = patcherFn(config);
    if (!nextConfig) return false;
    fs.writeFileSync(filePath, JSON.stringify(nextConfig, null, 2));
    return true;
  } catch (error) {
    console.log('[LINUX-PROTON DEBUG] failed to patch json', { filePath, error });
    return false;
  }
}

function patchPermissionCache(multiplayerPath) {
  const cacheRoot = path.join(multiplayerPath || '', 'cache');
  if (!fs.existsSync(cacheRoot)) return;
  const data = Buffer.from([...permissions, 255]);
  for (const name of fs.readdirSync(cacheRoot)) {
    const dir = path.join(cacheRoot, name);
    if (fs.existsSync(dir) && fs.lstatSync(dir).isDirectory()) {
      fs.writeFileSync(path.join(dir, 'permissions'), data);
    }
  }
}

function adaptLaunchConfigForProton(launchOptionsPath) {
  if (!isProtonRuntime()) return;

  let multiplayerConfigPath = '';
  const launchConfigChanged = patchJsonFile(launchOptionsPath, (config) => {
    let changed = false;
    if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== protonGtaPath) {
      console.log('[LINUX-PROTON DEBUG] rewriting gtaPath for native patcher', { from: config.gtaPath, to: protonGtaPath });
      config.gtaPath = protonGtaPath;
      changed = true;
    }
    if (['steam', 'rgl', 'egs'].includes(protonPlatform) && config.gtaPlatform !== protonPlatform) {
      console.log('[LINUX-PROTON DEBUG] selecting Proton platform for native patcher', { from: config.gtaPlatform, to: protonPlatform });
      config.gtaPlatform = protonPlatform;
      changed = true;
    }
    if (config.debug !== false) {
      config.debug = false;
      changed = true;
    }
    if (disableCefGpu && config.cefUseHardwareAcceleration !== false) {
      config.cefUseHardwareAcceleration = false;
      changed = true;
    }
    if (config.multiplayerPath && config.configFileName) {
      multiplayerConfigPath = path.join(config.multiplayerPath, config.configFileName);
      patchPermissionCache(config.multiplayerPath);
    }
    return changed ? config : null;
  });

  if (launchConfigChanged) console.log('[LINUX-PROTON DEBUG] launch config adapted for Proton');

  if (multiplayerConfigPath) {
    const multiplayerConfigChanged = patchJsonFile(multiplayerConfigPath, (config) => {
      let changed = false;
      if (config.debug !== false) {
        config.debug = false;
        changed = true;
      }
      if (disableCefGpu && config.cefUseHardwareAcceleration !== false) {
        config.cefUseHardwareAcceleration = false;
        changed = true;
      }
      return changed ? config : null;
    });
    if (multiplayerConfigChanged) {
      console.log('[LINUX-PROTON DEBUG] multiplayer config adapted for Proton', multiplayerConfigPath);
    }
  }
}

parentPort.on('message', async (launchOptionsPath) => {
  try {
    adaptLaunchConfigForProton(launchOptionsPath);
    const patchResult = patcher.patchMultiplayer(launchOptionsPath);
    parentPort.postMessage(patchResult);
  } catch (error) {
    parentPort.postMessage({ success: false, error });
  }
});
`;

  write(workerPath, worker);
}

patchIndex();
patchWorker();
console.log("Majestic Proton JS patch applied");
