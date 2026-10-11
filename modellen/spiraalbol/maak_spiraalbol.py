#!/usr/bin/env python3
"""Maak een spiraalbol-lampkap na: diameter 20 cm, gat boven en onder.

De vorm volgt de hanglamp op de foto: een bolvormige kap met diagonale
ribben, een opening aan de bovenkant (snoer) en een opening aan de
onderkant. Het STL-bestand is in millimeters, oorsprong in het midden,
Z omhoog.

Buitendiameter (toppen van de ribben): 200 mm.
Wand: één lijntje, nozzle 0,4 mm, dus 0,4 mm dik.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import Image

# --- afmetingen, millimeters -------------------------------------------------
DIAMETER = 200.0          # top tot top van de ribben
AMPLITUDE = 2.3           # halve ribhoogte; top-dal = 2 * AMPLITUDE
N_RIBBEN = 24             # ribben rondom
HOEK_GRADEN = 33.0        # helling van een rib t.o.v. de horizontaal, op de evenaar
GAT_BOVEN = 76.0          # diameter van de bovenopening
GAT_ONDER = 70.0          # diameter van de onderopening
WAND = 0.4                # één wandlijn bij een nozzle van 0,4 mm

OUT_DIR = Path(__file__).resolve().parent
STL_PATH = OUT_DIR / "spiraalbol-20cm.stl"
PREVIEW_PATH = OUT_DIR / "preview.png"


def rib_helling():
    """d(fase)/d(theta). Negatief: op de voorzijde lopen de ribben naar rechtsonder."""
    alfa = np.radians(HOEK_GRADEN)
    # tan(alfa) = N / |T| op de evenaar, met fase = N*phi + T*theta
    return -N_RIBBEN / np.tan(alfa)


def rib_verzwakking(theta):
    """Ribben lopen naar de gaten toe zacht uit, zodat de rand rond blijft."""
    th0, th1 = poolhoeken()
    breedte = 0.42

    def zacht(x):
        x = np.clip(x, 0.0, 1.0)
        return x * x * (3.0 - 2.0 * x)

    return zacht((theta - th0) / breedte) * zacht((th1 - theta) / breedte)


def straal_oppervlak(theta, phi):
    """Buitenstraal. Toppen raken precies DIAMETER/2."""
    fase = N_RIBBEN * phi + rib_helling() * theta
    golf = np.cos(fase) * rib_verzwakking(theta)
    return (DIAMETER / 2) - AMPLITUDE + AMPLITUDE * golf


def gemiddelde_straal():
    return (DIAMETER / 2) - AMPLITUDE


def poolhoeken():
    """Polarhoek van de boven- en onderrand (0 = noordpool)."""
    rm = gemiddelde_straal()
    th_boven = np.arcsin((GAT_BOVEN / 2) / rm)
    th_onder = np.pi - np.arcsin((GAT_ONDER / 2) / rm)
    return float(th_boven), float(th_onder)


def bol_basis(theta, phi, straal):
    st, ct = np.sin(theta), np.cos(theta)
    cp, sp = np.cos(phi), np.sin(phi)
    return np.stack((straal * st * cp, straal * st * sp, straal * ct), axis=-1)


def buiten_normalen(theta, phi):
    """Analytische normaal van de gegolfde bol, naar buiten."""
    T = rib_helling()
    th0, th1 = poolhoeken()
    breedte = 0.42
    fase = N_RIBBEN * phi + T * theta
    c = np.cos(fase)
    s = np.sin(fase)
    xb = np.clip((theta - th0) / breedte, 0.0, 1.0)
    xo = np.clip((th1 - theta) / breedte, 0.0, 1.0)
    mb = xb * xb * (3.0 - 2.0 * xb)
    mo = xo * xo * (3.0 - 2.0 * xo)
    mask = mb * mo
    dmb = np.where((xb > 0) & (xb < 1), 6.0 * xb * (1.0 - xb) / breedte, 0.0)
    dmo = np.where((xo > 0) & (xo < 1), 6.0 * xo * (1.0 - xo) / breedte, 0.0)
    dmask = dmb * mo + mb * (-dmo)
    dr_dth = AMPLITUDE * (dmask * c + mask * (-s) * T)
    dr_dph = AMPLITUDE * (mask * (-s) * N_RIBBEN)
    rs = straal_oppervlak(theta, phi)
    st, ct = np.sin(theta), np.cos(theta)
    cp, sp = np.cos(phi), np.sin(phi)
    rad = np.stack((st * cp, st * sp, ct), axis=-1)
    dth = np.stack((ct * cp, ct * sp, -st), axis=-1)
    dph = np.stack((-st * sp, st * cp, np.zeros_like(st)), axis=-1)
    dp_dth = dr_dth[..., None] * rad + rs[..., None] * dth
    dp_dph = dr_dph[..., None] * rad + rs[..., None] * dph
    n = np.cross(dp_dth, dp_dph)
    lengte = np.linalg.norm(n, axis=-1, keepdims=True)
    n = n / np.maximum(lengte, 1e-9)
    # cross(dθ, dφ) wijst bij deze parametrisatie naar buiten
    return n


def bouw_mesh(n_theta=160, n_phi=360):
    """Gesloten schaal: buitenkant, binnenkant en randen rond beide gaten."""
    th0, th1 = poolhoeken()
    theta = np.linspace(th0, th1, n_theta)
    phi = np.linspace(0, 2 * np.pi, n_phi, endpoint=False)
    TH, PH = np.meshgrid(theta, phi, indexing="ij")
    rs = straal_oppervlak(TH, PH)
    buiten = bol_basis(TH, PH, rs)

    # Normaal via centrale differentie, phi wikkelt rond.
    dth = np.gradient(buiten, theta, axis=0, edge_order=2)
    dph = (np.roll(buiten, -1, axis=1) - np.roll(buiten, 1, axis=1)) * (
        n_phi / (4 * np.pi)
    )
    nrm = np.cross(dth, dph)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-9)
    naar_buiten = np.sum(nrm * buiten, axis=-1, keepdims=True)
    nrm = nrm * np.sign(naar_buiten)

    binnen = buiten - WAND * nrm

    nt, np_ = n_theta, n_phi
    v_buiten = buiten.reshape(-1, 3)
    v_binnen = binnen.reshape(-1, 3)
    n_buiten = nrm.reshape(-1, 3)
    n_binnen = -n_buiten
    verts = np.vstack((v_buiten, v_binnen)).astype(np.float64)
    vnorm = np.vstack((n_buiten, n_binnen)).astype(np.float64)

    def oid(i, j):
        return i * np_ + (j % np_)

    def iid(i, j):
        return nt * np_ + i * np_ + (j % np_)

    tris = []
    for i in range(nt - 1):
        for j in range(np_):
            j2 = j + 1
            tris.append((oid(i, j), oid(i + 1, j), oid(i + 1, j2)))
            tris.append((oid(i, j), oid(i + 1, j2), oid(i, j2)))
            # binnenwand: tegengestelde omloop, wordt hierna gecorrigeerd
            tris.append((iid(i, j), iid(i + 1, j2), iid(i + 1, j)))
            tris.append((iid(i, j), iid(i, j2), iid(i + 1, j2)))
    for j in range(np_):
        j2 = j + 1
        # bovenrand, normaal omhoog
        tris.append((oid(0, j), oid(0, j2), iid(0, j2)))
        tris.append((oid(0, j), iid(0, j2), iid(0, j)))
        # onderrand, normaal omlaag
        tris.append((oid(nt - 1, j), iid(nt - 1, j), iid(nt - 1, j2)))
        tris.append((oid(nt - 1, j), iid(nt - 1, j2), oid(nt - 1, j2)))

    tris = np.asarray(tris, dtype=np.int32)
    tris = oriënteer(tris, verts, vnorm, nt, np_)
    return verts, tris, vnorm, (th0, th1)


def oriënteer(tris, verts, vnorm, n_theta, n_phi):
    """Zet elke driehoek zo dat de normaal van het materiaal af wijst."""
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    # randen: de gedeelde hoekpunten hebben schaalnormalen, niet de randnormaal.
    # Daarom de randvlakken apart richten, de schaal via de vertexnormalen.
    n_schaal = (n_theta - 1) * n_phi * 4
    gewenst = vnorm[tris[:n_schaal, 0]] + vnorm[tris[:n_schaal, 1]] + vnorm[tris[:n_schaal, 2]]
    flip = np.sum(fn[:n_schaal] * gewenst, axis=1) < 0
    schaal = tris[:n_schaal].copy()
    a = schaal[flip, 1].copy()
    schaal[flip, 1] = schaal[flip, 2]
    schaal[flip, 2] = a

    rand = tris[n_schaal:].copy()
    fnr = fn[n_schaal:]
    # eerste helft van de randvlakken is de bovenkant, tweede de onderkant
    n_rand = len(rand) // 2
    flip_b = fnr[:n_rand, 2] < 0
    flip_o = fnr[n_rand:, 2] > 0
    for blok, mask, start in (
        (rand[:n_rand], flip_b, 0),
        (rand[n_rand:], flip_o, n_rand),
    ):
        b = blok.copy()
        aa = b[mask, 1].copy()
        b[mask, 1] = b[mask, 2]
        b[mask, 2] = aa
        rand[start : start + len(b)] = b
    return np.vstack((schaal, rand))


def schrijf_stl(pad, verts, tris):
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    lengte = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = fn / np.maximum(lengte, 1e-12)
    n = len(tris)
    rec = np.empty(
        n,
        dtype=np.dtype(
            [
                ("n", "<f4", (3,)),
                ("v", "<f4", (3, 3)),
                ("attr", "<u2"),
            ]
        ),
    )
    rec["n"] = fn.astype(np.float32)
    rec["v"][:, 0] = v0.astype(np.float32)
    rec["v"][:, 1] = v1.astype(np.float32)
    rec["v"][:, 2] = v2.astype(np.float32)
    rec["attr"] = 0
    with open(pad, "wb") as f:
        f.write(b"Spiraalbol lamp 20cm, mm, Z omhoog".ljust(80, b"\0"))
        f.write(struct.pack("<I", n))
        rec.tofile(f)
    return n


def controleer(verts, tris):
    """Watertichtheid, afmetingen en of de binnenwand niet door zichzelf gaat."""
    from collections import Counter

    kanten = Counter()
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            kanten[tuple(sorted(e))] += 1
    los = sum(1 for v in kanten.values() if v != 2)
    buiten = verts[: len(verts) // 2]
    binnen = verts[len(verts) // 2 :]
    straal_buiten = np.linalg.norm(buiten, axis=1)
    dikte = np.linalg.norm(buiten - binnen, axis=1)
    bb_min = verts.min(axis=0)
    bb_max = verts.max(axis=0)
    return {
        "driehoeken": int(len(tris)),
        "open_kanten": int(los),
        "wand_min": float(dikte.min()),
        "wand_max": float(dikte.max()),
        "wand_mediaan": float(np.median(dikte)),
        "bbox_min": bb_min,
        "bbox_max": bb_max,
        "diameter_xy": float(max(bb_max[0] - bb_min[0], bb_max[1] - bb_min[1])),
        "hoogte": float(bb_max[2] - bb_min[2]),
        "max_straal": float(straal_buiten.max()),
    }


def _velden(p):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    r = np.sqrt(x * x + y * y + z * z) + 1e-9
    theta = np.arccos(np.clip(z / r, -1, 1))
    phi = np.arctan2(y, x)
    rs = straal_oppervlak(theta, phi)
    return r, theta, phi, rs


def render(breedte, hoogte, elev_deg, azim_deg, afstand, fov_deg, achtergrond, met_binnen=True):
    """Straalmarch van hetzelfde oppervlak als het STL-bestand."""
    th0, th1 = poolhoeken()
    elev = np.radians(elev_deg)
    azim = np.radians(azim_deg)
    oog = np.array(
        [
            afstand * np.cos(elev) * np.sin(azim),
            -afstand * np.cos(elev) * np.cos(azim),
            afstand * np.sin(elev),
        ],
        dtype=np.float64,
    )
    doel = np.zeros(3)
    vooruit = doel - oog
    vooruit /= np.linalg.norm(vooruit)
    rechts = np.cross(vooruit, np.array([0.0, 0.0, 1.0]))
    rechts /= np.linalg.norm(rechts)
    omhoog = np.cross(rechts, vooruit)

    ys, xs = np.mgrid[0:hoogte, 0:breedte]
    u = ((xs + 0.5) / breedte * 2 - 1) * np.tan(np.radians(fov_deg) / 2) * (breedte / hoogte)
    v = (1 - (ys + 0.5) / hoogte * 2) * np.tan(np.radians(fov_deg) / 2)
    dirs = vooruit + rechts * u[..., None] + omhoog * v[..., None]
    dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)

    kleur = np.zeros((hoogte, breedte, 3), dtype=np.float64)
    kleur[:] = achtergrond
    # zacht kamerlicht: de lamp op de foto is mat en bijna rondom verlicht
    L = np.array([0.70, -0.20, 0.68])
    L /= np.linalg.norm(L)
    L2 = np.array([-0.40, -0.85, 0.28])
    L2 /= np.linalg.norm(L2)
    L3 = np.array([0.05, -0.35, -0.85])
    L3 /= np.linalg.norm(L3)
    albedo = np.array([0.96, 0.91, 0.82])
    binnen_kleur = np.array([0.55, 0.40, 0.28])

    Rmax = DIAMETER / 2 + 1.0
    nsteps = 220
    rijen = 24
    for y0 in range(0, hoogte, rijen):
        y1 = min(hoogte, y0 + rijen)
        d = dirs[y0:y1]
        hh, ww = d.shape[:2]
        b = 2 * np.einsum("hwi,i->hw", d, oog)
        c = float(np.dot(oog, oog) - Rmax * Rmax)
        disc = b * b - 4 * c
        ok = disc > 0
        sd = np.sqrt(np.maximum(disc, 0))
        t_bij = np.maximum((-b - sd) / 2, 0)
        t_ver = (-b + sd) / 2
        ok &= t_ver > t_bij + 0.2
        frac = (np.arange(nsteps)[:, None, None] + 0.5) / nsteps
        t = t_bij + (t_ver - t_bij) * frac
        P = oog + t[..., None] * d[None, ...]
        r, theta, phi, rs = _velden(P)
        band = (theta >= th0) & (theta <= th1)
        # Alleen een echte snijding met de buitenkant telt: de straal kruist rs
        # terwijl beide samples in de schaalband zitten. Een straal door het gat
        # komt de band al binnen de schaal binnen en is dus geen buitentreffer.
        f = r - rs
        paar = band[:-1] & band[1:] & (f[:-1] > 0) & (f[1:] <= 0)
        treffer = np.zeros_like(band)
        treffer[1:] = paar
        heeft = treffer.any(axis=0) & ok
        eerste = np.argmax(treffer, axis=0)

        # lineaire verfijning tussen de twee samples rond de snijding
        i = eerste
        i0 = np.maximum(i - 1, 0)
        yy, xx = np.mgrid[0:hh, 0:ww]
        f1 = (r - rs)[i, yy, xx]
        f0 = (r - rs)[i0, yy, xx]
        t1 = t[i, yy, xx]
        t0 = t[i0, yy, xx]
        alpha = np.clip(f0 / (f0 - f1 + 1e-9), 0, 1)
        # als i==0 is er geen vorige sample buiten de bol; alpha negeren
        alpha = np.where(i > 0, alpha, 0.0)
        t_hit = t0 + (t1 - t0) * alpha
        P_hit = oog + t_hit[..., None] * d
        _, th_h, ph_h, _ = _velden(P_hit)
        n = buiten_normalen(th_h, ph_h)
        view = -d
        half = L + view
        half /= np.maximum(np.linalg.norm(half, axis=-1, keepdims=True), 1e-9)
        ndotl = np.sum(n * L, axis=-1)
        ndotl2 = np.sum(n * L2, axis=-1)
        ndotl3 = np.sum(n * L3, axis=-1)
        wrap = 0.48
        diff = np.clip((ndotl + wrap) / (1 + wrap), 0, 1)
        diff2 = np.clip((ndotl2 + wrap) / (1 + wrap), 0, 1)
        diff3 = np.clip((ndotl3 + wrap) / (1 + wrap), 0, 1)
        spec = np.clip(np.sum(n * half, axis=-1), 0, 1) ** 64
        schaduw = 0.24 + 0.58 * diff + 0.24 * diff2 + 0.12 * diff3
        rgb = albedo * schaduw[..., None] + 0.07 * spec[..., None]
        kleur[y0:y1][heeft] = np.clip(rgb, 0, 1)[heeft]

        if not met_binnen:
            continue
        # kijk door het gat: de straal raakt de binnenwand aan de overkant.
        # De wand is dunner dan de stap, dus de straal mag in één stap door de wand heen schieten.
        r_in = rs - WAND
        binnen_holte = r < r_in
        kruist = binnen_holte[:-1] & ~binnen_holte[1:] & band[:-1] & band[1:]
        # alleen waar de buitenkant niet al geraakt is
        heeft_buiten_voor = np.cumsum(treffer, axis=0) > 0
        kruist = kruist & ~heeft_buiten_voor[:-1]
        heeft_in = kruist.any(axis=0) & ok & ~heeft
        if not heeft_in.any():
            continue
        i_in = np.argmax(kruist, axis=0) + 1
        f_in1 = (r - r_in)[i_in, yy, xx]
        i_in0 = i_in - 1
        f_in0 = (r - r_in)[i_in0, yy, xx]
        ti1 = t[i_in, yy, xx]
        ti0 = t[i_in0, yy, xx]
        a_in = np.clip(f_in0 / (f_in0 - f_in1 + 1e-9), 0, 1)
        t_in = ti0 + (ti1 - ti0) * a_in
        P_in = oog + t_in[..., None] * d
        _, th_i, ph_i, _ = _velden(P_in)
        n_in = -buiten_normalen(th_i, ph_i)
        nd = np.clip(np.sum(n_in * L, axis=-1), 0, 1)
        gloed = binnen_kleur * (0.22 + 0.28 * nd)[..., None]
        blok = kleur[y0:y1]
        blok[heeft_in] = gloed[heeft_in]
        kleur[y0:y1] = blok
    return (np.clip(kleur, 0, 1) * 255).astype(np.uint8)


def toon_afmetingen():
    th0, th1 = poolhoeken()
    rm = gemiddelde_straal()
    return {
        "diameter_mm": DIAMETER,
        "ribben": N_RIBBEN,
        "ribhoogte_top_dal_mm": 2 * AMPLITUDE,
        "helling_graden": HOEK_GRADEN,
        "gat_boven_mm": GAT_BOVEN,
        "gat_onder_mm": GAT_ONDER,
        "wand_mm": WAND,
        "hoogte_ongeveer_mm": float(rm * (np.cos(th0) - np.cos(th1))),
        "theta_boven_graden": float(np.degrees(th0)),
        "theta_onder_graden": float(np.degrees(th1)),
    }


def maak(preview=True, mesh_theta=170, mesh_phi=420):
    info = toon_afmetingen()
    print("Afmetingen:")
    for k, v in info.items():
        print(f"  {k}: {v}")
    if preview:
        print("Renderen...")
        muur = np.array([0.765, 0.725, 0.685])
        beeld = render(
            780, 920, elev_deg=-18, azim_deg=18, afstand=430, fov_deg=32, achtergrond=muur
        )
        Image.fromarray(beeld).save(PREVIEW_PATH)
        onder = render(
            720, 720, elev_deg=-70, azim_deg=25, afstand=360, fov_deg=36, achtergrond=muur
        )
        Image.fromarray(onder).save(OUT_DIR / "onderaanzicht.png")
        boven = render(
            720, 720, elev_deg=68, azim_deg=-15, afstand=360, fov_deg=36, achtergrond=muur
        )
        Image.fromarray(boven).save(OUT_DIR / "bovenaanzicht.png")
        print(f"Preview: {PREVIEW_PATH}")
    print("Mesh...")
    verts, tris, _, _ = bouw_mesh(mesh_theta, mesh_phi)
    rapport = controleer(verts, tris)
    print("Controle:")
    for k, v in rapport.items():
        print(f"  {k}: {v}")
    if rapport["open_kanten"] != 0:
        raise SystemExit("Mesh is niet gesloten")
    if not (0.35 <= rapport["wand_min"] and rapport["wand_max"] <= 0.45):
        raise SystemExit("Wanddikte wijkt af van 0,4 mm")
    n = schrijf_stl(STL_PATH, verts, tris)
    print(f"STL: {STL_PATH} ({n} driehoeken)")
    return rapport


if __name__ == "__main__":
    maak(preview=True)
