#!/usr/bin/env python
"""
declare_page_furniture.py — populate the flat-region ledger with each plate's page furniture.

The plate images are full BOOK-PAGE scans: motto and epigram text, page number,
music staves bleeding in from the facing page, and the book's own edges. None of
that is pictorial scene, so none of it should count as extraction debt — but until
it is declared `flat` in data/coverage_regions.json, the coverage metric is diluted
and the gap list is dominated by page-edge noise (the identical ~(0.66, 0.50) gap
centroid across early emblems is the book fore-edge, not missing cutouts).

This script detects the pictorial engraving block per plate — after morphological
closing + hole-filling it is by far the largest solid component with a plausibly
frame-shaped bbox — and writes the four complement strips (top/bottom/left/right of
the frame) as `flat` rects for that emblem. The ledger stays human-editable; rerun
after adding plates. Emblems where no plausible frame is found are left undeclared
and reported, so a failed detection can't silently blanket a whole plate as flat.

Run:
  python scripts/declare_page_furniture.py             # all emblems
  python scripts/declare_page_furniture.py --emblem 7
  python scripts/declare_page_furniture.py --dry-run   # report frames, write nothing
"""
import argparse, json
import numpy as np
from PIL import Image
from scipy import ndimage

import coverage_lib as cov

CLOSE_IT  = 6       # same closing scale the backdrop builder uses
MARGIN    = 0.012   # pad the detected frame outward (keep frame border ink scored)
MIN_SIDE  = 0.28    # plausible frame bbox: each side between MIN_SIDE..MAX_SIDE of page
MAX_SIDE  = 0.92
MIN_FILL  = 0.5     # component must fill >= this fraction of its own bbox


def detect_frame(n, thr):
    """Normalised [x0,y0,x1,y1] of the pictorial block, or None if implausible.

    Only full-page scans (portrait) carry page furniture; the square-ish picture
    crops (emblems 10+) are all pictorial, and running the detector on them would
    latch onto a dark landscape mass and wrongly flat-declare real scene ink."""
    gray = np.asarray(Image.open(cov.plate_path(n)).convert("L"), dtype=np.float32) / 255.0
    PH, PW = gray.shape
    if PH <= PW:
        return "crop"
    ink = gray < thr
    st = ndimage.generate_binary_structure(2, 2)
    sheet = ndimage.binary_fill_holes(ndimage.binary_closing(ink, structure=st, iterations=CLOSE_IT))
    lbl, nc = ndimage.label(sheet)
    if not nc:
        return None
    best, best_area = None, 0
    for sl in ndimage.find_objects(lbl):
        h = (sl[0].stop - sl[0].start) / PH
        w = (sl[1].stop - sl[1].start) / PW
        if not (MIN_SIDE <= w <= MAX_SIDE and MIN_SIDE <= h <= MAX_SIDE):
            continue                       # page edges / stave strips / specks
        comp = sheet[sl]
        area = int(comp.sum())
        if area / comp.size < MIN_FILL:
            continue                       # hollow ring, not a solid engraving block
        if area > best_area:
            best_area = area
            best = [sl[1].start / PW, sl[0].start / PH, sl[1].stop / PW, sl[0].stop / PH]
    if best is None:
        return None
    x0, y0, x1, y1 = best
    return [max(0.0, round(x0 - MARGIN, 3)), max(0.0, round(y0 - MARGIN, 3)),
            min(1.0, round(x1 + MARGIN, 3)), min(1.0, round(y1 + MARGIN, 3))]


def strips_outside(frame):
    """Four flat rects covering everything outside the pictorial frame."""
    x0, y0, x1, y1 = frame
    return [[0.0, 0.0, 1.0, y0],       # above (motto, running head, page number)
            [0.0, y1, 1.0, 1.0],       # below (epigram, signature marks)
            [0.0, y0, x0, y1],         # left  (facing-page staves, spine)
            [x1, y0, 1.0, y1]]         # right (fore-edge)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emblem", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    layers = cov.load_layers()
    regions = cov.load_regions()
    nums = [args.emblem] if args.emblem is not None else sorted(layers)

    declared, skipped = 0, []
    for n in nums:
        if not cov.plate_path(n).exists():
            continue
        thr = cov.budget_for(regions, n)["ink_threshold"]
        frame = detect_frame(n, thr)
        if frame == "crop":
            continue                      # picture-crop plate: all pictorial, nothing to declare
        if frame is None:
            skipped.append(n)
            print(f"  emblem-{n:02d}: no plausible pictorial frame — left undeclared")
            continue
        declared += 1
        w, h = frame[2] - frame[0], frame[3] - frame[1]
        print(f"  emblem-{n:02d}: frame x[{frame[0]:.2f}..{frame[2]:.2f}] "
              f"y[{frame[1]:.2f}..{frame[3]:.2f}]  ({w:.2f}x{h:.2f})")
        if not args.dry_run:
            emb = regions.setdefault("emblems", {}).setdefault(str(n), {})
            emb["flat"] = strips_outside(frame)

    if not args.dry_run:
        cov.REGIONS.write_text(json.dumps(regions, indent=1), encoding="utf-8")
        print(f"\ndeclared page furniture for {declared} emblems -> {cov.REGIONS.name}")
    if skipped:
        print(f"undeclared (inspect by hand): {skipped}")


if __name__ == "__main__":
    main()
