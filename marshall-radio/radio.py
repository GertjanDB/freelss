#!/usr/bin/env python3
"""Speel Belgische radio naar een Marshall-speaker, zonder telefoon."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATIONS_PATH = ROOT / "stations.json"


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


class Player:
    def __init__(self, stations: list, config: dict):
        self.stations = {s["id"]: s for s in stations}
        self.volume = int(config.get("volume", 70))
        self.current_id = None
        self.proc = None
        self.mpv = shutil.which("mpv")

    def status(self) -> dict:
        alive = self.proc is not None and self.proc.poll() is None
        if not alive:
            self.proc = None
        station = self.stations.get(self.current_id) if alive else None
        return {
            "backend": "mpv" if self.mpv else "browser",
            "hasMpv": bool(self.mpv),
            "playing": alive,
            "stationId": self.current_id if alive else None,
            "stationName": station["name"] if station else None,
            "volume": self.volume,
        }

    def play(self, station_id: str) -> dict:
        station = self.stations.get(station_id)
        if not station:
            raise KeyError(station_id)
        if not self.mpv:
            self.current_id = station_id
            return self.status()
        self.stop()
        self.current_id = station_id
        self.proc = subprocess.Popen(
            [
                self.mpv,
                "--no-video",
                "--really-quiet",
                "--no-terminal",
                "--audio-display=no",
                f"--volume={self.volume}",
                station["url"],
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return self.status()

    def stop(self) -> dict:
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.proc = None
        return self.status()

    def set_volume(self, volume: int) -> dict:
        self.volume = max(0, min(100, int(volume)))
        if self.current_id and self.proc and self.proc.poll() is None:
            self.play(self.current_id)
        return self.status()


class Handler(SimpleHTTPRequestHandler):
    player: Player
    stations: list

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, payload, code=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self.path = "/radio.html"
            return super().do_GET()
        if path == "/api/status":
            return self._json(self.player.status())
        if path == "/api/stations":
            return self._json(self.stations)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._read_json()
        try:
            if path == "/api/play":
                station_id = data.get("id") or data.get("stationId")
                return self._json(self.player.play(station_id))
            if path == "/api/stop":
                return self._json(self.player.stop())
            if path == "/api/volume":
                return self._json(self.player.set_volume(data.get("volume", 70)))
        except KeyError:
            return self._json({"error": "onbekende zender"}, 404)
        self._json({"error": "onbekend"}, 404)


def main():
    config = load_json(CONFIG_PATH, {"default": "radio2", "volume": 70, "autostart": True, "port": 8088})
    stations = load_json(STATIONS_PATH, [])
    if not stations:
        sys.exit("stations.json ontbreekt of is leeg")
    player = Player(stations, config)
    Handler.player = player
    Handler.stations = stations

    if config.get("autostart", True) and player.mpv:
        default_id = config.get("default") or stations[0]["id"]
        try:
            player.play(default_id)
            print("Gestart:", player.stations[default_id]["name"], flush=True)
        except KeyError:
            print("Standaardzender niet gevonden:", default_id, flush=True)
    elif not player.mpv:
        print("mpv niet gevonden — browser speelt zelf (oké om te testen).", flush=True)

    port = int(config.get("port", 8088))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Semi-slim radio op http://0.0.0.0:{port}", flush=True)

    def shutdown(*_args):
        player.stop()
        server.shutdown()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        server.serve_forever()
    finally:
        player.stop()


if __name__ == "__main__":
    main()
