# EmblemPapercraft — Project Instructions

## What this is

A static Three.js site that renders *Atalanta Fugiens* emblems as **layered paper
pop-ups**: extracted figure cutouts stacked as flat paper cards in front of the
full plate, lit so each card casts its cut shape as a shadow. Sibling to
`C:\Dev\HPin3D` (which renders the same plates as carved *reliefs*).

## Layout

- `index.html` — viewer shell (UI, importmap).
- `js/papercraft.js` — the renderer (scene, shadow-casting paper cards, nav).
- `data/emblems.json` — emblem metadata (copied from HPin3D).
- `data/layers.json` — per-emblem cutout manifest (`cx,cy,nw,nh,depth,file`).
- `images/emblems/` — 51 full plates (backing pages).
- `images/cutouts/emblem-NN/` — 143 transparent-PNG figure cutouts.
- `scripts/build_layers.py` — regenerates cutouts + `layers.json` from the
  sibling `EmblemPrintShop` extraction.
- `scripts/coverage_lib.py` + `audit_coverage.py` + `test_coverage.py` — the
  coverage measurement/enforcement system (see below).
- `data/coverage_regions.json` — budget + declared-flat-region ledger.
- `docs/PAPERCRAFT_EXTRACTION_STYLEGUIDE.md` — how to cut a plate judiciously.

## The core technique

Papercraft depth comes from **shadows**, not geometry. Every cutout mesh gets a
`customDepthMaterial = MeshDepthMaterial({ map, alphaTest, depthPacking:
RGBADepthPacking })` so its shadow is the cut silhouette. `renderer.shadowMap`
must stay enabled (PCFSoft). If shadows look like rectangles, the
`customDepthMaterial` is missing.

## Conventions

- No build step. Three.js r168 from jsDelivr via `importmap`. Bump the `?v=` on
  `js/papercraft.js` in `index.html` when you change the module (cache-bust).
- Preview server: `python -m http.server 3458` (see `.claude/launch.json`).
- Assets are relative paths (`images/…`, `data/…`) so it works on any static host.

## Coverage / extraction quality

The papercraft should realize the **whole pictorial scene**, not a few big blobs.
`build_layers.py` currently keeps only the 10 largest parts, so most engraving is
left flat — baseline **mean coverage 22.8%**. Enforce better cuts with the coverage
system (all in normalized `[0,1]²` space matching the renderer):

- `python scripts/audit_coverage.py` → `reports/coverage.{json,md}` + per-emblem
  overlays (`reports/coverage/emblem-NN.png`: green=covered ink, **red=stranded ink
  = extraction debt**, blue=overlap).
- `python scripts/test_coverage.py` → gate (nonzero exit) on coverage / gap / stranded
  budgets. Run after any re-extraction.
- Declare text/border as backing in `data/coverage_regions.json` (`flat` rects); it's
  the audit trail of "this is backing, not a missing cutout."

Full rules in `docs/PAPERCRAFT_EXTRACTION_STYLEGUIDE.md`.

## Verify

Prefer render-and-screenshot. If the screenshot tool is unavailable, verify
structurally (data loads, cutouts fetch `200`, zero console errors) and disclose
that the visual is unconfirmed — never claim the look is right unseen.

## Cross-project

Cutouts + manifest originate from `C:\Dev\EmblemPrintShop` (743 labelled figure
extractions). Kept as a self-contained copy here — do not read siblings at
runtime.
