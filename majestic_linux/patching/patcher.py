from __future__ import annotations

from .api import patch_js_tree, patch_source_tree, patch_state, patch_text, worker_adapter
from .common import PatchReport, PatchStatus, PatchTargets
from .index import patch_index, patch_updater
from .native import build_native_module, inject_prebuilt_native, patch_native_source_tree
from .source_find import patch_source_find_gta, patch_source_revalidate_gta
from .source_runtime import patch_source_game, patch_source_patcher
from .targets import find_js_files, resolve_targets
from .worker import patch_worker

__all__ = [
    "PatchReport",
    "PatchStatus",
    "PatchTargets",
    "find_js_files",
    "patch_index",
    "patch_native_source_tree",
    "inject_prebuilt_native",
    "patch_js_tree",
    "patch_updater",
    "patch_source_find_gta",
    "patch_source_game",
    "patch_source_patcher",
    "patch_source_revalidate_gta",
    "patch_source_tree",
    "patch_state",
    "patch_text",
    "patch_worker",
    "resolve_targets",
    "worker_adapter",
]
