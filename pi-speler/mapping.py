# SPDX-License-Identifier: GPL-3.0-or-later
"""Achttien knoppen: zes versies, drie talen, één bestand per knop."""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("pi-speler")

LANGUAGES = ("nl", "fr", "en")


@dataclass(frozen=True)
class ButtonSpec:
    version: int
    language: str
    bcm: int
    header_pin: int

    def wav_path(self, audio_root: Path) -> Path:
        return audio_root / self.language / f"{self.version}.wav"


# BCM-nummer en fysieke headerpin. Volgorde is de afspraak uit de opdracht.
BUTTONS: tuple[ButtonSpec, ...] = (
    ButtonSpec(1, "nl", 17, 11),
    ButtonSpec(1, "fr", 27, 13),
    ButtonSpec(1, "en", 22, 15),
    ButtonSpec(2, "nl", 5, 29),
    ButtonSpec(2, "fr", 6, 31),
    ButtonSpec(2, "en", 13, 33),
    ButtonSpec(3, "nl", 19, 35),
    ButtonSpec(3, "fr", 26, 37),
    ButtonSpec(3, "en", 23, 16),
    ButtonSpec(4, "nl", 24, 18),
    ButtonSpec(4, "fr", 25, 22),
    ButtonSpec(4, "en", 12, 32),
    ButtonSpec(5, "nl", 16, 36),
    ButtonSpec(5, "fr", 20, 38),
    ButtonSpec(5, "en", 21, 40),
    ButtonSpec(6, "nl", 4, 7),
    ButtonSpec(6, "fr", 18, 12),
    ButtonSpec(6, "en", 7, 26),
)


def find_button(version: int, language: str) -> ButtonSpec | None:
    language = language.lower()
    for spec in BUTTONS:
        if spec.version == version and spec.language == language:
            return spec
    return None


def parse_bench_line(line: str) -> ButtonSpec | str | None:
    """Bench-regel: 'nl 1', 'fr3', '6 en', 'stop' of 'quit'."""

    text = line.strip().lower()
    if not text or text.startswith("#"):
        return None
    if text in {"q", "quit", "exit"}:
        return "quit"
    if text == "stop":
        return "stop"
    compact = re.sub(r"\s+", "", text)
    match = re.fullmatch(r"(nl|fr|en)([1-6])", compact)
    if match:
        return find_button(int(match.group(2)), match.group(1))
    match = re.fullmatch(r"([1-6])(nl|fr|en)", compact)
    if match:
        return find_button(int(match.group(1)), match.group(2))
    return None


def resolve_audio_root(app_dir: Path, usb_mount: Path) -> Path:
    """USB als audio/nl, audio/fr én audio/en daarop staan, anders ./audio."""

    local = (Path(app_dir) / "audio").resolve()
    usb_audio = Path(usb_mount) / "audio"
    if all((usb_audio / language).is_dir() for language in LANGUAGES):
        return usb_audio.resolve()
    return local


class AudioLibrary:
    """Kiest bij elke druk opnieuw, zodat een stick zonder herstart werkt."""

    def __init__(self, app_dir: Path, usb_mount: Path) -> None:
        self.app_dir = Path(app_dir)
        self.usb_mount = Path(usb_mount)
        self._active: Path | None = None
        self._lock = threading.Lock()

    def root(self) -> Path:
        chosen = resolve_audio_root(self.app_dir, self.usb_mount)
        with self._lock:
            if chosen != self._active:
                log.info("audiomap %s", chosen)
                self._active = chosen
        return chosen
