# Emblem Papercraft

Layered **paper pop-up** renderings of the fifty-one emblems of Michael Maier's
*Atalanta Fugiens* (Frankfurt, 1617). Each emblem's engraved figures are cut out
and stacked as flat paper cards in front of the full plate, then lit so every
card throws its own cut shape as a **shadow** onto the layers behind it — the
image reads as three-dimensional while keeping the original woodcut linework.

A sibling to [HPin3D / EmblemsIn3d](https://github.com/t3dy/EmblemsIn3d), which
carves the same plates into *reliefs*; this project renders them as *papercraft*.

## Run it

```bash
python -m http.server 3458
# then open http://localhost:3458/
```

Drag to orbit, scroll to zoom, ← → to change emblem, and use the **pop depth**
slider to exaggerate or flatten the layering.

## How it works

- **Backing page** — the full emblem plate (`images/emblems/emblem-NN.jpg`) as a
  matte paper plane that *receives* shadows.
- **Paper cards** — each extracted figure cutout (`images/cutouts/…`, transparent
  PNG) becomes a `MeshStandardMaterial` plane with `alphaTest`, positioned at its
  source location and lifted forward by an inferred depth.
- **The papercraft trick** — each card is given a `customDepthMaterial`
  (`MeshDepthMaterial` + `map` + `alphaTest`) so its *shadow* is the cut shape,
  not the bounding rectangle. A warm raking `DirectionalLight` with a soft shadow
  map casts those shapes onto the page and onto each other.

## Data

- `data/emblems.json` — emblem metadata (numeral, title) for the UI.
- `data/layers.json` — per-emblem, depth-ordered cutout manifest
  (`cx, cy, nw, nh, depth, file`), produced by `scripts/build_layers.py` from a
  computer-vision extraction of the plates. 33 emblems have ≥2 layers (a real
  pop-up); sparser plates show as a flat page.

## Tech

Three.js r168 via CDN importmap, no build step. `OrbitControls`, PCF soft shadow
maps, ACES tone mapping. Pure static site.

## Status

Prototype. Next: per-card paper thickness/curl, denuded backing pages (so cutouts
don't double their flat copy), a "fold-flat → pop-up" animation, and print-ready
net/tab export so the models can be built in real paper.
