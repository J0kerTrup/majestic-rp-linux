#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");
const childProcess = require("child_process");

const scriptDir = __dirname;
const logDir = path.join(scriptDir, "logs");
const logFile = path.join(logDir, "majestic-proton.log");
const logMaxBytes = 10 * 1024 * 1024;
const logMaxFiles = 10;

function initLogging() {
  fs.mkdirSync(logDir, { recursive: true });
  if (fs.existsSync(logFile)) {
    const size = fs.statSync(logFile).size;
    if (size >= logMaxBytes) {
      const lastRotated = `${logFile}.${logMaxFiles - 1}`;
      if (fs.existsSync(lastRotated)) fs.rmSync(lastRotated, { force: true });
      for (let i = logMaxFiles - 2; i >= 1; i--) {
        const current = `${logFile}.${i}`;
        if (fs.existsSync(current)) fs.renameSync(current, `${logFile}.${i + 1}`);
      }
      fs.renameSync(logFile, `${logFile}.1`);
    }
  }
  fs.closeSync(fs.openSync(logFile, "a"));
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function colorFor(level) {
  if (!process.stderr.isTTY) return "";
  return {
    INFO: "\x1b[34m",
    DEBUG: "\x1b[90m",
    SUCCESS: "\x1b[32m",
    WARN: "\x1b[33m",
    ERROR: "\x1b[31m",
  }[level] || "";
}

function formatData(data) {
  if (data === undefined || data === null || data === "") return "";
  if (data instanceof Error) {
    return `name=${data.name} message=${data.message} stack=${JSON.stringify(data.stack || "")}`;
  }
  if (typeof data === "string") return data;
  return JSON.stringify(data);
}

function log(level, moduleName, message, data) {
  const extra = formatData(data);
  const line = `[${timestamp()}] [${level}] [${moduleName}] ${message}${extra ? ` | ${extra}` : ""}`;
  fs.appendFileSync(logFile, `${line}\n`);
  const color = colorFor(level);
  const reset = color ? "\x1b[0m" : "";
  process.stderr.write(`${color}${line}${reset}\n`);
}

const logInfo = (moduleName, message, data) => log("INFO", moduleName, message, data);
const logDebug = (moduleName, message, data) => log("DEBUG", moduleName, message, data);
const logWarn = (moduleName, message, data) => log("WARN", moduleName, message, data);
const logError = (moduleName, message, data) => log("ERROR", moduleName, message, data);
const logSuccess = (moduleName, message, data) => log("SUCCESS", moduleName, message, data);

initLogging();

const root = process.argv[2];
const permissions = process.argv[3] || "1,3,4";
if (!root) {
  logError("Patcher", "Missing required root argument", {
    exitCode: 2,
    command: process.argv.join(" "),
    usage: "majestic-proton-js-patcher.js <app-dir|resources-dir|app.asar|app.asar.unpacked> [permissions]",
  });
  process.exit(2);
}

const marker = "MAJESTIC_PROTON_PATCH_V2";
const indexCompatMarker = "MAJESTIC_PROTON_INDEX_COMPAT_V4";
const directMarker = "MAJESTIC_PROTON_DIRECT_PATCH_V1";
const sourceMarker = "MAJESTIC_PROTON_SOURCE_PATCH_V1";
const asarBin = process.env.ASAR_BIN || "asar";

logInfo("Patcher", "Starting Majestic Proton JS patcher", {
  root,
  permissions,
  scriptDir,
  logFile,
  node: process.version,
  platform: process.platform,
  asarBin,
});
logDebug("Environment", "Relevant environment values", {
  ASAR_BIN: process.env.ASAR_BIN,
  STEAM_COMPAT_DATA_PATH: process.env.STEAM_COMPAT_DATA_PATH,
  STEAM_COMPAT_CLIENT_INSTALL_PATH: process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH,
  MAJESTIC_GTA_WIN_PATH: process.env.MAJESTIC_GTA_WIN_PATH,
  MAJESTIC_PROTON_PLATFORM: process.env.MAJESTIC_PROTON_PLATFORM,
  MAJESTIC_DISABLE_CEF_GPU: process.env.MAJESTIC_DISABLE_CEF_GPU,
  WINEPREFIX: process.env.WINEPREFIX,
});

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
  logDebug("Files", "Reading text file", { file });
  return fs.readFileSync(file, "utf8");
}

function write(file, data) {
  logInfo("Files", "Writing text file", { file, bytes: Buffer.byteLength(data, "utf8") });
  fs.writeFileSync(file, data);
  logSuccess("Files", "Text file written", { file });
}

function commandParts(command) {
  if (exists(command)) return [command];
  return command.trim().split(/\s+/);
}

function run(command, args) {
  const [cmd, ...preArgs] = commandParts(command);
  logInfo("Command", "Executing command", { command: `${command} ${args.join(" ")}`, args });
  const result = childProcess.spawnSync(cmd, [...preArgs, ...args], {
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  if (result.error) {
    logError("Command", "Command failed to start", { command, args, error: result.error });
    throw result.error;
  }
  if (result.status !== 0) {
    logError("Command", "Command exited with non-zero status", {
      command: `${command} ${args.join(" ")}`,
      exitCode: result.status,
      signal: result.signal,
    });
    throw new Error(`${command} ${args.join(" ")} failed with status ${result.status}`);
  }
  logSuccess("Command", "Command completed successfully", { command: `${command} ${args.join(" ")}`, exitCode: result.status });
}

function resolveTargets(inputPath) {
  const resolvedRoot = path.resolve(inputPath);
  const appAsarFromRoot = path.join(resolvedRoot, "app.asar");
  const siblingAppAsar = path.join(path.dirname(resolvedRoot), "app.asar");
  const extractedIndexPath = path.join(resolvedRoot, "dist", "electron", "main", "index.js");
  const sourceFindGtaPath = path.join(resolvedRoot, "src", "electron", "main", "utils", "findGTA.js");
  const sourcePatcherPath = path.join(resolvedRoot, "src", "electron", "main", "patcher.js");

  logInfo("Patcher", "Resolving patch targets", {
    inputPath,
    resolvedRoot,
    appAsarFromRoot,
    siblingAppAsar,
    extractedIndexPath,
    sourceFindGtaPath,
    sourcePatcherPath,
  });

  if (isFile(sourceFindGtaPath) && isFile(sourcePatcherPath)) {
    const targets = {
      mode: "source",
      appRoot: resolvedRoot,
      resourcesDir: path.dirname(resolvedRoot),
      asarPath: "",
      unpackedRoot: resolvedRoot,
      cleanupRoot: "",
    };
    logSuccess("Patcher", "Resolved recovered source tree target", targets);
    return targets;
  }

  if (isFile(resolvedRoot) && path.basename(resolvedRoot) === "app.asar") {
    const resourcesDir = path.dirname(resolvedRoot);
    const extractedRoot = fs.mkdtempSync(path.join(os.tmpdir(), "majestic-app-asar-"));
    const targets = {
      mode: "asar",
      appRoot: extractedRoot,
      resourcesDir,
      asarPath: resolvedRoot,
      unpackedRoot: path.join(resourcesDir, "app.asar.unpacked"),
      cleanupRoot: extractedRoot,
    };
    logSuccess("Patcher", "Resolved app.asar file target", targets);
    return targets;
  }

  if (isDirectory(resolvedRoot) && isFile(appAsarFromRoot)) {
    const extractedRoot = fs.mkdtempSync(path.join(os.tmpdir(), "majestic-app-asar-"));
    const targets = {
      mode: "asar",
      appRoot: extractedRoot,
      resourcesDir: resolvedRoot,
      asarPath: appAsarFromRoot,
      unpackedRoot: path.join(resolvedRoot, "app.asar.unpacked"),
      cleanupRoot: extractedRoot,
    };
    logSuccess("Patcher", "Resolved resources directory target", targets);
    return targets;
  }

  if (isDirectory(resolvedRoot) && path.basename(resolvedRoot) === "app.asar.unpacked" && isFile(siblingAppAsar)) {
    const extractedRoot = fs.mkdtempSync(path.join(os.tmpdir(), "majestic-app-asar-"));
    const targets = {
      mode: "asar",
      appRoot: extractedRoot,
      resourcesDir: path.dirname(resolvedRoot),
      asarPath: siblingAppAsar,
      unpackedRoot: resolvedRoot,
      cleanupRoot: extractedRoot,
    };
    logSuccess("Patcher", "Resolved app.asar.unpacked target with sibling app.asar", targets);
    return targets;
  }

  if (isFile(extractedIndexPath)) {
    const targets = {
      mode: "extracted",
      appRoot: resolvedRoot,
      resourcesDir: path.dirname(resolvedRoot),
      asarPath: "",
      unpackedRoot: resolvedRoot,
      cleanupRoot: "",
    };
    logSuccess("Patcher", "Resolved extracted app directory target", targets);
    return targets;
  }

  logError("Patcher", "Could not locate Majestic app files", { resolvedRoot });
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
  if (targets.mode !== "asar") {
    logDebug("Patcher", "ASAR extraction skipped for extracted target", targets);
    return;
  }
  logInfo("Patcher", "Extracting app.asar", { asarPath: targets.asarPath, appRoot: targets.appRoot, asarBin });
  run(asarBin, ["extract", targets.asarPath, targets.appRoot]);
  logSuccess("Patcher", "app.asar extracted", { appRoot: targets.appRoot });
}

function repackAsar(targets) {
  if (targets.mode !== "asar") {
    logDebug("Patcher", "ASAR repack skipped for extracted target", targets);
    return;
  }
  const backupPath = `${targets.asarPath}.bak`;
  if (!exists(backupPath)) {
    logInfo("Files", "Creating app.asar backup", { source: targets.asarPath, backup: backupPath });
    fs.copyFileSync(targets.asarPath, backupPath);
    logSuccess("Files", "app.asar backup created", { backup: backupPath });
  } else {
    logDebug("Files", "app.asar backup already exists", { backup: backupPath });
  }
  logInfo("Patcher", "Packing patched app.asar", { appRoot: targets.appRoot, asarPath: targets.asarPath, asarBin });
  run(asarBin, ["pack", targets.appRoot, targets.asarPath]);
  logSuccess("Patcher", "Patched app.asar packed", { asarPath: targets.asarPath });
}

function cleanup(targets) {
  if (targets.cleanupRoot) {
    logInfo("Files", "Removing temporary extraction directory", { directory: targets.cleanupRoot });
    fs.rmSync(targets.cleanupRoot, { recursive: true, force: true });
    logSuccess("Files", "Temporary extraction directory removed", { directory: targets.cleanupRoot });
  } else {
    logDebug("Files", "Cleanup skipped because no temporary directory was created");
  }
}

function sourcePermissionValues() {
  return permissions
    .split(",")
    .map((x) => Number.parseInt(x.trim(), 10))
    .filter((x) => Number.isInteger(x) && x >= 0 && x <= 254);
}

function ensureSourceImports(src) {
  let next = src;
  if (!next.includes("import fs from 'fs';") && !next.includes('import fs from "fs";')) {
    next = "import fs from 'fs';\n" + next;
  }
  if (!next.includes("import path from 'path';") && !next.includes('import path from "path";')) {
    next = "import path from 'path';\n" + next;
  }
  return next;
}

function patchSourceFindGta(filePath) {
  logInfo("Patcher", "Patching recovered source findGTA.js", { filePath });
  let src = read(filePath);
  if (src.includes(sourceMarker)) {
    logDebug("Patcher", "Source findGTA.js patch marker already present", { marker: sourceMarker });
    return;
  }

  const findNeedle = "export const findGTA = async () => {";
  const platformNeedle = "export const findValidGTAPlatform = (gtaPath, potentialPlatform) => {";
  if (!src.includes(findNeedle) || !src.includes(platformNeedle)) {
    throw new Error("Could not find source findGTA patch anchors");
  }

  src = src.replace(
    findNeedle,
    `${findNeedle}
    const JO_ENV_GTA = process.env.MAJESTIC_GTA_WIN_PATH;
    const JO_ENV_PLATFORM = process.env.MAJESTIC_PROTON_PLATFORM;
    if (JO_ENV_GTA && ['steam', 'rgl', 'egs'].includes(JO_ENV_PLATFORM) && checkForValidGTAPath(JO_ENV_GTA)) {
        log.info('[findGTA] using forced Proton GTA path', JO_ENV_GTA, JO_ENV_PLATFORM);
        return [JO_ENV_GTA, JO_ENV_PLATFORM];
    }`
  );
  src = src.replace(
    platformNeedle,
    `${platformNeedle}
    const JO_FORCED_PLATFORM = process.env.MAJESTIC_PROTON_PLATFORM;
    if (['steam', 'rgl', 'egs'].includes(JO_FORCED_PLATFORM)) return JO_FORCED_PLATFORM;`
  );
  src = `/* ${sourceMarker}: force configured Proton GTA path and platform in recovered source tree. */\n` + src;
  write(filePath, src);
  logSuccess("Patcher", "Recovered source findGTA.js patched", { filePath });
}

function patchSourcePatcher(filePath) {
  logInfo("Patcher", "Patching recovered source patcher.js", { filePath });
  let src = read(filePath);
  if (src.includes(sourceMarker)) {
    logDebug("Patcher", "Source patcher.js patch marker already present", { marker: sourceMarker });
    return;
  }

  const callNeedle = "const result = await patcher.patchMultiplayerWithProgress(launchConfigPath, (event) => {";
  if (!src.includes(callNeedle)) {
    throw new Error("Could not find source patcher native call anchor");
  }

  src = ensureSourceImports(src);
  const helper = `/* ${sourceMarker}: adapt Majestic native patcher launch config under Proton. */
const JO_PROTON_PERMISSIONS = ${JSON.stringify(sourcePermissionValues())};
const JO_PROTON_GTA_PATH = process.env.MAJESTIC_GTA_WIN_PATH || 'G:\\\\';
const JO_PROTON_PLATFORM = process.env.MAJESTIC_PROTON_PLATFORM || 'rgl';
const JO_PROTON_DISABLE_CEF_GPU = process.env.MAJESTIC_DISABLE_CEF_GPU !== '0';

function JO_isProtonRuntime() {
    return process.platform === 'win32' && Boolean(
        process.env.STEAM_COMPAT_DATA_PATH ||
        process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH ||
        process.env.MAJESTIC_PROTON_PLATFORM ||
        process.env.WINEPREFIX
    );
}

function JO_patchJsonFile(filePath, patcherFn) {
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

function JO_patchPermissionCache(multiplayerPath) {
    const cacheRoot = path.join(multiplayerPath || '', 'cache');
    if (!fs.existsSync(cacheRoot)) return;
    const data = Buffer.from([...JO_PROTON_PERMISSIONS, 255]);
    for (const name of fs.readdirSync(cacheRoot)) {
        const dir = path.join(cacheRoot, name);
        if (fs.existsSync(dir) && fs.lstatSync(dir).isDirectory()) {
            fs.writeFileSync(path.join(dir, 'permissions'), data);
        }
    }
}

function JO_adaptLaunchConfigForProton(launchOptionsPath) {
    if (!JO_isProtonRuntime()) return;

    let multiplayerConfigPath = '';
    const launchConfigChanged = JO_patchJsonFile(launchOptionsPath, (config) => {
        let changed = false;
        if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== JO_PROTON_GTA_PATH) {
            config.gtaPath = JO_PROTON_GTA_PATH;
            changed = true;
        }
        if (['steam', 'rgl', 'egs'].includes(JO_PROTON_PLATFORM) && config.gtaPlatform !== JO_PROTON_PLATFORM) {
            config.gtaPlatform = JO_PROTON_PLATFORM;
            changed = true;
        }
        if (config.debug !== false) {
            config.debug = false;
            changed = true;
        }
        if (JO_PROTON_DISABLE_CEF_GPU && config.cefUseHardwareAcceleration !== false) {
            config.cefUseHardwareAcceleration = false;
            changed = true;
        }
        if (config.multiplayerPath && config.configFileName) {
            multiplayerConfigPath = path.join(config.multiplayerPath, config.configFileName);
            JO_patchPermissionCache(config.multiplayerPath);
        }
        return changed ? config : null;
    });

    if (launchConfigChanged) console.log('[LINUX-PROTON DEBUG] launch config adapted for Proton');

    if (multiplayerConfigPath) {
        JO_patchJsonFile(multiplayerConfigPath, (config) => {
            let changed = false;
            if (String(config.gtapath || '').startsWith('Z:\\\\') || String(config.gtapath || '') !== JO_PROTON_GTA_PATH) {
                config.gtapath = JO_PROTON_GTA_PATH;
                changed = true;
            }
            if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== JO_PROTON_GTA_PATH) {
                config.gtaPath = JO_PROTON_GTA_PATH;
                changed = true;
            }
            if (config.debug !== false) {
                config.debug = false;
                changed = true;
            }
            if (JO_PROTON_DISABLE_CEF_GPU && config.cefUseHardwareAcceleration !== false) {
                config.cefUseHardwareAcceleration = false;
                changed = true;
            }
            return changed ? config : null;
        });
    }
}

`;

  const insertNeedle = "export const requestPatcherCancel = () => {";
  if (!src.includes(insertNeedle)) {
    throw new Error("Could not find source patcher helper insertion anchor");
  }
  src = src.replace(insertNeedle, helper + insertNeedle);
  src = src.replace(callNeedle, `JO_adaptLaunchConfigForProton(launchConfigPath);\n        ${callNeedle}`);
  write(filePath, src);
  logSuccess("Patcher", "Recovered source patcher.js patched", { filePath, permissionValues: sourcePermissionValues() });
}

function patchSourceTree(appRoot) {
  patchSourceFindGta(path.join(appRoot, "src", "electron", "main", "utils", "findGTA.js"));
  patchSourcePatcher(path.join(appRoot, "src", "electron", "main", "patcher.js"));
}

function patchIndex(indexPath) {
  logInfo("Patcher", "Patching Majestic index.js", { indexPath });
  if (!fs.existsSync(indexPath)) {
    logError("Patcher", "index.js not found", { indexPath });
    throw new Error(`index.js not found: ${indexPath}`);
  }

  let src = read(indexPath);
  logDebug("Patcher", "Loaded index.js", {
    indexPath,
    bytes: Buffer.byteLength(src, "utf8"),
    hasIndexCompatMarker: src.includes(indexCompatMarker),
    hasDirectMarker: src.includes(directMarker),
    hasWorkerMarker: src.includes(marker),
  });

  if (!src.includes(indexCompatMarker)) {
    let compatPatched = false;
    const findGtaNeedle = 'dB=async()=>{ft.info("[findGTA] Looking for Steam...");';
    if (src.includes(findGtaNeedle)) {
      logDebug("Patcher", "Applying legacy findGTA compatibility patch", { needle: findGtaNeedle });
      src = src.replace(
        findGtaNeedle,
        'dB=async()=>{const JO_ENV_GTA=process.env.MAJESTIC_GTA_WIN_PATH,JO_ENV_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(JO_ENV_GTA&&["steam","rgl","egs"].includes(JO_ENV_PLATFORM)&&dn(JO_ENV_GTA))return ft.info("[findGTA] using forced Proton GTA path",JO_ENV_GTA,JO_ENV_PLATFORM),[JO_ENV_GTA,JO_ENV_PLATFORM];ft.info("[findGTA] Looking for Steam...");'
      );
      compatPatched = true;
    }

    const findGtaNeedleCurrent = 'EO=async()=>{ht.info("[findGTA] Looking for Steam...");';
    if (src.includes(findGtaNeedleCurrent)) {
      logDebug("Patcher", "Applying current findGTA compatibility patch", { needle: findGtaNeedleCurrent });
      src = src.replace(
        findGtaNeedleCurrent,
        'EO=async()=>{const JO_ENV_GTA=process.env.MAJESTIC_GTA_WIN_PATH,JO_ENV_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(JO_ENV_GTA&&["steam","rgl","egs"].includes(JO_ENV_PLATFORM)&&dn(JO_ENV_GTA))return ht.info("[findGTA] using forced Proton GTA path",JO_ENV_GTA,JO_ENV_PLATFORM),[JO_ENV_GTA,JO_ENV_PLATFORM];ht.info("[findGTA] Looking for Steam...");'
      );
      compatPatched = true;
    }

    const platformNeedle = 'Nf=(e,t)=>{const n=e?.replace("GTA5.exe","");';
    if (src.includes(platformNeedle)) {
      logDebug("Patcher", "Applying legacy platform detection patch", { needle: platformNeedle });
      src = src.replace(
        platformNeedle,
        'Nf=(e,t)=>{const JO_FORCED_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(["steam","rgl","egs"].includes(JO_FORCED_PLATFORM))return JO_FORCED_PLATFORM;const n=e?.replace("GTA5.exe","");'
      );
      compatPatched = true;
    }

    const platformNeedleCurrent = 'tf=(e,t)=>{const n=e?.replace("GTA5.exe","");';
    if (src.includes(platformNeedleCurrent)) {
      logDebug("Patcher", "Applying current platform detection patch", { needle: platformNeedleCurrent });
      src = src.replace(
        platformNeedleCurrent,
        'tf=(e,t)=>{const JO_FORCED_PLATFORM=process.env.MAJESTIC_PROTON_PLATFORM;if(["steam","rgl","egs"].includes(JO_FORCED_PLATFORM))return JO_FORCED_PLATFORM;const n=e?.replace("GTA5.exe","");'
      );
      compatPatched = true;
    }

    const fallbackNeedle = 'JO_fallbackPlayGTAV=e=>new Promise(t=>{try{const n=e,r=oe.join(n,"PlayGTAV.exe"),i={...process.env,SteamAppId:process.env.SteamAppId||"271590",SteamGameId:process.env.SteamGameId||"271590"};';
    if (src.includes(fallbackNeedle)) {
      logDebug("Patcher", "Applying Steam fallback compatibility patch", { needle: fallbackNeedle });
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
      logSuccess("Patcher", "index.js compatibility patches applied", { indexPath });
    } else {
      logWarn("Patcher", "No known compatibility needles were found in index.js", { indexPath });
    }
  } else {
    logDebug("Patcher", "index.js compatibility marker already present", { marker: indexCompatMarker });
  }

  if (src.includes(directMarker) || src.includes(marker)) {
    logSuccess("Patcher", "index.js already contains Proton patch marker", {
      hasDirectMarker: src.includes(directMarker),
      hasWorkerMarker: src.includes(marker),
    });
    return;
  }

  const directNeedle = 'Ic.patchMultiplayerWithProgress(e,n=>{re("patcher_setPhase",n)})';
  if (src.includes(directNeedle)) {
    logInfo("Patcher", "Applying direct native patcher hook", { needle: directNeedle, permissions });
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
      logError("Patcher", "Direct patch anchor was not found", { anchor });
      throw new Error("Could not find patcher state anchor in index.js; app.asar was not patched");
    }
    src = src.replace(anchor, helper + anchor);
    src = src.replace(directNeedle, 'JO_patchMultiplayerWithProgress(e,n=>{re("patcher_setPhase",n)})');
    write(indexPath, src);
    logSuccess("Patcher", "Direct native patcher hook applied", { indexPath, permissionValues });
    return;
  }

  if (src.includes("app.asar.unpacked") && src.includes("gamePatcher.js")) {
    logInfo("Patcher", "Accepting existing app.asar.unpacked worker path redirect", { indexPath });
    src = `/* ${marker}: existing worker path redirect was accepted. */\n` + src;
    write(indexPath, src);
    logSuccess("Patcher", "Existing worker path redirect marked as accepted", { indexPath });
    return;
  }

  let patched = false;
  const workerNeedle = "gamePatcher.js";
  let pos = src.indexOf(workerNeedle);
  logInfo("Patcher", "Searching Worker(...gamePatcher.js...) call", { workerNeedle, firstPosition: pos });
  while (pos !== -1) {
    const before = src.lastIndexOf("new ", pos);
    const workerCall = src.indexOf(".Worker(", before);
    logDebug("Patcher", "Inspecting worker needle occurrence", { position: pos, before, workerCall });
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
        logDebug("Patcher", "Replacing Worker argument", {
          argStart,
          argEnd: i,
          originalArg,
          replacement,
        });
        src = src.slice(0, argStart) + replacement + src.slice(i);
        patched = true;
        break;
      }
    }
    pos = src.indexOf(workerNeedle, pos + workerNeedle.length);
  }

  if (!patched) {
    logError("Patcher", "Worker path patch failed because no compatible Worker call was found", { indexPath });
    throw new Error("Could not find Worker(...gamePatcher.js...) in index.js; app.asar was not patched");
  }

  src = `/* ${marker}: worker path redirects to app.asar.unpacked under Proton. */\n` + src;
  write(indexPath, src);
  logSuccess("Patcher", "Worker path redirect applied", { indexPath });
}

function patchWorker(workerPath) {
  logInfo("Patcher", "Writing Proton gamePatcher.js adapter", { workerPath });
  const mainDir = path.dirname(workerPath);
  logDebug("Files", "Ensuring worker directory exists", { directory: mainDir });
  fs.mkdirSync(mainDir, { recursive: true });
  const permissionValues = permissions
    .split(",")
    .map((x) => Number.parseInt(x.trim(), 10))
    .filter((x) => Number.isInteger(x) && x >= 0 && x <= 254);
  logDebug("Patcher", "Parsed permission values", { permissions, permissionValues });

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
  logSuccess("Patcher", "Proton gamePatcher.js adapter written", { workerPath, permissionValues });
}

let targets;
try {
  targets = resolveTargets(root);
  if (targets.mode === "source") {
    patchSourceTree(targets.appRoot);
  } else {
    const indexPath = path.join(targets.appRoot, "dist", "electron", "main", "index.js");
    const workerPath = path.join(targets.unpackedRoot, "dist", "electron", "main", "gamePatcher.js");
    logDebug("Patcher", "Resolved patch file paths", { indexPath, workerPath });
    extractAsar(targets);
    patchIndex(indexPath);
    patchWorker(workerPath);
    repackAsar(targets);
  }
  logSuccess("Patcher", "Majestic Proton JS patch completed successfully", {
    mode: targets.mode,
  });
} catch (error) {
  logError("Patcher", "Majestic Proton JS patch failed", {
    exitCode: 1,
    command: process.argv.join(" "),
    reason: error.message,
    stack: error.stack,
  });
  process.exitCode = 1;
} finally {
  if (targets) {
    cleanup(targets);
  }
}
