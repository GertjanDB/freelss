# SPDX-License-Identifier: GPL-3.0-or-later
"""Pi-speler: knoppen A en B, gids, stop, en een config-pin.

Zonder GPIO (laptop, test):

    PI_SPELER_BENCH=1 python3 pi_speler.py
"""

from __future__ import annotations

import logging
import os
import pwd
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Sequence

from config import (
    APLAY_DEVICE,
    BUTTON_KWARGS,
    FRAGMENT_BUTTON_KWARGS,
    FRAGMENT_DEBOUNCE_S,
    RELEASE_GUARD_S,
    LED_BLINK_S,
    OPSTART,
    OPSTART_PAUZE_S,
    STATE_PATH,
    USB_MOUNT,
    force_analog_command,
    volume_command,
)
from led import open_led
from mapping import BUTTONS, CONTROLS, AudioLibrary, ButtonSpec, ControlSpec, parse_bench_line
from playback import AplayBackend, OutputRoute, Playback

log = logging.getLogger("pi-speler")

APP_DIR = Path(__file__).resolve().parent
HEADPHONE_WAIT_S = 15.0


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def bench_enabled(argv: list[str]) -> bool:
    if "--bench" in argv:
        return True
    return os.environ.get("PI_SPELER_BENCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "ja",
    }


def playback_device(bench: bool) -> str:
    override = os.environ.get("PI_SPELER_DEVICE", "").strip()
    if override:
        return override
    if bench:
        return "default"
    return APLAY_DEVICE


def startup_enabled(bench: bool) -> bool:
    """Opstartreeks aan? Niet op de laptop. PI_SPELER_OPSTART=uit zet hem af."""

    if bench:
        return False
    choice = os.environ.get("PI_SPELER_OPSTART", "").strip().lower()
    if choice in {"0", "uit", "off", "nee", "no", "false"}:
        return False
    if choice in {"1", "aan", "on", "ja", "yes", "true"}:
        return True
    return OPSTART


def startup_specs() -> list[ButtonSpec]:
    """De drie A-knoppen in de volgorde van de header: Nederlands, Frans, Engels."""

    return [spec for spec in BUTTONS if spec.version == "a"]


class Player:
    def __init__(self, library: AudioLibrary, playback: Playback, route: OutputRoute) -> None:
        self._library = library
        self._playback = playback
        self._route = route
        # Opstartreeks: elke knop zet dit, de reeks stopt dan.
        self._startup_cancel = threading.Event()
        self._startup_lock = threading.Lock()
        self._startup_thread: threading.Thread | None = None

    def _cancel_startup(self) -> None:
        thread = self._startup_thread
        if thread is None or not thread.is_alive() or self._startup_cancel.is_set():
            return
        self._startup_cancel.set()
        log.info("opstartreeks afgebroken door een knop")
        # Wacht tot een fragment van de reeks dat net start, gestart is.
        # Zo wint de knop altijd.
        with self._startup_lock:
            pass

    def start_startup(
        self,
        specs: Sequence[ButtonSpec],
        device: str,
        pause: float = OPSTART_PAUZE_S,
    ) -> threading.Thread:
        """Speelt specs na elkaar op device, in een eigen draad. Knoppen blijven luisteren."""

        thread = threading.Thread(
            target=self._run_startup,
            args=(list(specs), device, pause),
            name="opstart",
            daemon=True,
        )
        self._startup_thread = thread
        thread.start()
        return thread

    def _run_startup(self, specs: list[ButtonSpec], device: str, pause: float) -> None:
        try:
            log.info("opstartreeks op de jack: %s", ", ".join(f"{s.version} {s.language}" for s in specs))
            for index, spec in enumerate(specs):
                if index and self._startup_cancel.wait(pause):
                    return
                with self._startup_lock:
                    if self._startup_cancel.is_set():
                        return
                    path = self._library.wav_for(spec)
                    log.info("opstart %s %s -> %s", spec.version, spec.language, path)
                    started = self._playback.press(path, device=device)
                if not started:
                    log.error("opstartreeks: %s %s speelde niet; reeks overgeslagen", spec.version, spec.language)
                    return
                while self._playback.is_playing():
                    if self._startup_cancel.wait(0.05):
                        return
            log.info("opstartreeks klaar; knoppen gebruiken de standaard")
        except Exception:
            log.exception("opstartreeks faalde; de knoppen werken gewoon")

    def press_button(self, spec: ButtonSpec) -> None:
        self._cancel_startup()
        try:
            path = self._library.wav_for(spec)
            log.info(
                "knop %s %s bcm=%s pin=%s -> %s",
                spec.version,
                spec.language,
                spec.bcm,
                spec.header_pin,
                path,
            )
            self._playback.press(path)
        except Exception:
            log.exception(
                "knop %s %s faalde; de speler blijft lopen",
                spec.version,
                spec.language,
            )

    def stop(self) -> None:
        self._cancel_startup()
        try:
            log.info("stop")
            self._playback.stop()
        except Exception:
            log.exception("stoppen mislukt")

    def guide(self) -> None:
        self._cancel_startup()
        try:
            via = self._route.toggle_guide()
            log.info("gids %s", via)
            self._playback.replay_if_playing()
        except Exception:
            log.exception("gids faalde; de speler blijft lopen")

    def configure(self) -> None:
        self._cancel_startup()
        try:
            choice = self._route.toggle_default()
            log.info("standaard %s", choice)
            self._playback.replay_if_playing()
        except Exception:
            log.exception("config faalde; de speler blijft lopen")

    def close(self) -> None:
        self._startup_cancel.set()
        try:
            self._playback.stop()
        except Exception:
            log.exception("stoppen mislukt")


def install_signals(player: Player) -> None:
    def handle(signum: int, _frame: object) -> None:
        log.info("stop (signaal %s)", signum)
        player.close()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)


def _run_command(argv: list[str], *, user: str | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=8,
            user=user,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("%s: %s", " ".join(argv), exc)
        return None


def force_analog_output() -> None:
    """Zet PipeWire op de jack. Fouten blijven in de log; het programma stopt niet.

    Het commando is exact:

        pactl set-default-sink alsa_output.platform-bcm2835_audio.stereo-fallback

    Afspelen zelf gaat daarna met aplay naar plughw:CARD=Headphones,DEV=0,
    de analoge kaart. De HDMI-kaarten (vc4hdmi0, vc4hdmi1) worden niet geopend.
    """

    command = force_analog_command()
    shown = " ".join(command)
    if shutil.which(command[0]) is None:
        # Lite heeft geen PipeWire/pactl. aplay gaat rechtstreeks naar de kaart.
        log.info("geen pactl; afspelen gaat rechtstreeks naar %s", APLAY_DEVICE)
        return
    result = _run_command(command)
    if result is not None and result.returncode == 0:
        log.info("analoge uitgang gezet: %s", shown)
        return
    # Root heeft meestal geen eigen PipeWire. Alleen een gebruiker met een
    # draaiende PipeWire/Pulse proberen we nog; anders één info-regel.
    sessions = _sound_sessions()
    if not sessions:
        log.info("geen PipeWire/Pulse actief; afspelen gaat rechtstreeks naar %s", APLAY_DEVICE)
        return
    for entry, name in sessions:
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = str(entry)
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={entry}/bus"
        result = _run_command(command, user=name, env=env)
        if result is not None and result.returncode == 0:
            log.info("analoge uitgang gezet voor %s: %s", name, shown)
            return
        detail = result.stderr.strip() if result is not None else "niet gestart"
        log.info("analoge uitgang voor %s niet gezet: %s", name, detail)
    log.info("afspelen gaat toch naar de koptelefoonkaart")


def _sound_sessions(run_user: Path = Path("/run/user")) -> list[tuple[Path, str]]:
    """Gebruikers met een PipeWire- of Pulse-socket in /run/user/UID."""

    found: list[tuple[Path, str]] = []
    try:
        entries = sorted(run_user.iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.isdigit():
            continue
        if not ((entry / "pulse" / "native").exists() or (entry / "pipewire-0").exists()):
            continue
        try:
            name = pwd.getpwuid(int(entry.name)).pw_name
        except KeyError:
            continue
        found.append((entry, name))
    return found


def set_fixed_volume() -> None:
    command = volume_command()
    result = _run_command(command)
    if result is None:
        return
    if result.returncode != 0:
        log.warning(
            "volume niet gezet (%s): %s",
            " ".join(command),
            (result.stderr or result.stdout).strip(),
        )
        return
    log.info("volume vast: %s", " ".join(command))


def headphone_card_present() -> bool | None:
    try:
        result = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("aplay -l: %s", exc)
        return None
    if "Headphones" in result.stdout:
        return True
    return False


def wait_for_headphone_card(timeout: float = HEADPHONE_WAIT_S) -> None:
    deadline = time.monotonic() + timeout
    while True:
        present = headphone_card_present()
        if present is None or present:
            if present:
                log.info("koptelefoonkaart Headphones is aanwezig")
            return
        if time.monotonic() >= deadline:
            log.warning(
                "kaart Headphones nog niet zichtbaar; knoppen blijven luisteren"
            )
            try:
                listed = subprocess.run(
                    ["aplay", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                log.warning("aplay -l: %s", exc)
            else:
                log.warning("aplay -l:\n%s", (listed.stdout or listed.stderr).strip())
            return
        time.sleep(0.5)


def prepare_analog_output() -> None:
    log.info("afspelen met: aplay -D %s", APLAY_DEVICE)
    wait_for_headphone_card()
    force_analog_output()
    set_fixed_volume()


LGPIO_HINT = (
    "installeer python3-lgpio: sudo apt install python3-lgpio "
    "(of: sudo bash /boot/firmware/pi-speler/install.sh). "
    "Nieuwere kernels (Trixie) hebben geen /sys/class/gpio meer."
)


class PressDetector:
    """Eigen drukdetectie voor één fragmentknop, op het niveau van de pin.

    Elk laag niveau (knop naar massa) telt als druk, ook als de vorige
    losgelaten-flank nooit binnenkwam. Zo speelt dezelfde knop altijd opnieuw.
    Dender: binnen debounce na de vorige druk, of binnen guard na het
    loslaten, telt niet.
    """

    def __init__(
        self,
        on_press: Callable[[], None],
        *,
        debounce: float = FRAGMENT_DEBOUNCE_S,
        guard: float = RELEASE_GUARD_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._on_press = on_press
        self._debounce = debounce
        self._guard = guard
        self._clock = clock
        self._last_press: float | None = None
        self._last_release: float | None = None
        self._lock = threading.Lock()

    def on_level(self, _ticks: object = None, state: object = 0) -> None:
        try:
            level = int(state)
        except (TypeError, ValueError):
            return
        if level not in (0, 1):
            # lgpio meldt 2 bij een watchdog: geen flank.
            return
        now = self._clock()
        with self._lock:
            if level == 1:
                self._last_release = now
                return
            if self._last_release is not None and now - self._last_release < self._guard:
                return
            if self._last_press is not None and now - self._last_press < self._debounce:
                return
            self._last_press = now
        try:
            self._on_press()
        except Exception:
            log.exception("druk verwerken mislukt")


class PressWorker:
    """Voert drukken uit in één eigen draad, in volgorde.

    De GPIO-draad wacht dan nooit op aplay; geen druk gaat verloren.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="knoppen", daemon=True)
        self._thread.start()

    def submit(self, action: Callable[[], None]) -> None:
        self._queue.put(action)

    def _run(self) -> None:
        while True:
            action = self._queue.get()
            try:
                action()
            except Exception:
                log.exception("knop faalde; de speler blijft lopen")
            finally:
                self._queue.task_done()

    def join(self, timeout: float = 2.0) -> None:
        """Voor de tests: wacht tot alle drukken verwerkt zijn."""

        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.005)


def attach_fragment_button(button: object, press: Callable[[], None], keep: list[object]) -> str:
    """Hangt de eigen detectie aan de pin. Lukt dat niet: gewoon when_pressed."""

    detector = PressDetector(press)
    pin = getattr(button, "pin", None)
    if pin is not None:
        try:
            # gpiozero houdt maar een zwakke verwijzing: keep houdt hem levend.
            pin.when_changed = detector.on_level
            keep.append(detector)
            return "pin"
        except Exception:
            log.exception("eigen drukdetectie niet gezet; gpiozero when_pressed")

    def on_press(*_args: object) -> None:
        press()

    button.when_pressed = on_press
    keep.append(on_press)
    return "when_pressed"


LG_WD_DEFAULT = "/run/pi-speler"


def prepare_lgpio_dir(default: str = LG_WD_DEFAULT) -> str | None:
    """lgpio maakt .lgd-nfy*-pijpjes in de werkmap. Dat kan niet op FAT.

    Zet LG_WD (als die leeg is) en ga daar naartoe. Lukt het niet, dan /tmp.
    """

    candidates = [os.environ.get("LG_WD", "").strip(), default, "/tmp"]
    for folder in candidates:
        if not folder:
            continue
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
            os.chdir(folder)
        except OSError as exc:
            log.warning("werkmap %s niet bruikbaar: %s", folder, exc)
            continue
        os.environ["LG_WD"] = folder
        log.info("lgpio-werkmap %s", folder)
        return folder
    log.error("geen werkmap voor lgpio; knoppen kunnen falen")
    return None


def choose_pin_factory() -> str:
    """lgpio als standaard. Werkt op Bookworm en Trixie, ook zonder /sys/class/gpio.

    GPIOZERO_PIN_FACTORY uit de omgeving wint. Staat er lgpio maar ontbreekt
    de module, dan laten we gpiozero zelf zoeken en loggen we de tip.
    """

    chosen = os.environ.get("GPIOZERO_PIN_FACTORY", "").strip()
    if not chosen:
        chosen = "lgpio"
    if chosen == "lgpio":
        try:
            import lgpio  # noqa: F401
        except ImportError:
            log.error("lgpio ontbreekt; gpiozero zoekt zelf een pin-factory. %s", LGPIO_HINT)
            os.environ.pop("GPIOZERO_PIN_FACTORY", None)
            return "automatisch"
        except Exception as exc:
            # Bijvoorbeeld: werkmap op FAT, .lgd-nfy-pijpje niet gemaakt.
            log.error(
                "lgpio start niet (%s: %s); gpiozero zoekt zelf. "
                "Tip: LG_WD=/run/pi-speler en WorkingDirectory=/run/pi-speler in de service, "
                "of sudo bash /boot/firmware/pi-speler/install.sh",
                type(exc).__name__,
                exc,
            )
            os.environ.pop("GPIOZERO_PIN_FACTORY", None)
            return "automatisch"
    os.environ["GPIOZERO_PIN_FACTORY"] = chosen
    return chosen


def _wait_forever() -> None:
    # Geen knoppen: toch blijven lopen. Geen herstartlus, de opstartreeks speelt.
    try:
        signal.pause()
    except Exception:
        log.exception("wachten mislukt")


def serve_gpio(player: Player) -> None:
    try:
        wanted = choose_pin_factory()
    except Exception:
        log.exception("pin-factory kiezen mislukt; gpiozero zoekt zelf")
        wanted = "automatisch"
    log.info("pin-factory gevraagd: %s", wanted)
    try:
        from gpiozero import Button
    except Exception:
        log.error(
            "gpiozero ontbreekt. Op de Pi: sudo apt install python3-gpiozero python3-lgpio. "
            "Zonder pinnen: PI_SPELER_BENCH=1 python3 pi_speler.py"
        )
        _wait_forever()
        return

    held: list[Button] = []
    keep: list[object] = []
    worker = PressWorker()
    failed_once = False

    def report(what: str) -> None:
        # Eén keer de volledige fout, daarna één regel per knop.
        nonlocal failed_once
        if failed_once:
            log.error("%s niet geopend", what)
        else:
            log.exception("%s niet geopend; de andere knoppen gaan door", what)
            failed_once = True

    for spec in BUTTONS:
        try:
            button = Button(spec.bcm, **FRAGMENT_BUTTON_KWARGS)
        except Exception:
            report(f"knop {spec.version} {spec.language} bcm={spec.bcm} pin={spec.header_pin}")
            continue

        def on_press(chosen: ButtonSpec = spec) -> None:
            # Elke druk: wat speelt stopt, dit fragment begint vooraan. Ook dezelfde knop.
            worker.submit(lambda: player.press_button(chosen))

        attach_fragment_button(button, on_press, keep)
        held.append(button)
    for spec in CONTROLS:
        try:
            button = Button(spec.bcm, **BUTTON_KWARGS)
        except Exception:
            report(f"knop {spec.action} bcm={spec.bcm} pin={spec.header_pin}")
            continue

        def run_control(chosen: ControlSpec) -> None:
            if chosen.action == "gids":
                player.guide()
            elif chosen.action == "stop":
                player.stop()
            elif chosen.action == "config":
                player.configure()

        def on_control(*_args: object, chosen: ControlSpec = spec) -> None:
            # Zelfde draad als de fragmentknoppen: de volgorde van drukken blijft.
            worker.submit(lambda: run_control(chosen))

        button.when_pressed = on_control
        held.append(button)
        if spec.wired:
            log.info("knop %s bcm=%s pin=%s", spec.action, spec.bcm, spec.header_pin)
        else:
            log.info(
                "config bcm=%s pin=%s luistert, niet bekabelen",
                spec.bcm,
                spec.header_pin,
            )
    if not held:
        log.error("geen enkele knop kon openen; de speler blijft lopen zonder knoppen. %s", LGPIO_HINT)
        _wait_forever()
        return
    try:
        factory = type(held[0].pin_factory).__name__
    except Exception:
        factory = "onbekend"
    log.info("%s knoppen actief, pin-factory %s", len(held), factory)
    try:
        signal.pause()
    finally:
        for button in held:
            try:
                button.close()
            except Exception:
                log.exception("knop sluiten mislukt")


def serve_bench(player: Player) -> None:
    log.info("bench: typ 'a nl', 'b frans', 'gids', 'stop', 'config' of 'quit'")
    while True:
        try:
            line = input()
        except EOFError:
            return
        action = parse_bench_line(line)
        if action is None:
            if line.strip():
                log.warning("onbekende regel: %s", line.strip())
            continue
        if action == "quit":
            return
        if action == "stop":
            player.stop()
            continue
        if action == "gids":
            player.guide()
            continue
        if action == "config":
            player.configure()
            continue
        if isinstance(action, ButtonSpec):
            player.press_button(action)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = list(sys.argv[1:] if argv is None else argv)
    bench = bench_enabled(args)
    library = AudioLibrary(APP_DIR, USB_MOUNT)
    device = playback_device(bench)
    route = OutputRoute(STATE_PATH, APLAY_DEVICE)
    log.info("standaard %s", route.preference)
    # Groene ACT-led: knippert tijdens een fragment. Zonder led gaat alles gewoon door.
    led = open_led(interval=LED_BLINK_S)
    player = Player(
        library,
        Playback(AplayBackend(device, follow_cards=not bench, route=route, led=led)),
        route,
    )
    install_signals(player)
    try:
        if bench:
            log.info("bench aan, apparaat %s", device)
            serve_bench(player)
        else:
            try:
                prepare_analog_output()
            except Exception:
                log.exception("audio-voorbereiding mislukt; knoppen gaan toch aan")
            if startup_enabled(bench):
                # Altijd de mini-jack, ook als de standaard USB is. Daarna weer de standaard.
                player.start_startup(startup_specs(), APLAY_DEVICE)
            else:
                log.info("opstartreeks uit")
            try:
                prepare_lgpio_dir()
            except Exception:
                log.exception("lgpio-werkmap niet gezet")
            try:
                serve_gpio(player)
            except Exception:
                # GPIO mag de speler nooit in een herstartlus duwen.
                log.exception("knoppen faalden; de speler blijft lopen. %s", LGPIO_HINT)
                _wait_forever()
    finally:
        player.close()
        try:
            led.close()
        except Exception:
            log.exception("groene led terugzetten mislukt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
