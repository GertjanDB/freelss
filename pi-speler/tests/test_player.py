# SPDX-License-Identifier: GPL-3.0-or-later
"""Knop → bestand, en een nieuwe druk kapt het vorige geluid af."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import types
import time
import unittest
import unittest.mock
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import APLAY_DEVICE, BUTTON_KWARGS, force_analog_command, volume_command
from led import ActLed, NoLed, current_trigger, find_led, open_led
import pi_speler
from pi_speler import Player, choose_pin_factory, startup_enabled, startup_specs
from mapping import BUTTONS, CONTROLS, FILE_NAMES, audio_dirs, parse_bench_line, resolve_wav
from playback import (
    AplayBackend,
    OutputRoute,
    Playback,
    aplay_command,
    choose_output_device,
    valid_wav,
)

# Onafhankelijk van mapping.py, zodat een verschoven pin de test laat falen.
SPEC = [
    ("a", "nl", 17, 11),
    ("a", "fr", 27, 13),
    ("a", "en", 22, 15),
    ("b", "nl", 5, 29),
    ("b", "fr", 6, 31),
    ("b", "en", 13, 33),
]

POWER_OR_GND = {1, 2, 4, 6, 9, 14, 17, 20, 25, 30, 34, 39}


def write_wav(path: Path, seconds: float = 0.05) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 8000
    count = int(rate * seconds)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * count)


class FakeBackend:
    def __init__(self) -> None:
        self.events: list[tuple[str, Path | None]] = []
        self.playing: Path | None = None

    def stop(self) -> None:
        self.events.append(("stop", self.playing))
        self.playing = None

    def play(self, path: Path) -> None:
        self.events.append(("play", Path(path)))
        self.playing = Path(path)


class MapTests(unittest.TestCase):
    def test_button_file_map_matches_spec(self) -> None:
        actual = [(b.version, b.language, b.bcm, b.header_pin) for b in BUTTONS]
        self.assertEqual(actual, SPEC)
        self.assertEqual(len(BUTTONS), 6)
        self.assertEqual(len({b.bcm for b in BUTTONS}), 6)
        self.assertEqual(len({b.header_pin for b in BUTTONS}), 6)
        for spec in BUTTONS:
            self.assertNotIn(spec.header_pin, POWER_OR_GND)

        root = Path("/audio")
        paths = [spec.wav_path(root) for spec in BUTTONS]
        self.assertEqual(len(set(paths)), 6)
        self.assertEqual(paths[0], Path("/audio/a-nederlands.wav"))
        self.assertEqual(paths[-1], Path("/audio/b-engels.wav"))
        for version, language, _bcm, _pin in SPEC:
            match = [
                spec
                for spec in BUTTONS
                if spec.version == version and spec.language == language
            ]
            self.assertEqual(len(match), 1)
            self.assertEqual(
                match[0].wav_path(root),
                root / FILE_NAMES[(version, language)],
            )

    def test_buttons_are_active_low_with_pullup_and_40ms_debounce(self) -> None:
        self.assertEqual(BUTTON_KWARGS["pull_up"], True)
        self.assertEqual(BUTTON_KWARGS["bounce_time"], 0.04)
        source = (ROOT / "pi_speler.py").read_text(encoding="utf-8")
        self.assertIn("when_pressed", source)
        self.assertNotIn("when_held", source)
        self.assertNotIn("RPi.GPIO", source)
        for name in ("config.py", "mapping.py", "playback.py", "led.py", "pi_speler.py"):
            self.assertNotIn("RPi.GPIO", (ROOT / name).read_text(encoding="utf-8"))

    def test_bench_lines_use_the_same_map(self) -> None:
        dutch = parse_bench_line("a nl")
        self.assertEqual((dutch.version, dutch.language, dutch.bcm), ("a", "nl", 17))
        french = parse_bench_line("b frans")
        self.assertEqual((french.version, french.language, french.bcm), ("b", "fr", 6))
        english = parse_bench_line("a-engels")
        self.assertEqual((english.version, english.language, english.bcm), ("a", "en", 22))
        self.assertEqual(parse_bench_line("quit"), "quit")
        self.assertEqual(parse_bench_line("stop"), "stop")
        self.assertEqual(parse_bench_line("gids"), "gids")
        self.assertEqual(parse_bench_line("config"), "config")
        self.assertIsNone(parse_bench_line("c nl"))
        self.assertIsNone(parse_bench_line("nl 1"))
        self.assertIsNone(parse_bench_line(""))

    def test_usb_beats_sd_card_and_sd_card_beats_local_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # macOS: /var is een link naar /private/var.
            base = Path(tmp).resolve()
            app = base / "app"
            local = app / "audio"
            boot = base / "boot"
            usb = base / "stick" / "audio"
            for folder, names in (
                (local, FILE_NAMES.values()),
                (boot, ("a-nederlands.wav",)),
                (usb, ("a-frans.wav",)),
            ):
                folder.mkdir(parents=True)
                for name in names:
                    write_wav(folder / name)

            dirs = audio_dirs(
                app,
                base / "stick",
                boot_dirs=(boot,),
                scan_media=False,
            )
            by_name = {spec.filename(): spec for spec in BUTTONS}
            self.assertEqual(resolve_wav(by_name["a-frans.wav"], dirs), usb / "a-frans.wav")
            self.assertEqual(
                resolve_wav(by_name["a-nederlands.wav"], dirs),
                boot / "a-nederlands.wav",
            )
            self.assertEqual(
                resolve_wav(by_name["b-engels.wav"], dirs),
                local / "b-engels.wav",
            )

    def test_guide_stop_and_unwired_config_pins(self) -> None:
        self.assertEqual(
            [(item.action, item.bcm, item.header_pin, item.wired) for item in CONTROLS],
            [
                ("gids", 23, 16, True),
                ("stop", 24, 18, True),
                ("config", 25, 22, False),
            ],
        )
        pins = [item.header_pin for item in BUTTONS] + [item.header_pin for item in CONTROLS]
        bcms = [item.bcm for item in BUTTONS] + [item.bcm for item in CONTROLS]
        self.assertEqual(len(pins), 9)
        self.assertEqual(len(set(pins)), 9)
        self.assertEqual(len(set(bcms)), 9)
        for pin in pins:
            self.assertNotIn(pin, POWER_OR_GND)


class ClipTests(unittest.TestCase):
    def test_shipped_clips_are_audible_wavs(self) -> None:
        import array
        import math

        for name in FILE_NAMES.values():
            path = ROOT / "audio" / name
            self.assertTrue(path.is_file(), name)
            self.assertTrue(valid_wav(path), name)
            with wave.open(str(path)) as handle:
                self.assertEqual(handle.getnchannels(), 1)
                self.assertEqual(handle.getsampwidth(), 2)
                frames = handle.getnframes()
                rate = handle.getframerate()
                raw = handle.readframes(frames)
            seconds = frames / rate
            self.assertGreater(seconds, 0.8, name)
            self.assertLess(seconds, 5, name)
            samples = array.array("h")
            samples.frombytes(raw)
            rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
            self.assertGreater(rms, 500, name)


class PlaybackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def wav(self, language: str, number: str) -> Path:
        path = self.root / language / f"{number}.wav"
        write_wav(path)
        return path

    def test_new_press_cuts_previous_sound(self) -> None:
        backend = FakeBackend()
        playback = Playback(backend)
        first = self.wav("nl", "1")
        second = self.wav("fr", "2")

        playback.press(first)
        playback.press(second)

        self.assertEqual(
            backend.events,
            [
                ("stop", None),
                ("play", first),
                ("stop", first),
                ("play", second),
            ],
        )
        self.assertEqual(backend.playing, second)

        playback.press(second)
        self.assertEqual(backend.events[-2:], [("stop", second), ("play", second)])
        self.assertEqual(backend.playing, second)

    def test_latest_press_wins_when_they_overlap(self) -> None:
        order: list[tuple[str, str | None]] = []
        first_inside = threading.Event()

        class SlowBackend:
            def __init__(self) -> None:
                self.playing: Path | None = None

            def stop(self) -> None:
                first_inside.set()
                time.sleep(0.08)
                name = None if self.playing is None else self.playing.name
                order.append(("stop", name))
                self.playing = None

            def play(self, path: Path) -> None:
                order.append(("play", path.name))
                self.playing = path

        playback = Playback(SlowBackend())
        first = self.wav("nl", "1")
        second = self.wav("en", "6")
        earlier = threading.Thread(target=playback.press, args=(first,))
        earlier.start()
        self.assertTrue(first_inside.wait(timeout=2))
        later = threading.Thread(target=playback.press, args=(second,))
        later.start()
        earlier.join(timeout=2)
        later.join(timeout=2)
        self.assertFalse(earlier.is_alive())
        self.assertFalse(later.is_alive())
        plays = [name for kind, name in order if kind == "play"]
        self.assertEqual(plays, ["1.wav", "6.wav"])
        self.assertEqual(order[-1], ("play", "6.wav"))

    def test_missing_or_bad_file_does_not_escape(self) -> None:
        backend = FakeBackend()
        playback = Playback(backend)
        good = self.wav("nl", "1")
        playback.press(good)

        missing = self.root / "nl" / "2.wav"
        playback.press(missing)
        self.assertIsNone(backend.playing)
        self.assertEqual(backend.events[-1][0], "stop")

        bad = self.root / "nl" / "3.wav"
        bad.write_bytes(b"dit is geen wav")
        playback.press(bad)
        self.assertIsNone(backend.playing)

        playback.press(good)
        self.assertEqual(backend.playing, good)

    def test_backend_errors_do_not_escape(self) -> None:
        class Boom:
            def stop(self) -> None:
                raise RuntimeError("stop kapot")

            def play(self, path: Path) -> None:
                raise RuntimeError(f"play kapot {path}")

        playback = Playback(Boom())
        playback.press(self.wav("nl", "1"))
        playback.press(self.wav("fr", "1"))


class _BlockedStderr:
    def __init__(self, done: threading.Event) -> None:
        self._done = done

    def read(self) -> bytes:
        self._done.wait(2)
        return b""


class FakeProc:
    def __init__(self, cmd: list[str], **_kwargs: object) -> None:
        self.cmd = list(cmd)
        self._done = threading.Event()
        self.returncode: int | None = None
        self.stderr = _BlockedStderr(self._done)
        FakeProc.spawned.append(self)

    spawned: list[FakeProc] = []

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15
        self._done.set()

    def kill(self) -> None:
        self.returncode = -9
        self._done.set()

    def wait(self, timeout: float | None = None) -> int:
        limit = 2 if timeout is None else timeout
        if not self._done.wait(limit):
            raise subprocess.TimeoutExpired(self.cmd, limit)
        return 0 if self.returncode is None else self.returncode


class AplayCommandTests(unittest.TestCase):
    def test_command_targets_headphone_jack_once(self) -> None:
        command = aplay_command(APLAY_DEVICE, Path("audio/nl/1.wav"))
        self.assertEqual(
            command,
            ["aplay", "-D", "plughw:CARD=Headphones,DEV=0", "audio/nl/1.wav"],
        )
        self.assertNotIn("hdmi", " ".join(command).lower())
        self.assertNotIn("-l", command[1:])

    def test_force_analog_command_is_the_bookworm_jack(self) -> None:
        self.assertEqual(
            force_analog_command(),
            [
                "pactl",
                "set-default-sink",
                "alsa_output.platform-bcm2835_audio.stereo-fallback",
            ],
        )
        volume = " ".join(volume_command()).lower()
        self.assertIn("headphones", volume)
        self.assertNotIn("hdmi", volume)

    def test_new_aplay_cuts_the_previous_process(self) -> None:
        FakeProc.spawned = []
        backend = AplayBackend("plughw:CARD=Headphones,DEV=0")
        self.addCleanup(backend.stop)
        with unittest.mock.patch("playback.subprocess.Popen", FakeProc):
            backend.play(Path("audio/nl/1.wav"))
            backend.play(Path("audio/fr/2.wav"))

        procs = FakeProc.spawned
        self.assertEqual(procs[0].cmd[:3], ["aplay", "-D", "plughw:CARD=Headphones,DEV=0"])
        self.assertEqual(procs[0].returncode, -15)
        self.assertTrue(procs[0].cmd[-1].endswith("1.wav"))
        self.assertTrue(procs[1].cmd[-1].endswith("2.wav"))
        self.assertEqual(procs[1].cmd[2], "plughw:CARD=Headphones,DEV=0")

    def test_usb_amp_wins_and_jack_returns_when_it_is_gone(self) -> None:
        listing = """
**** List of PLAYBACK Hardware Devices ****
card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]
card 1: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
card 2: Audio [Up2Stream USB Audio], device 0: USB Audio [USB Audio]
"""
        jack = "plughw:CARD=Headphones,DEV=0"
        self.assertEqual(
            choose_output_device(listing, jack),
            "plughw:CARD=Audio,DEV=0",
        )
        self.assertEqual(
            choose_output_device(listing.split("card 2:")[0], jack),
            jack,
        )
        self.assertNotIn("hdmi", choose_output_device(listing, jack).lower())

    def test_guide_flips_the_route_and_config_stores_the_default(self) -> None:
        listing = """
card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]
card 2: Audio [Up2Stream USB Audio], device 0: USB Audio [USB Audio]
"""
        jack = APLAY_DEVICE
        usb = "plughw:CARD=Audio,DEV=0"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "standaard"
            route = OutputRoute(path, jack)
            self.assertEqual(route.preference, "usb")
            self.assertEqual(route.device_for(listing), usb)
            self.assertEqual(route.toggle_guide(), "jack")
            self.assertEqual(route.device_for(listing), jack)
            self.assertEqual(route.toggle_guide(), "usb")
            route.toggle_guide()
            self.assertEqual(route.toggle_default(), "jack")
            self.assertFalse(route.guide)
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "jack")
            self.assertEqual(route.device_for(listing), jack)
            kept = OutputRoute(path, jack)
            self.assertEqual(kept.preference, "jack")
            self.assertEqual(kept.toggle_guide(), "usb")
            self.assertEqual(kept.device_for(listing), usb)
            # Geen USB-versterker: geen stille wissel naar de jack.
            self.assertIsNone(kept.device_for("card 0: Headphones [bcm2835 Headphones], device 0: x"))

    def test_guide_restarts_the_clip_on_the_other_output(self) -> None:
        listing = """
card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]
card 2: Audio [Up2Stream USB Audio], device 0: USB Audio [USB Audio]
"""
        jack = APLAY_DEVICE
        route = OutputRoute(Path("/tmp/pi-speler-standaard-test-missing"), jack)
        backend = AplayBackend(jack, follow_cards=True, route=route)
        self.addCleanup(backend.stop)
        listed = unittest.mock.Mock(stdout=listing, stderr="", returncode=0)
        FakeProc.spawned = []
        with (
            unittest.mock.patch("playback.subprocess.Popen", FakeProc),
            unittest.mock.patch("playback.subprocess.run", return_value=listed),
        ):
            backend.play(Path("audio/a-nederlands.wav"))
            route.toggle_guide()
            backend.replay_if_playing()
            backend.stop()
            backend.replay_if_playing()
        procs = FakeProc.spawned
        self.assertEqual(procs[0].cmd[2], "plughw:CARD=Audio,DEV=0")
        self.assertEqual(procs[1].cmd[2], jack)
        self.assertTrue(procs[1].cmd[-1].endswith("a-nederlands.wav"))
        self.assertEqual(len(procs), 2)


def fake_led(folder: Path, trigger: str = "none [mmc0] timer heartbeat") -> Path:
    folder.mkdir(parents=True)
    (folder / "trigger").write_text(trigger, encoding="utf-8")
    (folder / "brightness").write_text("0", encoding="utf-8")
    (folder / "max_brightness").write_text("255", encoding="utf-8")
    return folder


def wait_until(check, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.01)
    return check()


class RecordingLed:
    def __init__(self) -> None:
        self.events: list[str] = []

    def blink(self) -> None:
        self.events.append("blink")

    def idle(self) -> None:
        self.events.append("idle")

    def close(self) -> None:
        self.events.append("close")


class LedTests(unittest.TestCase):
    def test_act_wins_and_led0_is_the_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            act = base / "ACT"
            led0 = fake_led(base / "led0")
            self.assertEqual(find_led((act, led0)), led0)
            fake_led(act)
            self.assertEqual(find_led((act, led0)), act)
            self.assertIsNone(find_led((base / "nergens",)))
        self.assertEqual(current_trigger("none [mmc0] timer"), "mmc0")
        self.assertIsNone(current_trigger("none mmc0"))

    def test_led_blinks_while_playing_and_goes_back_after(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = fake_led(Path(tmp) / "ACT")
            led = ActLed(folder, interval=0.02)
            self.addCleanup(led.close)
            brightness = folder / "brightness"
            self.assertEqual((folder / "trigger").read_text(encoding="utf-8"), "none")
            self.assertEqual(brightness.read_text(encoding="utf-8"), "0")
            led.blink()
            led.blink()
            seen: set[str] = set()

            def toggled() -> bool:
                seen.add(brightness.read_text(encoding="utf-8"))
                return {"0", "255"} <= seen

            self.assertTrue(wait_until(toggled))
            led.idle()
            self.assertEqual(brightness.read_text(encoding="utf-8"), "0")
            time.sleep(0.08)
            self.assertEqual(brightness.read_text(encoding="utf-8"), "0")
            led.close()
            self.assertEqual((folder / "trigger").read_text(encoding="utf-8"), "mmc0")

    def test_close_falls_back_to_sd_activity_after_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = fake_led(Path(tmp) / "ACT", "[none] mmc0 timer")
            led = ActLed(folder, interval=0.02)
            led.close()
            self.assertEqual((folder / "trigger").read_text(encoding="utf-8"), "mmc0")

    def test_no_led_or_no_rights_never_breaks_the_player(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.assertIsInstance(open_led((base / "ACT",)), NoLed)
            folder = fake_led(base / "ACT")
            with unittest.mock.patch.dict(os.environ, {"PI_SPELER_LED": "uit"}):
                self.assertIsInstance(open_led((folder,)), NoLed)
            with unittest.mock.patch.object(
                Path, "write_text", side_effect=PermissionError("geen rechten")
            ):
                with self.assertLogs("pi-speler", level="WARNING"):
                    led = open_led((folder,))
            self.assertIsInstance(led, NoLed)
            led.blink()
            led.idle()
            led.close()

            real = ActLed(folder, interval=0.01)
            with unittest.mock.patch.object(
                Path, "write_text", side_effect=OSError("weg")
            ):
                with self.assertLogs("pi-speler", level="WARNING"):
                    real.blink()
                    wait_until(lambda: not real.usable)
                real.idle()
                real.close()
            self.assertFalse(real.usable)

    def test_backend_drives_the_led(self) -> None:
        FakeProc.spawned = []
        led = RecordingLed()
        backend = AplayBackend(APLAY_DEVICE, led=led)
        self.addCleanup(backend.stop)
        with unittest.mock.patch("playback.subprocess.Popen", FakeProc):
            backend.play(Path("audio/a-nederlands.wav"))
            self.assertEqual(led.events[-1], "blink")
            # Nieuwe druk: even uit, meteen weer knipperen.
            backend.play(Path("audio/a-frans.wav"))
            self.assertEqual(led.events[-1], "blink")
            backend.stop()
            self.assertEqual(led.events[-1], "idle")
            # Vanzelf gedaan: led terug uit.
            backend.play(Path("audio/b-engels.wav"))
            self.assertEqual(led.events[-1], "blink")
            proc = FakeProc.spawned[-1]
            proc.returncode = 0
            proc._done.set()
            self.assertTrue(wait_until(lambda: led.events[-1] == "idle"))

    def test_old_clip_ending_does_not_turn_off_the_new_one(self) -> None:
        FakeProc.spawned = []
        led = RecordingLed()
        backend = AplayBackend(APLAY_DEVICE, led=led)
        self.addCleanup(backend.stop)
        with unittest.mock.patch("playback.subprocess.Popen", FakeProc):
            backend.play(Path("audio/a-nederlands.wav"))
            backend.play(Path("audio/a-frans.wav"))
            time.sleep(0.05)
        self.assertEqual(led.events[-1], "blink")

    def test_broken_led_does_not_stop_playback(self) -> None:
        class BadLed:
            def blink(self) -> None:
                raise RuntimeError("led kapot")

            def idle(self) -> None:
                raise RuntimeError("led kapot")

        FakeProc.spawned = []
        backend = AplayBackend(APLAY_DEVICE, led=BadLed())
        self.addCleanup(backend.stop)
        with unittest.mock.patch("playback.subprocess.Popen", FakeProc):
            with self.assertLogs("pi-speler", level="ERROR"):
                backend.play(Path("audio/a-nederlands.wav"))
                backend.stop()
        self.assertEqual(len(FakeProc.spawned), 1)
        self.assertEqual(FakeProc.spawned[0].returncode, -15)


class NoFallbackTests(unittest.TestCase):
    ONLY_JACK = "card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]\n"

    def test_default_usb_stays_silent_without_amp_and_guide_uses_jack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            route = OutputRoute(Path(tmp) / "standaard", APLAY_DEVICE)
            led = RecordingLed()
            backend = AplayBackend(APLAY_DEVICE, follow_cards=True, route=route, led=led)
            self.addCleanup(backend.stop)
            listed = unittest.mock.Mock(stdout=self.ONLY_JACK, stderr="", returncode=0)
            FakeProc.spawned = []
            with (
                unittest.mock.patch("playback.subprocess.Popen", FakeProc),
                unittest.mock.patch("playback.subprocess.run", return_value=listed),
            ):
                with self.assertLogs("pi-speler", level="ERROR") as logs:
                    backend.play(Path("audio/a-nederlands.wav"))
                self.assertEqual(FakeProc.spawned, [])
                self.assertIn("niet naar de jack", "\n".join(logs.output))
                self.assertNotIn("blink", led.events)
                # Gids: de mini-jack, ook zonder USB.
                self.assertEqual(route.toggle_guide(), "jack")
                backend.play(Path("audio/a-nederlands.wav"))
                self.assertEqual(len(FakeProc.spawned), 1)
                self.assertEqual(FakeProc.spawned[0].cmd[2], APLAY_DEVICE)
                self.assertEqual(led.events[-1], "blink")

    def test_config_pin_makes_jack_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "standaard"
            route = OutputRoute(path, APLAY_DEVICE)
            self.assertEqual(route.toggle_default(), "jack")
            backend = AplayBackend(APLAY_DEVICE, follow_cards=True, route=OutputRoute(path, APLAY_DEVICE))
            self.addCleanup(backend.stop)
            FakeProc.spawned = []
            with unittest.mock.patch("playback.subprocess.Popen", FakeProc):
                backend.play(Path("audio/b-frans.wav"))
            self.assertEqual(FakeProc.spawned[0].cmd[2], APLAY_DEVICE)
            # Gids bij standaard jack: USB, en zonder versterker stil.
            backend.route.toggle_guide()
            listed = unittest.mock.Mock(stdout=self.ONLY_JACK, stderr="", returncode=0)
            with (
                unittest.mock.patch("playback.subprocess.Popen", FakeProc),
                unittest.mock.patch("playback.subprocess.run", return_value=listed),
                self.assertLogs("pi-speler", level="ERROR"),
            ):
                backend.play(Path("audio/b-frans.wav"))
            self.assertEqual(len(FakeProc.spawned), 1)

    def test_unreadable_card_list_does_not_fall_back_to_jack(self) -> None:
        route = OutputRoute(Path("/tmp/pi-speler-standaard-test-missing"), APLAY_DEVICE)
        backend = AplayBackend(APLAY_DEVICE, follow_cards=True, route=route)
        FakeProc.spawned = []
        with (
            unittest.mock.patch("playback.subprocess.Popen", FakeProc),
            unittest.mock.patch("playback.subprocess.run", side_effect=OSError("geen aplay")),
            self.assertLogs("pi-speler", level="ERROR"),
        ):
            backend.play(Path("audio/a-engels.wav"))
        self.assertEqual(FakeProc.spawned, [])

    def test_playback_and_buttons_survive_missing_usb(self) -> None:
        route = OutputRoute(Path("/tmp/pi-speler-standaard-test-missing"), APLAY_DEVICE)
        backend = AplayBackend(APLAY_DEVICE, follow_cards=True, route=route)
        playback = Playback(backend)
        listed = unittest.mock.Mock(stdout=self.ONLY_JACK, stderr="", returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "a-nederlands.wav"
            write_wav(wav)
            with (
                unittest.mock.patch("playback.subprocess.Popen", FakeProc),
                unittest.mock.patch("playback.subprocess.run", return_value=listed),
                self.assertLogs("pi-speler", level="ERROR"),
            ):
                playback.press(wav)
                playback.stop()
                playback.press(wav)


class TimedBackend:
    """Speelt 'seconds' lang, of tot stop. Onthoudt welk apparaat."""

    def __init__(self, seconds: float = 0.05, refuse: bool = False) -> None:
        self.seconds = seconds
        self.refuse = refuse
        self.events: list[tuple[str, str, str | None]] = []
        self._until = 0.0
        self._lock = threading.Lock()

    def stop(self) -> None:
        with self._lock:
            if self._until:
                self.events.append(("stop", "", None))
            self._until = 0.0

    def play(self, path: Path, device: str | None = None) -> bool:
        with self._lock:
            self.events.append(("play", Path(path).name, device))
            if self.refuse:
                return False
            self._until = time.monotonic() + self.seconds
            return True

    def is_playing(self) -> bool:
        with self._lock:
            return time.monotonic() < self._until

    def plays(self) -> list[tuple[str, str | None]]:
        with self._lock:
            return [(name, device) for kind, name, device in self.events if kind == "play"]


class StubLibrary:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        for name in FILE_NAMES.values():
            write_wav(folder / name)

    def wav_for(self, spec) -> Path:
        return spec.wav_path(self.folder)


class StartupTests(unittest.TestCase):
    JACK = APLAY_DEVICE

    def make(self, backend: TimedBackend) -> Player:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        route = OutputRoute(Path(tmp.name) / "standaard", self.JACK)
        return Player(StubLibrary(Path(tmp.name) / "audio"), Playback(backend), route)

    def test_three_a_clips_in_order_on_the_jack_then_default(self) -> None:
        self.assertEqual(
            [(s.version, s.language) for s in startup_specs()],
            [("a", "nl"), ("a", "fr"), ("a", "en")],
        )
        backend = TimedBackend(0.05)
        player = self.make(backend)
        thread = player.start_startup(startup_specs(), self.JACK, pause=0.01)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(
            backend.plays(),
            [
                ("a-nederlands.wav", self.JACK),
                ("a-frans.wav", self.JACK),
                ("a-engels.wav", self.JACK),
            ],
        )
        # Daarna: gewone keuze (standaard USB), geen afgedwongen jack.
        player.press_button(BUTTONS[3])
        self.assertEqual(backend.plays()[-1], ("b-nederlands.wav", None))

    def test_any_button_cancels_the_rest(self) -> None:
        for action in ("knop", "stop", "gids"):
            backend = TimedBackend(0.3)
            player = self.make(backend)
            thread = player.start_startup(startup_specs(), self.JACK, pause=0.01)
            self.assertTrue(wait_until(lambda: backend.plays() != []))
            if action == "knop":
                player.press_button(BUTTONS[5])
            elif action == "stop":
                player.stop()
            else:
                player.guide()
            thread.join(2)
            self.assertFalse(thread.is_alive(), action)
            names = [name for name, _device in backend.plays()]
            self.assertEqual(names[0], "a-nederlands.wav", action)
            self.assertNotIn("a-frans.wav", names, action)
            self.assertNotIn("a-engels.wav", names, action)
            if action == "knop":
                self.assertEqual(backend.plays()[-1], ("b-engels.wav", None))

    def test_sequence_stops_when_a_clip_cannot_start(self) -> None:
        backend = TimedBackend(refuse=True)
        player = self.make(backend)
        with self.assertLogs("pi-speler", level="ERROR"):
            thread = player.start_startup(startup_specs(), self.JACK, pause=0.01)
            thread.join(2)
        self.assertEqual(len(backend.plays()), 1)

    def test_switch_and_bench(self) -> None:
        with unittest.mock.patch.dict(os.environ, {"PI_SPELER_OPSTART": ""}):
            self.assertTrue(startup_enabled(False))
            self.assertFalse(startup_enabled(True))
        with unittest.mock.patch.dict(os.environ, {"PI_SPELER_OPSTART": "uit"}):
            self.assertFalse(startup_enabled(False))

    def test_forced_jack_plays_even_without_usb_amp(self) -> None:
        listed = unittest.mock.Mock(
            stdout="card 0: Headphones [bcm2835 Headphones], device 0: x\n",
            stderr="",
            returncode=0,
        )
        route = OutputRoute(Path("/tmp/pi-speler-standaard-test-missing"), self.JACK)
        led = RecordingLed()
        backend = AplayBackend(self.JACK, follow_cards=True, route=route, led=led)
        self.addCleanup(backend.stop)
        FakeProc.spawned = []
        with (
            unittest.mock.patch("playback.subprocess.Popen", FakeProc),
            unittest.mock.patch("playback.subprocess.run", return_value=listed),
        ):
            self.assertTrue(backend.play(Path("audio/a-nederlands.wav"), device=self.JACK))
            self.assertTrue(backend.is_playing())
            self.assertEqual(FakeProc.spawned[0].cmd[2], self.JACK)
            self.assertEqual(led.events[-1], "blink")
            # Gewone druk zonder versterker: stil, geen wissel naar de jack.
            with self.assertLogs("pi-speler", level="ERROR"):
                self.assertFalse(backend.play(Path("audio/a-frans.wav")))
            self.assertEqual(len(FakeProc.spawned), 1)
            self.assertFalse(backend.is_playing())


# Alleen nepwaarden. Echte wachtwoorden horen niet in tests.
FAKE_SSID = "TestNet"
FAKE_WIFI_PW = "nep-wifi-wachtwoord-123"
FAKE_USER_PW = "nep-gebruiker-wachtwoord"


def write_stub(folder: Path, name: str, body: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)


def openssl_sha512_works() -> bool:
    try:
        out = subprocess.run(
            ["openssl", "passwd", "-6", "-stdin"],
            input="x\n",
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except OSError:
        return False
    return out.startswith("$6$")


def all_card_text(folder: Path) -> str:
    parts = []
    for path in folder.rglob("*"):
        if path.is_file():
            parts.append(path.read_bytes().decode("utf-8", "replace"))
    return "\n".join(parts)


@unittest.skipUnless(shutil.which("bash") and openssl_sha512_works(), "bash en openssl passwd -6 nodig")
class WifiSetupTests(unittest.TestCase):
    def make_card(self, base: Path) -> Path:
        boot = base / "bootfs"
        boot.mkdir()
        (boot / "config.txt").write_text("auto_initramfs=1\n", encoding="utf-8")
        (boot / "cmdline.txt").write_text("console=tty1 root=PARTUUID=1234-02 rootwait\n", encoding="utf-8")
        return boot

    def stubs(self, base: Path, keychain: str | None) -> Path:
        bin_dir = base / "bin"
        bin_dir.mkdir()
        write_stub(
            bin_dir,
            "networksetup",
            'case "$1" in\n'
            '  -listallhardwareports) printf "Hardware Port: Wi-Fi\\nDevice: en0\\n" ;;\n'
            f'  -listpreferredwirelessnetworks) printf "Preferred networks on en0:\\n\\t{FAKE_SSID}\\n" ;;\n'
            "esac",
        )
        write_stub(bin_dir, "ipconfig", 'echo "  SSID : <redacted>"')
        if keychain is None:
            write_stub(bin_dir, "security", "exit 44")
        else:
            write_stub(bin_dir, "security", f'printf "%s\\n" "{keychain}"')
        return bin_dir

    def run_script(self, base: Path, boot: Path, keychain: str | None, answers: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{self.stubs(base, keychain)}{os.pathsep}{env.get('PATH', '')}"
        return subprocess.run(
            ["bash", str(ROOT / "sd" / "zet-klaar.sh"), "--boot", str(boot), "--wifi"],
            input=answers,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    def check_card(self, boot: Path, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        access = boot / "pi-speler" / "toegang"
        self.assertEqual((access / "hostnaam").read_text(encoding="utf-8").strip(), "pi-speler")
        self.assertEqual((access / "land").read_text(encoding="utf-8").strip(), "BE")
        user, hashed = (access / "gebruiker").read_text(encoding="utf-8").strip().split(":", 1)
        self.assertEqual(user, "gertjan")
        self.assertTrue(hashed.startswith("$6$"))
        conn = (access / "wifi.nmconnection").read_text(encoding="utf-8")
        self.assertIn(f"ssid={FAKE_SSID}\n", conn)
        self.assertIn("key-mgmt=wpa-psk", conn)
        psk = hashlib.pbkdf2_hmac("sha1", FAKE_WIFI_PW.encode(), FAKE_SSID.encode(), 4096, 32).hex()
        self.assertIn(f"psk={psk}\n", conn)
        self.assertTrue((boot / "ssh").is_file())
        self.assertTrue((boot / "pi-speler" / "toegang.sh").is_file())
        self.assertIn("systemd.run=/boot/firmware/pi-speler/eenmalig.sh", (boot / "cmdline.txt").read_text(encoding="utf-8"))
        # Geen leesbaar wachtwoord op de kaart, op het scherm of in een fout.
        card = all_card_text(boot)
        shown = result.stdout + result.stderr
        for secret in (FAKE_WIFI_PW, FAKE_USER_PW, hashed, psk):
            self.assertNotIn(secret, shown)
        for secret in (FAKE_WIFI_PW, FAKE_USER_PW):
            self.assertNotIn(secret, card)
        self.assertIn("pi-speler.local", shown)

    def test_typed_wifi_password_when_keychain_has_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            boot = self.make_card(base)
            answers = f"\n{FAKE_WIFI_PW}\n\n{FAKE_USER_PW}\n{FAKE_USER_PW}\n"
            result = self.run_script(base, boot, None, answers)
            self.check_card(boot, result)
            self.assertIn(f"Enter = {FAKE_SSID}", result.stderr)

    def test_keychain_password_is_used_without_asking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            boot = self.make_card(base)
            answers = f"\n\n{FAKE_USER_PW}\n{FAKE_USER_PW}\n"
            result = self.run_script(base, boot, FAKE_WIFI_PW, answers)
            self.check_card(boot, result)
            self.assertIn("gevonden", result.stderr)

    def test_different_passwords_stop_without_secrets_on_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            boot = self.make_card(base)
            answers = f"\n{FAKE_WIFI_PW}\n\n{FAKE_USER_PW}\nanders-wachtwoord\n"
            result = self.run_script(base, boot, None, answers)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((boot / "pi-speler" / "toegang").exists())
            self.assertNotIn("systemd.run", (boot / "cmdline.txt").read_text(encoding="utf-8"))
            self.assertNotIn(FAKE_WIFI_PW, result.stdout + result.stderr)

    def test_wifi_and_root_together_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            boot = self.make_card(base)
            result = subprocess.run(
                ["bash", str(ROOT / "sd" / "zet-klaar.sh"), "--boot", str(boot), "--root", str(base), "--wifi"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)


@unittest.skipUnless(shutil.which("bash"), "bash nodig")
class AccessOnPiTests(unittest.TestCase):
    def test_access_folder_is_applied_and_wiped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "systeem"
            (target / "etc" / "cloud").mkdir(parents=True)
            (target / "etc" / "hosts").write_text("127.0.0.1\tlocalhost\n127.0.1.1\t\traspberrypi\n", encoding="utf-8")
            state = target / "var" / "lib" / "NetworkManager"
            state.mkdir(parents=True)
            (state / "NetworkManager.state").write_text("[main]\nNetworkingEnabled=true\nWirelessEnabled=false\n", encoding="utf-8")
            rfkill = target / "var" / "lib" / "systemd" / "rfkill"
            rfkill.mkdir(parents=True)
            (rfkill / "platform-fe300000.mmcnr:wlan").write_text("1\n", encoding="utf-8")
            firmware = target / "boot" / "firmware"
            firmware.mkdir(parents=True)
            (firmware / "cmdline.txt").write_text("console=tty1 root=PARTUUID=1234-02 rootwait\n", encoding="utf-8")

            fake_hash = "$6$nepzout$nephash"
            access = base / "toegang"
            access.mkdir()
            (access / "hostnaam").write_text("pi-speler\n", encoding="utf-8")
            (access / "land").write_text("BE\n", encoding="utf-8")
            (access / "gebruiker").write_text(f"gertjan:{fake_hash}\n", encoding="utf-8")
            (access / "wifi.nmconnection").write_text("[connection]\nid=pi-speler-wifi\n", encoding="utf-8")

            log_file = base / "opdrachten.log"
            bin_dir = base / "bin"
            bin_dir.mkdir()
            write_stub(bin_dir, "id", "exit 1")
            write_stub(bin_dir, "getent", 'case "$2" in sudo|audio|gpio|video) exit 0 ;; esac\nexit 2')
            write_stub(bin_dir, "useradd", f'echo "useradd $*" >>"{log_file}"')
            write_stub(bin_dir, "chpasswd", f'echo "chpasswd $*" >>"{log_file}"; cat >"{base}/chpasswd.in"')
            write_stub(bin_dir, "systemctl", f'echo "systemctl $*" >>"{log_file}"')
            write_stub(bin_dir, "rfkill", f'echo "rfkill $*" >>"{log_file}"')
            write_stub(bin_dir, "raspi-config", "exit 1")
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["PI_SPELER_DOEL"] = str(target)
            result = subprocess.run(
                ["bash", str(ROOT / "toegang.sh"), str(access)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(fake_hash, result.stdout + result.stderr)
            self.assertFalse(access.exists())

            self.assertEqual((target / "etc" / "hostname").read_text(encoding="utf-8").strip(), "pi-speler")
            hosts = (target / "etc" / "hosts").read_text(encoding="utf-8")
            self.assertIn("127.0.1.1\tpi-speler", hosts)
            self.assertNotIn("raspberrypi", hosts)
            self.assertIn("preserve_hostname: true", (target / "etc" / "cloud" / "cloud.cfg.d" / "99-pi-speler.cfg").read_text(encoding="utf-8"))

            commands = log_file.read_text(encoding="utf-8")
            self.assertIn("useradd -m -s /bin/bash -G sudo,audio,video,gpio gertjan", commands)
            self.assertNotIn(fake_hash, commands)
            self.assertIn("chpasswd -e", commands)
            self.assertEqual((base / "chpasswd.in").read_text(encoding="utf-8").strip(), f"gertjan:{fake_hash}")
            self.assertIn("systemctl enable ssh", commands)
            self.assertIn("rfkill unblock wifi", commands)

            conn = target / "etc" / "NetworkManager" / "system-connections" / "pi-speler-wifi.nmconnection"
            self.assertTrue(conn.is_file())
            self.assertEqual(stat.S_IMODE(conn.stat().st_mode), 0o600)
            self.assertIn("WirelessEnabled=true", (state / "NetworkManager.state").read_text(encoding="utf-8"))
            self.assertEqual((rfkill / "platform-fe300000.mmcnr:wlan").read_text(encoding="utf-8").strip(), "0")
            self.assertIn("cfg80211.ieee80211_regdom=BE", (firmware / "cmdline.txt").read_text(encoding="utf-8"))

    def test_nothing_to_do_without_folder(self) -> None:
        result = subprocess.run(["bash", str(ROOT / "toegang.sh"), "/bestaat/niet"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class LGPIOFactory:
    pass


def fake_gpiozero(fail: bool) -> types.ModuleType:
    module = types.ModuleType("gpiozero")
    opened: list[int] = []

    class Button:
        pin_factory = LGPIOFactory()

        def __init__(self, pin: int, **_kwargs: object) -> None:
            if fail:
                raise OSError(22, "Invalid argument")
            opened.append(pin)
            self.when_pressed = None

        def close(self) -> None:
            pass

    module.Button = Button
    module.opened = opened
    return module


class PinFactoryTests(unittest.TestCase):
    def test_lgpio_is_the_default_and_env_wins(self) -> None:
        with (
            unittest.mock.patch.dict(os.environ, {}, clear=False),
            unittest.mock.patch.dict(sys.modules, {"lgpio": types.ModuleType("lgpio")}),
        ):
            os.environ.pop("GPIOZERO_PIN_FACTORY", None)
            self.assertEqual(choose_pin_factory(), "lgpio")
            self.assertEqual(os.environ["GPIOZERO_PIN_FACTORY"], "lgpio")
            os.environ["GPIOZERO_PIN_FACTORY"] = "native"
            self.assertEqual(choose_pin_factory(), "native")

    def test_missing_lgpio_gives_the_hint_and_lets_gpiozero_search(self) -> None:
        with (
            unittest.mock.patch.dict(os.environ, {"GPIOZERO_PIN_FACTORY": "lgpio"}),
            unittest.mock.patch.dict(sys.modules, {"lgpio": None}),
            self.assertLogs("pi-speler", level="ERROR") as logs,
        ):
            self.assertEqual(choose_pin_factory(), "automatisch")
            self.assertNotIn("GPIOZERO_PIN_FACTORY", os.environ)
        self.assertIn("python3-lgpio", "\n".join(logs.output))

    def player(self) -> Player:
        route = OutputRoute(Path("/tmp/pi-speler-standaard-test-missing"), APLAY_DEVICE)
        return Player(StubLibrary.__new__(StubLibrary), Playback(FakeBackend()), route)

    def test_no_button_opens_keeps_running_without_crash_loop(self) -> None:
        pause = unittest.mock.Mock()
        with (
            unittest.mock.patch.dict(os.environ, {"GPIOZERO_PIN_FACTORY": "lgpio"}),
            unittest.mock.patch.dict(
                sys.modules,
                {"gpiozero": fake_gpiozero(fail=True), "lgpio": types.ModuleType("lgpio")},
            ),
            unittest.mock.patch.object(pi_speler.signal, "pause", pause),
            self.assertLogs("pi-speler", level="INFO") as logs,
        ):
            pi_speler.serve_gpio(self.player())
        pause.assert_called_once()
        text = "\n".join(logs.output)
        self.assertIn("geen enkele knop kon openen", text)
        self.assertIn("python3-lgpio", text)
        # Eén volledige fout, de rest één regel.
        self.assertEqual(text.count("Traceback"), 1)

    def test_buttons_open_and_factory_is_logged(self) -> None:
        module = fake_gpiozero(fail=False)
        pause = unittest.mock.Mock()
        with (
            unittest.mock.patch.dict(os.environ, {"GPIOZERO_PIN_FACTORY": "lgpio"}),
            unittest.mock.patch.dict(sys.modules, {"gpiozero": module, "lgpio": types.ModuleType("lgpio")}),
            unittest.mock.patch.object(pi_speler.signal, "pause", pause),
            self.assertLogs("pi-speler", level="INFO") as logs,
        ):
            pi_speler.serve_gpio(self.player())
        self.assertEqual(len(module.opened), len(BUTTONS) + len(CONTROLS))
        self.assertIn("pin-factory LGPIOFactory", "\n".join(logs.output))
        pause.assert_called_once()


class LgpioCrashTests(unittest.TestCase):
    def test_lgpio_crash_on_import_is_caught(self) -> None:
        real_import = __import__

        def broken(name, *args, **kwargs):
            if name == "lgpio":
                raise FileNotFoundError(2, "No such file or directory", ".lgd-nfy-3")
            return real_import(name, *args, **kwargs)

        with (
            unittest.mock.patch.dict(os.environ, {"GPIOZERO_PIN_FACTORY": "lgpio"}),
            unittest.mock.patch("builtins.__import__", side_effect=broken),
            self.assertLogs("pi-speler", level="ERROR") as logs,
        ):
            self.assertEqual(choose_pin_factory(), "automatisch")
            self.assertNotIn("GPIOZERO_PIN_FACTORY", os.environ)
        text = "\n".join(logs.output)
        self.assertIn("lgpio start niet", text)
        self.assertIn("LG_WD", text)

    def test_any_factory_error_keeps_the_player_running(self) -> None:
        pause = unittest.mock.Mock()
        route = OutputRoute(Path("/tmp/pi-speler-standaard-test-missing"), APLAY_DEVICE)
        player = Player(StubLibrary.__new__(StubLibrary), Playback(FakeBackend()), route)
        with (
            unittest.mock.patch.object(pi_speler, "choose_pin_factory", side_effect=RuntimeError("kapot")),
            unittest.mock.patch.dict(sys.modules, {"gpiozero": fake_gpiozero(fail=True)}),
            unittest.mock.patch.object(pi_speler.signal, "pause", pause),
            self.assertLogs("pi-speler", level="ERROR"),
        ):
            pi_speler.serve_gpio(player)
        pause.assert_called_once()

    def test_lgpio_work_dir_is_set_and_entered(self) -> None:
        start = os.getcwd()
        self.addCleanup(os.chdir, start)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "run" / "pi-speler"
            with unittest.mock.patch.dict(os.environ, {"LG_WD": ""}):
                self.assertEqual(pi_speler.prepare_lgpio_dir(str(target)), str(target))
                self.assertEqual(os.environ["LG_WD"], str(target))
                self.assertEqual(Path(os.getcwd()).resolve(), target)
            os.chdir(start)
            blocker = Path(tmp) / "bestand"
            blocker.write_text("x", encoding="utf-8")
            with unittest.mock.patch.dict(os.environ, {"LG_WD": str(blocker)}):
                chosen = pi_speler.prepare_lgpio_dir(str(blocker))
                self.assertEqual(chosen, "/tmp")
                self.assertEqual(os.environ["LG_WD"], "/tmp")
            os.chdir(start)

    def test_missing_pactl_is_skipped_quietly(self) -> None:
        run = unittest.mock.Mock()
        with (
            unittest.mock.patch.object(pi_speler.shutil, "which", return_value=None),
            unittest.mock.patch.object(pi_speler, "_run_command", run),
            self.assertLogs("pi-speler", level="INFO") as logs,
        ):
            pi_speler.force_analog_output()
        run.assert_not_called()
        self.assertFalse([line for line in logs.output if line.startswith("WARNING")])
        self.assertIn("geen pactl", "\n".join(logs.output))


class InstallFileTests(unittest.TestCase):
    def test_service_starts_after_sound_and_restarts(self) -> None:
        text = (ROOT / "pi-speler.service").read_text(encoding="utf-8")
        self.assertIn("After=sound.target", text)
        self.assertIn("Restart=on-failure", text)
        self.assertIn("WantedBy=multi-user.target", text)
        self.assertNotIn("PI_SPELER_BENCH", text)
        # De groene led vraagt root.
        self.assertIn("User=root", text)
        self.assertIn("Environment=GPIOZERO_PIN_FACTORY=lgpio", text)
        install_text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('"${APT[@]}" install -y python3-lgpio', install_text)
        self.assertIn("python3-rpi-lgpio", install_text)
        self.assertIn("DPkg::Lock::Timeout=120", install_text)
        start = (ROOT / "start.sh").read_text(encoding="utf-8")
        # Geen apt bij elke start: dat hield het dpkg-slot vast.
        self.assertNotIn("apt-get", start)
        self.assertIn("LG_WD", start)
        self.assertIn("RuntimeDirectory=pi-speler", text)
        self.assertIn("WorkingDirectory=/run/pi-speler", text)
        self.assertIn("Environment=LG_WD=/run/pi-speler", text)
        klaar = (ROOT / "sd" / "zet-klaar.sh").read_text(encoding="utf-8")
        self.assertEqual(klaar.count("led.py"), 2)
        self.assertEqual(klaar.count("toegang.sh"), 2)
        self.assertIn(
            'bash "$ROOT/toegang.sh" "$ROOT/toegang"',
            (ROOT / "install.sh").read_text(encoding="utf-8"),
        )
        nieuw = (ROOT / "sd" / "nieuw-systeem.sh").read_text(encoding="utf-8")
        self.assertIn("--wifi", nieuw)
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("python3-gpiozero", install)
        self.assertIn("alsa-utils", install)
        self.assertIn("pulseaudio-utils", install)
        self.assertIn("systemctl enable", install)
        self.assertIn("/var/lib/pi-speler", install)
        self.assertNotIn("apt-get remove", install)
        self.assertNotIn("config.txt", install)
        self.assertNotIn("RPi.GPIO", install)


if __name__ == "__main__":
    unittest.main()
