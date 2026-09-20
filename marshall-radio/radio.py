#!/usr/bin/env python3
"""Speel Belgische radio naar een Marshall Acton over wifi (Chromecast).

AUX blijft vrij voor de platenspeler, Bluetooth voor de gsm.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATIONS_PATH = ROOT / "stations.json"


class CastError(RuntimeError):
    pass


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def match_cast(casts, needle: str):
    """Kies een Chromecast. needle='Acton' matcht 'Acton Multi-room'."""
    named = [(cc, (getattr(cc, "name", None) or "").strip()) for cc in casts]
    if needle:
        want = needle.casefold()
        hits = [(cc, name) for cc, name in named if want in name.casefold()]
        if hits:
            return hits[0][0]
        return None
    for cc, name in named:
        lower = name.casefold()
        if "acton" in lower or "marshall" in lower:
            return cc
    return named[0][0] if named else None


class ChromecastSink:
    def __init__(self, device: str = "Acton", host: str = ""):
        self.device = (device or "Acton").strip()
        self.host = (host or "").strip() or None
        self.browser = None
        self.cast = None
        self.lock = threading.Lock()
        try:
            import pychromecast  # noqa: F401
        except ImportError as exc:
            raise CastError(
                "pychromecast ontbreekt. Op de Pi: sudo ./install.sh"
            ) from exc

    def close(self):
        with self.lock:
            if self.browser is not None:
                try:
                    self.browser.stop_discovery()
                except Exception:
                    pass
            self.browser = None
            self.cast = None

    def list_names(self, timeout: float = 8) -> list[str]:
        import pychromecast

        known = [self.host] if self.host else None
        casts, browser = pychromecast.get_chromecasts(
            timeout=timeout, known_hosts=known
        )
        names = [cc.name for cc in casts if getattr(cc, "name", None)]
        try:
            browser.stop_discovery()
        except Exception:
            pass
        return names

    def connect(self, timeout: float = 12):
        import pychromecast

        known = [self.host] if self.host else None
        if self.browser is not None:
            try:
                self.browser.stop_discovery()
            except Exception:
                pass
            self.browser = None
            self.cast = None
        casts, browser = pychromecast.get_chromecasts(
            timeout=timeout, known_hosts=known
        )
        self.browser = browser
        self.cast = match_cast(casts, self.device)
        if self.cast is None:
            found = ", ".join(cc.name for cc in casts if getattr(cc, "name", None)) or "geen"
            raise CastError(
                "Acton niet gevonden op wifi (gevonden: %s). "
                "Zet de speaker aan, bronknop op wifi, zelfde netwerk als de Pi."
                % found
            )
        self.cast.wait(timeout=timeout)

    def ensure(self):
        if self.cast is None:
            self.connect()
            return
        try:
            if not self.cast.socket_client.is_connected:
                self.connect()
        except Exception:
            self.connect()

    def play(self, url: str, title: str, volume: int):
        with self.lock:
            self.ensure()
            self.cast.set_volume(max(0, min(100, volume)) / 100.0)
            mc = self.cast.media_controller
            mc.play_media(
                url,
                "audio/mpeg",
                title=title,
                stream_type="LIVE",
                autoplay=True,
            )
            mc.block_until_active(timeout=12)

    def stop(self):
        with self.lock:
            if self.cast is None:
                return
            try:
                self.cast.media_controller.stop()
            except Exception:
                pass
            try:
                self.cast.quit_app()
            except Exception:
                pass

    def set_volume(self, volume: int):
        with self.lock:
            if self.cast is None:
                return
            try:
                self.cast.set_volume(max(0, min(100, volume)) / 100.0)
            except Exception:
                pass

    @property
    def name(self) -> str | None:
        if self.cast is None:
            return None
        return getattr(self.cast, "name", None)


class Player:
    def __init__(self, stations: list, config: dict, sink=None):
        self.stations = {s["id"]: s for s in stations}
        self.volume = int(config.get("volume", 70))
        self.output = (config.get("output") or "chromecast").strip().lower()
        self.current_id = None
        self.playing = False
        self.last_error = ""
        self.proc = None
        self.mpv = shutil.which("mpv")
        self.sink = sink
        if self.output == "chromecast" and self.sink is None:
            try:
                self.sink = ChromecastSink(
                    device=str(config.get("device") or "Acton"),
                    host=str(config.get("host") or ""),
                )
            except CastError as exc:
                self.last_error = str(exc)
                self.sink = None

    def status(self) -> dict:
        if self.output == "chromecast":
            backend = "chromecast"
            alive = bool(self.playing and self.sink is not None)
        elif self.output == "mpv":
            alive = self.proc is not None and self.proc.poll() is None
            if not alive:
                self.proc = None
                self.playing = False
            backend = "mpv" if self.mpv else "browser"
        else:
            alive = False
            backend = "browser"
        station = self.stations.get(self.current_id) if alive else None
        return {
            "backend": backend,
            "output": self.output,
            "hasRemote": backend in ("mpv", "chromecast"),
            "hasMpv": bool(self.mpv),
            "playing": bool(alive),
            "stationId": self.current_id if alive else None,
            "stationName": station["name"] if station else None,
            "volume": self.volume,
            "deviceName": self.sink.name if self.sink is not None else None,
            "error": self.last_error,
        }

    def play(self, station_id: str) -> dict:
        station = self.stations.get(station_id)
        if not station:
            raise KeyError(station_id)
        self.last_error = ""
        if self.output == "chromecast":
            if self.sink is None:
                raise CastError(self.last_error or "Chromecast is niet klaar.")
            try:
                self.sink.play(station["url"], station["name"], self.volume)
            except CastError:
                self.playing = False
                raise
            except Exception as exc:
                self.playing = False
                raise CastError(
                    "Acton reageert niet over wifi. Zet hem aan, bronknop op wifi. (%s)"
                    % exc
                ) from exc
            self.current_id = station_id
            self.playing = True
            return self.status()
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
        self.playing = True
        return self.status()

    def stop(self) -> dict:
        self.playing = False
        if self.sink is not None:
            try:
                self.sink.stop()
            except Exception:
                pass
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
        if self.output == "chromecast" and self.sink is not None and self.playing:
            self.sink.set_volume(self.volume)
        elif self.output == "mpv" and self.current_id and self.proc and self.proc.poll() is None:
            self.play(self.current_id)
        return self.status()

    def close(self):
        self.stop()
        if self.sink is not None:
            try:
                self.sink.close()
            except Exception:
                pass


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
        if path == "/api/devices":
            names = []
            err = ""
            if self.player.sink is not None:
                try:
                    names = self.player.sink.list_names()
                except Exception as exc:
                    err = str(exc)
            else:
                err = self.player.last_error or "Chromecast is niet klaar."
            return self._json({"devices": names, "error": err})
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
        except CastError as exc:
            payload = self.player.status()
            payload["error"] = str(exc)
            self.player.last_error = str(exc)
            return self._json(payload, 503)
        self._json({"error": "onbekend"}, 404)


def autostart_loop(player: Player, station_id: str, stop_event: threading.Event):
    while not stop_event.is_set():
        if player.status().get("playing"):
            stop_event.wait(20)
            continue
        try:
            player.play(station_id)
            print("Gestart:", player.stations[station_id]["name"], flush=True)
        except Exception as exc:
            print("Wacht op Acton op wifi:", exc, flush=True)
        stop_event.wait(15)


def discover(config: dict) -> int:
    try:
        sink = ChromecastSink(
            device=str(config.get("device") or "Acton"),
            host=str(config.get("host") or ""),
        )
    except CastError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("Zoeken naar Chromecast op het netwerk…", flush=True)
    names = sink.list_names(timeout=12)
    if not names:
        print("Niets gevonden. Acton aan? Zelfde wifi als deze machine? Bronknop op wifi?")
        return 1
    print("Gevonden:")
    for name in names:
        mark = "  ← deze" if config.get("device", "Acton").lower() in name.lower() else ""
        print(f"  - {name}{mark}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Semi-slimme Marshall-radio over wifi")
    parser.add_argument("--discover", action="store_true", help="Toon Chromecast-speakers op het netwerk")
    args = parser.parse_args()

    config = load_json(
        CONFIG_PATH,
        {
            "default": "radio2",
            "volume": 70,
            "autostart": True,
            "port": 8088,
            "output": "chromecast",
            "device": "Acton",
            "host": "",
        },
    )
    if args.discover:
        raise SystemExit(discover(config))

    stations = load_json(STATIONS_PATH, [])
    if not stations:
        sys.exit("stations.json ontbreekt of is leeg")
    player = Player(stations, config)
    Handler.player = player
    Handler.stations = stations

    stop_event = threading.Event()
    worker = None
    if config.get("autostart", True) and player.output == "chromecast":
        default_id = config.get("default") or stations[0]["id"]
        worker = threading.Thread(
            target=autostart_loop, args=(player, default_id, stop_event), daemon=True
        )
        worker.start()
    elif config.get("autostart", True) and player.mpv and player.output == "mpv":
        default_id = config.get("default") or stations[0]["id"]
        try:
            player.play(default_id)
            print("Gestart:", player.stations[default_id]["name"], flush=True)
        except KeyError:
            print("Standaardzender niet gevonden:", default_id, flush=True)
    elif player.output != "chromecast" and not player.mpv:
        print("mpv niet gevonden — browser speelt zelf (oké om te testen).", flush=True)

    port = int(config.get("port", 8088))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Semi-slim radio op http://0.0.0.0:{port}  output={player.output}", flush=True)

    def shutdown(*_args):
        stop_event.set()
        player.close()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        server.serve_forever()
    finally:
        stop_event.set()
        player.close()


if __name__ == "__main__":
    main()
