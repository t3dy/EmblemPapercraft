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

## Verify

Prefer render-and-screenshot. If the screenshot tool is unavailable, verify
structurally (data loads, cutouts fetch `200`, zero console errors) and disclose
that the visual is unconfirmed — never claim the look is right unseen.

## Cross-project

Cutouts + manifest originate from `C:\Dev\EmblemPrintShop` (743 labelled figure
extractions). Kept as a self-contained copy here — do not read siblings at
runtime.
