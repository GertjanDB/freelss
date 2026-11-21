# SPDX-License-Identifier: GPL-3.0-or-later
"""Pi-speler: knoppen A en B, gids, stop, en een config-pin.

Zonder GPIO (laptop, test):

    PI_SPELER_BENCH=1 python3 pi_speler.py
"""

from __future__ import annotations

import logging
import os
import pwd
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from config import (
    APLAY_DEVICE,
    BUTTON_KWARGS,
    MORNING_STAMP,
    STATE_PATH,
    USB_MOUNT,
    force_analog_command,
    volume_command,
)
from hours import MorningReset, NightIdle
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


class Player:
    def __init__(
        self,
        library: AudioLibrary,
        playback: Playback,
        route: OutputRoute,
        night: NightIdle | None = None,
        morning: MorningReset | None = None,
    ) -> None:
        self._library = library
        self._playback = playback
        self._route = route
        self._night = night or NightIdle()
        self._morning = morning or MorningReset(MORNING_STAMP)

    def night_tick(self) -> None:
        try:
            change = self._night.tick()
        except Exception:
            log.exception("klok faalde; de speler blijft lopen")
            return
        if change == "nacht":
            log.info("nacht tot 08:00, knoppen stil")
            try:
                self._playback.stop()
            except Exception:
                log.exception("stoppen voor de nacht mislukt")
        elif change == "dag":
            log.info("dag, knoppen aan")

    def morning_due(self) -> bool:
        try:
            return self._morning.tick()
        except Exception:
            log.exception("ochtendklok faalde")
            return False

    def morning_clear(self) -> None:
        self._morning.clear()

    def morning_commit(self) -> bool:
        return self._morning.commit()

    def _quiet(self) -> bool:
        self.night_tick()
        return self._night.silent

    def press_button(self, spec: ButtonSpec) -> None:
        try:
            if self._quiet():
                log.info("nacht, knop %s %s genegeerd", spec.version, spec.language)
                return
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
        try:
            log.info("stop")
            self._playback.stop()
        except Exception:
            log.exception("stoppen mislukt")

    def guide(self) -> None:
        try:
            if self._quiet():
                log.info("nacht, gids genegeerd")
                return
            via = self._route.toggle_guide()
            log.info("gids %s", via)
            self._playback.replay_if_playing()
        except Exception:
            log.exception("gids faalde; de speler blijft lopen")

    def configure(self) -> None:
        try:
            choice = self._route.toggle_default()
            log.info("standaard %s", choice)
            self._playback.replay_if_playing()
        except Exception:
            log.exception("config faalde; de speler blijft lopen")

    def close(self) -> None:
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
    result = _run_command(command)
    if result is not None and result.returncode == 0:
        log.info("analoge uitgang gezet: %s", shown)
        return
    if result is not None:
        log.warning("analoge uitgang niet gezet (%s): %s", shown, result.stderr.strip())
    run_user = Path("/run/user")
    if not run_user.is_dir():
        log.info("afspelen gaat toch naar de koptelefoonkaart")
        return
    for entry in sorted(run_user.iterdir()):
        if not entry.name.isdigit():
            continue
        try:
            name = pwd.getpwuid(int(entry.name)).pw_name
        except KeyError:
            continue
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = str(entry)
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={entry}/bus"
        result = _run_command(command, user=name, env=env)
        if result is not None and result.returncode == 0:
            log.info("analoge uitgang gezet voor %s: %s", name, shown)
            return
        detail = result.stderr.strip() if result is not None else "niet gestart"
        log.warning("analoge uitgang voor %s mislukt: %s", name, detail)
    log.info("afspelen gaat toch naar de koptelefoonkaart")


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
    log.info("pipewire-standaard: %s", " ".join(force_analog_command()))
    wait_for_headphone_card()
    force_analog_output()
    set_fixed_volume()


def serve_gpio(player: Player) -> None:
    try:
        from gpiozero import Button
    except ImportError:
        log.error(
            "gpiozero ontbreekt. Op de Pi: sudo apt install python3-gpiozero. "
            "Zonder pinnen: PI_SPELER_BENCH=1 python3 pi_speler.py"
        )
        raise SystemExit(1)

    held: list[Button] = []
    for spec in BUTTONS:
        try:
            button = Button(spec.bcm, **BUTTON_KWARGS)
        except Exception:
            log.exception(
                "knop %s %s bcm=%s pin=%s niet geopend; de andere knoppen gaan door",
                spec.version,
                spec.language,
                spec.bcm,
                spec.header_pin,
            )
            continue

        def on_press(*_args: object, chosen: ButtonSpec = spec) -> None:
            player.press_button(chosen)

        button.when_pressed = on_press
        held.append(button)
    for spec in CONTROLS:
        try:
            button = Button(spec.bcm, **BUTTON_KWARGS)
        except Exception:
            log.exception(
                "knop %s bcm=%s pin=%s niet geopend",
                spec.action,
                spec.bcm,
                spec.header_pin,
            )
            continue

        def on_control(*_args: object, chosen: ControlSpec = spec) -> None:
            if chosen.action == "gids":
                player.guide()
            elif chosen.action == "stop":
                player.stop()
            elif chosen.action == "config":
                player.configure()

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
        log.error("geen enkele knop kon openen")
        raise SystemExit(1)
    log.info("%s knoppen actief", len(held))
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


def reboot_pi() -> bool:
    log.info("ochtendreset")
    try:
        result = subprocess.run(
            ["systemctl", "reboot"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("ochtendreset mislukt: %s", exc)
        return False
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        log.warning("ochtendreset mislukt: %s", detail or result.returncode)
        return False
    return True


def watch_night(player: Player, done: threading.Event, bench: bool) -> None:
    while not done.wait(20):
        player.night_tick()
        if bench or not player.morning_due():
            continue
        if player.morning_commit() and reboot_pi():
            continue
        player.morning_clear()


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = list(sys.argv[1:] if argv is None else argv)
    bench = bench_enabled(args)
    library = AudioLibrary(APP_DIR, USB_MOUNT)
    device = playback_device(bench)
    route = OutputRoute(STATE_PATH, APLAY_DEVICE)
    log.info("standaard %s", route.preference)
    player = Player(
        library,
        Playback(AplayBackend(device, follow_cards=not bench, route=route)),
        route,
    )
    install_signals(player)
    done = threading.Event()
    watcher = threading.Thread(
        target=watch_night,
        args=(player, done, bench),
        name="nacht",
        daemon=True,
    )
    watcher.start()
    try:
        if bench:
            log.info("bench aan, apparaat %s", device)
            serve_bench(player)
        else:
            try:
                prepare_analog_output()
            except Exception:
                log.exception("audio-voorbereiding mislukt; knoppen gaan toch aan")
            serve_gpio(player)
    finally:
        done.set()
        player.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
