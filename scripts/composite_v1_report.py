"""C2 results: each COMPOSITE_V1 table against its trigger and its complement, judged by the card's rule.

Pure reader, a sibling of `scripts/composite_ingredients.py` (whose loaders it imports): it reads
`experiments/done/<id>/results.json` for the four triggers and the 8 composite replays and writes
`research/diagnostics/composite_v1.md` and `reports/composite_v1.json`. No network, no dataset, train split
only. A replay that has not landed is listed as pending; the script runs cleanly with all 8 pending.

Per table, on the `top` selection of the trigger's own side: trigger, composite and complement edge (points),
share of the trigger's dates the composite covers, years where composite edge > trigger edge (of 6; a year
without composite picks counts as not above), and the pre-declared rule from `cards/COMPOSITE_V1.yml`:

  1. composite edge > trigger edge;
  2. composite-minus-trigger positive in at least 4 of the 6 train years;
  3. composite dates >= 40% of the trigger's dates.

All three hold -> the table adopts the composite; otherwise the table keeps its plain trigger. The rule needs
only the composite's replay; the complement is shown beside it (and listed as pending if it has not landed).

    python3 -m scripts.composite_v1_report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.composite_ingredients import DONE, TRAIN_YEARS, TRIGGER_RUNS, by_year, load_results, pts, side_block
from strategies.composite_v1 import COMPOSITES, composite_id
from strategies.g_gates import TRIGGERS

ROOT = Path(__file__).resolve().parent.parent
MD_OUT = ROOT / "research" / "diagnostics" / "composite_v1.md"
JSON_OUT = ROOT / "reports" / "composite_v1.json"

MIN_YEARS = 4
MIN_COVERAGE = 0.40
PRIOR_TRIALS = 34  # C1 cells (each with its complement) before C2


def experiment_id(table: str, keep: bool) -> str:
    horizon = TRIGGERS[COMPOSITES[table][0]].horizon
    return f"composite-v1-{table.replace('_', '-')}" + ("" if keep else "-not") + f"-{horizon}"


def table_row(table: str, trig: dict, keep: dict, comp: dict | None) -> dict:
    trigger, gates = COMPOSITES[table]
    ky, ty = by_year(keep), by_year(trig)
    diffs = {y: ky[y] - ty[y] for y in TRAIN_YEARS if y in ky and y in ty}
    years_above = sum(d > 0 for d in diffs.values())
    k_edge, t_edge = keep.get("edge"), trig.get("edge")
    t_dates, k_dates = trig.get("n_dates") or 0, keep.get("n_dates") or 0
    coverage = k_dates / t_dates if t_dates else None
    r1 = k_edge is not None and t_edge is not None and k_edge > t_edge
    r2 = years_above >= MIN_YEARS
    r3 = coverage is not None and coverage >= MIN_COVERAGE
    passed = bool(r1 and r2 and r3)
    return {
        "table": table.replace("_", " "),
        "composite": composite_id(table),
        "complement": composite_id(table, keep=False),
        "trigger": TRIGGERS[trigger].label,
        "gates": [g.upper() for g in gates],
        "status": "results",
        "trigger_edge_pts": pts(t_edge),
        "composite_edge_pts": pts(k_edge),
        "complement_edge_pts": None if comp is None else pts(comp.get("edge")),
        "complement_landed": comp is not None,
        "composite_t": None if keep.get("edge_t") is None else round(float(keep["edge_t"]), 2),
        "composite_n_picks": int(keep.get("n_picks") or 0),
        "trigger_n_dates": t_dates,
        "composite_n_dates": k_dates,
        "date_coverage": None if coverage is None else round(coverage, 3),
        "composite_minus_trigger_by_year_pts": {str(y): pts(d) for y, d in diffs.items()},
        "years_composite_above_trigger": years_above,
        "rule_1_edge_above_trigger": r1,
        "rule_2_years_above": r2,
        "rule_3_coverage": r3,
        "passes": passed,
        "decision": "adopt composite" if passed else f"keep plain {TRIGGERS[trigger].label}",
    }


def build(done: Path = DONE) -> dict:
    rows, pending = [], []
    for table, (trigger, gates) in COMPOSITES.items():
        side = TRIGGERS[trigger].side
        tr = load_results(done, TRIGGER_RUNS[trigger])
        k_id, c_id = experiment_id(table, True), experiment_id(table, False)
        kr, cr = load_results(done, k_id), load_results(done, c_id)
        missing = [i for i, r in ((TRIGGER_RUNS[trigger], tr), (k_id, kr), (c_id, cr)) if r is None]
        if tr is None or kr is None:
            pending.append({"table": table.replace("_", " "), "composite": composite_id(table), "missing": missing})
            continue
        row = table_row(table, side_block(tr, side), side_block(kr, side), None if cr is None else side_block(cr, side))
        if missing:
            row["missing"] = missing
        rows.append(row)
    return {
        "split": "train",
        "selection": "top",
        "rule": {"min_years_above_trigger": MIN_YEARS, "of_years": len(TRAIN_YEARS), "min_date_coverage": MIN_COVERAGE},
        "trials": {"c1_cells": PRIOR_TRIALS, "c2_composites": len(COMPOSITES), "c2_complements": len(COMPOSITES)},
        "tables": rows,
        "pending": pending,
    }


def _fmt(x, suffix: str = "") -> str:
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return f"{x:+.2f}{suffix}"
    return f"{x}{suffix}"


def render_md(table: dict) -> str:
    t = table["trials"]
    out = [
        "# C2 COMPOSITE_V1: train results",
        "",
        "One combined rule per live table: the trigger AND every C1 gate that qualified for it (`cards/COMPOSITE_V1.yml`).",
        "Edges are in points: hit rate above the market line on the trigger's own table side, `top` selection.",
        "The complement (trigger AND NOT all gates, among picks every gate judged) sits beside the composite so shrinkage alone cannot pass for an edge.",
        f"Trials: {t['c2_composites']} composites + {t['c2_complements']} complements, on top of C1's {t['c1_cells']} cells and their complements. Train split (2015-2020) only.",
        "These are aggregate statements about rules, not about any single stock; nothing here is advice. Generated by `scripts/composite_v1_report.py`.",
        "",
        "## Pre-declared rule (per table, all three required)",
        "",
        "1. Composite edge above the trigger's edge.",
        f"2. Composite minus trigger positive in at least {MIN_YEARS} of the {len(TRAIN_YEARS)} train years (a year without composite picks counts as not positive).",
        f"3. Composite fires on at least {MIN_COVERAGE:.0%} of the trigger's dates.",
        "",
        "A table that fails keeps its plain trigger.",
        "",
        "## Tables with results",
        "",
        "| Table | Composite | Trig | Comp. | Compl. | t | Date coverage | Yrs above trig | 1 | 2 | 3 | Decision |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in table["tables"]:
        cov = "-" if r["date_coverage"] is None else f"{100 * r['date_coverage']:.0f}%"
        out.append(
            f"| {r['table']} | {r['trigger']} AND {' AND '.join(r['gates'])} | {_fmt(r['trigger_edge_pts'])} | {_fmt(r['composite_edge_pts'])} "
            f"| {_fmt(r['complement_edge_pts'])} | {_fmt(r['composite_t'])} | {cov} | {r['years_composite_above_trigger']} of {len(TRAIN_YEARS)} "
            f"| {_fmt(r['rule_1_edge_above_trigger'])} | {_fmt(r['rule_2_years_above'])} | {_fmt(r['rule_3_coverage'])} | **{r['decision']}** |"
        )
    if not table["tables"]:
        out.append("| (none yet) |" + " |" * 11)
    out += ["", "### Per-year composite minus trigger (pts)", "", "| Table | Year | Composite - trigger |", "|---|---|---|"]
    for r in table["tables"]:
        for y in TRAIN_YEARS:
            out.append(f"| {r['table']} | {y} | {_fmt(r['composite_minus_trigger_by_year_pts'].get(str(y)))} |")
    out += ["", "## Pending (replay not landed yet)", "", "| Table | Composite | Missing replays |", "|---|---|---|"]
    for p in table["pending"]:
        out.append(f"| {p['table']} | {p['composite']} | {', '.join(f'`{m}`' for m in p['missing'])} |")
    for r in table["tables"]:
        if r.get("missing"):
            out.append(f"| {r['table']} | {r['composite']} | {', '.join(f'`{m}`' for m in r['missing'])} |")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--done", type=Path, default=DONE)
    ap.add_argument("--md", type=Path, default=MD_OUT)
    ap.add_argument("--json", type=Path, default=JSON_OUT)
    args = ap.parse_args(argv)
    table = build(args.done)
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render_md(table))
    args.json.write_text(json.dumps(table, indent=2) + "\n")
    for r in table["tables"]:
        print(f"{r['table']}: {r['decision']}")
    print(f"{len(table['tables'])} tables with results, {len(table['pending'])} pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
