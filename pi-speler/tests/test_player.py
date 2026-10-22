# SPDX-License-Identifier: GPL-3.0-or-later
"""Knop → bestand, en een nieuwe druk kapt het vorige geluid af."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import APLAY_DEVICE, BUTTON_KWARGS, force_analog_command, volume_command
from mapping import BUTTONS, parse_bench_line, resolve_audio_root
from playback import AplayBackend, Playback, aplay_command

# Onafhankelijk van mapping.py, zodat een verschoven pin de test laat falen.
SPEC = [
    (1, "nl", 17, 11),
    (1, "fr", 27, 13),
    (1, "en", 22, 15),
    (2, "nl", 5, 29),
    (2, "fr", 6, 31),
    (2, "en", 13, 33),
    (3, "nl", 19, 35),
    (3, "fr", 26, 37),
    (3, "en", 23, 16),
    (4, "nl", 24, 18),
    (4, "fr", 25, 22),
    (4, "en", 12, 32),
    (5, "nl", 16, 36),
    (5, "fr", 20, 38),
    (5, "en", 21, 40),
    (6, "nl", 4, 7),
    (6, "fr", 18, 12),
    (6, "en", 7, 26),
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
        self.assertEqual(len(BUTTONS), 18)
        self.assertEqual(len({b.bcm for b in BUTTONS}), 18)
        self.assertEqual(len({b.header_pin for b in BUTTONS}), 18)
        for spec in BUTTONS:
            self.assertNotIn(spec.header_pin, POWER_OR_GND)

        root = Path("/audio")
        paths = [spec.wav_path(root) for spec in BUTTONS]
        self.assertEqual(len(set(paths)), 18)
        self.assertEqual(paths[0], Path("/audio/nl/1.wav"))
        self.assertEqual(paths[-1], Path("/audio/en/6.wav"))
        for version in range(1, 7):
            for language in ("nl", "fr", "en"):
                match = [
                    spec
                    for spec in BUTTONS
                    if spec.version == version and spec.language == language
                ]
                self.assertEqual(len(match), 1)
                self.assertEqual(
                    match[0].wav_path(root),
                    Path("/audio") / language / f"{version}.wav",
                )

    def test_buttons_are_active_low_with_pullup_and_40ms_debounce(self) -> None:
        self.assertEqual(BUTTON_KWARGS["pull_up"], True)
        self.assertEqual(BUTTON_KWARGS["bounce_time"], 0.04)
        source = (ROOT / "pi_speler.py").read_text(encoding="utf-8")
        self.assertIn("when_pressed", source)
        self.assertNotIn("when_held", source)
        self.assertNotIn("RPi.GPIO", source)
        for name in ("config.py", "mapping.py", "playback.py", "pi_speler.py"):
            self.assertNotIn("RPi.GPIO", (ROOT / name).read_text(encoding="utf-8"))

    def test_bench_lines_use_the_same_map(self) -> None:
        dutch = parse_bench_line("nl 1")
        self.assertEqual((dutch.version, dutch.language, dutch.bcm), (1, "nl", 17))
        french = parse_bench_line("FR3")
        self.assertEqual((french.version, french.language, french.bcm), (3, "fr", 26))
        english = parse_bench_line("6 en")
        self.assertEqual((english.version, english.language, english.bcm), (6, "en", 7))
        self.assertEqual(parse_bench_line("quit"), "quit")
        self.assertEqual(parse_bench_line("stop"), "stop")
        self.assertIsNone(parse_bench_line("nl 7"))
        self.assertIsNone(parse_bench_line(""))

    def test_usb_stick_wins_only_when_all_three_languages_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = base / "app"
            (app / "audio" / "nl").mkdir(parents=True)
            usb = base / "stick"
            for language in ("nl", "fr", "en"):
                (usb / "audio" / language).mkdir(parents=True)
            self.assertEqual(
                resolve_audio_root(app, usb),
                (usb / "audio").resolve(),
            )
            (usb / "audio" / "en").rmdir()
            self.assertEqual(
                resolve_audio_root(app, usb),
                (app / "audio").resolve(),
            )


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


class InstallFileTests(unittest.TestCase):
    def test_service_starts_after_sound_and_restarts(self) -> None:
        text = (ROOT / "pi-speler.service").read_text(encoding="utf-8")
        self.assertIn("After=sound.target", text)
        self.assertIn("Restart=on-failure", text)
        self.assertIn("WantedBy=multi-user.target", text)
        self.assertNotIn("PI_SPELER_BENCH", text)
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("python3-gpiozero", install)
        self.assertIn("alsa-utils", install)
        self.assertIn("pulseaudio-utils", install)
        self.assertIn("systemctl enable", install)
        self.assertNotIn("apt-get remove", install)
        self.assertNotIn("config.txt", install)
        self.assertNotIn("RPi.GPIO", install)


if __name__ == "__main__":
    unittest.main()
