#!/usr/bin/env python3
"""Serve the Mutsje app and merge KMI Jette weather with a live forecast."""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8765
CACHE_SECONDS = 8 * 60
USER_AGENT = "MutsjeApp/1.0 (materniteit Jette; +https://www.meteo.be)"

JETTE_LAT = 50.8754
JETTE_LON = 4.3246
UCCLE_SYNOP = 6447

KMI_BULLETIN_FALLBACK = (
    "Deze namiddag is het vaak zwaarbewolkt en aanvankelijk nog overwegend droog. "
    "In de loop van de namiddag trekt een storing het land in vanaf de kust met regen. "
    "In de latere namiddag en vooravond bereikt de regen het centrum van het land. "
    "De maxima schommelen tussen 15 en 20 graden bij een matige zuidwestelijke wind."
)

FALLBACK = {
    "ok": True,
    "source": "KMI-momentopname",
    "location": "Jette",
    "station": "Ukkel (KMI)",
    "condition": "Zwaar bewolkt, droog",
    "bulletin": KMI_BULLETIN_FALLBACK,
    "observedAt": "2026-09-17T12:00:00+02:00",
    "temp": 17.2,
    "feelsLike": 13.8,
    "humidity": 64,
    "cloudinessOctas": 7,
    "cloudCover": 100,
    "windKmh": 22,
    "windGustKmh": 38,
    "windDirection": 222,
    "precipMm": 0,
    "raining": False,
    "rainSoon": True,
    "todayMin": 12,
    "todayMax": 19,
    "hourly": [],
}

_cache = {"payload": None, "fetched_at": 0.0}
_lock = threading.Lock()


def _get(url: str, timeout: float = 8.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _wind_kmh(speed: float | None, unit: int | None) -> float | None:
    if speed is None:
        return None
    # KMI synop: unit 0 = km/h, 1 = m/s, 2 = knots
    if unit == 1:
        return round(speed * 3.6, 1)
    if unit == 2:
        return round(speed * 1.852, 1)
    return round(float(speed), 1)


def fetch_kmi_synop() -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = urllib.parse.urlencode(
        {
            "service": "wfs",
            "version": "2.0.0",
            "request": "getFeature",
            "typeNames": "synop:synop_data",
            "outputformat": "application/json",
            "count": "5",
            "sortBy": "timestamp D",
            "CQL_FILTER": f"code={UCCLE_SYNOP} AND timestamp AFTER {since}",
        }
    )
    url = f"https://opendata.meteo.be/service/ows?{query}"
    data = json.loads(_get(url, timeout=10).decode("utf-8"))
    features = data.get("features") or []
    if not features:
        raise RuntimeError("geen KMI-synop")
    features.sort(key=lambda item: item["properties"].get("timestamp") or "", reverse=True)
    props = features[0]["properties"]
    stamp = props.get("timestamp")
    if stamp:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - observed > timedelta(hours=6):
            raise RuntimeError(f"KMI-synop te oud: {stamp}")
    wind = _wind_kmh(props.get("wind_speed"), props.get("wind_speed_unit"))
    gust = _wind_kmh(props.get("wind_peak_speed"), props.get("wind_speed_unit"))
    octas = props.get("cloudiness")
    return {
        "station": "Ukkel (KMI)",
        "observedAt": stamp,
        "temp": props.get("temp"),
        "humidity": props.get("humidity_relative"),
        "cloudinessOctas": octas,
        "cloudCover": None if octas is None else int(round((octas / 8) * 100)),
        "windKmh": wind,
        "windGustKmh": gust,
        "windDirection": props.get("wind_direction"),
        "pressure": props.get("pressure"),
    }


def fetch_kmi_widget() -> dict:
    html = _get(
        "https://www.meteo.be/services/widget/?lang=nl&nbDay=5&postcode=1090&type=7",
        timeout=8,
    ).decode("utf-8", "ignore")
    temps = [int(value) for value in re.findall(r"(-?\d+)\s*°", html)]
    today_min = today_max = None
    if len(temps) >= 2:
        today_min, today_max = sorted(temps[:2])
    condition = None
    match = re.search(
        r"Weersverwachting voor vandaag.*?</h2>\s*<p[^>]*>(.*?)</p>",
        html,
        re.I | re.S,
    )
    bulletin = re.sub(r"<[^>]+>", " ", match.group(1)).strip() if match else None
    if bulletin:
        bulletin = re.sub(r"\s+", " ", bulletin)
    if re.search(r"zwaar\s*bewolkt", html, re.I):
        condition = "Zwaar bewolkt, droog" if "droog" in html.lower() else "Zwaar bewolkt"
    return {
        "todayMin": today_min,
        "todayMax": today_max,
        "bulletin": bulletin,
        "condition": condition,
    }


def fetch_kmi_jette_page() -> dict:
    html = _get("https://www.meteo.be/nl/jette", timeout=8).decode("utf-8", "ignore")
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\n+", "\n", text)
    condition = None
    for line in text.splitlines():
        clean = " ".join(line.split())
        if re.search(r"(bewolkt|regen|opklaring|zonnig|mist|buien)", clean, re.I):
            if 8 < len(clean) < 80:
                condition = clean.rstrip(".")
                break
    return {"condition": condition}


def fetch_open_meteo() -> dict:
    params = {
        "latitude": JETTE_LAT,
        "longitude": JETTE_LON,
        "current": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "weather_code",
                "cloud_cover",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "precipitation",
                "is_day",
            ]
        ),
        "hourly": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Europe/Brussels",
        "forecast_days": "2",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    return json.loads(_get(url, timeout=8).decode("utf-8"))


def _hourly(meteo: dict) -> list[dict]:
    hourly = meteo.get("hourly") or {}
    times = hourly.get("time") or []
    brussels = ZoneInfo("Europe/Brussels")
    now = datetime.now(brussels).replace(minute=0, second=0, microsecond=0)
    rows = []
    for index, stamp in enumerate(times):
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=brussels)
        if moment < now:
            continue
        rows.append(
            {
                "time": stamp,
                "temp": (hourly.get("temperature_2m") or [None])[index],
                "feelsLike": (hourly.get("apparent_temperature") or [None])[index],
                "rainChance": (hourly.get("precipitation_probability") or [None])[index],
                "precipMm": (hourly.get("precipitation") or [None])[index],
                "windKmh": (hourly.get("wind_speed_10m") or [None])[index],
                "weatherCode": (hourly.get("weather_code") or [None])[index],
            }
        )
        if len(rows) >= 10:
            break
    return rows


def build_payload() -> dict:
    payload = dict(FALLBACK)
    sources = ["KMI"]
    try:
        synop = fetch_kmi_synop()
        payload.update({key: value for key, value in synop.items() if value is not None})
        payload["source"] = "KMI Ukkel"
    except Exception as error:
        payload["kmiError"] = str(error)
        sources = ["KMI-momentopname"]

    try:
        widget = fetch_kmi_widget()
        for key, value in widget.items():
            if value is not None:
                payload[key] = value
    except Exception:
        pass

    try:
        page = fetch_kmi_jette_page()
        if page.get("condition"):
            payload["condition"] = page["condition"]
    except Exception:
        pass

    try:
        meteo = fetch_open_meteo()
        current = meteo.get("current") or {}
        if payload.get("temp") is None:
            payload["temp"] = current.get("temperature_2m")
        payload["feelsLike"] = current.get("apparent_temperature", payload.get("feelsLike"))
        payload["precipMm"] = current.get("precipitation", 0) or 0
        payload["raining"] = bool(payload["precipMm"] and payload["precipMm"] > 0)
        if not payload.get("windKmh"):
            payload["windKmh"] = current.get("wind_speed_10m")
        if not payload.get("windGustKmh"):
            payload["windGustKmh"] = current.get("wind_gusts_10m")
        if not payload.get("humidity"):
            payload["humidity"] = current.get("relative_humidity_2m")
        if payload.get("cloudCover") is None:
            payload["cloudCover"] = current.get("cloud_cover")
        daily = meteo.get("daily") or {}
        if payload.get("todayMin") is None and daily.get("temperature_2m_min"):
            payload["todayMin"] = daily["temperature_2m_min"][0]
        if payload.get("todayMax") is None and daily.get("temperature_2m_max"):
            payload["todayMax"] = daily["temperature_2m_max"][0]
        payload["hourly"] = _hourly(meteo)
        soon = payload["hourly"][:6]
        payload["rainSoon"] = any((item.get("rainChance") or 0) >= 40 or (item.get("precipMm") or 0) > 0 for item in soon)
        sources.append("Open-Meteo uurverwachting")
    except Exception as error:
        payload["forecastError"] = str(error)

    if not payload.get("bulletin"):
        payload["bulletin"] = KMI_BULLETIN_FALLBACK
    if not payload.get("condition"):
        payload["condition"] = "Zwaar bewolkt, droog"
    payload["sources"] = sources
    payload["ok"] = True
    payload["fetchedAt"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return payload


def get_weather() -> dict:
    now = time.time()
    with _lock:
        if _cache["payload"] and now - _cache["fetched_at"] < CACHE_SECONDS:
            return _cache["payload"]
    try:
        payload = build_payload()
    except Exception as error:
        payload = dict(FALLBACK)
        payload["ok"] = True
        payload["offline"] = True
        payload["error"] = str(error)
    with _lock:
        _cache["payload"] = payload
        _cache["fetched_at"] = time.time()
    return payload


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        print("[mutsje]", self.address_string(), "-", args[0] if args else format)

    def do_GET(self):
        if self.path.split("?", 1)[0] in {"/api/weather", "/api/weather.json"}:
            body = json.dumps(get_weather(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


def main() -> None:
    threading.Thread(target=get_weather, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Mutsje-app: http://127.0.0.1:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
