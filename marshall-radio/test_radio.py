#!/usr/bin/env python3
import unittest

from radio import CastError, Player, match_cast


class FakeCast:
    def __init__(self, name):
        self.name = name


class FakeSink:
    def __init__(self, name="Acton Multi-room"):
        self.name = name
        self.played = []
        self.stopped = False
        self.volume = None

    def play(self, url, title, volume):
        self.played.append((url, title, volume))

    def stop(self):
        self.stopped = True

    def set_volume(self, volume):
        self.volume = volume

    def close(self):
        pass

    def list_names(self, timeout=8):
        return [self.name]


class MatchTests(unittest.TestCase):
    def test_substring_acton(self):
        casts = [FakeCast("Living Room"), FakeCast("Acton Multi-room")]
        self.assertEqual(match_cast(casts, "Acton").name, "Acton Multi-room")

    def test_prefers_marshall_when_no_needle(self):
        casts = [FakeCast("TV"), FakeCast("Marshall keuken")]
        self.assertEqual(match_cast(casts, "").name, "Marshall keuken")

    def test_empty(self):
        self.assertIsNone(match_cast([], "Acton"))


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.stations = [
            {"id": "radio2", "name": "Radio 2", "url": "https://example.test/r2.mp3"}
        ]
        self.sink = FakeSink()
        self.player = Player(
            self.stations,
            {"output": "chromecast", "volume": 65, "device": "Acton"},
            sink=self.sink,
        )

    def test_play_over_wifi_not_aux(self):
        status = self.player.play("radio2")
        self.assertEqual(status["backend"], "chromecast")
        self.assertTrue(status["hasRemote"])
        self.assertTrue(status["playing"])
        self.assertEqual(status["deviceName"], "Acton Multi-room")
        self.assertEqual(self.sink.played[-1][1], "Radio 2")
        self.assertEqual(self.sink.played[-1][2], 65)

    def test_stop_and_volume(self):
        self.player.play("radio2")
        self.player.set_volume(40)
        self.assertEqual(self.sink.volume, 40)
        self.player.stop()
        self.assertTrue(self.sink.stopped)
        self.assertFalse(self.player.status()["playing"])

    def test_unknown_station(self):
        with self.assertRaises(KeyError):
            self.player.play("bestaatniet")

    def test_keeps_error_when_sink_missing(self):
        player = Player(self.stations, {"output": "chromecast"})
        if player.sink is not None:
            self.skipTest("pychromecast is geïnstalleerd")
        self.assertTrue(player.last_error)
        with self.assertRaises(CastError):
            player.play("radio2")
        self.assertTrue(player.status()["error"])

    def test_cast_error_surfaces(self):
        class Boom(FakeSink):
            def play(self, url, title, volume):
                raise CastError("Acton niet gevonden op wifi")

        player = Player(self.stations, {"output": "chromecast"}, sink=Boom())
        with self.assertRaises(CastError):
            player.play("radio2")
        self.assertFalse(player.status()["playing"])


if __name__ == "__main__":
    unittest.main()
