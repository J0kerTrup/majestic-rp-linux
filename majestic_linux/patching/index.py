from __future__ import annotations

import re
from pathlib import Path

from ..core.errors import PatchError
from .common import (
    DIRECT_MARKER,
    DIRECT_MARKER_V1,
    DIRECT_MARKER_V3,
    INDEX_COMPAT_MARKER,
    MARKER,
    PatchStatus,
    fix_legacy_arrays,
    permissions as parse_permissions,
    read_text,
    validate_text,
    write_text,
)

def _index_direct_helper(permissions: str) -> str:
    values = parse_permissions(permissions)
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
    src = read_text(file)
    original = src
    src = fix_legacy_arrays(src, status)

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
        validate_text(src, file)
        write_text(file, src, dry_run=dry_run, status=status)
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
