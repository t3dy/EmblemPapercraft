#!/usr/bin/env python
"""
test_coverage.py — enforce that the emblems are cut up judiciously.

A gate, not a report: it recomputes coverage and asserts each emblem meets its
budget (global defaults, overridable per-emblem in data/coverage_regions.json).
Fails the emblem — and exits nonzero — when the papercraft leaves too much of the
engraving stranded flat. Wire it into CI or run it after every re-extraction.

Checks per emblem:
  · coverage      >= min_coverage      (enough of the ink is realised as paper)
  · largest_gap   <= max_gap_frac      (no big pictorial region left flat)
  · every card's registration >= min_registration  (its own ink lands on plate ink; not mis-placed)

Run:
  python scripts/test_coverage.py            # gate every emblem
  python scripts/test_coverage.py --emblem 32
  python scripts/test_coverage.py -v         # list every passing check too
"""
import argparse, sys

import coverage_lib as cov


def check(res):
    """Return (ok, [failure messages]) for one emblem against its budget."""
    b = res["budget"]
    fails = []
    if res["coverage"] < b["min_coverage"]:
        fails.append(f"coverage {res['coverage']:.1%} < {b['min_coverage']:.0%} "
                     f"({res['n_gaps']} gaps stranded flat)")
    if res["figure_coverage"] < b["min_figure_coverage"]:
        fails.append(f"figure_coverage {res['figure_coverage']:.1%} < "
                     f"{b['min_figure_coverage']:.0%} (backdrop-only; needs real figures)")
    if res["largest_gap"] > b["max_gap_frac"]:
        g = res["gaps"][0]
        fails.append(f"largest gap {res['largest_gap']:.1%} > {b['max_gap_frac']:.1%} "
                     f"at ({g['centroid'][0]}, {g['centroid'][1]}) — likely a missing cutout")
    for c in res["cards"]:
        if c.get("missing"):
            fails.append(f"cutout file missing: {c['file']}")
        elif c.get("offplate"):
            fails.append(f"cutout placed off-plate: {c['file']}")
        elif c.get("stranded"):
            fails.append(f"mis-placed card: {c['file'].split('/')[-1]} "
                         f"(registration {c['registration']:.0%} < {b['min_registration']:.0%}, "
                         f"{c['ink_px']} ink px)")
    return (not fails), fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emblem", type=int, default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    layers = cov.load_layers()
    regions = cov.load_regions()
    nums = [args.emblem] if args.emblem is not None else sorted(layers)

    npass = nfail = 0
    for n in nums:
        if not cov.plate_path(n).exists():
            continue
        res = cov.analyze(n, layers, regions)
        ok, fails = check(res)
        if ok:
            npass += 1
            if args.verbose:
                print(f"PASS emblem-{n:02d}  coverage={res['coverage']:.1%} "
                      f"[{cov.grade(res['coverage'])}]")
        else:
            nfail += 1
            print(f"FAIL emblem-{n:02d}  coverage={res['coverage']:.1%} "
                  f"[{cov.grade(res['coverage'])}]")
            for f in fails:
                print(f"       - {f}")

    print(f"\n{npass} passed, {nfail} failed")
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
