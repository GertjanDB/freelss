#!/usr/bin/env python3
"""Website voor drankjes die je lekker vindt, met drankjes.xlsx als bron."""

from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from zipfile import BadZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.properties import CalcProperties
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_PATH = ROOT / "data" / "drankjes.xlsx"
LOCK = threading.Lock()
MAX_DRINKS = 200
GLASS_ML = 250
SUGAR_CUBE_G = 4

HEADER_MAP = {
    "naam": "naam",
    "suiker (g/100 ml)": "suiker",
    "suiker": "suiker",
    "suiker per 100 ml": "suiker",
    "calorieën (kcal/100 ml)": "kcal",
    "calorieen (kcal/100 ml)": "kcal",
    "calorieën": "kcal",
    "calorieen": "kcal",
    "kcal": "kcal",
    "notitie": "notitie",
    "toegevoegd": "toegevoegd",
    "rang": "rang",
    "id": "id",
}


class DrinkError(Exception):
    pass


class StoreError(Exception):
    pass


@dataclass
class Drink:
    id: str
    naam: str
    suiker: float
    kcal: float
    notitie: str
    toegevoegd: str
    source_row: int | None = None


@dataclass
class Loaded:
    drinks: list[Drink]
    warnings: list[str]
    dirty: bool


def seed_drinks() -> list[Drink]:
    today = date.today().isoformat()
    rows = [
        (
            "ice-tea",
            "Ice tea (Lipton Peach)",
            3,
            13,
            "Lipton Peach: gezoet met suiker en stevia.",
        ),
        (
            "yugen",
            "Yugen Kombucha Passion Fruit Elderflower",
            3.8,
            15,
            "Gefermenteerde thee met 4% passievruchtsap.",
        ),
        (
            "almdudler",
            "Almdudler",
            8,
            33,
            "Oostenrijkse kruidenlimonade.",
        ),
        (
            "cola",
            "Coca-Cola",
            10.6,
            42,
            "Klassieke cola.",
        ),
    ]
    return [
        Drink(id=i, naam=n, suiker=s, kcal=k, notitie=note, toegevoegd=today)
        for i, n, s, k, note in rows
    ]


def band(suiker: float) -> str:
    if suiker <= 5:
        return "lichter"
    if suiker <= 8:
        return "gemiddeld"
    return "zwaar"


def ranked(drinks: list[Drink]) -> list[Drink]:
    return sorted(drinks, key=lambda d: (d.suiker, d.kcal, d.naam.casefold(), d.id))


def _q(value: float, places: int) -> float:
    quantum = Decimal("1").scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def drink_json(drink: Drink, rang: int) -> dict:
    factor = GLASS_ML / 100
    glas_suiker = _q(drink.suiker * factor, 2)
    return {
        "id": drink.id,
        "naam": drink.naam,
        "suiker": drink.suiker,
        "kcal": drink.kcal,
        "notitie": drink.notitie,
        "toegevoegd": drink.toegevoegd,
        "rang": rang,
        "band": band(drink.suiker),
        "glasMl": GLASS_ML,
        "glasSuiker": glas_suiker,
        "glasKcal": _q(drink.kcal * factor, 1),
        "klontjes": _q(glas_suiker / SUGAR_CUBE_G, 1),
    }


def _new_id(taken: set[str]) -> str:
    from uuid import uuid4

    while True:
        candidate = uuid4().hex[:8]
        if candidate not in taken:
            return candidate


def _parse_number(value, label: str) -> float:
    if isinstance(value, bool) or value is None:
        raise DrinkError(f"{label} moet een getal zijn, bijvoorbeeld 3,8.")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise DrinkError(f"{label} moet een getal zijn, bijvoorbeeld 3,8.")
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(" ", "").replace(",", ".")
        if text == "":
            raise DrinkError("leeg")
        try:
            return float(Decimal(text))
        except Exception as exc:
            raise DrinkError(f"{label} moet een getal zijn, bijvoorbeeld 3,8.") from exc
    raise DrinkError(f"{label} moet een getal zijn, bijvoorbeeld 3,8.")


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def parse_payload(data, existing: Drink | None = None) -> Drink:
    if not isinstance(data, dict):
        raise DrinkError("De invoer klopt niet.")
    naam = " ".join(str(data.get("naam", "")).split())
    if not naam:
        raise DrinkError("Vul een naam in.")
    if len(naam) > 80:
        raise DrinkError("De naam is te lang.")
    if "suiker" not in data or _blank(data.get("suiker")):
        raise DrinkError("Vul de suiker per 100 ml in. Die staat op het etiket.")
    try:
        suiker = _parse_number(data.get("suiker"), "Suiker")
    except DrinkError as exc:
        if str(exc) == "leeg":
            raise DrinkError("Vul de suiker per 100 ml in. Die staat op het etiket.") from exc
        raise
    if suiker < 0:
        raise DrinkError("Suiker kan niet onder nul.")
    if suiker > 100:
        raise DrinkError("Meer dan 100 g suiker per 100 ml klopt meestal niet. Controleer de komma.")
    suiker = _q(suiker, 2)

    kcal_raw = data.get("kcal", None)
    if _blank(kcal_raw):
        kcal = _q(suiker * 4, 1)
    else:
        try:
            kcal = _parse_number(kcal_raw, "Calorieën")
        except DrinkError as exc:
            if str(exc) == "leeg":
                kcal = _q(suiker * 4, 1)
            else:
                raise DrinkError("Calorieën moeten een getal zijn.") from exc
        if kcal < 0:
            raise DrinkError("Calorieën kunnen niet onder nul.")
        if kcal > 900:
            raise DrinkError("Dat zijn wel heel veel calorieën per 100 ml. Controleer de komma.")
        kcal = _q(kcal, 1)

    notitie = " ".join(str(data.get("notitie", "")).split())
    if len(notitie) > 200:
        raise DrinkError("De notitie is te lang.")

    if existing is None:
        taken = set()
        drink_id = _new_id(taken)
        toegevoegd = date.today().isoformat()
    else:
        drink_id = existing.id
        toegevoegd = existing.toegevoegd
    return Drink(drink_id, naam, suiker, kcal, notitie, toegevoegd)


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_date_text(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _cell_number(value):
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.startswith("="):
        return None
    return _parse_number(value, "Suiker")


def _header_key(value) -> str | None:
    if not isinstance(value, str):
        return None
    return HEADER_MAP.get(" ".join(value.strip().lower().split()))


def _set_text(cell, value: str) -> None:
    cell.value = value
    # Een naam als "=1+1" moet tekst blijven, geen Excel-formule.
    if isinstance(value, str) and value[:1] in "=-+@":
        cell.data_type = "s"


def _rang_formula(row: int) -> str:
    return (
        f'=IF(A{row}="","",'
        f'COUNTIFS($B$2:$B$500,"<"&B{row})+'
        f'COUNTIFS($B$2:$B$500,B{row},$C$2:$C$500,"<"&C{row})+1)'
    )


def _write(path: Path, drinks: list[Drink]) -> None:
    drinks = ranked(drinks)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.calculation = CalcProperties(calcMode="auto", fullCalcOnLoad=True)
    wb.properties.title = "Drankjes die je lekker vindt"
    wb.properties.creator = "Drankjeslijst"

    ws = wb.active
    ws.title = "Drankjes"
    headers = [
        "Naam",
        "Suiker (g/100 ml)",
        "Calorieën (kcal/100 ml)",
        "Notitie",
        "Toegevoegd",
        "Rang",
        "Id",
    ]
    header_fill = PatternFill("solid", fgColor="1E6A45")
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=12)
    thin = Border(
        left=Side(style="thin", color="E4D9C8"),
        right=Side(style="thin", color="E4D9C8"),
        top=Side(style="thin", color="E4D9C8"),
        bottom=Side(style="thin", color="E4D9C8"),
    )
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(1, col, header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin
    ws.row_dimensions[1].height = 28
    ws.auto_filter.ref = "A1:F500"
    ws.freeze_panes = "A2"
    ws.conditional_formatting.add(
        "B2:B500",
        ColorScaleRule(
            start_type="min",
            start_color="1E6A45",
            mid_type="percentile",
            mid_value=50,
            mid_color="E6C36A",
            end_type="max",
            end_color="9D3A32",
        ),
    )
    sugar_rule = DataValidation(
        type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True
    )
    sugar_rule.error = "Suiker kan niet onder nul."
    sugar_rule.errorTitle = "Suiker"
    sugar_rule.add("B2:B500")
    kcal_rule = DataValidation(
        type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True
    )
    kcal_rule.error = "Calorieën kunnen niet onder nul."
    kcal_rule.errorTitle = "Calorieën"
    kcal_rule.add("C2:C500")
    ws.add_data_validation(sugar_rule)
    ws.add_data_validation(kcal_rule)

    body_font = Font(name="Calibri", size=11, color="221E1A")
    for offset, drink in enumerate(drinks):
        row = offset + 2
        values = {
            1: drink.naam,
            4: drink.notitie,
            7: drink.id,
        }
        for col, text in values.items():
            cell = ws.cell(row, col)
            _set_text(cell, text)
            cell.font = body_font
            cell.border = thin
            cell.alignment = Alignment(
                vertical="center", wrap_text=col == 4, horizontal="left"
            )
        sugar = ws.cell(row, 2, drink.suiker)
        sugar.number_format = "0.00"
        sugar.font = body_font
        sugar.border = thin
        sugar.alignment = Alignment(horizontal="center", vertical="center")
        kcal = ws.cell(row, 3, drink.kcal)
        kcal.number_format = "0.0"
        kcal.font = body_font
        kcal.border = thin
        kcal.alignment = Alignment(horizontal="center", vertical="center")
        added = ws.cell(row, 5, date.fromisoformat(drink.toegevoegd) if _iso_date(drink.toegevoegd) else drink.toegevoegd)
        if _iso_date(drink.toegevoegd):
            added.number_format = "YYYY-MM-DD"
        else:
            _set_text(added, drink.toegevoegd)
        added.font = body_font
        added.border = thin
        added.alignment = Alignment(horizontal="center", vertical="center")
        rank = ws.cell(row, 6, _rang_formula(row))
        rank.font = Font(name="Calibri", size=11, bold=True, color="1E6A45")
        rank.border = thin
        rank.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row].height = 22

    widths = {"A": 46, "B": 22, "C": 26, "D": 52, "E": 16, "F": 12, "G": 14}
    for column, width in widths.items():
        ws.column_dimensions[column].width = width
    ws.column_dimensions["G"].hidden = True

    if drinks:
        chart = BarChart()
        chart.type = "bar"
        chart.title = "Suiker per 100 ml"
        chart.y_axis.title = None
        chart.x_axis.title = None
        data = Reference(ws, min_col=2, min_row=1, max_row=1 + len(drinks))
        cats = Reference(ws, min_col=1, min_row=2, max_row=1 + len(drinks))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.shape = 4
        chart.legend = None
        chart.y_axis.scaling.min = 0
        chart.width = 18
        chart.height = 8
        ws.add_chart(chart, "I2")

    info = wb.create_sheet("Uitleg")
    info.sheet_properties.tabColor = "1E6A45"
    lines = [
        (1, "Drankjes die je lekker vindt", True),
        (3, "Deze spreadsheet is de bron van de website. Beide laten dezelfde lijst zien.", False),
        (4, "Start de site vanuit deze map met: python3 server.py", False),
        (5, "Open daarna http://127.0.0.1:8765", False),
        (7, "Sortering", True),
        (8, "Minste suiker per 100 ml staat bovenaan. Bij gelijke suiker telt het minste aantal calorieën, daarna de naam.", False),
        (9, "Tot 5 g per 100 ml heet lichter, tot 8 g gemiddeld, daarboven zwaar.", False),
        (11, "Zelf een rij toevoegen", True),
        (12, "Vul op het blad Drankjes een naam en de suiker per 100 ml in. Calorieën mag leeg blijven: de site rekent dan 4 kcal per gram suiker. Sla het bestand op en ververs de site.", False),
        (13, "De kolom Rang is een formule. De kolom Id vult de site zelf in; die mag leeg blijven.", False),
        (15, "Een gedownloade kopie loopt niet vanzelf mee. Bewerk dit bestand, of voeg drankjes toe via de site.", False),
    ]
    for row, text, title in lines:
        cell = info.cell(row, 1, text)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.font = Font(
            name="Calibri",
            size=16 if title else 12,
            bold=title,
            color="221E1A",
        )
        info.row_dimensions[row].height = 24 if title else 36
    info.column_dimensions["A"].width = 120

    tmp = path.with_suffix(".xlsx.tmp")
    wb.save(tmp)
    tmp.replace(path)


def _iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _ensure(path: Path) -> None:
    if not path.exists():
        _write(path, seed_drinks())


def _read(path: Path) -> Loaded:
    try:
        wb = load_workbook(path, data_only=False)
    except (BadZipFile, InvalidFileException, OSError) as exc:
        raise StoreError(
            "De spreadsheet is niet leesbaar. Controleer of drankjes.xlsx geen beschadigd bestand is."
        ) from exc
    if "Drankjes" not in wb.sheetnames:
        raise StoreError("De spreadsheet mist het blad Drankjes.")
    ws = wb["Drankjes"]
    columns: dict[int, str] = {}
    for col in range(1, ws.max_column + 1):
        key = _header_key(ws.cell(1, col).value)
        if key:
            columns[col] = key
    fields = set(columns.values())
    if "naam" not in fields or "suiker" not in fields:
        raise StoreError("De spreadsheet mist de kolommen Naam en Suiker (g/100 ml).")

    drinks: list[Drink] = []
    warnings: list[str] = []
    dirty = False
    seen: set[str] = set()
    for row in range(2, ws.max_row + 1):
        raw = {key: ws.cell(row, col).value for col, key in columns.items()}
        if all(_blank(value) or key == "rang" for key, value in raw.items()):
            continue
        naam = " ".join(_as_text(raw.get("naam")).split())
        if not naam:
            warnings.append(f"Rij {row} heeft geen naam en telt niet mee.")
            continue
        try:
            suiker = _cell_number(raw.get("suiker"))
        except DrinkError:
            warnings.append(f"Rij {row} ({naam}) heeft geen bruikbare suiker en telt niet mee.")
            continue
        if suiker is None:
            warnings.append(
                f"Rij {row} ({naam}) heeft wel een naam, maar geen suiker. Die rij telt niet mee tot je de suiker invult."
            )
            continue
        if suiker < 0 or suiker > 100:
            warnings.append(f"Rij {row} ({naam}) heeft een suikerwaarde buiten 0 tot 100 en telt niet mee.")
            continue
        suiker = _q(suiker, 2)
        kcal_value = raw.get("kcal")
        if _blank(kcal_value):
            kcal = _q(suiker * 4, 1)
            dirty = True
        else:
            try:
                kcal = _cell_number(kcal_value)
            except DrinkError:
                warnings.append(f"Rij {row} ({naam}) heeft calorieën die geen getal zijn en telt niet mee.")
                continue
            if kcal is None or kcal < 0 or kcal > 900:
                warnings.append(f"Rij {row} ({naam}) heeft calorieën buiten bereik en telt niet mee.")
                continue
            kcal = _q(kcal, 1)
        notitie = " ".join(_as_text(raw.get("notitie")).split())
        if len(notitie) > 200:
            notitie = notitie[:200]
            dirty = True
        if len(naam) > 80:
            naam = naam[:80].rstrip()
            dirty = True
        drink_id = _as_text(raw.get("id"))
        if not drink_id or drink_id.startswith("=") or drink_id in seen:
            drink_id = _new_id(seen)
            dirty = True
        seen.add(drink_id)
        toegevoegd = _as_date_text(raw.get("toegevoegd"))
        if not toegevoegd:
            toegevoegd = date.today().isoformat()
            dirty = True
        drinks.append(
            Drink(drink_id, naam, suiker, kcal, notitie, toegevoegd, source_row=row)
        )
        if len(drinks) > MAX_DRINKS:
            raise StoreError(f"De lijst heeft meer dan {MAX_DRINKS} drankjes.")
    return Loaded(drinks, warnings, dirty)


def _column_map(ws) -> dict[str, int]:
    columns: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        key = _header_key(ws.cell(1, col).value)
        if key:
            columns[key] = col
    return columns


def _ensure_column(ws, columns: dict[str, int], key: str, header: str) -> bool:
    if key in columns:
        return False
    col = ws.max_column + 1
    cell = ws.cell(1, col, header)
    cell.font = Font(name="Calibri", bold=True, color="FFFFFF", size=12)
    cell.fill = PatternFill("solid", fgColor="1E6A45")
    columns[key] = col
    return True


def _fill_gaps(path: Path, drinks: list[Drink]) -> None:
    """Vul alleen lege Id-, calorieën- en datumcellen aan. Andere rijen blijven staan."""
    wb = load_workbook(path)
    ws = wb["Drankjes"]
    columns = _column_map(ws)
    changed = False
    changed = _ensure_column(ws, columns, "id", "Id") or changed
    changed = _ensure_column(ws, columns, "kcal", "Calorieën (kcal/100 ml)") or changed
    changed = _ensure_column(ws, columns, "toegevoegd", "Toegevoegd") or changed
    for drink in drinks:
        if drink.source_row is None:
            continue
        row = drink.source_row
        id_cell = ws.cell(row, columns["id"])
        if _as_text(id_cell.value) != drink.id:
            _set_text(id_cell, drink.id)
            changed = True
        kcal_cell = ws.cell(row, columns["kcal"])
        if _blank(kcal_cell.value):
            kcal_cell.value = drink.kcal
            kcal_cell.number_format = "0.0"
            changed = True
        added_cell = ws.cell(row, columns["toegevoegd"])
        if _blank(added_cell.value):
            if _iso_date(drink.toegevoegd):
                added_cell.value = date.fromisoformat(drink.toegevoegd)
                added_cell.number_format = "YYYY-MM-DD"
            else:
                _set_text(added_cell, drink.toegevoegd)
            changed = True
        name_cell = ws.cell(row, columns["naam"])
        if _as_text(name_cell.value) != drink.naam and len(_as_text(name_cell.value)) > 80:
            _set_text(name_cell, drink.naam)
            changed = True
        if "notitie" in columns:
            note_cell = ws.cell(row, columns["notitie"])
            if len(_as_text(note_cell.value)) > 200:
                _set_text(note_cell, drink.notitie)
                changed = True
    if not changed:
        return
    tmp = path.with_suffix(".xlsx.tmp")
    wb.save(tmp)
    tmp.replace(path)


def _snapshot_unlocked(path: Path) -> dict:
    _ensure(path)
    loaded = _read(path)
    if loaded.dirty:
        _fill_gaps(path, loaded.drinks)
        loaded = _read(path)
    ordered = ranked(loaded.drinks)
    return {
        "spreadsheet": str(path.resolve()),
        "gewijzigd": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "warnings": loaded.warnings,
        "drinks": [drink_json(drink, index) for index, drink in enumerate(ordered, start=1)],
    }


def snapshot(path: Path | None = None) -> dict:
    with LOCK:
        return _snapshot_unlocked(path or DATA_PATH)


def add_drink(data, path: Path | None = None) -> dict:
    path = path or DATA_PATH
    with LOCK:
        _ensure(path)
        loaded = _read(path)
        if len(loaded.drinks) >= MAX_DRINKS:
            raise DrinkError(f"De lijst is vol ({MAX_DRINKS} drankjes).")
        drink = parse_payload(data)
        taken = {item.id for item in loaded.drinks}
        if drink.id in taken:
            drink.id = _new_id(taken)
        _write(path, loaded.drinks + [drink])
        payload = _snapshot_unlocked(path)
        payload["savedId"] = drink.id
        return payload


def update_drink(drink_id: str, data, path: Path | None = None) -> dict:
    path = path or DATA_PATH
    with LOCK:
        _ensure(path)
        loaded = _read(path)
        current = next((item for item in loaded.drinks if item.id == drink_id), None)
        if current is None:
            raise DrinkError("Dit drankje staat niet meer op de lijst. Ververs de pagina.")
        updated = parse_payload(data, existing=current)
        drinks = [updated if item.id == drink_id else item for item in loaded.drinks]
        _write(path, drinks)
        payload = _snapshot_unlocked(path)
        payload["savedId"] = drink_id
        return payload


def delete_drink(drink_id: str, path: Path | None = None) -> dict:
    path = path or DATA_PATH
    with LOCK:
        _ensure(path)
        loaded = _read(path)
        if not any(item.id == drink_id for item in loaded.drinks):
            raise DrinkError("Dit drankje staat niet meer op de lijst. Ververs de pagina.")
        _write(path, [item for item in loaded.drinks if item.id != drink_id])
        return _snapshot_unlocked(path)


def spreadsheet_bytes(path: Path | None = None) -> bytes:
    path = path or DATA_PATH
    with LOCK:
        _ensure(path)
        loaded = _read(path)
        if loaded.dirty:
            _write(path, loaded.drinks)
        return path.read_bytes()


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


def _static_file(url_path: str) -> Path | None:
    if url_path == "/":
        url_path = "/index.html"
    rel = unquote(url_path).lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    root = STATIC_DIR.resolve()
    candidate = (root / rel).resolve()
    if candidate.is_file() and (candidate == root or root in candidate.parents):
        return candidate
    return None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/drinks":
            self._safe(lambda: snapshot())
            return
        if path == "/api/spreadsheet":
            try:
                body = spreadsheet_bytes()
            except DrinkError as exc:
                self._json(400, {"error": str(exc)})
                return
            except (StoreError, OSError) as exc:
                message = str(exc) if isinstance(exc, StoreError) else (
                    "De spreadsheet kon niet worden gelezen. Sluit het bestand als het in Excel openstaat, en probeer opnieuw."
                )
                self._json(500, {"error": message})
                return
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header("Content-Disposition", 'attachment; filename="drankjes.xlsx"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        static = _static_file(path)
        if static is None:
            self._json(404, {"error": "Niet gevonden."})
            return
        body = static.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(static.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/drinks":
            self._json(404, {"error": "Niet gevonden."})
            return
        self._safe(lambda: add_drink(self._body()))

    def do_PUT(self):
        drink_id = self._drink_id()
        if drink_id is None:
            self._json(404, {"error": "Niet gevonden."})
            return
        self._safe(lambda: update_drink(drink_id, self._body()))

    def do_DELETE(self):
        drink_id = self._drink_id()
        if drink_id is None:
            self._json(404, {"error": "Niet gevonden."})
            return
        self._safe(lambda: delete_drink(drink_id))

    def _drink_id(self) -> str | None:
        path = urlparse(self.path).path
        prefix = "/api/drinks/"
        if not path.startswith(prefix):
            return None
        drink_id = unquote(path[len(prefix):]).strip("/")
        if not drink_id or "/" in drink_id:
            return None
        return drink_id

    def _body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 100_000:
            raise DrinkError("De invoer is te groot.")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise DrinkError("De invoer klopt niet.") from exc

    def _safe(self, action):
        try:
            self._json(200, action())
        except DrinkError as exc:
            status = 404 if "niet meer op de lijst" in str(exc) else 400
            self._json(status, {"error": str(exc)})
        except StoreError as exc:
            self._json(500, {"error": str(exc)})
        except PermissionError:
            self._json(
                500,
                {"error": "De spreadsheet is geopend in een ander programma. Sla die op, sluit hem, en probeer opnieuw."},
            )
        except OSError:
            self._json(
                500,
                {"error": "De spreadsheet kon niet worden opgeslagen. Sluit het bestand als het in Excel openstaat, en probeer opnieuw."},
            )

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[drankjes] {self.address_string()} {fmt % args}")


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    with LOCK:
        _ensure(DATA_PATH)
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    shown = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    print(f"Drankjeslijst: http://{shown}:{port}")
    print(f"Spreadsheet:   {DATA_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGestopt.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
