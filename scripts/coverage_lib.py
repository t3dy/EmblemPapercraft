#!/usr/bin/env python
"""
coverage_lib.py — measure how completely the papercraft cutouts realize each plate.

The papercraft stacks transparent-PNG cutouts in front of the full engraving. A
"judicious" cut turns the whole PICTORIAL scene into paper layers; a lazy one keeps
only a few big blobs and leaves most of the engraving stranded flat on the backing.
This module reconstructs, in the renderer's own normalised [0,1]x[0,1] space, which
plate pixels are covered by at least one cutout, and compares that against the
plate's INK (the engraved marks). The gap between them is extraction debt.

Everything downstream (audit_coverage.py, test_coverage.py) is built on `analyze()`.

Coordinate model — must match js/papercraft.js:
  · the plate image is stretched to fill the page plane (UV 0..1 both axes);
  · a cutout sits at normalised centre (cx,cy) with normalised size (nw,nh).
So we rasterise onto a canvas at the plate's own pixel size, treating that as the
[0,1]^2 grid, and stamp each cutout's alpha scaled to (nw,nh) at (cx,cy). Aspect
stretch applies equally to plate and cutouts, so alignment here == on screen.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT      = Path(__file__).resolve().parent.parent
PLATES    = ROOT / "images" / "emblems"
CUTOUTS   = ROOT / "images" / "cutouts"
LAYERS    = ROOT / "data" / "layers.json"
REGIONS   = ROOT / "data" / "coverage_regions.json"

# Budget defaults — overridable globally or per-emblem in coverage_regions.json.
DEFAULTS = {
    "ink_threshold":       0.55,   # plate pixels darker than this (0..1) are "ink"
    "min_coverage":        0.85,   # completeness floor — achievable now backdrops exist
    "min_figure_coverage": 0.0,    # >= this fraction of ink under NON-backdrop cards (decomposition floor)
    "max_gap_frac":        0.045,  # no single uncovered-ink blob larger than this frac of plate
    "min_registration":    0.20,   # each card's OWN ink must land at least this fraction on plate ink
    "gap_min_frac":        0.004,  # ignore uncovered blobs smaller than this (specks, frame lines)
    "min_card_frac":       0.0,    # (reserved) flag cards smaller than this fraction of plate
}


def load_layers():
    return {e["number"]: e for e in json.loads(LAYERS.read_text(encoding="utf-8"))}


def load_regions():
    if REGIONS.exists():
        return json.loads(REGIONS.read_text(encoding="utf-8"))
    return {"defaults": {}, "emblems": {}}


def budget_for(regions, n):
    """Merged budget dict for emblem n: DEFAULTS < regions.defaults < regions.emblems[n]."""
    b = dict(DEFAULTS)
    b.update(regions.get("defaults", {}))
    e = regions.get("emblems", {}).get(str(n), {})
    b.update({k: v for k, v in e.items() if k in DEFAULTS})
    return b


def plate_path(n):
    return PLATES / f"emblem-{n:02d}.jpg"


def _flat_mask(shape, flats):
    """Boolean mask of intentionally-flat rectangles [x0,y0,x1,y1] in normalised coords."""
    PH, PW = shape
    m = np.zeros(shape, dtype=bool)
    for r in flats or []:
        x0, y0, x1, y1 = r
        m[int(y0 * PH):int(y1 * PH), int(x0 * PW):int(x1 * PW)] = True
    return m


def place_layer(L, PW, PH):
    """Stamp one manifest layer into plate-sized masks (renderer geometry).

    Returns (placed_alpha, meta) or (None, meta) if the cutout is missing/off-plate.
    meta["ink"] is the placed mask of the cutout's OWN dark lines (for registration).
    """
    cp = CUTOUTS / L["file"]
    if not cp.exists():
        return None, {"missing": True}
    rgba = np.asarray(Image.open(cp).convert("RGBA"))
    alpha = rgba[:, :, 3] > 128
    cink = (rgba[:, :, :3].mean(axis=2) < 140) & alpha   # the cutout's engraved lines
    bw = max(1, round(L["nw"] * PW))
    bh = max(1, round(L["nh"] * PH))

    def stamp(mask):
        m = np.asarray(Image.fromarray((mask * 255).astype("uint8"))
                       .resize((bw, bh), Image.NEAREST)) > 128
        cx, cy = round(L["cx"] * PW), round(L["cy"] * PH)
        x0, y0 = cx - bw // 2, cy - bh // 2
        xs, ys = max(0, x0), max(0, y0)
        xe, ye = min(PW, x0 + bw), min(PH, y0 + bh)
        if xe <= xs or ye <= ys:
            return None, None
        out = np.zeros((PH, PW), dtype=bool)
        out[ys:ye, xs:xe] = m[ys - y0:ye - y0, xs - x0:xe - x0]
        return out, (cx, cy)

    placed, ctr = stamp(alpha)
    if placed is None:
        return None, {"offplate": True}
    placed_ink, _ = stamp(cink)
    cx, cy = ctr
    return placed, {"ink": placed_ink,
                    "bbox": [round((cx - bw / 2) / PW, 3), round((cy - bh / 2) / PH, 3),
                             round((cx + bw / 2) / PW, 3), round((cy + bh / 2) / PH, 3)]}


def analyze(n, layers_by_num, regions):
    """Full coverage analysis for one emblem. Returns a dict of metrics + masks.

    A layer with role=="backdrop" is a generated residual back-sheet: it counts
    toward completeness (coverage) but is excluded from overlap and from the
    figure-share metric, so it can't disguise an un-decomposed plate as judicious.
    """
    b = budget_for(regions, n)
    emb_regions = regions.get("emblems", {}).get(str(n), {})
    flats = emb_regions.get("flat", [])

    im = Image.open(plate_path(n)).convert("L")
    plate = np.asarray(im, dtype=np.float32) / 255.0
    PH, PW = plate.shape
    ink = plate < b["ink_threshold"]
    ink_dil = ndimage.binary_dilation(ink, iterations=2)  # tolerance for registration
    flat = _flat_mask((PH, PW), flats)
    ink_scored = ink & ~flat            # ink we hold the extraction responsible for

    count = np.zeros((PH, PW), dtype=np.uint16)   # figure cards covering each pixel
    cover_fg = np.zeros((PH, PW), dtype=bool)     # union of figure (non-backdrop) cards
    cover_bd = np.zeros((PH, PW), dtype=bool)     # union of backdrop cards
    cards = []
    for L in layers_by_num.get(n, {}).get("layers", []):
        is_bd = L.get("role") == "backdrop"
        placed, meta = place_layer(L, PW, PH)
        if placed is None:
            meta["file"] = L["file"]; meta["role"] = L.get("role")
            cards.append(meta)
            continue
        if is_bd:
            cover_bd |= placed
        else:
            count[placed] += 1
            cover_fg |= placed
        area = int(placed.sum())
        pink = meta.get("ink")
        ink_px = int(pink.sum()) if pink is not None else 0
        # registration: fraction of the cutout's OWN engraved lines landing on plate ink
        # (robust to line-art cutouts that enclose lots of white, unlike alpha-on-ink).
        registration = float((pink & ink_dil).sum()) / ink_px if ink_px else 0.0
        cards.append({
            "file": L["file"], "role": L.get("role"), "depth": L.get("depth"),
            "area_frac": round(area / (PW * PH), 4),
            "registration": round(registration, 3), "ink_px": ink_px, "bbox": meta["bbox"],
            # backdrops legitimately sit over paper (their own holes); don't strand-flag them
            "stranded": (not is_bd) and registration < b["min_registration"],
        })

    cover = cover_fg | cover_bd
    overlap = count > 1                 # redundancy among figure cards only

    ink_total = int(ink_scored.sum())
    ink_cov   = int((cover & ink_scored).sum())
    coverage  = ink_cov / max(1, ink_total)
    figure_coverage = int((cover_fg & ink_scored).sum()) / max(1, ink_total)

    # Uncovered-ink gap regions — the actionable "what's missing" list.
    gap = ink_scored & ~cover
    lbl, nlbl = ndimage.label(gap)
    gaps = []
    if nlbl:
        areas = ndimage.sum(np.ones_like(lbl), lbl, range(1, nlbl + 1))
        for i in np.argsort(areas)[::-1]:
            frac = areas[i] / (PW * PH)
            if frac < b["gap_min_frac"]:
                break
            ys, xs = np.where(lbl == (i + 1))
            gaps.append({
                "area_frac": round(float(frac), 4),
                "bbox": [round(xs.min() / PW, 3), round(ys.min() / PH, 3),
                         round(xs.max() / PW, 3), round(ys.max() / PH, 3)],
                "centroid": [round(float(xs.mean()) / PW, 3), round(float(ys.mean()) / PH, 3)],
            })

    overlap_frac = float(overlap.sum()) / max(1, int(cover_fg.sum()))
    stranded = [c for c in cards if c.get("stranded")]
    n_fig = len([c for c in cards if c.get("bbox") and c.get("role") != "backdrop"])
    has_backdrop = any(c.get("role") == "backdrop" for c in cards)

    return {
        "number": n,
        "plate_px": [PW, PH],
        "n_cards": len([c for c in cards if not c.get("missing") and not c.get("offplate")]),
        "n_figures": n_fig,
        "has_backdrop": has_backdrop,
        "coverage": round(coverage, 4),
        "figure_coverage": round(figure_coverage, 4),
        "ink_frac": round(ink_total / (PW * PH), 4),
        "overlap_frac": round(overlap_frac, 4),
        "largest_gap": gaps[0]["area_frac"] if gaps else 0.0,
        "n_gaps": len(gaps),
        "gaps": gaps,
        "cards": cards,
        "n_stranded": len(stranded),
        "n_flat": len(flats),
        "budget": b,
        # masks kept for the image renderer; JSON serialisers should drop these.
        "_masks": {"plate": plate, "ink": ink, "flat": flat, "gap": gap,
                   "cover_fg": cover_fg, "cover_bd": cover_bd, "overlap": overlap},
    }


def render_overlay(res):
    """Diagnostic PNG: green=figure-covered ink, teal=backdrop-only, red=uncovered,
    blue=figure overlap, grey=flat."""
    m = res["_masks"]
    PH, PW = m["plate"].shape
    base = (m["plate"] * 90 + 25).astype(np.uint8)          # dim paper
    rgb = np.stack([base, base, base], axis=-1).astype(np.uint16)
    bd_only = m["ink"] & m["cover_bd"] & ~m["cover_fg"]
    rgb[bd_only]                = [30, 150, 150]            # backdrop-only ink -> teal
    rgb[m["ink"] & m["cover_fg"]] = [40, 190, 70]           # figure-covered ink -> green
    rgb[m["gap"]]               = [230, 55, 45]             # uncovered ink -> red
    rgb[m["overlap"]]          += np.array([0, 0, 120], dtype=np.uint16)  # overlap -> blue
    rgb[m["flat"] & m["ink"]]   = [110, 110, 120]           # intentionally flat -> grey
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def grade(coverage):
    for thr, g in [(0.85, "A"), (0.72, "B"), (0.58, "C"), (0.4, "D")]:
        if coverage >= thr:
            return g
    return "F"


def strip_masks(res):
    return {k: v for k, v in res.items() if k != "_masks"}
