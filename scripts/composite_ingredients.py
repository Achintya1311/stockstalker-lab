"""C1 results table: every trigger x gate cell against its trigger and its complement (train split only).

Pure reader: it reads `experiments/done/<id>/results.json` (and peeks at the first record of `picks.json`)
and writes `research/diagnostics/composite_ingredients.md` and `reports/composite_ingredients.json`. No
network, no dataset. The cell table is `strategies.g_gates` (`CELLS`, `SKIPPED`); experiment ids come from
`scripts.gen_g_cells.experiment_id`.

For each cell, on the `top` selection of the trigger's own side: trigger, keep and complement edge (points
= edge x 100), keep t, picks, the share of the trigger's dates the keep cell covers, directional move,
positive years, and per-year keep-minus-trigger and keep-minus-complement edge differences.

Difference interval. The engine's `picks.json` stores date, symbol and score only, no per-pick outcome, so
an edge per date cannot be recomputed without the dataset and no bootstrap interval is computed here.
`picks_have_outcomes` checks this on every run; if outcome fields ever appear, the markdown says so and the
interval stays a to-do rather than being invented. In its place the by-year differences are reported:
"years keep > complement: k of n" with a one-sided sign-test p-value (binomial, p = 0.5).

C2 screen, as pre-declared (cards/COMPOSITE_INGREDIENTS.yml, RESEARCH.md section 5), without intervals:
  A. interval substitute: keep edge > trigger edge in at least 4 train years AND keep edge > complement
     edge overall;
  B. positive in at least 4 of 6 train years, read both ways the declaration allows: the keep-minus-trigger
     difference (the card's wording) and the keep cell's own edge; both must hold;
  C. beats its complement: keep edge > complement edge overall.
`qualifies` = A and B and C. Nothing else is chosen or tuned.

    python3 -m scripts.composite_ingredients
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from scripts.gen_g_cells import experiment_id
from strategies.g_gates import CELLS, GATE_NAMES, SKIPPED, TRIGGERS, cell_batch, cell_id

ROOT = Path(__file__).resolve().parent.parent
DONE = ROOT / "experiments" / "done"
MD_OUT = ROOT / "research" / "diagnostics" / "composite_ingredients.md"
JSON_OUT = ROOT / "reports" / "composite_ingredients.json"

TRIGGER_RUNS = {
    "e2a": "e2a-day",
    "t04": "t04-connors-rsi2-day",
    "a05b": "a05b-max-effect-ranked-week",
    "a01": "a01-weekly-reversal-week",
}
TRAIN_YEARS = list(range(2015, 2021))  # config/splits.yml train
MIN_YEARS = 4
OUTCOME_KEYS = ("hit", "outcome", "move", "fwd_return", "market_line", "correct")


def load_results(done: Path, exp_id: str) -> dict | None:
    path = done / exp_id / "results.json"
    if not path.exists():
        return None
    r = json.loads(path.read_text())
    if r.get("split") != "train":
        raise ValueError(f"{exp_id}: split {r.get('split')!r}, this table is train only")
    return r


def side_block(results: dict, side: int, selection: str = "top") -> dict:
    return results["selections"][selection]["bullish" if side > 0 else "bearish"]


def picks_have_outcomes(done: Path, exp_id: str) -> bool | None:
    """True if `picks.json` records a per-pick outcome; None when there is no picks file."""
    path = done / exp_id / "picks.json"
    if not path.exists():
        return None
    picks = json.loads(path.read_text())
    first = picks[0] if isinstance(picks, list) and picks else {}
    return any(k in first for k in OUTCOME_KEYS)


def by_year(block: dict) -> dict[int, float]:
    return {int(y["year"]): float(y["edge"]) for y in block.get("by_year", []) if y.get("edge") is not None}


def sign_test_p(k: int, n: int) -> float | None:
    """One-sided P(X >= k) for X ~ Binomial(n, 0.5)."""
    if n == 0:
        return None
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n


def pts(x: float | None) -> float | None:
    return None if x is None else round(100.0 * x, 2)


def cell_row(trigger: str, gate: str, trig_block: dict, keep: dict, comp: dict) -> dict:
    ky, cy, ty = by_year(keep), by_year(comp), by_year(trig_block)
    kt = {y: ky[y] - ty[y] for y in TRAIN_YEARS if y in ky and y in ty}
    kc = {y: ky[y] - cy[y] for y in TRAIN_YEARS if y in ky and y in cy}
    k_edge, c_edge, t_edge = keep.get("edge"), comp.get("edge"), trig_block.get("edge")
    years_kt = sum(d > 0 for d in kt.values())
    years_kc = sum(d > 0 for d in kc.values())
    years_pos = sum(ky.get(y, 0.0) > 0 for y in TRAIN_YEARS)
    beats_comp = k_edge is not None and (c_edge is None or k_edge > c_edge)  # an empty complement cannot beat it
    crit_a = years_kt >= MIN_YEARS and beats_comp
    crit_b = years_kt >= MIN_YEARS and years_pos >= MIN_YEARS
    t_dates = trig_block.get("n_dates") or 0
    return {
        "cell": cell_id(trigger, gate),
        "complement": cell_id(trigger, gate, keep=False),
        "trigger": TRIGGERS[trigger].label,
        "gate": gate.upper(),
        "gate_name": GATE_NAMES[gate],
        "batch": cell_batch(trigger, gate),
        "status": "results",
        "trigger_edge_pts": pts(t_edge),
        "keep_edge_pts": pts(k_edge),
        "complement_edge_pts": pts(c_edge),
        "keep_t": None if keep.get("edge_t") is None else round(float(keep["edge_t"]), 2),
        "keep_n_picks": int(keep.get("n_picks") or 0),
        "complement_n_picks": int(comp.get("n_picks") or 0),
        "date_share": round((keep.get("n_dates") or 0) / t_dates, 3) if t_dates else None,
        "keep_directional_move_pct": None if keep.get("directional_move") is None else round(100.0 * keep["directional_move"], 3),
        "keep_years_positive": years_pos,
        "keep_minus_trigger_by_year_pts": {str(y): pts(d) for y, d in kt.items()},
        "keep_minus_complement_by_year_pts": {str(y): pts(d) for y, d in kc.items()},
        "years_keep_gt_trigger": years_kt,
        "years_keep_gt_complement": years_kc,
        "years_compared_complement": len(kc),
        "sign_test_p_keep_gt_complement": None if not kc else round(sign_test_p(years_kc, len(kc)), 3),
        "difference_interval": None,
        "crit_a_interval_substitute": crit_a,
        "crit_b_positive_years": crit_b,
        "crit_c_beats_complement": beats_comp,
        "qualifies": bool(crit_a and crit_b and beats_comp),
    }


def build(done: Path = DONE) -> dict:
    triggers, rows, pending = {}, [], []
    outcomes_seen = {}
    for trigger, run in TRIGGER_RUNS.items():
        r = load_results(done, run)
        if r is None:
            raise FileNotFoundError(f"trigger replay {run} not in {done}")
        block = side_block(r, TRIGGERS[trigger].side)
        triggers[trigger] = {"run": run, "side": TRIGGERS[trigger].side_word, "horizon": TRIGGERS[trigger].horizon,
                             "edge_pts": pts(block.get("edge")), "n_dates": block.get("n_dates"), "block": block}
        outcomes_seen[run] = picks_have_outcomes(done, run)
    for trigger, gate in CELLS:
        k_id, c_id = experiment_id(trigger, gate, True), experiment_id(trigger, gate, False)
        kr, cr = load_results(done, k_id), load_results(done, c_id)
        if kr is None or cr is None:
            missing = [i for i, r in ((k_id, kr), (c_id, cr)) if r is None]
            pending.append({"cell": cell_id(trigger, gate), "batch": cell_batch(trigger, gate), "missing": missing})
            continue
        side = TRIGGERS[trigger].side
        rows.append(cell_row(trigger, gate, triggers[trigger]["block"], side_block(kr, side), side_block(cr, side)))
        outcomes_seen[k_id] = picks_have_outcomes(done, k_id)
    has_outcomes = any(v for v in outcomes_seen.values())
    return {
        "split": "train",
        "selection": "top",
        "per_pick_outcomes_in_picks_json": has_outcomes,
        "interval_method": "none: picks.json has no per-pick outcomes; by-year differences and a sign test instead"
        if not has_outcomes else "to do: picks.json now has outcome fields; date-block bootstrap not yet implemented",
        "triggers": {t: {k: v for k, v in d.items() if k != "block"} for t, d in triggers.items()},
        "cells": rows,
        "pending": pending,
        "skipped": [{"cell": cell_id(t, g), "trigger": TRIGGERS[t].label, "gate": g.upper(), "why": why}
                    for (t, g), why in SKIPPED.items()],
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
    out = [
        "# C1 composite ingredients: train results table",
        "",
        "A cell is one live rule (the trigger) with one extra keep-only condition (the gate); its complement is the same trigger with the condition failing.",
        "Edges are in points: hit rate above the market line on the trigger's own table side, `top` selection (5 strongest readings per date).",
        "Keep, complement and trigger edges sit side by side so a gate that only shrinks the sample cannot look like an improvement.",
        "Train split (2015-2020) only; every cell and every complement is a separate replay and is counted as a trial in `ledger/trials.csv`.",
        "These are aggregate statements about rules, not about any single stock; nothing here is advice. Generated by `scripts/composite_ingredients.py`.",
        "",
        "## Triggers",
        "",
        "| Trigger | Replay | Side | Edge (pts) | Dates |",
        "|---|---|---|---|---|",
    ]
    for t, d in table["triggers"].items():
        out.append(f"| {TRIGGERS[t].label} | `{d['run']}` | {d['horizon']} {d['side']} | {_fmt(d['edge_pts'])} | {d['n_dates']} |")
    out += [
        "",
        "## Cells with results",
        "",
        "Columns: trigger, keep and complement edge (pts); keep t; keep picks; share of the trigger's dates the keep cell covers; "
        "keep directional move after costs (%); keep years positive of 6; years keep > trigger of 6; years keep > complement "
        "(k of n, one-sided sign-test p); C2 criteria A, B, C and `qualifies`.",
        "",
        "| Cell | Trig | Keep | Compl | t | Picks | Date share | Dir. move | Yrs+ | K>T yrs | K>C yrs (p) | A | B | C | qualifies |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in table["cells"]:
        p = r["sign_test_p_keep_gt_complement"]
        out.append(
            f"| {r['cell']} | {_fmt(r['trigger_edge_pts'])} | {_fmt(r['keep_edge_pts'])} | {_fmt(r['complement_edge_pts'])} "
            f"| {_fmt(r['keep_t'])} | {r['keep_n_picks']} | {'-' if r['date_share'] is None else f"{100 * r['date_share']:.0f}%"} | {_fmt(r['keep_directional_move_pct'], '%')} "
            f"| {r['keep_years_positive']} of 6 | {r['years_keep_gt_trigger']} of 6 "
            f"| {r['years_keep_gt_complement']} of {r['years_compared_complement']} ({'-' if p is None else f'{p:.3f}'}) "
            f"| {_fmt(r['crit_a_interval_substitute'])} | {_fmt(r['crit_b_positive_years'])} | {_fmt(r['crit_c_beats_complement'])} "
            f"| **{_fmt(r['qualifies'])}** |"
        )
    if not table["cells"]:
        out.append("| (none yet) |" + " |" * 14)
    out += ["", "### Per-year differences (pts)", "", "| Cell | Year | Keep - trigger | Keep - complement |", "|---|---|---|---|"]
    for r in table["cells"]:
        for y in TRAIN_YEARS:
            kt, kc = r["keep_minus_trigger_by_year_pts"].get(str(y)), r["keep_minus_complement_by_year_pts"].get(str(y))
            out.append(f"| {r['cell']} | {y} | {_fmt(kt)} | {_fmt(kc)} |")
    out += [
        "",
        "## Pre-declared C2 screen (applied, not tuned)",
        "",
        "- **A (interval substitute)**: keep edge above the trigger's in at least 4 of the 6 train years AND keep edge above the complement's overall.",
        "- **B (positive in at least 4 of 6 years)**: read both ways the declaration allows, and both must hold: the keep-minus-trigger difference is positive in at least 4 years, and the keep cell's own edge is positive in at least 4 years. A year without keep picks counts as not positive.",
        "- **C (beats its complement)**: keep edge above the complement edge overall (an empty complement counts as beaten).",
        "- `qualifies` = A and B and C.",
        "",
        "## Limitation: no difference interval",
        "",
    ]
    if table["per_pick_outcomes_in_picks_json"]:
        out.append("`picks.json` now carries per-pick outcome fields, but the date-block bootstrap is not implemented yet; no interval is shown.")
    else:
        out.append(
            "The engine's `picks.json` stores only date, symbol and score for each pick, with no hit or move, so the edge per date "
            "cannot be recomputed without the dataset and no bootstrap interval for keep minus trigger or keep minus complement is "
            "given. The by-year counts and the sign test above stand in for it; with 6 years, even 6 of 6 gives a one-sided p of "
            "0.016 and 5 of 6 gives 0.109, so this is a coarse read."
        )
    out += ["", "## Pending (replay not landed yet)", "", "| Cell | Batch | Missing replays |", "|---|---|---|"]
    for p in table["pending"]:
        out.append(f"| {p['cell']} | {p['batch']} | {', '.join(f'`{m}`' for m in p['missing'])} |")
    out += ["", "## Skipped cells", "", "| Cell | Why |", "|---|---|"]
    for s in table["skipped"]:
        out.append(f"| {s['cell']} | {s['why']} |")
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
    q = [r["cell"] for r in table["cells"] if r["qualifies"]]
    print(f"{len(table['cells'])} cells with results, {len(table['pending'])} pending, {len(q)} qualify: {', '.join(q) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
