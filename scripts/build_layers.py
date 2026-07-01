#!/usr/bin/env python
"""
build_diorama.py — prepare layered 2.5-D diorama assets for HPin3D.

Source: EmblemPrintShop's per-emblem cutouts (transparent PNGs + summary.json).
Output:
  images/cutouts/emblem-NN/<slug>.png   web-optimized, bbox-cropped figure cutouts
  src/data/diorama.json                  per-emblem, depth-ordered layer manifest

Depth (z-order) is INFERRED — the source has no Z metadata. Heuristic: vertical
position in the plate (higher up = further back) + a per-category bias
(sky/landscape/architecture recede; figures/animals come forward) + a mild
"big things sit behind" area term. Output `depth` is 0 (back) .. 1 (front).
"""
import json, re, sys
from pathlib import Path
from PIL import Image

SRC   = Path(r"C:\Dev\EmblemPrintShop\assets\extracted_all")
HP    = Path(r"C:\Dev\HPin3D")
OUT_IMG = HP / "images" / "cutouts"
OUT_MANIFEST = HP / "src" / "data" / "diorama.json"

MAX_DIM        = 340     # px, longest side of each web cutout
MAX_PARTS      = 10      # keep the N largest parts per emblem
MIN_AREA_FRAC  = 0.0014  # drop parts smaller than this fraction of the plate
MIN_MASK_PX    = 1400    # ...and tiny masks

# category → how far back it sits (subtracted from the vertical-position depth)
CAT_BIAS = {
    "sky": 0.42, "landscape": 0.34, "architecture": 0.24,
    "plants": 0.05, "objects": -0.10, "animals": -0.16, "figures": -0.20,
}

def slug(stem: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", stem.lower().replace("_transparent", ""))

def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))

def main():
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    emblems = []
    total_parts = 0

    for n in range(0, 51):
        sdir = SRC / f"emblem-{n:02d}"
        summ = sdir / "summary.json"
        if not summ.exists():
            print(f"  emblem-{n:02d}: no summary.json, skipping")
            continue
        data = json.loads(summ.read_text(encoding="utf-8"))
        parts = [p for p in data.get("individual", []) if p.get("tight_bbox")]

        # source canvas size (read once from the first transparent png)
        if not parts:
            continue
        with Image.open(parts[0]["transparent_png"]) as im0:
            W, H = im0.size

        # filter + rank by mask size, keep the biggest few
        parts = [p for p in parts
                 if p.get("mask_pixel_count", 0) >= MIN_MASK_PX
                 and (p["tight_bbox"][2] * p["tight_bbox"][3]) / (W * H) >= MIN_AREA_FRAC]
        parts.sort(key=lambda p: p.get("mask_pixel_count", 0), reverse=True)
        parts = parts[:MAX_PARTS]
        if not parts:
            continue

        edir = OUT_IMG / f"emblem-{n:02d}"
        edir.mkdir(parents=True, exist_ok=True)
        layers = []
        for p in parts:
            x, y, w, h = p["tight_bbox"]
            if w <= 0 or h <= 0:
                continue
            png = Path(p["transparent_png"])
            if not png.exists():
                continue
            with Image.open(png) as im:
                im = im.convert("RGBA").crop((x, y, x + w, y + h))
                scale = MAX_DIM / max(im.size)
                if scale < 1:
                    im = im.resize((max(1, round(im.width * scale)),
                                    max(1, round(im.height * scale))), Image.LANCZOS)
                name = slug(png.stem) + ".png"
                im.save(edir / name, optimize=True)

            cx, cy = (x + w / 2) / W, (y + h / 2) / H
            nw, nh = w / W, h / H
            cat = (p.get("category") or "objects").lower()
            depth = clamp(cy - CAT_BIAS.get(cat, 0.0) - 0.15 * (nw * nh))
            layers.append({
                "file": f"emblem-{n:02d}/{name}",
                "label": p.get("label", ""), "category": cat,
                "cx": round(cx, 4), "cy": round(cy, 4),
                "nw": round(nw, 4), "nh": round(nh, 4),
                "score": round(p.get("score", 0), 3),
                "depth": round(depth, 4),
            })

        layers.sort(key=lambda L: L["depth"])  # back -> front
        emblems.append({"number": n, "source_w": W, "source_h": H, "layers": layers})
        total_parts += len(layers)
        print(f"  emblem-{n:02d}: {len(layers)} layers  ({W}x{H})")

    OUT_MANIFEST.write_text(json.dumps(emblems, indent=1), encoding="utf-8")
    print(f"\n{len(emblems)} emblems, {total_parts} cutout layers")
    print(f"manifest: {OUT_MANIFEST}")

if __name__ == "__main__":
    main()
