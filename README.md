# Emblem Papercraft

Layered **paper pop-up** renderings of the fifty-one emblems of Michael Maier's
*Atalanta Fugiens* (Frankfurt, 1617). Each emblem's engraved figures are cut out
and stacked as flat paper cards in front of the full plate, then lit so every
card throws its own cut shape as a **shadow** onto the layers behind it — the
image reads as three-dimensional while keeping the original woodcut linework.

### ▶ [Open the live viewer](https://t3dy.github.io/EmblemPapercraft/) · [Browse all 51 in the gallery](https://t3dy.github.io/EmblemPapercraft/gallery.html)

Drag to orbit, scroll to zoom, ← → to change emblem, and use the **pop depth**
slider to exaggerate or flatten the layering. The gallery is a contact sheet of
every plate — hover a card for its motto, click to open it in the viewer.

## The *Atalanta Fugiens* family

This is one of several projects built from the same 1617 emblem book — different
media, one source engraving set:

| Project | What it does | Code | Live |
|---|---|---|---|
| **Emblem Papercraft** | this repo — plates as shadow-casting paper pop-ups | [GitHub](https://github.com/t3dy/EmblemPapercraft) | [site](https://t3dy.github.io/EmblemPapercraft/) |
| **Emblems in 3D** (HPin3D) | the sibling — same plates carved as walkable woodcut *reliefs* | [GitHub](https://github.com/t3dy/EmblemsIn3d) | [site](https://t3dy.github.io/EmblemsIn3d/) |
| **Emblem Roguelike** | a Dragon-Warrior-style RPG whose art is the extracted engravings | [GitHub](https://github.com/t3dy/EmblemRoguelike) | [site](https://t3dy.github.io/EmblemRoguelike/) |
| **Atalanta Claudiens** | DH site on H.M.E. de Jong's scholarship on the emblem book | [GitHub](https://github.com/t3dy/AtalantaClaudiens) | [site](https://t3dy.github.io/AtalantaClaudiens/) |
| **Emblem Print Shop** | the computer-vision pipeline that cut every figure used here | [GitHub](https://github.com/t3dy/EmblemPrintShop) | — |
| **Fugue Jukebox** | NES-style chiptune variations of Maier's 50 emblem fugues | [GitHub](https://github.com/t3dy/FugueJukebox) | — |

## Run it locally

```bash
python -m http.server 3458
# then open http://localhost:3458/
```

Assets are relative paths, so it works on any static host with no build step.

## How it works

Papercraft depth comes from **shadows**, not geometry:

- **Backing page** — the full emblem plate (`images/emblems/emblem-NN.jpg`) as a
  matte paper plane that *receives* shadows.
- **Paper cards** — each extracted figure cutout (`images/cutouts/…`, transparent
  PNG) becomes a `MeshStandardMaterial` plane with `alphaTest`, positioned at its
  source location and lifted forward by an inferred depth.
- **The papercraft trick** — each card is given a `customDepthMaterial`
  (`MeshDepthMaterial` + `map` + `alphaTest`) so its *shadow* is the cut shape,
  not the bounding rectangle. A warm raking `DirectionalLight` with a soft shadow
  map casts those shapes onto the page and onto each other.

## Data & coverage

- `data/emblems.json` — emblem metadata (numeral, title, motto) for the UI.
- `data/layers.json` — per-emblem, depth-ordered cutout manifest
  (`cx, cy, nw, nh, depth, file`).
- `data/coverage_regions.json` — the coverage budget + declared-backing ledger.

The goal is **full pictorial realization**: the papercraft should tile the whole
engraved scene into stacked layers, not lift a couple of big blobs. A coverage
system (`scripts/audit_coverage.py`, `scripts/test_coverage.py`) measures, in the
renderer's own normalized space, how much engraved ink is realized as paper and
flags what's stranded flat. Current state: **all 51 plates have real figure pops**,
mean ink coverage **96.5%**, mean figure-decomposition **41.6%**, gate 51/51.

New cards are cut *in place* off the plate (`scripts/cut_region.py`) so their
registration is correct by construction. See
`docs/PAPERCRAFT_EXTRACTION_STYLEGUIDE.md` for the full method.

## Tech

Three.js r168 via CDN importmap, no build step. `OrbitControls`, PCF soft shadow
maps, ACES tone mapping. Pure static site.

## Credits

Emblem engravings from Michael Maier, *Atalanta Fugiens* (1617). Figure cutouts
and manifest originate from the [Emblem Print Shop](https://github.com/t3dy/EmblemPrintShop)
computer-vision extraction. A sibling to [Emblems in 3D](https://github.com/t3dy/EmblemsIn3d),
which renders the same plates as carved reliefs.
