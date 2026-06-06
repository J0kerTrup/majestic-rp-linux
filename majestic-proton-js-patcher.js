#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");
const childProcess = require("child_process");

const root = process.argv[2];
const permissions = process.argv[3] || "1,3,4";
if (!root) {
  console.error("Usage: majestic-proton-js-patcher.js <app-dir|resources-dir|app.asar|app.asar.unpacked> [permissions]");
  process.exit(2);
}

const marker = "MAJESTIC_PROTON_PATCH_V2";
const indexCompatMarker = "MAJESTIC_PROTON_INDEX_COMPAT_V4";
const directMarker = "MAJESTIC_PROTON_DIRECT_PATCH_V1";
const asarBin = process.env.ASAR_BIN || "asar";

function exists(file) {
  return fs.existsSync(file);
}

function isFile(file) {
  return exists(file) && fs.lstatSync(file).isFile();
}

function isDirectory(file) {
  return exists(file) && fs.lstatSync(file).isDirectory();
}

function read(file) {
  return fs.readFileSync(file, "utf8");
}

function write(file, data) {
  fs.writeFileSync(file, data);
}

function run(command, args) {
  const result = childProcess.spawnSync(command, args, {
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with status ${result.status}`);
  }
}

function resolveTargets(inputPath) {
  const resolvedRoot = path.resolve(inputPath);
  const appAsarFromRoot = path.join(resolvedRoot, "app.asar");
  const siblingAppAsar = path.join(path.dirname(resolvedRoot), "app.asar");
  const extractedIndexPath = path.join(resolvedRoot, "dist", "electron", "main", "index.js");

  if (isFile(resolvedRoot) && path.basename(resolvedRoot) === "app.asar") {
    const resourcesDir = path.dirname(resolvedRoot);
    const extractedRoot = fs.mkdtempSync(path.join(os.tmpdir(), "majestic-app-asar-"));
    return {
      mode: "asar",
      appRoot: extractedRoot,
      resourcesDir,
      asarPath: resolvedRoot,
      unpackedRoot: path.join(resourcesDir, "app.asar.unpacked"),
      cleanupRoot: extractedRoot,
    };
  }

  if (isDirectory(resolvedRoot) && isFile(appAsarFromRoot)) {
    const extractedRoot = fs.mkdtempSync(path.join(os.tmpdir(), "majestic-app-asar-"));
    return {
      mode: "asar",
      appRoot: extractedRoot,
      resourcesDir: resolvedRoot,
      asarPath: appAsarFromRoot,
      unpackedRoot: path.join(resolvedRoot, "app.asar.unpacked"),
      cleanupRoot: extractedRoot,
    };
  }

  if (isDirectory(resolvedRoot) && path.basename(resolvedRoot) === "app.asar.unpacked" && isFile(siblingAppAsar)) {
    const extractedRoot = fs.mkdtempSync(path.join(os.tmpdir(), "majestic-app-asar-"));
    return {
      mode: "asar",
      appRoot: extractedRoot,
      resourcesDir: path.dirname(resolvedRoot),
      asarPath: siblingAppAsar,
      unpackedRoot: resolvedRoot,
      cleanupRoot: extractedRoot,
    };
  }

  if (isFile(extractedIndexPath)) {
    return {
      mode: "extracted",
      appRoot: resolvedRoot,
      resourcesDir: path.dirname(resolvedRoot),
      asarPath: "",
      unpackedRoot: resolvedRoot,
      cleanupRoot: "",
    };
  }

  throw new Error(
    [
      `Could not locate Majestic app files under: ${resolvedRoot}`,
      "Pass one of these paths:",
      "  - resources directory containing app.asar",
      "  - resources/app.asar",
      "  - resources/app.asar.unpacked",
      "  - extracted app directory containing dist/electron/main/index.js",
    ].join("\n")
  );
}

function extractAsar(targets) {
  if (targets.mode !== "asar") return;
  run(asarBin, ["extract", targets.asarPath, targets.appRoot]);
}

function repackAsar(targets) {
  if (targets.mode !== "asar") return;
  const backupPath = `${targets.asarPath}.bak`;
  if (!exists(backupPath)) {
    fs.copyFileSync(targets.asarPath, backupPath);
    console.log(`Backup created: ${backupPath}`);
  }
  run(asarBin, ["pack", targets.appRoot, targets.asarPath]);
}

function cleanup(targets) {
  if (targets.cleanupRoot) {
    fs.rmSync(targets.cleanupRoot, { recursive: true, force: true });
  }
}

function patchIndex(indexPath) {
  if (!fs.existsSync(indexPath)) {
    throw new Error(`index.js not found: ${indexPath}`);
  }

  let src = read(indexPath);

  if (!src.includes(indexCompatMarker)) {
    let compatPatched = false;
    const findGtaNeedle = 'dB=async()=>{ft.info("[findGTA] Looking for Steam...");';
    if (src.includes(findGtaNeedle)) {
      src = src.replace(
        findGtaNeedle,
        'dB=async()=>{const JO_ENV_GTA=process.env.MAJESTIC_GTA_WIN_PATH,JO_ENV_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(JO_ENV_GTA&&["rgl","egs"].includes(JO_ENV_PLATFORM)&&dn(JO_ENV_GTA))return ft.info("[findGTA] using forced Proton GTA path",JO_ENV_GTA,JO_ENV_PLATFORM),[JO_ENV_GTA,JO_ENV_PLATFORM];ft.info("[findGTA] Looking for Steam...");'
      );
      compatPatched = true;
    }

    const findGtaNeedleCurrent = 'EO=async()=>{ht.info("[findGTA] Looking for Steam...");';
    if (src.includes(findGtaNeedleCurrent)) {
      src = src.replace(
        findGtaNeedleCurrent,
        'EO=async()=>{const JO_ENV_GTA=process.env.MAJESTIC_GTA_WIN_PATH,JO_ENV_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(JO_ENV_GTA&&["steam","rgl","egs"].includes(JO_ENV_PLATFORM)&&dn(JO_ENV_GTA))return ht.info("[findGTA] using forced Proton GTA path",JO_ENV_GTA,JO_ENV_PLATFORM),[JO_ENV_GTA,JO_ENV_PLATFORM];ht.info("[findGTA] Looking for Steam...");'
      );
      compatPatched = true;
    }

    const platformNeedle = 'Nf=(e,t)=>{const n=e?.replace("GTA5.exe","");';
    if (src.includes(platformNeedle)) {
      src = src.replace(
        platformNeedle,
        'Nf=(e,t)=>{const JO_FORCED_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(["rgl","egs"].includes(JO_FORCED_PLATFORM))return JO_FORCED_PLATFORM;const n=e?.replace("GTA5.exe","");'
      );
      compatPatched = true;
    }

    const platformNeedleCurrent = 'tf=(e,t)=>{const n=e?.replace("GTA5.exe","");';
    if (src.includes(platformNeedleCurrent)) {
      src = src.replace(
        platformNeedleCurrent,
        'tf=(e,t)=>{const JO_FORCED_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(["steam","rgl","egs"].includes(JO_FORCED_PLATFORM))return JO_FORCED_PLATFORM;const n=e?.replace("GTA5.exe","");'
      );
      compatPatched = true;
    }

    const fallbackNeedle = 'JO_fallbackPlayGTAV=e=>new Promise(t=>{try{const n=e,r=oe.join(n,"PlayGTAV.exe"),i={...process.env,SteamAppId:process.env.SteamAppId||"271590",SteamGameId:process.env.SteamGameId||"271590"};';
    if (src.includes(fallbackNeedle)) {
      src = src.replace(
        fallbackNeedle,
        'JO_fallbackPlayGTAV=e=>new Promise(t=>{try{if(process.env.MAJESTIC_PROTON_PLATFORM!=="steam")return P.info(JO_DBG,"fallback PlayGTAV disabled for non-Steam platform",{platform:process.env.MAJESTIC_PROTON_PLATFORM}),t(!1);const n=e,r=oe.join(n,"PlayGTAV.exe"),i={...process.env,SteamAppId:process.env.SteamAppId||"271590",SteamGameId:process.env.SteamGameId||"271590"};'
      );
      compatPatched = true;
    }

    if (compatPatched) {
      src = `/* ${indexCompatMarker}: force configured Rockstar/Epic platform and disable Steam fallback. */\n` + src;
      write(indexPath, src);
      src = read(indexPath);
    }
  }

  if (src.includes(directMarker) || src.includes(marker)) {
    return;
  }

  const directNeedle = 'Ic.patchMultiplayerWithProgress(e,n=>{re("patcher_setPhase",n)})';
  if (src.includes(directNeedle)) {
    const permissionValues = permissions
      .split(",")
      .map((x) => Number.parseInt(x.trim(), 10))
      .filter((x) => Number.isInteger(x) && x >= 0 && x <= 254);
    const helper = `/* ${directMarker}: adapt Majestic native patcher launch config under Proton. */
const JO_PROTON_PERMISSIONS=${JSON.stringify(permissionValues)},JO_PROTON_GTA_PATH=process.env.MAJESTIC_GTA_WIN_PATH||"G:\\\\",JO_PROTON_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM||"rgl",JO_PROTON_DISABLE_CEF_GPU=process.env.MAJESTIC_DISABLE_CEF_GPU!=="0";
function JO_isProtonRuntime(){return process.platform==="win32"&&!!(process.env.STEAM_COMPAT_DATA_PATH||process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH||process.env.MAJESTIC_PROTON_PLATFORM||process.env.WINEPREFIX)}
function JO_patchJsonFile(e,t){if(!e||!ue.existsSync(e))return!1;try{const n=JSON.parse(ue.readFileSync(e,"utf8")),r=t(n);return r?(ue.writeFileSync(e,JSON.stringify(r,null,2)),!0):!1}catch(n){return P.log("[LINUX-PROTON DEBUG] failed to patch json",{filePath:e,error:n}),!1}}
function JO_patchPermissionCache(e){const t=ae.join(e||"","cache");if(ue.existsSync(t)){const n=Buffer.from([...JO_PROTON_PERMISSIONS,255]);for(const r of ue.readdirSync(t)){const i=ae.join(t,r);ue.existsSync(i)&&ue.lstatSync(i).isDirectory()&&ue.writeFileSync(ae.join(i,"permissions"),n)}}}
function JO_adaptLaunchConfigForProton(e){if(!JO_isProtonRuntime())return;let t="";const n=JO_patchJsonFile(e,r=>{let i=!1;return(String(r.gtaPath||"").startsWith("Z:\\\\")||String(r.gtaPath||"")!==JO_PROTON_GTA_PATH)&&(P.info("[LINUX-PROTON DEBUG] rewriting gtaPath for native patcher",{from:r.gtaPath,to:JO_PROTON_GTA_PATH}),r.gtaPath=JO_PROTON_GTA_PATH,i=!0),["steam","rgl","egs"].includes(JO_PROTON_PLATFORM)&&r.gtaPlatform!==JO_PROTON_PLATFORM&&(P.info("[LINUX-PROTON DEBUG] selecting Proton platform for native patcher",{from:r.gtaPlatform,to:JO_PROTON_PLATFORM}),r.gtaPlatform=JO_PROTON_PLATFORM,i=!0),r.debug!==!1&&(r.debug=!1,i=!0),JO_PROTON_DISABLE_CEF_GPU&&r.cefUseHardwareAcceleration!==!1&&(r.cefUseHardwareAcceleration=!1,i=!0),r.multiplayerPath&&r.configFileName&&(t=ae.join(r.multiplayerPath,r.configFileName),JO_patchPermissionCache(r.multiplayerPath)),i?r:null});n&&P.info("[LINUX-PROTON DEBUG] launch config adapted for Proton");t&&JO_patchJsonFile(t,r=>{let i=!1;return(String(r.gtapath||"").startsWith("Z:\\\\")||String(r.gtapath||"")!==JO_PROTON_GTA_PATH)&&(r.gtapath=JO_PROTON_GTA_PATH,i=!0),((String(r.gtaPath||"").startsWith("Z:\\\\")||String(r.gtaPath||"")!==JO_PROTON_GTA_PATH)&&(r.gtaPath=JO_PROTON_GTA_PATH,i=!0)),r.debug!==!1&&(r.debug=!1,i=!0),JO_PROTON_DISABLE_CEF_GPU&&r.cefUseHardwareAcceleration!==!1&&(r.cefUseHardwareAcceleration=!1,i=!0),i?r:null})}
function JO_patchMultiplayerWithProgress(e,t){return JO_adaptLaunchConfigForProton(e),Ic.patchMultiplayerWithProgress(e,t)}
`;
    const anchor = "let Lc=!1,uf=!1;";
    if (!src.includes(anchor)) {
      throw new Error("Could not find patcher state anchor in index.js; app.asar was not patched");
    }
    src = src.replace(anchor, helper + anchor);
    src = src.replace(directNeedle, 'JO_patchMultiplayerWithProgress(e,n=>{re("patcher_setPhase",n)})');
    write(indexPath, src);
    return;
  }

  if (src.includes("app.asar.unpacked") && src.includes("gamePatcher.js")) {
    src = `/* ${marker}: existing worker path redirect was accepted. */\n` + src;
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
    throw new Error("Could not find Worker(...gamePatcher.js...) in index.js; app.asar was not patched");
  }

  src = `/* ${marker}: worker path redirects to app.asar.unpacked under Proton. */\n` + src;
  write(indexPath, src);
}

function patchWorker(workerPath) {
  const mainDir = path.dirname(workerPath);
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
      if (String(config.gtapath || '').startsWith('Z:\\\\') || String(config.gtapath || '') !== protonGtaPath) {
        config.gtapath = protonGtaPath;
        changed = true;
      }
      if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== protonGtaPath) {
        config.gtaPath = protonGtaPath;
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

const targets = resolveTargets(root);
const indexPath = path.join(targets.appRoot, "dist", "electron", "main", "index.js");
const workerPath = path.join(targets.unpackedRoot, "dist", "electron", "main", "gamePatcher.js");

try {
  extractAsar(targets);
  patchIndex(indexPath);
  patchWorker(workerPath);
  repackAsar(targets);
  console.log(`Majestic Proton JS patch applied (${targets.mode})`);
  console.log(`index.js: ${indexPath}`);
  console.log(`gamePatcher.js: ${workerPath}`);
} finally {
  cleanup(targets);
}
