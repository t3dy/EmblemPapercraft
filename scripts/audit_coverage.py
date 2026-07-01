#!/usr/bin/env python
"""
audit_coverage.py — report how judiciously each emblem is cut into papercraft layers.

For every emblem it measures ink coverage (see coverage_lib) and writes:
  reports/coverage.json          full machine-readable metrics + gap lists
  reports/coverage.md            human summary table + worst-offender rundown
  reports/coverage/emblem-NN.png diagnostic overlay (green covered / red stranded ink)

Run:
  python scripts/audit_coverage.py                 # all emblems, with overlays
  python scripts/audit_coverage.py --emblem 32     # one emblem
  python scripts/audit_coverage.py --no-images     # metrics only, faster

The red regions in the overlays are the extraction debt: engraving with no paper
card in front of it. Chase them down per the extraction style guide, or declare
them intentionally-flat in data/coverage_regions.json (motto/epigram/border).
"""
import argparse, json, sys
from pathlib import Path

import coverage_lib as cov

REPORTS = cov.ROOT / "reports"
IMGDIR  = REPORTS / "coverage"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emblem", type=int, default=None, help="audit a single emblem number")
    ap.add_argument("--no-images", action="store_true", help="skip overlay PNGs")
    args = ap.parse_args()

    layers = cov.load_layers()
    regions = cov.load_regions()
    nums = [args.emblem] if args.emblem is not None else sorted(layers)

    REPORTS.mkdir(exist_ok=True)
    if not args.no_images:
        IMGDIR.mkdir(parents=True, exist_ok=True)

    results = []
    for n in nums:
        if not cov.plate_path(n).exists():
            print(f"  emblem-{n:02d}: no plate, skipping")
            continue
        res = cov.analyze(n, layers, regions)
        if not args.no_images:
            cov.render_overlay(res).save(IMGDIR / f"emblem-{n:02d}.png")
        results.append(res)
        g = cov.grade(res["coverage"])
        flag = "  <-- low" if res["coverage"] < res["budget"]["min_coverage"] else ""
        print(f"  emblem-{n:02d}  [{g}]  coverage={res['coverage']:6.1%}  "
              f"cards={res['n_cards']:2d}  gaps={res['n_gaps']:2d}  "
              f"largest_gap={res['largest_gap']:5.1%}  stranded={res['n_stranded']}{flag}")

    # ── machine-readable dump ────────────────────────────────────────────────
    dump = [cov.strip_masks(r) for r in results]
    (REPORTS / "coverage.json").write_text(json.dumps(dump, indent=1), encoding="utf-8")

    # ── human summary ────────────────────────────────────────────────────────
    if results:
        avg = sum(r["coverage"] for r in results) / len(results)
        worst = sorted(results, key=lambda r: r["coverage"])[:12]
        lines = [
            "# Papercraft coverage audit",
            "",
            f"{len(results)} emblems · mean ink coverage **{avg:.1%}** · "
            f"grade distribution "
            + ", ".join(f"{g}:{sum(1 for r in results if cov.grade(r['coverage'])==g)}"
                        for g in "ABCDF"),
            "",
            "Coverage = fraction of engraved (non-flat) ink with a paper card in front of it.",
            "Red areas in `reports/coverage/emblem-NN.png` are engraving left flat on the backing.",
            "",
            "## Worst offenders (chase these first)",
            "",
            "| emblem | grade | coverage | cards | largest gap | gap centroid |",
            "|-------:|:-----:|---------:|------:|------------:|:-------------|",
        ]
        for r in worst:
            gc = r["gaps"][0]["centroid"] if r["gaps"] else ["–", "–"]
            lines.append(f"| {r['number']:02d} | {cov.grade(r['coverage'])} | "
                         f"{r['coverage']:.1%} | {r['n_cards']} | {r['largest_gap']:.1%} | "
                         f"({gc[0]}, {gc[1]}) |")
        lines += ["", "## All emblems", "",
                  "| emblem | grade | coverage | cards | gaps | stranded | flat regions |",
                  "|-------:|:-----:|---------:|------:|-----:|---------:|-------------:|"]
        for r in sorted(results, key=lambda r: r["number"]):
            lines.append(f"| {r['number']:02d} | {cov.grade(r['coverage'])} | "
                         f"{r['coverage']:.1%} | {r['n_cards']} | {r['n_gaps']} | "
                         f"{r['n_stranded']} | {r['n_flat']} |")
        (REPORTS / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        print(f"\n{len(results)} emblems · mean coverage {avg:.1%}")
        print(f"wrote reports/coverage.json, reports/coverage.md"
              + ("" if args.no_images else ", reports/coverage/*.png"))


if __name__ == "__main__":
    main()
