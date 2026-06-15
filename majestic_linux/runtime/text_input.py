from __future__ import annotations

from ..core.config import RunnerConfig


def apply_text_input_environment(env: dict[str, str], config: RunnerConfig) -> None:
    requested = getattr(config, "input_method", "none")
    method = _select_input_method(env, requested)
    if method is None:
        return
    _ensure_utf8_ctype(env)
    values = {
        "XMODIFIERS": f"@im={method}",
        "GTK_IM_MODULE": method,
        "QT_IM_MODULE": method,
        "SDL_IM_MODULE": method,
        "GLFW_IM_MODULE": method,
    }
    if (requested or "auto").strip().lower() in {"auto", ""}:
        for key, value in values.items():
            env.setdefault(key, value)
    else:
        env.update(values)


def _ensure_utf8_ctype(env: dict[str, str]) -> None:
    if _is_utf8_locale(env.get("LC_ALL", "")) or _is_utf8_locale(env.get("LC_CTYPE", "")):
        return
    lang = env.get("LANG", "")
    env["LC_CTYPE"] = lang if _is_utf8_locale(lang) else "C.UTF-8"


def _is_utf8_locale(value: str) -> bool:
    normalized = value.replace("-", "").lower()
    return "utf8" in normalized


def _select_input_method(env: dict[str, str], requested: str) -> str | None:
    requested = (requested or "none").strip().lower()
    if requested in {"none", "off", "0", "false"}:
        return None
    if requested in {"ibus", "fcitx"}:
        return requested
    if requested not in {"auto", ""}:
        return requested
    haystack = " ".join(env.get(key, "") for key in ("XMODIFIERS", "GTK_IM_MODULE", "QT_IM_MODULE", "SDL_IM_MODULE", "GLFW_IM_MODULE")).lower()
    if "fcitx" in haystack:
        return "fcitx"
    if "ibus" in haystack or env.get("IBUS_ADDRESS"):
        return "ibus"
    return "ibus"
