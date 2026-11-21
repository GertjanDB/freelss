# SPDX-License-Identifier: GPL-3.0-or-later
"""Zes knoppen: A en B, elk in het Nederlands, Frans en Engels.

Een druk leest het bestand op dat moment. Een nieuwer bestand op de
USB-stick wint van de map audio op de SD-kaart, en die wint van de
kopie naast dit programma.
"""

from __future__ import annotations

import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("pi-speler")

# Naam op de SD-kaart en op de stick. Zo zie je in de verkenner welk fragment het is.
FILE_NAMES = {
    ("a", "nl"): "a-nederlands.wav",
    ("a", "fr"): "a-frans.wav",
    ("a", "en"): "a-engels.wav",
    ("b", "nl"): "b-nederlands.wav",
    ("b", "fr"): "b-frans.wav",
    ("b", "en"): "b-engels.wav",
}

LANGUAGE_ALIASES = {
    "nl": "nl",
    "nederlands": "nl",
    "fr": "fr",
    "frans": "fr",
    "francais": "fr",
    "en": "en",
    "engels": "en",
    "english": "en",
}

# Bookworm mount de FAT-partitie hier. Oudere images gebruiken /boot.
BOOT_AUDIO_DIRS = (
    Path("/boot/firmware/audio"),
    Path("/boot/audio"),
)

MEDIA_ROOTS = (
    Path("/media"),
    Path("/run/media"),
)


@dataclass(frozen=True)
class ButtonSpec:
    version: str
    language: str
    bcm: int
    header_pin: int

    def filename(self) -> str:
        return FILE_NAMES[(self.version, self.language)]

    def wav_path(self, audio_root: Path) -> Path:
        return Path(audio_root) / self.filename()


# BCM-nummer en fysieke headerpin.
# A zit bij elkaar: pin 11, 13 en 15, massa op pin 9.
# B zit bij elkaar: pin 29, 31 en 33, massa op pin 34.
BUTTONS: tuple[ButtonSpec, ...] = (
    ButtonSpec("a", "nl", 17, 11),
    ButtonSpec("a", "fr", 27, 13),
    ButtonSpec("a", "en", 22, 15),
    ButtonSpec("b", "nl", 5, 29),
    ButtonSpec("b", "fr", 6, 31),
    ButtonSpec("b", "en", 13, 33),
)


def find_button(version: str, language: str) -> ButtonSpec | None:
    version = version.lower()
    language = language.lower()
    for spec in BUTTONS:
        if spec.version == version and spec.language == language:
            return spec
    return None


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_marks.replace(".wav", "").replace("_", " ").replace("-", " ")


def _language(token: str) -> str | None:
    return LANGUAGE_ALIASES.get(token)


def _pair(left: str, right: str) -> ButtonSpec | None:
    if left in {"a", "b"} and _language(right):
        return find_button(left, _language(right) or "")
    if right in {"a", "b"} and _language(left):
        return find_button(right, _language(left) or "")
    return None


def parse_bench_line(line: str) -> ButtonSpec | str | None:
    """Bench-regel: 'a nl', 'b frans', 'a-engels', 'stop' of 'quit'."""

    text = line.strip().lower()
    if not text or text.startswith("#"):
        return None
    if text in {"q", "quit", "exit"}:
        return "quit"
    if text == "stop":
        return "stop"
    parts = _fold(text).split()
    if len(parts) == 1:
        match = re.fullmatch(r"([ab])(nl|fr|en|nederlands|frans|francais|engels|english)", parts[0])
        if not match:
            return None
        return find_button(match.group(1), _language(match.group(2)) or "")
    if len(parts) == 2:
        return _pair(parts[0], parts[1])
    return None


def _has_clip(directory: Path) -> bool:
    return any((directory / name).is_file() for name in FILE_NAMES.values())


def _add(ordered: list[Path], seen: set[Path], directory: Path) -> None:
    try:
        if not directory.is_dir() or not _has_clip(directory):
            return
        resolved = directory.resolve()
    except OSError:
        return
    if resolved in seen:
        return
    seen.add(resolved)
    ordered.append(resolved)


def _media_dirs(media_roots: tuple[Path, ...]) -> list[Path]:
    found: list[Path] = []
    for root in media_roots:
        try:
            if not root.is_dir():
                continue
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            found.append(child)
            try:
                for label in child.iterdir():
                    if label.is_dir():
                        found.append(label)
            except OSError:
                continue
    return found


def audio_dirs(
    app_dir: Path,
    usb_mount: Path,
    *,
    boot_dirs: tuple[Path, ...] = BOOT_AUDIO_DIRS,
    media_roots: tuple[Path, ...] = MEDIA_ROOTS,
    scan_media: bool = True,
) -> list[Path]:
    """USB eerst, dan de map audio op de SD-kaart, dan de map naast het programma."""

    ordered: list[Path] = []
    seen: set[Path] = set()
    mount = Path(usb_mount)
    _add(ordered, seen, mount)
    _add(ordered, seen, mount / "audio")
    if scan_media:
        for directory in _media_dirs(media_roots):
            _add(ordered, seen, directory)
            _add(ordered, seen, directory / "audio")
    for boot in boot_dirs:
        _add(ordered, seen, Path(boot))
    local = Path(app_dir) / "audio"
    _add(ordered, seen, local)
    try:
        local_resolved = local.resolve()
    except OSError:
        local_resolved = local
    if local_resolved not in seen:
        ordered.append(local_resolved)
    return ordered


def resolve_wav(spec: ButtonSpec, directories: list[Path]) -> Path:
    name = spec.filename()
    for directory in directories:
        path = directory / name
        if path.is_file():
            return path
    return directories[-1] / name


class AudioLibrary:
    """Kiest bij elke druk opnieuw, zodat een stick zonder herstart werkt."""

    def __init__(self, app_dir: Path, usb_mount: Path) -> None:
        self.app_dir = Path(app_dir)
        self.usb_mount = Path(usb_mount)
        self._active: Path | None = None
        self._lock = threading.Lock()

    def wav_for(self, spec: ButtonSpec) -> Path:
        directories = audio_dirs(self.app_dir, self.usb_mount)
        path = resolve_wav(spec, directories)
        with self._lock:
            if path.parent != self._active:
                log.info("audiomap %s", path.parent)
                self._active = path.parent
        return path
