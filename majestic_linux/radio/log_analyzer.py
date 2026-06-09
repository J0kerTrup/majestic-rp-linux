from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

KEYWORDS = (
    "winegstreamer", "gstreamer", "mfplat", "media foundation", "windows media",
    "xaudio", "xact", "quartz", "cef", "chromium", "gpu process", "media pipeline",
    "audio service", "radio", "stream", "audio", "pipewire", "pulseaudio", "alsa",
    "segfault", "exception", "crash", "access violation", "libgstlibav",
    "libbz2.so.1.0", "failed to load plugin", "wrong elf class",
    "ntdcompositionregisterthumbnailvisual", "unimplemented function", "dcomposition", "win32u",
)
URL_RE = re.compile(r"https://[A-Za-z0-9./?&%_=:#@!~+\-]+")
WORD_KEYWORDS = {"cef", "alsa", "xact"}


@dataclass(slots=True)
class LogHit:
    file: Path
    line: int
    keyword: str
    text: str


@dataclass(slots=True)
class Cause:
    title: str
    confidence: int
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LogAnalysis:
    files: list[Path]
    hits: list[LogHit]
    urls: list[str]
    causes: list[Cause]


def analyze_logs(paths: list[Path], max_bytes: int = 512_000) -> LogAnalysis:
    hits: list[LogHit] = []
    urls: set[str] = set()
    files = [path for path in paths if path.exists() and path.is_file()]
    for path in files:
        text = _tail_text(path, max_bytes)
        urls.update(URL_RE.findall(text))
        for keyword in KEYWORDS:
            if _contains(text, keyword):
                hits.extend(_keyword_hits(path, text, keyword))
    causes = rank_causes(hits)
    return LogAnalysis(files, hits[:250], sorted(urls)[:50], causes)


def rank_causes(hits: list[LogHit]) -> list[Cause]:
    text = "\n".join(hit.keyword for hit in hits)
    rules = [
        ("Proton GStreamer dependency failure", ("libgstlibav", "libbz2.so.1.0", "failed to load plugin", "wrong elf class")),
        ("Win32u/DComposition unimplemented function", ("ntdcompositionregisterthumbnailvisual", "unimplemented function", "dcomposition", "win32u")),
        ("CEF/Chromium media or GPU crash", ("cef", "chromium", "gpu process", "media pipeline", "audio service")),
        ("Missing multimedia codec or GStreamer plugin", ("gstreamer", "winegstreamer", "media foundation", "mfplat")),
        ("Wine multimedia DLL override conflict", ("winegstreamer", "quartz", "mfplat", "xaudio", "xact")),
        ("Audio server/backend conflict", ("pipewire", "pulseaudio", "alsa", "audio")),
        ("Network radio stream/TLS issue", ("stream", "radio", "https")),
        ("Native crash/access violation", ("segfault", "exception", "crash", "access violation")),
    ]
    causes: list[Cause] = []
    for title, words in rules:
        evidence = [word for word in words if word in text]
        if not evidence:
            continue
        confidence = min(95, 35 + len(evidence) * 12 + _severe_bonus(text))
        causes.append(Cause(title, confidence, evidence))
    return sorted(causes, key=lambda item: item.confidence, reverse=True)


def _tail_text(path: Path, max_bytes: int) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            return fh.read().decode("utf-8", "ignore")
    except OSError:
        return ""


def _keyword_hits(path: Path, text: str, keyword: str) -> list[LogHit]:
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        if _contains(line, keyword):
            hits.append(LogHit(path, number, keyword, line.strip()[:240]))
            if len(hits) >= 8:
                break
    return hits


def _contains(text: str, keyword: str) -> bool:
    lowered = text.lower()
    if keyword in WORD_KEYWORDS:
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lowered) is not None
    return keyword in lowered


def _severe_bonus(text: str) -> int:
    severe = ("crash", "segfault", "access violation", "exception")
    return 12 if any(word in text for word in severe) else 0
