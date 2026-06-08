from __future__ import annotations

from pathlib import Path

from ..core.errors import PatchError
from .common import SOURCE_MARKER, PatchStatus, read_text, write_text

def patch_source_find_gta(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    src = read_text(file)
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
    write_text(file, src, dry_run=dry_run, status=status)
    return status


def patch_source_revalidate_gta(file: Path, *, dry_run: bool) -> PatchStatus:
    status = PatchStatus(file)
    src = read_text(file)
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
    write_text(file, src, dry_run=dry_run, status=status)
    return status
