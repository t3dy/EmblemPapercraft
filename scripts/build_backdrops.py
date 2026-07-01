#!/usr/bin/env python
"""
build_backdrops.py — generate the residual "back-sheet" layer for every emblem.

The style guide's rule 'the background is a layer too' made concrete. The source
segmentation only lifts ~3 figures per plate, leaving most of the engraving stranded
flat (mean coverage 22.8%). This closes the gap without inventing content: for each
emblem it builds ONE back-sheet card that carries all the scene EXCEPT the foreground
figures, which are punched out as holes (so the figure cards drop into them). The
scene now reads as a true diorama — a printed backdrop with figures popping in front —
and coverage becomes complete by construction.

The backdrop is flagged role="backdrop" in data/layers.json; coverage_lib counts it
toward completeness but excludes it from overlap and from the figure-share metric, so
it can't disguise an un-decomposed plate as judiciously cut.

Output per emblem:
  images/cutouts/emblem-NN/_backdrop.png   RGBA: RGB=plate engraving, A=residual sheet
  data/layers.json                          a back-most role="backdrop" layer (idempotent)

Run:
  python scripts/build_backdrops.py               # all emblems
  python scripts/build_backdrops.py --emblem 32
"""
import argparse, json
import numpy as np
from PIL import Image
from scipy import ndimage

import coverage_lib as cov

BACKDROP_NAME = "_backdrop.png"
MAX_DIM   = 900     # cap backdrop resolution (longest side)
CLOSE_IT  = 6       # morphological closing to fuse engraving into a solid sheet
DILATE_IT = 2       # grow foreground before punching holes (kills ink halos at edges)
MIN_COMP  = 0.01    # drop sheet components smaller than this fraction of the plate


def residual_sheet(n, layers_by_num, thr):
    """(plate_uint8, residual_mask) — the scene sheet minus the foreground figures."""
    im = Image.open(cov.plate_path(n)).convert("L")
    gray = np.asarray(im, dtype=np.uint8)
    PH, PW = gray.shape
    ink = (gray.astype(np.float32) / 255.0) < thr

    fg = np.zeros((PH, PW), dtype=bool)
    for L in layers_by_num.get(n, {}).get("layers", []):
        if L.get("role") == "backdrop":
            continue
        placed, _ = cov.place_layer(L, PW, PH)
        if placed is not None:
            fg |= placed

    st = ndimage.generate_binary_structure(2, 2)
    sheet = ndimage.binary_fill_holes(ndimage.binary_closing(ink, structure=st, iterations=CLOSE_IT))
    lbl, nc = ndimage.label(sheet)
    if nc:
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, nc + 1))
        sheet = np.isin(lbl, [1 + i for i, s in enumerate(sizes) if s > MIN_COMP * PW * PH])
    residual = sheet & ~ndimage.binary_dilation(fg, iterations=DILATE_IT)
    return gray, residual


def make_backdrop_png(gray, residual, out_path):
    PH, PW = gray.shape
    rgba = np.dstack([gray, gray, gray, (residual * 255).astype(np.uint8)])
    img = Image.fromarray(rgba, "RGBA")
    scale = MAX_DIM / max(img.size)
    if scale < 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emblem", type=int, default=None)
    args = ap.parse_args()

    manifest = json.loads(cov.LAYERS.read_text(encoding="utf-8"))
    by_num = {e["number"]: e for e in manifest}
    regions = cov.load_regions()
    nums = [args.emblem] if args.emblem is not None else sorted(by_num)

    made = 0
    for n in nums:
        if not cov.plate_path(n).exists():
            continue
        thr = cov.budget_for(regions, n)["ink_threshold"]
        gray, residual = residual_sheet(n, by_num, thr)
        cov_frac = float((residual).mean())
        out = cov.CUTOUTS / f"emblem-{n:02d}" / BACKDROP_NAME
        make_backdrop_png(gray, residual, out)

        emb = by_num[n]
        # idempotent: drop any prior backdrop, then insert a fresh one at the back.
        emb["layers"] = [L for L in emb["layers"] if L.get("role") != "backdrop"]
        emb["layers"].insert(0, {
            "file": f"emblem-{n:02d}/{BACKDROP_NAME}", "role": "backdrop",
            "label": "backdrop", "category": "landscape",
            "cx": 0.5, "cy": 0.5, "nw": 1.0, "nh": 1.0, "depth": 0.0,
        })
        made += 1
        print(f"  emblem-{n:02d}: backdrop sheet covers {cov_frac:.0%} of plate")

    cov.LAYERS.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"\n{made} backdrops written · updated data/layers.json")


if __name__ == "__main__":
    main()
