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
const marker = "MAJESTIC_PROTON_PATCH_V4";

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

  if (src.includes(marker)) {
    console.log("Already patched with V4. Skipping.");
    return;
  }

  src = src.replace(/\/\* MAJESTIC_PROTON_PATCH_V[23]:.*?\*\/\s*\(\(\) => \{[\s\S]*?\}\)\(\);\s*/gm, '');

  const permissionValues = permissions
  .split(",")
  .map((x) => Number.parseInt(x.trim(), 10))
  .filter((x) => Number.isInteger(x) && x >= 0 && x <= 254);

  const protonHook = `/* ${marker}: Direct interception of majestic-patcher for Proton compatibility */
  (() => {
    try {
      const Module = require("module");
      const originalLoad = Module._load;

      const protonGtaPath = process.env.MAJESTIC_GTA_WIN_PATH || 'G:\\\\';
      const protonPlatform = process.env.MAJESTIC_PROTON_PLATFORM || 'rgl';
      const disableCefGpu = process.env.MAJESTIC_DISABLE_CEF_GPU !== '0';
      const permissionsArr = ${JSON.stringify(permissionValues)};

      function isProtonRuntime() {
        return process.platform === 'win32' && Boolean(
          process.env.STEAM_COMPAT_DATA_PATH ||
          process.env.STEAM_COMPAT_CLIENT_INSTALL_PATH ||
          process.env.MAJESTIC_PROTON_PLATFORM ||
          process.env.WINEPREFIX
        );
      }

      function adaptLaunchOptions(opts) {
        if (!isProtonRuntime() || !opts) return opts;

        let config = opts;
        let isPath = typeof opts === 'string';
        let configPath = isPath ? opts : null;

        if (isPath) {
          try {
            config = JSON.parse(require('fs').readFileSync(opts, 'utf8'));
          } catch(e) {
            return opts;
          }
        }

        let changed = false;

        if (String(config.gtaPath || '').startsWith('Z:\\\\') || String(config.gtaPath || '') !== protonGtaPath) {
          console.log('[LINUX-PROTON] Rewriting gtaPath:', config.gtaPath, '->', protonGtaPath);
          config.gtaPath = protonGtaPath;
          changed = true;
        }
        if (['steam', 'rgl', 'egs'].includes(protonPlatform) && config.gtaPlatform !== protonPlatform) {
          console.log('[LINUX-PROTON] Rewriting gtaPlatform:', config.gtaPlatform, '->', protonPlatform);
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
          const cacheRoot = require('path').join(config.multiplayerPath, 'cache');
          if (require('fs').existsSync(cacheRoot)) {
            const data = Buffer.from([...permissionsArr, 255]);
            for (const name of require('fs').readdirSync(cacheRoot)) {
              const dir = require('path').join(cacheRoot, name);
              if (require('fs').existsSync(dir) && require('fs').lstatSync(dir).isDirectory()) {
                require('fs').writeFileSync(require('path').join(dir, 'permissions'), data);
              }
            }
          }

          const mpConfigPath = require('path').join(config.multiplayerPath, config.configFileName);
          try {
            const mpConfig = JSON.parse(require('fs').readFileSync(mpConfigPath, 'utf8'));
            let mpChanged = false;
            if (mpConfig.debug !== false) { mpConfig.debug = false; mpChanged = true; }
            if (disableCefGpu && mpConfig.cefUseHardwareAcceleration !== false) {
              mpConfig.cefUseHardwareAcceleration = false;
              mpChanged = true;
            }
            if (mpChanged) {
              require('fs').writeFileSync(mpConfigPath, JSON.stringify(mpConfig, null, 2));
              console.log('[LINUX-PROTON] Patched multiplayer config:', mpConfigPath);
            }
          } catch(e) {}
        }

        if (changed && isPath) {
          require('fs').writeFileSync(configPath, JSON.stringify(config, null, 2));
          return configPath;
        } else if (changed && !isPath) {
          return config;
        }

        return opts;
      }

      Module._load = function(request, parent, isMain) {
        const result = originalLoad.apply(this, arguments);

        if (request === "majestic-patcher" && result && result.patchMultiplayerWithProgress) {
          console.log('[LINUX-PROTON] Intercepted majestic-patcher');

          const originalPatch = result.patchMultiplayerWithProgress;
          result.patchMultiplayerWithProgress = async function(launchOptions, progressCallback) {
            console.log('[LINUX-PROTON] Adapting launch options before native patch...');
            const adaptedOptions = adaptLaunchOptions(launchOptions);
            return originalPatch.call(this, adaptedOptions, progressCallback);
          };

          Module._load = originalLoad;
        }

        return result;
      };

      console.log('[LINUX-PROTON] Main process hook installed successfully');
    } catch (error) {
      console.error('[LINUX-PROTON] Failed to install hook:', error);
    }
  })();
  `;

  src = protonHook + src;
  write(indexPath, src);
  console.log("Majestic Proton JS patch V4 applied successfully");
}

patchIndex();
