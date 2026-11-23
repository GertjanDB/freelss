# SPDX-License-Identifier: GPL-3.0-or-later
"""Eén WAV tegelijk. Een nieuwe druk stopt de vorige en begint vooraan.

Bestanden worden niet vooraf geladen. aplay leest het gekozen bestand
vanaf schijf en speelt het één keer (geen lus).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Protocol

log = logging.getLogger("pi-speler")


class Backend(Protocol):
    def stop(self) -> None: ...

    def play(self, path: Path) -> bool | None: ...


def aplay_command(device: str, path: Path) -> list[str]:
    """Open dit ALSA-apparaat. Geen lus, geen HDMI-kaart."""

    return ["aplay", "-D", device, os.fspath(path)]


_CARD_LINE = re.compile(
    r"^card \d+: (\S+) \[(.*?)\], device (\d+):",
    re.MULTILINE,
)


def choose_output_device(listing: str, jack: str) -> str:
    """USB-versterker als die eraan hangt, anders de 3,5 mm-jack.

    HDMI-kaarten worden overgeslagen. Zonder USB-kaart blijft de jack.
    """

    usb: list[str] = []
    other: list[str] = []
    for match in _CARD_LINE.finditer(listing):
        card, description, device = match.group(1), match.group(2), match.group(3)
        label = f"{card} {description}".lower()
        if "headphone" in label:
            continue
        if "hdmi" in label or card.lower().startswith("vc4hdmi"):
            continue
        target = f"plughw:CARD={card},DEV={device}"
        if "usb" in label or "up2stream" in label:
            usb.append(target)
        else:
            other.append(target)
    if usb:
        return usb[0]
    if other:
        return other[0]
    return jack


class OutputRoute:
    """Standaard is usb of jack. Gids gebruikt de andere tot de volgende gidsdruk.

    De standaard staat in een bestand en blijft na een herstart. Gids niet.
    Geen automatische wissel: ontbreekt de USB-versterker, dan geen geluid
    en een fout in de log. Alleen gids of de config-pin kiest de jack.
    """

    def __init__(self, path: Path, jack: str) -> None:
        self.path = Path(path)
        self.jack = jack
        self.preference = "usb"
        self.guide = False
        self._load()

    def _load(self) -> None:
        try:
            text = self.path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            return
        if text in {"usb", "jack"}:
            self.preference = text

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + ".tmp")
            temporary.write_text(self.preference + "\n", encoding="utf-8")
            temporary.replace(self.path)
        except OSError as exc:
            log.warning("standaard niet bewaard: %s", exc)

    def uses_usb(self) -> bool:
        return (self.preference == "usb") != self.guide

    def device_for(self, listing: str) -> str | None:
        """Het gekozen apparaat, of None als de USB-versterker ontbreekt."""

        if not self.uses_usb():
            return self.jack
        return choose_output_device(listing, "") or None

    def toggle_guide(self) -> str:
        self.guide = not self.guide
        return "usb" if self.uses_usb() else "jack"

    def toggle_default(self) -> str:
        self.preference = "jack" if self.preference == "usb" else "usb"
        self.guide = False
        self._save()
        return self.preference


def valid_wav(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return False
    return len(header) == 12 and header[0:4] == b"RIFF" and header[8:12] == b"WAVE"


class AplayBackend:
    """Stroomt één bestand naar één ALSA-apparaat. Stop = proces dood.

    Met follow_cards kijkt elke druk of de USB-versterker eraan hangt.
    Met led knippert de groene led zolang er een fragment speelt.
    """

    def __init__(
        self,
        device: str,
        *,
        follow_cards: bool = False,
        route: OutputRoute | None = None,
        led: object | None = None,
    ) -> None:
        self.device = device
        # Groene led: knippert zolang aplay loopt. None = geen led.
        self.led = led
        self.follow_cards = follow_cards
        self.route = route
        self._active = device
        self._path: Path | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        # Apart slot voor de led, zodat een oud fragment dat net eindigt
        # de led niet uitzet terwijl het nieuwe al speelt.
        self._led_lock = threading.Lock()

    def output_device(self) -> str | None:
        """None: de gekozen uitgang is er niet. Dan speelt er niets."""

        if not self.follow_cards:
            return self.device
        if self.route is not None and not self.route.uses_usb():
            chosen = self.route.jack
            if chosen != self._active:
                log.info("uitgang %s", chosen)
                self._active = chosen
            return chosen
        try:
            listed = subprocess.run(
                ["aplay", "-l"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("aplay -l: %s", exc)
            if self.route is not None:
                log.error("usb-uitgang niet te controleren; geen geluid, geen wissel naar de jack")
                return None
            return self.device
        if self.route is None:
            chosen = choose_output_device(listed.stdout, self.device)
        else:
            chosen = self.route.device_for(listed.stdout)
            if chosen is None:
                log.error(
                    "usb-versterker niet gevonden: geen geluid. Ik wissel niet naar de jack. "
                    "Kijk de USB-kabel na, of kies de jack met gids of de config-pin."
                )
                return None
        if chosen != self._active:
            log.info("uitgang %s", chosen)
            self._active = chosen
        return chosen

    def _led(self, action: str) -> None:
        # Een led-fout mag het afspelen nooit breken.
        if self.led is None:
            return
        try:
            getattr(self.led, action)()
        except Exception:
            log.exception("groene led %s mislukt; afspelen gaat door", action)

    def stop(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        try:
            if proc is None or proc.poll() is not None:
                return
            proc.terminate()
            try:
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.5)
        finally:
            with self._led_lock:
                self._led("idle")

    def replay_if_playing(self) -> None:
        with self._lock:
            proc = self._proc
            path = self._path
        if path is None or proc is None or proc.poll() is not None:
            return
        self.play(path)

    def is_playing(self) -> bool:
        with self._lock:
            proc = self._proc
        return proc is not None and proc.poll() is None

    def play(self, path: Path, device: str | None = None) -> bool:
        """True als aplay draait. False als de gekozen uitgang ontbreekt.

        device dwingt één apparaat af (de opstartreeks op de jack).
        Zonder device geldt de gewone keuze: standaard of gids.
        """

        # Ook als de aanroeper het vergeet: nooit twee bestanden tegelijk.
        self._path = path
        self.stop()
        if device is None:
            device = self.output_device()
        if device is None:
            # Gekozen uitgang ontbreekt: stil blijven, led uit, knoppen blijven werken.
            return False
        try:
            proc = subprocess.Popen(
                aplay_command(device, path),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise RuntimeError(f"aplay start mislukt: {exc}") from exc
        with self._lock:
            self._proc = proc
        with self._led_lock:
            self._led("blink")
        threading.Thread(
            target=self._watch,
            args=(proc,),
            name="aplay-watch",
            daemon=True,
        ).start()
        return True

    def _watch(self, proc: subprocess.Popen[bytes]) -> None:
        err = b""
        if proc.stderr is not None:
            err = proc.stderr.read()
        code = proc.wait()
        with self._lock:
            still_current = self._proc is proc
            if still_current:
                # Vanzelf gedaan: het fragment is uit, de led ook.
                self._proc = None
        if not still_current:
            return
        with self._led_lock:
            with self._lock:
                newer = self._proc is not None
            if not newer:
                self._led("idle")
        if code == 0:
            return
        text = err.decode("utf-8", "replace").strip()
        log.error("aplay fout (code %s): %s", code, text or "(geen melding)")


class Playback:
    """Seriële drukken. De druk die het slot het laatst pakt, wint."""

    def __init__(self, backend: Backend) -> None:
        self._backend = backend
        self._lock = threading.Lock()

    def press(self, path: Path, device: str | None = None) -> bool:
        """True als het fragment begon te spelen. device: zie AplayBackend.play."""

        with self._lock:
            self._stop_quiet()
            if not path.is_file():
                log.error("bestand ontbreekt: %s", path)
                return False
            if not valid_wav(path):
                log.error("ongeldig wav-bestand: %s", path)
                return False
            try:
                if device is None:
                    return self._backend.play(path) is not False
                return self._backend.play(path, device=device) is not False
            except Exception:
                log.exception("afspelen mislukt: %s", path)
                return False

    def is_playing(self) -> bool:
        check = getattr(self._backend, "is_playing", None)
        if check is None:
            return False
        try:
            return bool(check())
        except Exception:
            log.exception("afspeelstatus onbekend")
            return False

    def stop(self) -> None:
        with self._lock:
            self._stop_quiet()

    def replay_if_playing(self) -> None:
        replay = getattr(self._backend, "replay_if_playing", None)
        if replay is None:
            return
        try:
            replay()
        except Exception:
            log.exception("opnieuw afspelen mislukt")

    def _stop_quiet(self) -> None:
        try:
            self._backend.stop()
        except Exception:
            log.exception("stoppen mislukt")
