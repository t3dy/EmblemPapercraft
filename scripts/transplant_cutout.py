#!/usr/bin/env python
"""
transplant_cutout.py — borrow a cut SHAPE from an EmblemPrintShop extraction,
but take the paper from our own plate.

The 743 labelled extractions in C:\\Dev\\EmblemPrintShop were segmented on a
different scan (uncoloured, picture-only), so pasting their PIXELS onto our
hand-tinted plates mis-registers — and per the styleguide, re-placing them by
auto-correlation is unreliable. This tool transplants only the MASK: it detects
the pictorial frame on both scans (the engraved border box — the one landmark
both share by construction), maps the mask frame-to-frame, and cuts the RGBA
from OUR colour plate under the mapped silhouette. cx/cy come from where the
pixels land, so registration is ~1.0 by construction, like cut_region.py.

Run:
  python scripts/transplant_cutout.py --emblem 1 --name boreas --depth 0.75 \
      --mask C:/Dev/EmblemPrintShop/assets/extracted/emblem-01_figure_wind_transparent.png
Then rebuild that emblem's backdrop and re-run the audit.
"""
import argparse, json
import numpy as np
from PIL import Image
from scipy import ndimage

import coverage_lib as cov

CLOSE_IT = 6


def solid_bbox(gray, thr, portrait_furniture):
    """Pixel bbox (x0,y0,x1,y1) of the pictorial block.

    portrait_furniture=True (our full-page scans): require a plausibly framed
    block, as in declare_page_furniture. False (picture-only scans): just the
    largest solid component — the picture itself."""
    PH, PW = gray.shape
    ink = gray < thr
    st = ndimage.generate_binary_structure(2, 2)
    sheet = ndimage.binary_fill_holes(ndimage.binary_closing(ink, structure=st, iterations=CLOSE_IT))
    lbl, nc = ndimage.label(sheet)
    if not nc:
        raise SystemExit("no ink block found")
    best, best_area = None, 0
    for i, sl in enumerate(ndimage.find_objects(lbl), start=1):
        h, w = (sl[0].stop - sl[0].start) / PH, (sl[1].stop - sl[1].start) / PW
        if portrait_furniture and not (0.28 <= w <= 0.92 and 0.28 <= h <= 0.92):
            continue
        area = int((lbl[sl] == i).sum())
        if area > best_area:
            best_area, best = area, (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)
    if best is None:
        raise SystemExit("no plausible pictorial frame")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emblem", type=int, required=True)
    ap.add_argument("--mask", required=True, help="RGBA extraction png (alpha = figure mask)")
    ap.add_argument("--name", required=True)
    ap.add_argument("--depth", type=float, default=0.6)
    ap.add_argument("--label", default=None)
    ap.add_argument("--category", default="figure")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    n = args.emblem
    thr = cov.budget_for(cov.load_regions(), n)["ink_threshold"]

    src = np.asarray(Image.open(args.mask).convert("RGBA"))
    src_gray = np.asarray(Image.fromarray(src[:, :, :3]).convert("L"), dtype=np.float32) / 255.0
    src_mask = src[:, :, 3] > 128
    sx0, sy0, sx1, sy1 = solid_bbox(src_gray, thr, portrait_furniture=False)

    im = Image.open(cov.plate_path(n))
    rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
    gray = np.asarray(im.convert("L"), dtype=np.float32) / 255.0
    PH, PW = gray.shape
    dx0, dy0, dx1, dy1 = solid_bbox(gray, thr, portrait_furniture=PH > PW)

    # frame-to-frame affine: crop the mask to the source frame, scale to ours
    mcrop = Image.fromarray((src_mask[sy0:sy1, sx0:sx1] * 255).astype("uint8"))
    mapped = np.asarray(mcrop.resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR)) > 128
    full = np.zeros((PH, PW), dtype=bool)
    full[dy0:dy1, dx0:dx1] = mapped
    st = ndimage.generate_binary_structure(2, 2)
    full = ndimage.binary_closing(full, structure=st, iterations=3)   # smooth scissor line

    # drop detached specks (segmentation debris) — keep components >= 3% of the largest
    lbl, nc = ndimage.label(full, structure=st)
    if nc > 1:
        sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, nc + 1))
        full = np.isin(lbl, [i + 1 for i, s in enumerate(sizes) if s >= 0.03 * sizes.max()])

    ys, xs = np.where(full)
    ty0, ty1, tx0, tx1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    alpha = (full[ty0:ty1, tx0:tx1] * 255).astype(np.uint8)
    rgba = np.dstack([rgb[ty0:ty1, tx0:tx1], alpha])

    out = cov.CUTOUTS / f"emblem-{n:02d}" / f"{args.name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    cx, cy = round((tx0 + tx1) / 2 / PW, 4), round((ty0 + ty1) / 2 / PH, 4)
    nw, nh = round((tx1 - tx0) / PW, 4), round((ty1 - ty0) / PH, 4)
    print(f"  wrote {out.relative_to(cov.ROOT)}  centre=({cx}, {cy}) size=({nw}x{nh})")

    if args.dry_run:
        print("  dry run — manifest not touched")
        return
    manifest = json.loads(cov.LAYERS.read_text(encoding="utf-8"))
    emb = next(e for e in manifest if e["number"] == n)
    rel = f"emblem-{n:02d}/{args.name}.png"
    emb["layers"] = [L for L in emb["layers"] if L["file"] != rel]
    emb["layers"].append({
        "file": rel, "label": args.label or args.name.replace("_", " "),
        "category": args.category, "cx": cx, "cy": cy, "nw": nw, "nh": nh,
        "depth": args.depth,
    })
    cov.LAYERS.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"  manifest updated — now:  python scripts/build_backdrops.py --emblem {n}")


if __name__ == "__main__":
    main()
