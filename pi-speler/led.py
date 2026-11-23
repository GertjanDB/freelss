# SPDX-License-Identifier: GPL-3.0-or-later
"""De groene ACT-led op de Pi knippert zolang er een fragment speelt.

Geen draad nodig: de led zit op het bordje. De speler schrijft naar
/sys/class/leds/ACT (oudere images: led0). Daarvoor moet hij root zijn;
de service draait als root. config.txt blijft onaangeroerd.

Lukt de led niet (laptop, geen rechten), dan komt er één regel in de log
en spelen de knoppen gewoon verder.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Iterable

log = logging.getLogger("pi-speler")

LED_DIRS = (Path("/sys/class/leds/ACT"), Path("/sys/class/leds/led0"))

# Standaard van de Pi: de led knippert bij SD-kaartgebruik.
FALLBACK_TRIGGER = "mmc0"


def find_led(candidates: Iterable[Path] = LED_DIRS) -> Path | None:
    for path in candidates:
        if (path / "brightness").exists() and (path / "trigger").exists():
            return path
    return None


def current_trigger(text: str) -> str | None:
    """De actieve trigger staat tussen haken: 'none [mmc0] timer'."""

    for word in text.split():
        if word.startswith("[") and word.endswith("]"):
            return word[1:-1]
    return None


class NoLed:
    """Doet niets. Voor de laptop en als de led niet bestaat."""

    def blink(self) -> None:
        pass

    def idle(self) -> None:
        pass

    def close(self) -> None:
        pass


class ActLed:
    """Knippert met een eigen draad. Uit als er niets speelt.

    Elke fout wordt gelogd en zet de led uit gebruik. Nooit een uitzondering
    naar de knoppen of het afspelen.
    """

    def __init__(self, path: Path, interval: float = 0.25) -> None:
        self.path = Path(path)
        self.interval = interval
        self._broken = False
        self._lock = threading.Lock()
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._on = "1"
        self._original: str | None = None
        self._triggers: list[str] = []
        try:
            text = (self.path / "trigger").read_text(encoding="utf-8")
            self._triggers = [word.strip("[]") for word in text.split()]
            self._original = current_trigger(text)
        except OSError as exc:
            self._fail("trigger niet gelezen", exc)
            return
        try:
            top = (self.path / "max_brightness").read_text(encoding="utf-8").strip()
            if top.isdigit() and int(top) > 0:
                self._on = top
        except OSError:
            pass
        if self._write("trigger", "none"):
            self._write("brightness", "0")
            log.info("groene led %s knippert bij afspelen", self.path)

    @property
    def usable(self) -> bool:
        return not self._broken

    def _fail(self, what: str, exc: BaseException) -> None:
        if not self._broken:
            log.warning("groene led: %s (%s); afspelen gaat gewoon door", what, exc)
        self._broken = True

    def _write(self, name: str, value: str) -> bool:
        if self._broken:
            return False
        try:
            (self.path / name).write_text(value, encoding="utf-8")
            return True
        except OSError as exc:
            self._fail(f"{name} niet geschreven", exc)
            return False

    def blink(self) -> None:
        try:
            with self._lock:
                if self._broken or self._thread is not None:
                    return
                stop = threading.Event()
                thread = threading.Thread(
                    target=self._run,
                    args=(stop,),
                    name="led-knipper",
                    daemon=True,
                )
                self._stop_event = stop
                self._thread = thread
                thread.start()
        except Exception as exc:
            self._fail("knipperen niet gestart", exc)

    def _run(self, stop: threading.Event) -> None:
        lit = True
        while not self._broken:
            self._write("brightness", self._on if lit else "0")
            lit = not lit
            if stop.wait(self.interval):
                return

    def idle(self) -> None:
        try:
            with self._lock:
                stop, thread = self._stop_event, self._thread
                self._stop_event = None
                self._thread = None
            if stop is not None:
                stop.set()
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=1.0)
            self._write("brightness", "0")
        except Exception as exc:
            self._fail("uitzetten mislukt", exc)

    def close(self) -> None:
        """Terug naar het gewone gedrag van de Pi: knipperen bij SD-gebruik."""

        self.idle()
        if self._broken:
            return
        restore = self._original
        if restore in (None, "none", "timer"):
            restore = FALLBACK_TRIGGER if FALLBACK_TRIGGER in self._triggers else None
        if restore is not None:
            self._write("trigger", restore)


def open_led(candidates: Iterable[Path] = LED_DIRS, interval: float = 0.25) -> ActLed | NoLed:
    """PI_SPELER_LED=uit zet de led af. Geen led of geen rechten: NoLed."""

    choice = os.environ.get("PI_SPELER_LED", "").strip().lower()
    if choice in {"0", "uit", "off", "nee", "no"}:
        log.info("groene led uit (PI_SPELER_LED)")
        return NoLed()
    try:
        path = find_led(candidates)
        if path is None:
            log.info("geen groene led gevonden; afspelen zonder led")
            return NoLed()
        led = ActLed(path, interval)
        if not led.usable:
            return NoLed()
        return led
    except Exception as exc:
        log.warning("groene led niet geopend (%s); afspelen gaat gewoon door", exc)
        return NoLed()
