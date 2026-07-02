# Papercraft Extraction Style Guide

*How to cut an* Atalanta Fugiens *plate into paper layers so the whole engraving is
realized — not just the few biggest blobs.*

This guide governs what becomes a cutout card, what stays flat on the backing, and
how we **measure and enforce** that no part of the emblem goes unused. It exists
because the current extraction (`scripts/build_layers.py`) keeps only the 10 largest
segmented parts per plate, ranked by pixel count — so most of each engraving is left
stranded flat. The audit below quantifies it: **mean ink coverage is 22.8%**. Three
quarters of the average plate is not participating in the pop-up.

---

## 1. The governing principle — *full pictorial realization*

> A papercraft realization of an emblem should tile its **entire pictorial scene**
> into stacked paper layers. The backing plate is a **registration surface**, not a
> hiding place for un-extracted content.

If a viewer in `blank` backing mode (no plate behind the cards) would see holes where
engraving used to be, those holes are **extraction debt**. The ideal is a partition:
the union of all cutouts, projected onto the plate, covers the picture with small,
deliberate gaps only where the paper genuinely has none (true empty paper).

Corollary — **the background is a layer too.** After the foreground figures are lifted
out, the residual scene (sky, ground, water, distant landscape, framing) is not
nothing; it is the back-most card(s). Extract it. A pop-up whose "background" is only
the flat plate has skipped its largest layer.

`scripts/build_backdrops.py` makes this concrete: it generates one **residual
back-sheet** per emblem (`_backdrop.png`, flagged `role:"backdrop"`) carrying all the
scene ink the figures don't, with the figure silhouettes punched out as holes the
figure cards drop into. It guarantees *completeness* — but a backdrop is the floor,
not the goal. A plate whose only layer is its backdrop is un-decomposed; the
`figure_coverage` metric (§5.4) exists precisely to keep that honest. Genuine work
means lifting real figures/objects/structures into their own depth-sorted cards.

---

## 2. What becomes a card vs. what stays flat

**Cut into cards (pictorial content):**

| Class        | Examples                                              | Typical depth band |
|--------------|-------------------------------------------------------|--------------------|
| sky / clouds | cloud banks, rays, celestial bodies                   | 0.0 – 0.15 (back)  |
| landscape    | hills, water, ground plane, distant town silhouette   | 0.15 – 0.35        |
| architecture | buildings, walls, furnaces, arches, plinths           | 0.25 – 0.5         |
| plants       | trees, foliage clumps, shrubs                          | 0.3 – 0.55         |
| objects      | vessels, tools, apples, attributes                     | 0.4 – 0.7          |
| animals      | birds, beasts, the lion/eagle/dragon                   | 0.5 – 0.8          |
| figures      | Atalanta, Hippomenes, the alchemist, allegories        | 0.6 – 1.0 (front)  |

Every distinct pictorial element in these classes should be represented by at least
one card, down to the smallest legible motif. Prefer **one card per readable element**
over one card per "big region."

**Left flat on the backing (declare in the ledger, §5):**

- The **motto banner** (Latin title text at the top of full-page plates).
- The **epigram** (the Latin distich / verse block).
- The **plate border / frame** and engraver's imprint lines.
- The **title cartouche** on the frontispiece (emblem 00).

Text and frame are *backing*, not missing cutouts. Declaring a region flat in
`data/coverage_regions.json` is you certifying that on the record — it is then excluded
from the coverage denominator and the gap search. Everything not declared flat is
treated as pictorial content the extraction owes a card.

---

## 3. Cut quality

- **Silhouette, not rectangle.** The card's alpha is the figure's true outline. (The
  renderer already relies on this for shadows via `customDepthMaterial`.)
- **Margin.** Keep the ~3.5% cream paper margin the renderer adds; the cut mask itself
  should be tight to the ink with a 1–2 px feather, no clipped limbs.
- **No orphan speckle.** Drop disconnected stray pixels < ~0.05% of the card. A cutout
  should be one coherent piece (or a deliberately grouped motif), not confetti.
- **Don't split a readable figure across cards** unless depth genuinely differs (an arm
  reaching forward may warrant its own card; a figure's own torso should not be diced).
- **Occlusion seams.** Where a front figure overlaps a back one, the back card keeps the
  occluded area (it will be hidden) — cut the back piece whole, let the front sit over
  it. This is legitimate overlap; see §4.

---

## 4. Overlap discipline

Coverage measures whether ink is realized; **overlap** measures whether we did it
redundantly. Two cards claiming the same ink (`overlap_frac` high, blue in the overlay)
usually means duplicate extractions or a figure diced without depth reason.

- Overlap for **occlusion** is fine (front over back).
- Overlap from **duplicate cutouts** of the same element is not — pick one.
- Rule of thumb: `overlap_frac` (overlapping / covered) should stay under ~0.25 unless
  the scene is genuinely deeply layered. Emblem 33 (88% coverage but heavily blue) is
  the cautionary case: high coverage achieved by stacking near-duplicates.

---

## 5. The measurement & enforcement system

Three scripts under `scripts/`, sharing `coverage_lib.py`. They reconstruct each card's
placement in the renderer's own normalized `[0,1]²` space (plate stretched to fill,
card at `(cx,cy)` sized `(nw,nh)` — identical to `js/papercraft.js`), so what they
measure is what the viewer sees.

### 5.1 Audit — see the debt
```
python scripts/audit_coverage.py            # all emblems + overlays
python scripts/audit_coverage.py --emblem 32
python scripts/audit_coverage.py --no-images # metrics only
```
Writes:
- `reports/coverage.json` — full metrics + ranked gap list per emblem.
- `reports/coverage.md` — summary table, grade distribution, worst offenders.
- `reports/coverage/emblem-NN.png` — the diagnostic overlay:
  **green** = ink under a card · **red** = ink stranded flat (the debt) ·
  **blue** = overlap · **grey** = declared-flat ink.

Read the red. Each red blob is a candidate missing cutout; its centroid and bbox are in
`coverage.json` under `gaps`.

### 5.2 Test — gate the debt
```
python scripts/test_coverage.py             # exits nonzero on any failure
python scripts/test_coverage.py --emblem 32
python scripts/test_coverage.py -v          # show passes too
```
Per emblem it asserts, against the budget:
- `coverage ≥ min_coverage` — enough ink realized as paper.
- `largest_gap ≤ max_gap_frac` — no single pictorial region left flat.
- every figure card's `registration ≥ min_registration` — its own engraved lines land
  on the plate's ink, so it isn't mis-placed (robust to line-art cutouts).

Run it after every re-extraction; wire it into CI so coverage can't silently regress.

### 5.3 Ledger — record judicious decisions
`data/coverage_regions.json` holds the budget defaults and per-emblem overrides:
```jsonc
{
  "defaults": { "min_coverage": 0.85, "max_gap_frac": 0.045, "min_registration": 0.20 },
  "emblems": {
    "0": { "flat": [[0.30, 0.10, 0.70, 0.72]], "min_coverage": 0.5 }
  }
}
```
`flat` rectangles are the intentional-backing declarations from §2. Budget keys can be
tightened or relaxed per emblem when a plate justifies it (e.g. a genuinely sparse
scene). The file is the audit trail of every "this is backing, not a gap" call.

### 5.4 Metrics glossary

| metric | meaning |
|--------|---------|
| `coverage` | **completeness** — fraction of engraved (non-flat) ink under *any* card (backdrop included). Near 100% once backdrops exist |
| `figure_coverage` | **decomposition** — fraction of ink under a *non-backdrop* card. The real quality signal; a backdrop-only plate scores ~0 here |
| `grade` | on `coverage`: A ≥85% · B ≥72% · C ≥58% · D ≥40% · F below |
| `largest_gap` | biggest single uncovered-ink blob, as a fraction of the plate |
| `gaps[]` | ranked uncovered-ink regions, each with `area_frac`, `bbox`, `centroid` |
| `overlap_frac` | overlapping / figure-covered — redundancy among figure cards, backdrop excluded (§4) |
| `registration` (per card) | fraction of the card's *own* engraved lines landing on plate ink; low = mis-placed or junk. Robust to line-art cutouts (unlike raw alpha-on-ink) |
| `n_stranded` | figure cards below `min_registration` (backdrops are exempt) |
| `has_backdrop` / `n_figures` | whether a residual back-sheet exists, and how many real cards sit in front |

Budget keys `min_coverage` (completeness floor) and `min_figure_coverage` (decomposition
floor) gate the two independently, so completeness-by-backdrop can't paper over thin
figure extraction.

---

## 6. Workflow to close the debt

1. `python scripts/audit_coverage.py` — regenerate reports + overlays.
2. Open `reports/coverage.md`; work the worst-offenders list top-down.
3. For each red region in `reports/coverage/emblem-NN.png`:
   - **pictorial?** → extract a new cutout for it (new figure segmentation, or split an
     over-large region), add it to `data/layers.json` with a depth from §2's table.
   - **text / frame?** → add a `flat` rectangle for it in `data/coverage_regions.json`.
4. `python scripts/test_coverage.py --emblem NN` until it passes.
5. Verify in the viewer (`?emblem=NN`) that the new cards pop and shadow correctly.
6. Commit reports so coverage changes are reviewable in the diff.

---

## 7. Naming & manifest conventions

- Cutout files: `images/cutouts/emblem-NN/<slug>.png`, `<slug>` lower-snake of the motif
  (`distillation_vessel`, `person`, `crown`). Disambiguate siblings with `_02`, `_03`.
- Manifest entry (`data/layers.json`): `file, label, category, cx, cy, nw, nh, depth`.
  `cx,cy` = normalized center, `nw,nh` = normalized bbox size, `depth` 0 (back) → 1
  (front). Keep layers sorted back-to-front by `depth`.
- `category` must be one of §2's classes (drives the depth heuristic and this guide's
  bands).

---

## 8. Current baseline (2026-07-01)

- **Before backdrops:** mean coverage 22.8% · grades A 2, B 1, C 1, D 8, F 39. Three
  quarters of the average plate was stranded flat.
- **After `build_backdrops.py`:** mean **coverage 95.6%** (completeness closed) but mean
  **figure_coverage still 22.8%** — 20 plates are backdrop-only (`figure_coverage <10%`).

So completeness is done; the open work is *decomposition*. The target is to raise
`figure_coverage` — lift real figures/objects/structures out of the backdrop into their
own depth-sorted cards — starting with the 20 backdrop-only plates. Best-decomposed
today: 33 (88%), 09 (74%), 05 (66%).

**Gate status:** 45/51 pass. The 6 failures are genuinely mis-placed cutouts
(`registration <20%`): the source figure coordinates don't match these locally-cropped
plates, so the cutout lands off the engraving (e.g. emblem-01's serpent floats on the
page margin). These are real registration debt, not metric noise — fix by re-deriving
the cutout's `cx,cy,nw,nh` against the local plate, or drop the junk cutout. The gate
stays red until they're resolved (that's the system working, not a false alarm):
01, 02, 04, 05, 12, 25.
