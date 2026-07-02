#!/usr/bin/env python
"""
cut_region.py — cut a new figure card directly out of the plate, in place.

Phase 3/4 established that re-placing pre-cut cutouts by auto-correlation is
unreliable (see the styleguide). This tool sidesteps placement entirely: you name
a normalised bbox ON THE PLATE, it lifts the engraved silhouette inside that bbox
into a transparent-PNG card, and writes the manifest entry with cx/cy taken from
where the pixels actually came from. Registration is ~1.0 by construction — the
card's ink IS plate ink.

Silhouette = ink inside the bbox, morphologically closed and hole-filled (same
scale as the backdrop builder), small speck components dropped. Components are
kept only if they touch the bbox's central region, so a generous bbox doesn't
drag in unrelated background at the borders.

After cutting, REBUILD the emblem's backdrop (build_backdrops.py --emblem N) so
the back-sheet punches a hole where the new figure pops, then re-run the audit.

Run:
  python scripts/cut_region.py --emblem 1 --name boreas --bbox 0.40 0.22 0.66 0.62 --depth 0.8
  python scripts/cut_region.py ... --dry-run     # write a preview PNG only, no manifest change
"""
import argparse, json
import numpy as np
from PIL import Image
from scipy import ndimage

import coverage_lib as cov

CLOSE_IT = 6        # closing scale — matches build_backdrops.py
MIN_COMP = 0.005    # drop silhouette components smaller than this fraction of the crop
CORE     = 0.6      # components must touch the central CORE fraction of the bbox


def cut(n, bbox, thr):
    """(rgba_uint8_cropped, [cx, cy, nw, nh]) for the silhouette inside bbox."""
    im = Image.open(cov.plate_path(n))
    rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
    gray = np.asarray(im.convert("L"), dtype=np.float32) / 255.0
    PH, PW = gray.shape
    x0, y0 = int(bbox[0] * PW), int(bbox[1] * PH)
    x1, y1 = int(bbox[2] * PW), int(bbox[3] * PH)
    ink = gray[y0:y1, x0:x1] < thr

    st = ndimage.generate_binary_structure(2, 2)
    sil = ndimage.binary_fill_holes(ndimage.binary_closing(ink, structure=st, iterations=CLOSE_IT))
    lbl, nc = ndimage.label(sil)
    if not nc:
        raise SystemExit("no ink found in bbox")
    ch, cw = sil.shape
    cy0, cy1 = int(ch * (1 - CORE) / 2), int(ch * (1 + CORE) / 2)
    cx0, cx1 = int(cw * (1 - CORE) / 2), int(cw * (1 + CORE) / 2)
    keep = []
    for i, sl in enumerate(ndimage.find_objects(lbl), start=1):
        comp = lbl[sl] == i
        if comp.sum() < MIN_COMP * ch * cw:
            continue
        ys, xs = np.where(lbl == i)
        if (ys >= cy0).any() and (ys < cy1).any() and (xs >= cx0).any() and (xs < cx1).any():
            keep.append(i)
    if not keep:
        raise SystemExit("no silhouette component touches the bbox core — widen or move the bbox")
    sil = np.isin(lbl, keep)

    ys, xs = np.where(sil)
    ty0, ty1, tx0, tx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    alpha = (sil[ty0:ty1, tx0:tx1] * 255).astype(np.uint8)
    crop = rgb[y0 + ty0:y0 + ty1, x0 + tx0:x0 + tx1]
    rgba = np.dstack([crop, alpha])

    # manifest geometry: centre + size of the tight crop, in plate-normalised coords
    gx0, gy0 = x0 + tx0, y0 + ty0
    gx1, gy1 = x0 + tx1, y0 + ty1
    geom = [round((gx0 + gx1) / 2 / PW, 4), round((gy0 + gy1) / 2 / PH, 4),
            round((gx1 - gx0) / PW, 4), round((gy1 - gy0) / PH, 4)]
    return rgba, geom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emblem", type=int, required=True)
    ap.add_argument("--name", required=True, help="card slug -> images/cutouts/emblem-NN/<name>.png")
    ap.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--depth", type=float, default=0.6, help="pop depth 0..1 (renderer z)")
    ap.add_argument("--label", default=None)
    ap.add_argument("--category", default="figure")
    ap.add_argument("--dry-run", action="store_true", help="write the PNG, skip the manifest")
    args = ap.parse_args()

    n = args.emblem
    regions = cov.load_regions()
    thr = cov.budget_for(regions, n)["ink_threshold"]
    rgba, (cx, cy, nw, nh) = cut(n, args.bbox, thr)

    out = cov.CUTOUTS / f"emblem-{n:02d}" / f"{args.name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    print(f"  wrote {out.relative_to(cov.ROOT)}  centre=({cx}, {cy}) size=({nw}x{nh})")

    if args.dry_run:
        print("  dry run — manifest not touched")
        return

    manifest = json.loads(cov.LAYERS.read_text(encoding="utf-8"))
    emb = next(e for e in manifest if e["number"] == n)
    rel = f"emblem-{n:02d}/{args.name}.png"
    emb["layers"] = [L for L in emb["layers"] if L["file"] != rel]   # idempotent re-cut
    emb["layers"].append({
        "file": rel, "label": args.label or args.name.replace("_", " "),
        "category": args.category, "cx": cx, "cy": cy, "nw": nw, "nh": nh,
        "depth": args.depth,
    })
    cov.LAYERS.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"  manifest updated — now rebuild the backdrop:  "
          f"python scripts/build_backdrops.py --emblem {n}")


if __name__ == "__main__":
    main()
