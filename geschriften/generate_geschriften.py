#!/usr/bin/env python3
"""Maak handgeschreven voorbeeldteksten als SVG (vector) en PNG.

Teksten staan in geschriften/teksten/*.txt — pas die aan en run dit script
opnieuw. Elke letter krijgt een eigen pad, dus twee keer dezelfde e is
nooit identiek.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import xml.sax.saxutils as xml
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cairosvg
import numpy as np
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(ROOT, "fonts")
TEXT_DIR = os.path.join(ROOT, "teksten")
SVG_DIR = os.path.join(ROOT, "svg")
PNG_DIR = os.path.join(ROOT, "png")
STYLE_PATH = os.path.join(ROOT, "stijlen.json")

PAGE_W = 1240
PAGE_H = 1754
PNG_SCALE = 2
NUM_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


@dataclass
class Hand:
    id: str
    titel: str
    hand: str
    tekstbestand: str
    font: str
    grootte: float
    inkt: Tuple[int, int, int]
    papier: Tuple[int, int, int]
    slordig: float
    helling: float
    regelafstand: float
    tracking: float
    marge_links: float
    marge_boven: float
    marge_rechts: float
    pen: str
    lijntjes: bool
    rode_marge: bool
    zaad: int
    gewicht: Optional[int] = None


@dataclass
class GlyphCache:
    font: TTFont
    cmap: dict
    glyph_set: object
    units_per_em: int
    paths: Dict[str, str] = field(default_factory=dict)
    advances: Dict[str, float] = field(default_factory=dict)


def load_styles() -> List[Hand]:
    with open(STYLE_PATH, encoding="utf-8") as handle:
        raw = json.load(handle)
    hands = []
    for item in raw:
        ink = tuple(item["inkt"])
        paper = tuple(item["papier"])
        hands.append(
            Hand(
                id=item["id"],
                titel=item["titel"],
                hand=item["hand"],
                tekstbestand=item["tekstbestand"],
                font=item["font"],
                grootte=float(item["grootte"]),
                inkt=(int(ink[0]), int(ink[1]), int(ink[2])),
                papier=(int(paper[0]), int(paper[1]), int(paper[2])),
                slordig=float(item["slordig"]),
                helling=float(item["helling"]),
                regelafstand=float(item["regelafstand"]),
                tracking=float(item["tracking"]),
                marge_links=float(item["marge_links"]),
                marge_boven=float(item["marge_boven"]),
                marge_rechts=float(item["marge_rechts"]),
                pen=item.get("pen", "balpen"),
                lijntjes=bool(item.get("lijntjes", False)),
                rode_marge=bool(item.get("rode_marge", False)),
                zaad=int(item.get("zaad", 1)),
                gewicht=item.get("gewicht"),
            )
        )
    return hands


def load_text(hand: Hand) -> str:
    path = os.path.join(TEXT_DIR, hand.tekstbestand)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Tekstbestand ontbreekt: {path}")
    with open(path, encoding="utf-8") as handle:
        return handle.read().replace("\r\n", "\n").replace("\t", "    ")


def load_font(hand: Hand) -> GlyphCache:
    path = os.path.join(FONT_DIR, hand.font)
    font = TTFont(path)
    if "fvar" in font:
        font = instantiateVariableFont(font, {"wght": hand.gewicht or 400})
    return GlyphCache(
        font=font,
        cmap=font.getBestCmap() or {},
        glyph_set=font.getGlyphSet(),
        units_per_em=font["head"].unitsPerEm,
    )


def glyph_advance(cache: GlyphCache, ch: str) -> float:
    if ch in cache.advances:
        return cache.advances[ch]
    name = cache.cmap.get(ord(ch))
    if name is None:
        cache.advances[ch] = 0.48
        return 0.48
    cache.advances[ch] = float(cache.glyph_set[name].width) / cache.units_per_em
    return cache.advances[ch]


def glyph_path(cache: GlyphCache, ch: str) -> Optional[str]:
    if ch in cache.paths:
        return cache.paths[ch] or None
    name = cache.cmap.get(ord(ch))
    if name is None:
        cache.paths[ch] = ""
        return None
    pen = SVGPathPen(cache.glyph_set)
    transform = (1 / cache.units_per_em, 0, 0, -1 / cache.units_per_em, 0, 0)
    cache.glyph_set[name].draw(TransformPen(pen, transform))
    d = pen.getCommands()
    cache.paths[ch] = d
    return d or None


def perturb_path(d: str, rng: random.Random, amount: float) -> str:
    def repl(match: re.Match) -> str:
        value = float(match.group(0))
        if abs(value) < 1e-9:
            return match.group(0)
        return f"{value + rng.uniform(-amount, amount):.4f}"

    return NUM_RE.sub(repl, d)


def warp_path(d: str, squash_x: float, squash_y: float) -> str:
    parts = []
    pos = 0
    index = 0
    for match in NUM_RE.finditer(d):
        parts.append(d[pos : match.start()])
        value = float(match.group(0))
        value *= squash_x if index % 2 == 0 else squash_y
        parts.append(f"{value:.4f}")
        index += 1
        pos = match.end()
    parts.append(d[pos:])
    return "".join(parts)


def fallback_char(ch: str) -> str:
    table = str.maketrans(
        {
            "ë": "e",
            "ï": "i",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ü": "u",
            "ö": "o",
            "ä": "a",
            "ó": "o",
            "á": "a",
            "í": "i",
            "ú": "u",
            "–": "-",
            "—": "-",
            "’": "'",
            "‘": "'",
            "“": '"',
            "”": '"',
        }
    )
    return ch.translate(table)


def rgb(color: Tuple[int, int, int], fade: float = 0.0, rng: Optional[random.Random] = None) -> str:
    r, g, b = color
    if rng is not None:
        r = int(max(0, min(255, r + rng.randint(-10, 10))))
        g = int(max(0, min(255, g + rng.randint(-10, 10))))
        b = int(max(0, min(255, b + rng.randint(-10, 10))))
    r = int(r + (220 - r) * fade)
    g = int(g + (220 - g) * fade)
    b = int(b + (220 - b) * fade)
    return f"rgb({r},{g},{b})"


def measure(text: str, cache: GlyphCache, em: float, tracking: float) -> float:
    width = 0.0
    for ch in text:
        glyph = ch if ch in cache.cmap else fallback_char(ch)
        if glyph == " ":
            width += 0.34 * em
        else:
            width += max(0.18, glyph_advance(cache, glyph)) * em * tracking
    return width


def wrap_line(line: str, cache: GlyphCache, em: float, tracking: float, max_width: float) -> List[str]:
    indent = len(line) - len(line.lstrip(" "))
    prefix = line[:indent]
    body = line[indent:]
    if not body:
        return [line]
    if measure(line, cache, em, tracking) <= max_width:
        return [line]
    words = body.split(" ")
    lines: List[str] = []
    current: List[str] = []
    for word in words:
        trial = prefix + (" ".join(current + [word]) if current else word)
        if current and measure(trial, cache, em, tracking) > max_width:
            lines.append(prefix + " ".join(current))
            current = [word]
            prefix = " " * indent
        else:
            current.append(word)
    if current:
        lines.append(prefix + " ".join(current))
    return lines or [line]


def paper_background(hand: Hand) -> str:
    r, g, b = hand.papier
    parts = [f'<rect width="100%" height="100%" fill="rgb({r},{g},{b})"/>']
    if hand.lijntjes:
        y = hand.marge_boven
        lines = []
        while y < PAGE_H - 40:
            lines.append(
                f'<line x1="0" y1="{y:.1f}" x2="{PAGE_W}" y2="{y:.1f}" '
                f'stroke="#8eafd0" stroke-width="1.15" opacity="0.55"/>'
            )
            y += hand.regelafstand
        parts.append('<g id="schriftlijnen">' + "".join(lines) + "</g>")
    if hand.rode_marge:
        x = hand.marge_links - 28
        parts.append(
            f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{PAGE_H}" '
            f'stroke="#d27a7a" stroke-width="1.6" opacity="0.55"/>'
        )
    parts.append('<rect width="100%" height="100%" fill="url(#age)"/>')
    return "\n  ".join(parts)


def svg_defs(hand: Hand) -> str:
    r, g, b = hand.papier
    return f"""
  <defs>
    <radialGradient id="age" cx="48%" cy="38%" r="78%">
      <stop offset="0%" stop-color="rgb({min(255, r + 6)},{min(255, g + 4)},{b})" stop-opacity="0"/>
      <stop offset="100%" stop-color="rgb({max(0, r - 24)},{max(0, g - 28)},{max(0, b - 34)})" stop-opacity="0.22"/>
    </radialGradient>
  </defs>
"""


def pen_params(hand: Hand) -> Tuple[float, float, float]:
    """stroke width (em), smear, pressure variation."""
    if hand.pen == "vulpen":
        return 0.018, 0.7, 0.08
    if hand.pen == "potlood":
        return 0.012, 0.15, 0.05
    if hand.pen == "stift":
        return 0.04, 0.45, 0.04
    return 0.01, 0.28, 0.045


def write_line(
    line: str,
    x0: float,
    y: float,
    hand: Hand,
    cache: GlyphCache,
    rng: random.Random,
    line_i: int,
) -> Tuple[str, int]:
    em = hand.grootte
    sl = hand.slordig
    stroke_w, smear, pressure = pen_params(hand)
    word_slant = hand.helling + rng.uniform(-2.2, 2.2) * sl
    parts: List[str] = []
    x = x0
    drawn = 0
    max_x = PAGE_W - hand.marge_rechts

    # Slow drift of the baseline along the line (tired hand).
    phase = line_i * 0.37 + hand.zaad * 0.01

    for col, raw in enumerate(line):
        ch = raw if raw in cache.cmap else fallback_char(raw)
        if ch == " ":
            x += 0.34 * em + rng.uniform(-0.12, 0.22) * em * sl
            continue

        d = glyph_path(cache, ch)
        if not d:
            x += 0.4 * em
            continue

        wave = math.sin(x / 70.0 + phase) * (1.6 + 7.5 * sl)
        wave += math.sin(x / 180.0 + phase * 1.7) * (0.8 + 3.0 * sl)
        jx = rng.uniform(-1.1, 1.1) * (0.4 + sl)
        jy = rng.uniform(-1.3, 1.3) * (0.5 + sl) + wave
        rot = word_slant + rng.uniform(-3.8, 3.8) * sl
        # i-dots and t-bars wander a bit extra.
        if ch.lower() in "ijt":
            rot += rng.uniform(-1.4, 1.4) * sl
            jy += rng.uniform(-0.8, 0.9) * sl

        squash_x = 1.0 + rng.uniform(-0.05, 0.06) * (0.4 + sl)
        squash_y = 1.0 + rng.uniform(-pressure, pressure)
        amount = 0.0035 + sl * 0.011
        unique = warp_path(perturb_path(d, rng, amount), squash_x, squash_y)

        tired = min(0.28, (y / PAGE_H) * 0.18 * sl)
        opacity = 0.78 + rng.uniform(-0.12, 0.18) * (0.5 + sl) - tired
        if hand.pen == "potlood":
            opacity *= 0.72
        opacity = max(0.38, min(0.96, opacity))
        fill = rgb(hand.inkt, fade=tired + rng.uniform(0, 0.08 * sl), rng=rng)

        transform = (
            f"translate({x + jx:.2f} {y + jy:.2f}) "
            f"rotate({rot:.3f}) scale({em:.3f})"
        )
        path = xml.escape(unique, {"\"": "&quot;"})
        stroke = (
            f' stroke="{fill}" stroke-width="{stroke_w:.4f}" '
            f'stroke-linejoin="round" stroke-linecap="round"'
        )
        body = (
            f'<g transform="{transform}">'
            f'<path d="{path}" fill="{fill}" fill-opacity="{opacity:.3f}"{stroke}/>'
        )
        if smear > 0.35 and rng.random() < 0.45 * smear:
            ghost = perturb_path(unique, rng, amount * 0.5)
            dx = rng.uniform(0.004, 0.018) * smear
            dy = rng.uniform(-0.01, 0.012) * smear
            body += (
                f'<path d="{xml.escape(ghost, {"\"": "&quot;"})}" fill="{fill}" '
                f'fill-opacity="{opacity * 0.22:.3f}" '
                f'transform="translate({dx:.3f} {dy:.3f})"/>'
            )
        body += "</g>"
        parts.append(body)
        drawn += 1

        step = max(0.16, glyph_advance(cache, ch)) * em * hand.tracking
        step += rng.uniform(-0.06, 0.08) * em * sl
        x += step
        if x > max_x + 40:
            break

    return "".join(parts), drawn


def type_document(text: str, hand: Hand, cache: GlyphCache) -> str:
    rng = random.Random(hand.zaad)
    em = hand.grootte
    max_width = PAGE_W - hand.marge_links - hand.marge_rechts
    y = hand.marge_boven
    blocks: List[str] = []
    line_i = 0
    page_rot = rng.uniform(-0.45, 0.45) + hand.helling * 0.02

    for raw_line in text.split("\n"):
        if raw_line.strip() == "":
            y += hand.regelafstand * (0.45 + rng.uniform(-0.05, 0.08))
            continue
        visual_lines = wrap_line(raw_line, cache, em, hand.tracking, max_width)
        for visual in visual_lines:
            if y > PAGE_H - 70:
                break
            indent = len(visual) - len(visual.lstrip(" "))
            x0 = hand.marge_links + indent * (0.28 * em) + line_i * (0.12 * hand.slordig)
            x0 += rng.uniform(-1.8, 2.4) * hand.slordig
            svg, _ = write_line(visual.lstrip(" "), x0, y, hand, cache, rng, line_i)
            blocks.append(svg)
            y += hand.regelafstand + rng.uniform(-1.2, 1.8) * hand.slordig
            line_i += 1
        if y > PAGE_H - 70:
            break

    inner = "\n".join(blocks)
    return (
        f'<g transform="rotate({page_rot:.3f} {PAGE_W/2:.0f} {PAGE_H/2:.0f})">\n'
        f"{inner}\n"
        f"</g>"
    )


def write_svg(path: str, hand: Hand, body: str) -> None:
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}" height="{PAGE_H}" viewBox="0 0 {PAGE_W} {PAGE_H}">
{svg_defs(hand)}
  {paper_background(hand)}
  {body}
</svg>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(svg)


def paper_grain_png(img: Image.Image, hand: Hand) -> Image.Image:
    rng = np.random.default_rng(hand.zaad)
    w, h = img.size
    base = np.array(img).astype(np.float32)
    grain = rng.normal(0, 1.5, (h, w, 1)).astype(np.float32)
    fibre = rng.normal(0, 1.0, (h, max(1, w // 18), 1)).astype(np.float32)
    fibre = np.repeat(fibre, 18, axis=1)
    if fibre.shape[1] < w:
        fibre = np.concatenate(
            [fibre, np.repeat(fibre[:, -1:, :], w - fibre.shape[1], axis=1)], axis=1
        )
    fibre = fibre[:, :w]
    speck = (rng.random((h, w)) < 0.0012).astype(np.float32) * rng.uniform(-9, 7, (h, w))
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.sqrt(((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2)
    vig = np.clip((dist - 0.38) * 32, 0, 18)
    aged = np.zeros_like(base)
    aged[..., 0] -= vig * 0.85
    aged[..., 1] -= vig * 1.05
    aged[..., 2] -= vig * 1.3
    out = np.clip(base + grain + fibre * 2.1 + speck[..., None] + aged, 0, 255).astype(np.uint8)
    result = Image.fromarray(out, mode="RGB")
    if hand.pen == "potlood":
        result = result.filter(ImageFilter.SMOOTH)
    return result


def render_png(svg_path: str, png_path: str, hand: Hand) -> None:
    cairosvg.svg2png(
        url=svg_path,
        write_to=png_path,
        output_width=PAGE_W * PNG_SCALE,
        output_height=PAGE_H * PNG_SCALE,
    )
    img = Image.open(png_path).convert("RGB")
    img = paper_grain_png(img, hand)
    img.save(png_path, "PNG", dpi=(300, 300), optimize=True, compress_level=9)


def write_readme(rows: List[Tuple[str, str, str, str, str]]) -> None:
    lines = [
        "# Tien handschriften",
        "",
        "Voorbeeldteksten die eruitzien als écht handschrift: elke letter is een",
        "eigen vectorpad (andere helling, druk, inkt en omtrek).",
        "",
        "## Tekst aanpassen",
        "",
        "1. Open een bestand in `teksten/` (gewoon een `.txt`).",
        "2. Zet er je eigen tekst in. Lange regels worden automatisch omgebroken.",
        "3. Genereer opnieuw:",
        "",
        "```bash",
        "python3 geschriften/generate_geschriften.py",
        "```",
        "",
        "Alleen één blad:",
        "",
        "```bash",
        "python3 geschriften/generate_geschriften.py 01-anna-brief",
        "```",
        "",
        "Handschrift zelf (font, inktkleur, slordigheid, vulpen/balpen/potlood,",
        "gelinieerd papier) pas je aan in `stijlen.json`.",
        "",
        "| # | Geschrift | Hand | SVG | PNG | tekst |",
        "|---|-----------|------|-----|-----|-------|",
    ]
    for i, (slug, title, hand, svg_name, png_name) in enumerate(rows, 1):
        lines.append(
            f"| {i} | {title} | {hand} | [svg/{svg_name}](svg/{svg_name}) | "
            f"[png/{png_name}](png/{png_name}) | [teksten/{slug}.txt](teksten/{slug}.txt) |"
        )
    lines.append("")
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def select_hands(hands: List[Hand], ids: List[str]) -> List[Hand]:
    if not ids:
        return hands
    chosen = []
    for needle in ids:
        matches = [h for h in hands if h.id == needle or h.id.startswith(needle)]
        if not matches:
            known = ", ".join(h.id for h in hands)
            raise SystemExit(f"Onbekend id '{needle}'. Kies uit: {known}")
        for hand in matches:
            if hand not in chosen:
                chosen.append(hand)
    return chosen


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Maak handgeschreven SVG- en PNG-bladen van de teksten in teksten/."
    )
    parser.add_argument(
        "ids",
        nargs="*",
        help="id of begin van de id, bijvoorbeeld 01 of 01-anna-brief. Leeg = alle tien.",
    )
    parser.add_argument("--lijst", action="store_true", help="Toon de tien id's en stop.")
    args = parser.parse_args(argv)

    hands = load_styles()
    if args.lijst:
        for hand in hands:
            print(f"{hand.id:24}  {hand.titel}  ({hand.hand})")
        return

    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(PNG_DIR, exist_ok=True)
    chosen = select_hands(hands, args.ids)

    for hand in chosen:
        print(f"Schrijven: {hand.id}  ({hand.hand})")
        cache = load_font(hand)
        body = type_document(load_text(hand), hand, cache)
        svg_path = os.path.join(SVG_DIR, f"{hand.id}.svg")
        png_path = os.path.join(PNG_DIR, f"{hand.id}.png")
        write_svg(svg_path, hand, body)
        render_png(svg_path, png_path, hand)

    rows = []
    for hand in load_styles():
        rows.append(
            (
                hand.id,
                hand.titel,
                hand.hand,
                f"{hand.id}.svg",
                f"{hand.id}.png",
            )
        )
    write_readme(rows)
    print("Klaar. Teksten staan in geschriften/teksten/")


if __name__ == "__main__":
    main()
