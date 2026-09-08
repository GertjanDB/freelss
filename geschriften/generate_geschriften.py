#!/usr/bin/env python3
"""Generate 10 typewriter-style sample writings as SVG (vector) and PNG.

Each occurrence of a letter gets its own outline, ink, rotation and strike
so the page looks typed on a real machine rather than set in a digital font.
"""

from __future__ import annotations

import math
import os
import random
import re
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
SVG_DIR = os.path.join(ROOT, "svg")
PNG_DIR = os.path.join(ROOT, "png")

# A4 at 150 dpi in SVG user units; PNG is rendered 2x (300 dpi).
PAGE_W = 1240
PAGE_H = 1754
PNG_SCALE = 2


@dataclass
class Typewriter:
    """Persistent quirks of one machine / one typist."""

    name: str
    font_file: str
    size: float
    ink: Tuple[int, int, int]
    paper: Tuple[int, int, int]
    jitter: float
    rotation: float
    wear: float
    ribbon_fade: float
    tracking: float
    leading: float
    key_bias: Dict[str, Tuple[float, float]]
    double_strike: float
    skip_strike: float
    line_drift: float
    platen_slant: float
    margin_left: float
    margin_top: float
    margin_right: float
    strike_heavy: float
    ink_smear: float
    baseline_wave: float
    space_jitter: float
    weight: Optional[int] = None
    seed: int = 1


@dataclass
class GlyphCache:
    font: TTFont
    cmap: dict
    glyph_set: object
    units_per_em: int
    paths: Dict[str, str] = field(default_factory=dict)
    advances: Dict[str, float] = field(default_factory=dict)


SAMPLE_TEXTS: List[Tuple[str, str, str]] = [
    (
        "01-anna-brief",
        "Anna Vermeer — brief",
        """Rotterdam, 12 maart 1978

Lieve Karel,

Ik schrijf je vanaf de keukentafel. De radio speelt zacht
en de koffie is al koud. Gisteren ben ik langs de Maas
gelopen tot aan de brug. Het waaide hard, maar de lucht
was helder. Ik dacht aan die middag in Delft, toen we
uren op een bankje zaten en nauwelijks iets zeiden.

Moeder vraagt of je zondag mee-eet. Niets bijzonders,
erwtensoep en brood. Als je niet kunt, stuur dan een
kaartje. Ik kijk elke ochtend of de postbode stopt.

Groet ook je zus van mij. En kom gauw.

Hartelijke groeten,
Anna""",
    ),
    (
        "02-bert-memo",
        "Bert Hendriks — kantoornotitie",
        """INTERN MEMO
Afdeling Expeditie                 4 juni 1984

Aan: alle ploegleiders
Van: B. Hendriks

Vanaf maandag 11 juni vertrekt de ochtendronde om
zes uur dertig in plaats van zeven uur. De poort
aan de achterzijde blijft tot die tijd gesloten.
Wie later binnenkomt, meldt zich bij de portier.

Controleer de vrachtbrieven VOOR vertrek. Vorige
week ontbraken twee handtekeningen. Dat mag niet
meer voorkomen.

De kantine is tussen twaalf en half een open.
Geen eten in de laadhal.

Hendriks""",
    ),
    (
        "03-clara-dagboek",
        "Clara de Wit — dagboekblad",
        """Zaterdag 19 oktober 1963

Vandaag voor het eerst de nieuwe machine gebruikt.
De e-toets blijft hangen als ik te snel tik. Ik moet
leren trager te zijn.

Op school kreeg ik een acht voor aardrijkskunde.
Juffrouw Kramer zei dat mijn kaart van de rivier
duidelijk was. Daarna fietsen met Els naar het park.
We kochten een zak drop en zaten tot het donker werd.

Papa heeft in de schuur een plank gezaagd. Het ruikt
er naar zaagsel en olie. Ik mag morgen helpen schilderen
als het droog blijft.

Dit blad bewaar ik.""",
    ),
    (
        "04-dirk-verslag",
        "Dirk Bos — werkverslag",
        """WERKVERSLAG WEEK 37
Technische Dienst          Utrecht, 14 september 1991

Maandag: pomp 4 nagezien. Pakking vervangen. Proefdraaien
tot 14.20 uur. Geen lekkage.

Dinsdag: storing aan de band in hal B. Motor te warm.
Koeling schoongemaakt. Band liep vanaf 11.00 weer.

Woensdag: keuring ladders en steigers. Twee ladders
afgekeurd, labels erop. Bestelling geplaatst.

Donderdag: nieuwe filters geplaatst op compressor 2.
Oliepeil in orde.

Vrijdag: rapportage en magazijn. Voorraad bouten M8
is laag. Aanvraag ligt bij inkoop.

D. Bos""",
    ),
    (
        "05-eva-uitnodiging",
        "Eva Manders — uitnodiging",
        """UITNODIGING

Op zaterdag 8 mei 1976
om drie uur in de middag

vieren wij ons zilveren huwelijk
in de tuin achter het huis
Lindelaan 18, Haarlem

Er is koffie, thee en later soep.
Kinderen zijn van harte welkom.

Geen cadeaus, wel een verhaal
of een lied als je wilt.

Gelieve te laten weten of je komt.
Een briefkaart is genoeg.

Eva en Willem Manders""",
    ),
    (
        "06-fien-recept",
        "Fien Kuipers — recept",
        """APPELTAART VAN MOEDER
voor een vorm van 24 centimeter

300 gram bloem
200 gram boter, koud
100 gram suiker
1 ei
snuf zout

Voor de vulling:
6 zure appels
50 gram suiker
kaneel
handvol rozijnen
paneermeel voor de bodem

Boter in de bloem wrijven tot kruimels.
Suiker, zout en ei erbij. Snel tot deeg
werken. Een uur in de kelder leggen.

Appels schillen en in parten. Deeg uitrollen,
vorm bekleden, paneermeel strooien, vulling
erop. Strips over de bovenkant.

Vijftig minuten in de oven, matig warm.
Laat afkoelen voor je snijdt.""",
    ),
    (
        "07-gerrit-bevestiging",
        "Gerrit Smit — bevestiging",
        """G. SMIT  RIJWIELHANDEL
Voorstraat 9, Dordrecht

Dordrecht, 22 november 1982

Geachte heer Visser,

Hierbij bevestig ik de bestelling van
2 november:

  1 herenrijwiel, zwart, maat 61
  1 bagagedrager
  2 spatborden
  1 slot

De fiets staat klaar vanaf vrijdag
26 november. Openingstijden: acht tot
zes, zaterdag tot vier.

Het restant van honderd vijfentwintig
gulden voldoet u bij afhalen.

Hoogachtend,
G. Smit""",
    ),
    (
        "08-hanna-lijst",
        "Hanna Veldman — paklijst",
        """PAKLIJST KAMP  3 t/m 12 juli 1969

KLEDING
  4 shirts
  3 korte broeken
  1 lange broek
  1 trui
  2 paar schoenen
  6 paar sokken
  jas tegen regen
  zwemkleding
  pet

VERDER
  slaapzak
  zaklamp en batterijen
  mes, bord, beker, lepel
  handdoek
  zeep en tandenborstel
  schrijfblok en potlood
  briefkaarten
  zakgeld in een envelop

NIET VERGETEN
  medicijnen van dokter Vos
  adres van tante in Assen""",
    ),
    (
        "09-ivo-instructie",
        "Ivo Bakker — instructie",
        """HANDLEIDING KETELHUIS
alleen voor de nachtdienst

1. Bij binnenkomst druk op de groene knop
   links van de deur. Het lampje moet branden.

2. Controleer de manometer. De wijzer hoort
   tussen 2 en 4 te staan. Staat hij lager,
   dan de toevoer een kwartslag opendraaien.
   Nooit verder dan de rode streep.

3. Elke twee uur de ronde doen:
   - ketel 1 en 2
   - pomp in de kelder
   - achterdeur op slot

4. Storing: eerst de bel bij de portier.
   Daarna het nummer op het bord naast
   de telefoon. Blijf bij de ketel tot
   er iemand is.

5. Einde dienst: rapport in het schrift.
   Datum, tijd, naam, bijzonderheden.

I. Bakker, 1987""",
    ),
    (
        "10-joke-verklaring",
        "Joke Langerak — verklaring",
        """Leiden, 2 februari 1959

Verklaring

Ondergetekende, Johanna Langerak,
wonende Kerkstraat 4 te Leiden,
verklaart het volgende.

Op maandag 26 januari omstreeks
kwart over vier zag ik vanaf het
raam van de voorkamer een grijze
bestelwagen stilstaan voor nummer 7.
Twee mannen tilden een kast naar
binnen. Het duurde ongeveer twintig
minuten. Daarna reden zij weg in
de richting van de gracht.

Ik ken de mannen niet. De auto had
geen duidelijke tekst op de deur.

Aldus naar waarheid opgemaakt.

J. Langerak""",
    ),
]


TYPEWRITERS: List[Typewriter] = [
    Typewriter(
        name="Anna — oude Underwood",
        font_file="SpecialElite-Regular.ttf",
        size=21.5,
        ink=(32, 28, 24),
        paper=(242, 232, 210),
        jitter=1.15,
        rotation=2.1,
        wear=0.42,
        ribbon_fade=0.18,
        tracking=13.4,
        leading=34.0,
        key_bias={"e": (0.45, -0.55), "a": (-0.35, 0.25), "o": (0.2, 0.4), "n": (-0.15, -0.3)},
        double_strike=0.018,
        skip_strike=0.012,
        line_drift=0.22,
        platen_slant=0.35,
        margin_left=108,
        margin_top=130,
        margin_right=100,
        strike_heavy=0.55,
        ink_smear=0.65,
        baseline_wave=1.4,
        space_jitter=0.55,
        seed=1978,
    ),
    Typewriter(
        name="Bert — kantoor Olympia",
        font_file="CourierPrime-Regular.ttf",
        size=18.5,
        ink=(18, 32, 58),
        paper=(236, 236, 230),
        jitter=0.55,
        rotation=0.9,
        wear=0.18,
        ribbon_fade=0.14,
        tracking=11.6,
        leading=30.5,
        key_bias={"t": (0.0, 0.45), "r": (-0.25, 0.15), "i": (0.2, -0.2)},
        double_strike=0.008,
        skip_strike=0.006,
        line_drift=0.08,
        platen_slant=0.12,
        margin_left=120,
        margin_top=118,
        margin_right=110,
        strike_heavy=0.35,
        ink_smear=0.25,
        baseline_wave=0.6,
        space_jitter=0.25,
        seed=1984,
    ),
    Typewriter(
        name="Clara — portable Hermes",
        font_file="CutiveMono-Regular.ttf",
        size=19.0,
        ink=(48, 42, 36),
        paper=(248, 241, 226),
        jitter=1.35,
        rotation=2.4,
        wear=0.5,
        ribbon_fade=0.2,
        tracking=12.2,
        leading=32.0,
        key_bias={"e": (0.6, 0.2), "s": (-0.4, -0.5), "d": (0.3, 0.35), "l": (0.0, -0.45)},
        double_strike=0.028,
        skip_strike=0.02,
        line_drift=0.3,
        platen_slant=-0.45,
        margin_left=96,
        margin_top=140,
        margin_right=90,
        strike_heavy=0.7,
        ink_smear=0.8,
        baseline_wave=1.8,
        space_jitter=0.8,
        seed=1963,
    ),
    Typewriter(
        name="Dirk — IBM Selectric",
        font_file="IBMPlexMono-Regular.ttf",
        size=17.8,
        ink=(22, 22, 22),
        paper=(250, 248, 242),
        jitter=0.28,
        rotation=0.45,
        wear=0.08,
        ribbon_fade=0.08,
        tracking=10.9,
        leading=28.8,
        key_bias={"g": (0.12, 0.1)},
        double_strike=0.003,
        skip_strike=0.002,
        line_drift=0.04,
        platen_slant=0.05,
        margin_left=128,
        margin_top=112,
        margin_right=118,
        strike_heavy=0.22,
        ink_smear=0.12,
        baseline_wave=0.25,
        space_jitter=0.12,
        seed=1991,
    ),
    Typewriter(
        name="Eva — cursieve machine",
        font_file="CourierPrime-Italic.ttf",
        size=19.2,
        ink=(40, 24, 28),
        paper=(244, 236, 220),
        jitter=0.85,
        rotation=1.4,
        wear=0.28,
        ribbon_fade=0.22,
        tracking=12.0,
        leading=33.0,
        key_bias={"a": (-0.2, 0.3), "e": (0.25, -0.2), "n": (0.15, 0.2)},
        double_strike=0.014,
        skip_strike=0.01,
        line_drift=0.16,
        platen_slant=0.2,
        margin_left=150,
        margin_top=150,
        margin_right=140,
        strike_heavy=0.4,
        ink_smear=0.4,
        baseline_wave=1.0,
        space_jitter=0.4,
        seed=1976,
    ),
    Typewriter(
        name="Fien — zware Smith-Corona",
        font_file="ShareTechMono-Regular.ttf",
        size=18.2,
        ink=(26, 38, 30),
        paper=(239, 234, 218),
        jitter=1.05,
        rotation=1.7,
        wear=0.36,
        ribbon_fade=0.28,
        tracking=12.8,
        leading=31.0,
        key_bias={"o": (0.5, -0.3), "a": (-0.4, 0.4), "t": (0.1, 0.55), "e": (0.3, -0.15)},
        double_strike=0.02,
        skip_strike=0.015,
        line_drift=0.2,
        platen_slant=-0.22,
        margin_left=102,
        margin_top=122,
        margin_right=96,
        strike_heavy=0.8,
        ink_smear=0.7,
        baseline_wave=1.2,
        space_jitter=0.5,
        seed=1952,
    ),
    Typewriter(
        name="Gerrit — nette Adler",
        font_file="AnonymousPro-Regular.ttf",
        size=18.0,
        ink=(16, 20, 36),
        paper=(246, 246, 240),
        jitter=0.48,
        rotation=0.75,
        wear=0.14,
        ribbon_fade=0.12,
        tracking=11.2,
        leading=29.5,
        key_bias={"r": (-0.18, 0.22), "s": (0.22, -0.18)},
        double_strike=0.006,
        skip_strike=0.005,
        line_drift=0.07,
        platen_slant=0.1,
        margin_left=132,
        margin_top=124,
        margin_right=120,
        strike_heavy=0.3,
        ink_smear=0.22,
        baseline_wave=0.45,
        space_jitter=0.2,
        seed=1982,
    ),
    Typewriter(
        name="Hanna — schoolmachine",
        font_file="CourierPrime-Bold.ttf",
        size=18.8,
        ink=(20, 20, 18),
        paper=(232, 226, 208),
        jitter=0.95,
        rotation=1.6,
        wear=0.33,
        ribbon_fade=0.26,
        tracking=12.4,
        leading=31.5,
        key_bias={"i": (0.0, 0.5), "l": (0.0, 0.45), "e": (0.35, -0.25), "a": (-0.3, 0.2)},
        double_strike=0.016,
        skip_strike=0.014,
        line_drift=0.18,
        platen_slant=0.28,
        margin_left=110,
        margin_top=128,
        margin_right=100,
        strike_heavy=0.85,
        ink_smear=0.55,
        baseline_wave=1.1,
        space_jitter=0.45,
        seed=1969,
    ),
    Typewriter(
        name="Ivo — technische Olivetti",
        font_file="FragmentMono-Regular.ttf",
        size=17.4,
        ink=(24, 28, 40),
        paper=(241, 243, 238),
        jitter=0.7,
        rotation=1.15,
        wear=0.22,
        ribbon_fade=0.18,
        tracking=11.0,
        leading=28.2,
        key_bias={"1": (0.2, -0.35), "2": (-0.15, 0.2), "o": (0.25, 0.15)},
        double_strike=0.01,
        skip_strike=0.008,
        line_drift=0.1,
        platen_slant=-0.15,
        margin_left=118,
        margin_top=116,
        margin_right=108,
        strike_heavy=0.45,
        ink_smear=0.3,
        baseline_wave=0.7,
        space_jitter=0.3,
        seed=1987,
    ),
    Typewriter(
        name="Joke — vooroorlogse Remington",
        font_file="SpecialElite-Regular.ttf",
        size=20.4,
        ink=(38, 32, 26),
        paper=(228, 216, 188),
        jitter=1.5,
        rotation=2.6,
        wear=0.58,
        ribbon_fade=0.22,
        tracking=13.8,
        leading=35.5,
        key_bias={
            "e": (0.7, -0.6),
            "a": (-0.55, 0.4),
            "n": (0.35, 0.5),
            "r": (-0.4, -0.35),
            "t": (0.15, 0.7),
            "o": (0.45, -0.25),
        },
        double_strike=0.03,
        skip_strike=0.022,
        line_drift=0.38,
        platen_slant=0.55,
        margin_left=100,
        margin_top=145,
        margin_right=95,
        strike_heavy=0.62,
        ink_smear=0.9,
        baseline_wave=2.1,
        space_jitter=0.7,
        seed=1959,
    ),
]


def load_font(tw: Typewriter) -> GlyphCache:
    path = os.path.join(FONT_DIR, tw.font_file)
    font = TTFont(path)
    if "fvar" in font:
        weight = tw.weight or 400
        font = instantiateVariableFont(font, {"wght": weight})
    cmap = font.getBestCmap() or {}
    return GlyphCache(
        font=font,
        cmap=cmap,
        glyph_set=font.getGlyphSet(),
        units_per_em=font["head"].unitsPerEm,
    )


def glyph_advance(cache: GlyphCache, ch: str) -> float:
    if ch in cache.advances:
        return cache.advances[ch]
    name = cache.cmap.get(ord(ch))
    if name is None:
        cache.advances[ch] = 0.5
        return 0.5
    gs = cache.glyph_set[name]
    cache.advances[ch] = float(gs.width) / cache.units_per_em
    return cache.advances[ch]


def glyph_path(cache: GlyphCache, ch: str) -> Optional[str]:
    if ch in cache.paths:
        return cache.paths[ch]
    name = cache.cmap.get(ord(ch))
    if name is None:
        cache.paths[ch] = ""
        return None
    pen = SVGPathPen(cache.glyph_set)
    # Font space: y-up. SVG: y-down. Scale to 1em, flip Y, shift to baseline.
    transform = (1 / cache.units_per_em, 0, 0, -1 / cache.units_per_em, 0, 0)
    tpen = TransformPen(pen, transform)
    cache.glyph_set[name].draw(tpen)
    d = pen.getCommands()
    cache.paths[ch] = d
    return d or None


NUM_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def perturb_path(d: str, rng: random.Random, amount: float) -> str:
    """Nudge every coordinate so two strikes of the same letter differ."""

    def repl(match: re.Match) -> str:
        value = float(match.group(0))
        if abs(value) < 1e-9:
            return match.group(0)
        jittered = value + rng.uniform(-amount, amount)
        return f"{jittered:.4f}"

    return NUM_RE.sub(repl, d)


def warp_path(d: str, rng: random.Random, squash_x: float, squash_y: float) -> str:
    """Independent X/Y squash so the slug is never a uniform scale of the master."""
    parts = []
    last_was_num = False
    index = 0
    pos = 0
    for match in NUM_RE.finditer(d):
        parts.append(d[pos : match.start()])
        value = float(match.group(0))
        # Alternate x,y in SVG path numbers is not strictly true for all
        # commands, but for glyph outlines (M/L/C/Q) it is close enough,
        # and the extra chaos helps uniqueness.
        if index % 2 == 0:
            value *= squash_x
        else:
            value *= squash_y
        parts.append(f"{value:.4f}")
        index += 1
        pos = match.end()
        last_was_num = True
    parts.append(d[pos:])
    _ = last_was_num
    return "".join(parts)


def rgb(color: Tuple[int, int, int], fade: float = 0.0, rng: Optional[random.Random] = None) -> str:
    r, g, b = color
    if rng is not None:
        r = int(max(0, min(255, r + rng.randint(-8, 8))))
        g = int(max(0, min(255, g + rng.randint(-8, 8))))
        b = int(max(0, min(255, b + rng.randint(-8, 8))))
    r = int(r + (255 - r) * fade)
    g = int(g + (255 - g) * fade)
    b = int(b + (255 - b) * fade)
    return f"rgb({r},{g},{b})"


def paper_svg_fill(paper: Tuple[int, int, int]) -> str:
    r, g, b = paper
    return (
        f'<rect width="100%" height="100%" fill="rgb({r},{g},{b})"/>'
        f'<rect width="100%" height="100%" fill="url(#grain)" opacity="0.35"/>'
        f'<rect width="100%" height="100%" fill="url(#age)" opacity="0.55"/>'
    )


def svg_defs(paper: Tuple[int, int, int], seed: int) -> str:
    rng = random.Random(seed)
    r, g, b = paper
    spots = []
    for i in range(18):
        spots.append(
            f'<feTurbulence type="fractalNoise" baseFrequency="{0.6 + rng.random()*0.8:.3f}" '
            f'numOctaves="3" seed="{rng.randint(1, 9999)}" result="n{i}"/>'
        )
    # Keep defs compact: one turbulence + a warm vignette.
    return f"""
  <defs>
    <filter id="ink" x="-20%" y="-20%" width="140%" height="140%">
      <feTurbulence type="fractalNoise" baseFrequency="1.8" numOctaves="2" seed="{seed}" result="t"/>
      <feDisplacementMap in="SourceGraphic" in2="t" scale="0.55" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
    <filter id="grain">
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="4" seed="{seed + 7}" result="g"/>
      <feColorMatrix type="matrix" values="0 0 0 0 {r/255:.3f}  0 0 0 0 {g/255:.3f}  0 0 0 0 {b/255:.3f}  0 0 0 0.18 0"/>
    </filter>
    <radialGradient id="age" cx="50%" cy="40%" r="75%">
      <stop offset="0%" stop-color="rgb({min(255,r+8)},{min(255,g+6)},{max(0,b-4)})" stop-opacity="0"/>
      <stop offset="70%" stop-color="rgb({r},{g},{b})" stop-opacity="0"/>
      <stop offset="100%" stop-color="rgb({max(0,r-28)},{max(0,g-32)},{max(0,b-38)})" stop-opacity="0.28"/>
    </radialGradient>
  </defs>
"""


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


def type_document(text: str, tw: Typewriter, cache: GlyphCache) -> str:
    rng = random.Random(tw.seed)
    lines = text.replace("\t", "    ").split("\n")
    max_x = PAGE_W - tw.margin_right
    em = tw.size

    chars_svg: List[str] = []
    y = tw.margin_top
    char_index = 0
    total_chars = max(1, sum(len(line) for line in lines))

    for line_i, line in enumerate(lines):
        x = tw.margin_left + line_i * tw.line_drift
        # Paper feed is never perfectly even.
        y += rng.uniform(-0.35, 0.55)
        wave = math.sin(line_i * 0.55 + tw.seed) * tw.baseline_wave
        line_rot = rng.uniform(-0.18, 0.18)

        for col, raw in enumerate(line):
            ch = raw if raw in cache.cmap else fallback_char(raw)
            progress = char_index / total_chars
            fade = tw.ribbon_fade * (0.35 * progress + 0.65 * (x / PAGE_W))
            fade += rng.uniform(-0.04, 0.04)
            fade = max(0.0, min(0.72, fade))

            if ch == " ":
                x += tw.tracking + rng.uniform(-tw.space_jitter, tw.space_jitter)
                char_index += 1
                continue

            d = glyph_path(cache, ch)
            if not d:
                x += tw.tracking
                char_index += 1
                continue

            if rng.random() < tw.skip_strike:
                # Weak strike from a dry ribbon — never drop the letter.
                fade = min(0.42, fade + rng.uniform(0.12, 0.22))

            bias = tw.key_bias.get(ch, (0.0, 0.0))
            jx = rng.uniform(-tw.jitter, tw.jitter) + bias[0]
            jy = rng.uniform(-tw.jitter, tw.jitter) + bias[1] + wave
            rot = rng.uniform(-tw.rotation, tw.rotation) + line_rot
            # Harder/softer strike: independent x/y so the letter is not a clone.
            strike = 1.0 + rng.uniform(-0.045, 0.06) * tw.strike_heavy
            squash_x = strike * rng.uniform(0.97, 1.04)
            squash_y = strike * rng.uniform(0.96, 1.05)
            # Unique outline noise for this strike.
            amount = 0.004 + tw.wear * 0.012
            unique = perturb_path(d, rng, amount)
            unique = warp_path(unique, rng, squash_x, squash_y)

            opacity = 0.72 + rng.uniform(0.0, 0.28) * tw.strike_heavy
            opacity *= 1.0 - fade * 0.85
            opacity = max(0.22, min(0.98, opacity))
            fill = rgb(tw.ink, fade=fade * 0.55, rng=rng)

            smear_dx = rng.uniform(-0.03, 0.05) * tw.ink_smear
            smear_dy = rng.uniform(-0.02, 0.04) * tw.ink_smear
            smear_op = opacity * 0.28 * tw.ink_smear

            scale = em
            transform = (
                f"translate({x + jx:.2f} {y + jy:.2f}) "
                f"rotate({rot:.3f}) scale({scale:.3f})"
            )
            clip_attr = ""
            extra = ""

            def esc_path(p: str) -> str:
                return xml.escape(p, {"\"": "&quot;"})

            body = (
                f'<g transform="{transform}" filter="url(#ink)"{clip_attr}>'
                f'<path d="{esc_path(unique)}" fill="{fill}" fill-opacity="{opacity:.3f}"/>'
            )
            if tw.ink_smear > 0.2 and rng.random() < 0.7:
                smear_path = perturb_path(unique, rng, amount * 0.6)
                body += (
                    f'<path d="{esc_path(smear_path)}" fill="{fill}" '
                    f'fill-opacity="{smear_op:.3f}" transform="translate({smear_dx:.3f} {smear_dy:.3f})"/>'
                )
            body += "</g>"

            if rng.random() < tw.double_strike:
                dx = rng.uniform(0.6, 1.6)
                dy = rng.uniform(-0.5, 0.5)
                second = perturb_path(d, rng, amount)
                second = warp_path(second, rng, squash_x * rng.uniform(0.98, 1.02), squash_y)
                t2 = (
                    f"translate({x + jx + dx:.2f} {y + jy + dy:.2f}) "
                    f"rotate({rot + rng.uniform(-0.4, 0.4):.3f}) scale({scale:.3f})"
                )
                body += (
                    f'<g transform="{t2}" filter="url(#ink)">'
                    f'<path d="{esc_path(second)}" fill="{fill}" '
                    f'fill-opacity="{opacity * 0.55:.3f}"/>'
                    f"</g>"
                )

            chars_svg.append(extra + body)
            if rng.random() < 0.07 * tw.ink_smear:
                for _ in range(rng.randint(1, 3)):
                    sx = x + jx + rng.uniform(-1.2, em * 0.75)
                    sy = y + jy + rng.uniform(-em * 0.85, 2.0)
                    sr = rng.uniform(0.12, 0.48)
                    chars_svg.append(
                        f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="{sr:.2f}" '
                        f'fill="{fill}" fill-opacity="{opacity * 0.32:.3f}"/>'
                    )
            advance = max(tw.tracking * 0.85, glyph_advance(cache, ch) * em * 0.92)
            # Mix monospace carriage with the real glyph width so columns wander.
            step = tw.tracking * 0.72 + advance * 0.28
            x += step + rng.uniform(-0.35, 0.45)
            char_index += 1

            if x > max_x:
                break

        y += tw.leading + rng.uniform(-0.4, 0.8)
        if y > PAGE_H - 80:
            break

    slant = tw.platen_slant
    inner = "\n".join(chars_svg)
    return (
        f'<g transform="rotate({slant:.3f} {PAGE_W/2:.0f} {PAGE_H/2:.0f})">\n'
        f"{inner}\n"
        f"</g>"
    )


def write_svg(path: str, tw: Typewriter, body: str) -> None:
    r, g, b = tw.paper
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}" height="{PAGE_H}" viewBox="0 0 {PAGE_W} {PAGE_H}">
{svg_defs(tw.paper, tw.seed)}
  <rect width="100%" height="100%" fill="rgb({r},{g},{b})"/>
  <rect width="100%" height="100%" fill="url(#age)"/>
  {body}
</svg>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(svg)


def paper_grain_png(img: Image.Image, tw: Typewriter) -> Image.Image:
    rng = np.random.default_rng(tw.seed)
    w, h = img.size
    base = np.array(img).astype(np.float32)
    grain = rng.normal(0, 1.6, (h, w, 1)).astype(np.float32)
    # Fibrous paper: stretched noise
    fibre = rng.normal(0, 1.0, (h, max(1, w // 18), 1)).astype(np.float32)
    fibre = np.repeat(fibre, 18, axis=1)
    if fibre.shape[1] < w:
        pad = np.repeat(fibre[:, -1:, :], w - fibre.shape[1], axis=1)
        fibre = np.concatenate([fibre, pad], axis=1)
    fibre = fibre[:, :w]
    speck = (rng.random((h, w)) < 0.0015).astype(np.float32) * rng.uniform(-10, 8, (h, w))
    aged = np.zeros_like(base)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((xx - cx) / w) ** 2 + ((yy - cy) / h) ** 2)
    vignette = np.clip((dist - 0.35) * 38, 0, 22)
    aged[..., 0] -= vignette * 0.9
    aged[..., 1] -= vignette * 1.1
    aged[..., 2] -= vignette * 1.4
    out = base + grain + fibre * 2.4 + speck[..., None] + aged
    out = np.clip(out, 0, 255).astype(np.uint8)
    result = Image.fromarray(out, mode="RGB")
    # Soften digital edges of the ink a touch.
    return result.filter(ImageFilter.SMOOTH)


def render_png(svg_path: str, png_path: str, tw: Typewriter) -> None:
    cairosvg.svg2png(
        url=svg_path,
        write_to=png_path,
        output_width=PAGE_W * PNG_SCALE,
        output_height=PAGE_H * PNG_SCALE,
    )
    img = Image.open(png_path).convert("RGB")
    img = paper_grain_png(img, tw)
    img.save(png_path, "PNG", dpi=(300, 300), optimize=True, compress_level=9)


def main() -> None:
    os.makedirs(SVG_DIR, exist_ok=True)
    os.makedirs(PNG_DIR, exist_ok=True)

    index_rows = []
    for (slug, title, text), tw in zip(SAMPLE_TEXTS, TYPEWRITERS):
        print(f"Typen: {slug}  ({tw.name})")
        cache = load_font(tw)
        body = type_document(text, tw, cache)
        svg_path = os.path.join(SVG_DIR, f"{slug}.svg")
        png_path = os.path.join(PNG_DIR, f"{slug}.png")
        write_svg(svg_path, tw, body)
        render_png(svg_path, png_path, tw)
        index_rows.append((slug, title, tw.name, os.path.basename(svg_path), os.path.basename(png_path)))

    readme = [
        "# Tien getypte geschriften",
        "",
        "Voorbeeldteksten die eruitzien alsof ze op een echte schrijfmachine zijn getikt.",
        "Elke letter is een eigen vectorpad: andere rotatie, inkt, slijtage en omtrek,",
        "dus twee keer dezelfde `e` is nooit identiek.",
        "",
        "Opnieuw maken:",
        "",
        "```bash",
        "python3 geschriften/generate_geschriften.py",
        "```",
        "",
        "| # | Geschrift | Machine | SVG | PNG |",
        "|---|-----------|---------|-----|-----|",
    ]
    for i, (slug, title, machine, svg_name, png_name) in enumerate(index_rows, 1):
        readme.append(f"| {i} | {title} | {machine} | [svg/{svg_name}](svg/{svg_name}) | [png/{png_name}](png/{png_name}) |")
    readme.append("")
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(readme) + "\n")
    print("Klaar.")


if __name__ == "__main__":
    main()
