"""COMPOSITE_V2 train search: every config against its trigger, and the selection pre-declared in the card.

Pure reader, a sibling of `scripts/composite_v1_report.py` (it reuses the loaders of
`scripts/composite_ingredients.py`): it reads `experiments/done/<id>/results.json` for the four triggers and
the 60 config replays and writes `research/diagnostics/composite_v2.md` and `reports/composite_v2.json`. No
network, no dataset, train split only. A replay that has not landed is listed as pending; the script runs
cleanly with all of them pending.

Per config, on the `top` selection of the trigger's own side, from the per-year edges (`by_year`):

  fit gain    mean over the fit years 2015-2018 of (config edge - trigger edge), over the fit years where
              both have an edge; at least 3 such years are required (G5 and G9 never judge 2015);
  2019, 2020  config edge - trigger edge in each inner-check year (a year without config picks is not above);
  coverage    config dates / trigger dates over the whole train split.

Eligible (per table): fit gain > 0 AND above the trigger in both 2019 and 2020 AND coverage >= 40%.

Selection (per horizon, `cards/COMPOSITE_V2.yml`): among config keys eligible on BOTH tables of the horizon,
the one with the highest sum of its two fit gains (ties: first in declared order); both tables take it. If no
key is eligible on both, each table takes its own eligible config with the highest fit gain, marked "one
side only". A table with nothing eligible keeps its plain trigger. The selection is final only once the
horizon's triggers and every one of its configs have landed; before that it is shown as provisional.

    python3 -m scripts.composite_v2_report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.composite_ingredients import DONE, TRIGGER_RUNS, by_year, load_results, pts, side_block
from scripts.gen_composite_v2 import experiment_id, ordered_configs
from strategies import composite_v2 as C
from strategies.g_gates import TRIGGERS

ROOT = Path(__file__).resolve().parent.parent
MD_OUT = ROOT / "research" / "diagnostics" / "composite_v2.md"
JSON_OUT = ROOT / "reports" / "composite_v2.json"

FIT_YEARS = (2015, 2016, 2017, 2018)
CHECK_YEARS = (2019, 2020)
MIN_FIT_YEARS = 3
MIN_COVERAGE = 0.40
PRIOR_TRIALS = {"c1_cells_with_complements": 68, "composite_v1_with_complements": 8}


def config_row(table: str, key: str, trig: dict, cfg: dict) -> dict:
    s = C.CONFIGS[(table, key)]
    cy, ty = by_year(cfg), by_year(trig)
    fit = {y: cy[y] - ty[y] for y in FIT_YEARS if y in cy and y in ty}
    fit_gain = sum(fit.values()) / len(fit) if len(fit) >= MIN_FIT_YEARS else None
    check = {y: (cy[y] - ty[y]) if y in cy and y in ty else None for y in CHECK_YEARS}
    t_dates, c_dates = trig.get("n_dates") or 0, cfg.get("n_dates") or 0
    coverage = c_dates / t_dates if t_dates else None
    e_fit = fit_gain is not None and fit_gain > 0
    e_check = all(d is not None and d > 0 for d in check.values())
    e_cov = coverage is not None and coverage >= MIN_COVERAGE
    return {
        "table": table,
        "config": C.config_id(table, key),
        "config_key": C.config_key(table, s),
        "family": s.family_letter,
        "setting": C.describe(table, s),
        "experiment": experiment_id(table, key),
        "status": "results",
        "trigger_edge_pts": pts(trig.get("edge")),
        "config_edge_pts": pts(cfg.get("edge")),
        "config_t": None if cfg.get("edge_t") is None else round(float(cfg["edge_t"]), 2),
        "config_n_picks": int(cfg.get("n_picks") or 0),
        "trigger_n_dates": t_dates,
        "config_n_dates": c_dates,
        "date_coverage": None if coverage is None else round(coverage, 3),
        "fit_years_used": sorted(fit),
        "fit_gain_pts": pts(fit_gain),
        "check_minus_trigger_pts": {str(y): pts(d) for y, d in check.items()},
        "config_minus_trigger_by_year_pts": {str(y): pts(cy[y] - ty[y]) for y in sorted(cy) if y in ty},
        "eligible_fit": e_fit,
        "eligible_check": e_check,
        "eligible_coverage": e_cov,
        "eligible": bool(e_fit and e_check and e_cov),
        "_fit_gain": fit_gain,
    }


def select(horizon: str, rows: list[dict], complete: bool) -> dict:
    tables = C.HORIZON_TABLES[horizon]
    by = {(r["table"], r["config_key"]): r for r in rows if r["eligible"]}
    keys = list(dict.fromkeys(C.config_key(t, C.CONFIGS[(t, k)]) for t, k in ordered_configs() if t in tables))
    both = [k for k in keys if all((t, k) in by for t in tables)]
    out = {"horizon": horizon, "final": complete, "keys_eligible_on_both": both, "tables": {}}
    if both:
        best = max(both, key=lambda k: (sum(by[(t, k)]["_fit_gain"] for t in tables), -keys.index(k)))
        for t in tables:
            out["tables"][t] = {"decision": "config", "config": by[(t, best)]["config"], "config_key": best,
                                "one_side_only": False, "fit_gain_pts": by[(t, best)]["fit_gain_pts"]}
        out["selected_key"] = best
        out["sum_fit_gain_pts"] = pts(sum(by[(t, best)]["_fit_gain"] for t in tables))
        return out
    out["selected_key"] = None
    for t in tables:
        mine = [r for (tt, _), r in by.items() if tt == t]
        if not mine:
            out["tables"][t] = {"decision": f"keep plain {TRIGGERS[C.TABLES[t]].label}", "config": None,
                                "config_key": None, "one_side_only": False, "fit_gain_pts": None}
            continue
        order = {C.config_id(t, k): i for i, (tt, k) in enumerate(ordered_configs()) if tt == t}
        best = max(mine, key=lambda r: (r["_fit_gain"], -order[r["config"]]))
        out["tables"][t] = {"decision": "config", "config": best["config"], "config_key": best["config_key"],
                            "one_side_only": True, "fit_gain_pts": best["fit_gain_pts"]}
    return out


def build(done: Path = DONE) -> dict:
    rows, pending, selections = [], [], []
    for horizon, tables in C.HORIZON_TABLES.items():
        h_rows, complete = [], True
        for table in tables:
            trigger = C.TABLES[table]
            side = TRIGGERS[trigger].side
            tr = load_results(done, TRIGGER_RUNS[trigger])
            if tr is None:
                complete = False
            for t, key in ordered_configs():
                if t != table:
                    continue
                exp = experiment_id(table, key)
                cr = load_results(done, exp)
                if tr is None or cr is None:
                    complete = False
                    pending.append({"table": table, "config": C.config_id(table, key),
                                    "missing": [i for i, r in ((TRIGGER_RUNS[trigger], tr), (exp, cr)) if r is None]})
                    continue
                h_rows.append(config_row(table, key, side_block(tr, side), side_block(cr, side)))
        selections.append(select(horizon, h_rows, complete))
        rows += h_rows
    for r in rows:
        r.pop("_fit_gain")
    n = len(C.CONFIGS)
    return {
        "split": "train",
        "selection": "top",
        "rule": {"fit_years": list(FIT_YEARS), "check_years": list(CHECK_YEARS), "min_fit_years": MIN_FIT_YEARS,
                 "min_date_coverage": MIN_COVERAGE},
        "trials": {**PRIOR_TRIALS, "composite_v2_configs": n,
                   "composite_v2_day": sum(C.horizon_of(t) == "day" for t, _ in C.CONFIGS),
                   "composite_v2_week": sum(C.horizon_of(t) == "week" for t, _ in C.CONFIGS)},
        "configs": rows,
        "selections": selections,
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
        "# COMPOSITE_V2: train search results",
        "",
        "Other ways to combine the C1 gates (vote k of n, rank boost, single-gate threshold variants), each setting built for both the bullish and the bearish table of its horizon (`cards/COMPOSITE_V2.yml`).",
        "Edges are in points: hit rate above the market line on the trigger's own table side, `top` selection. The comparison is the trigger's own train replay; no complements this round.",
        f"Trials: {t['composite_v2_configs']} configs ({t['composite_v2_day']} day, {t['composite_v2_week']} week), on top of C1's {t['c1_cells_with_complements']} cell replays and COMPOSITE_V1's {t['composite_v1_with_complements']}. Train split (2015-2020) only.",
        "These are aggregate statements about rules, not about any single stock; nothing here is advice. Generated by `scripts/composite_v2_report.py`.",
        "",
        "## Pre-declared selection",
        "",
        f"- Fit gain: mean over {FIT_YEARS[0]}-{FIT_YEARS[-1]} of config minus trigger edge, over fit years where both have picks (at least {MIN_FIT_YEARS}).",
        f"- Eligible on a table: fit gain above zero, AND above the trigger in both {CHECK_YEARS[0]} and {CHECK_YEARS[1]}, AND fires on at least {MIN_COVERAGE:.0%} of the trigger's dates.",
        "- Per horizon: the config key eligible on both tables with the highest sum of its two fit gains; if none, each table's eligible config with the highest fit gain (one side only); if nothing is eligible, the plain trigger.",
        "- Only the selected config per table may later get one validation query.",
        "",
        "## Selection",
        "",
        "| Horizon | Table | Decision | Config | One side only | Fit gain | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for sel in table["selections"]:
        status = "final" if sel["final"] else "provisional (replays pending)"
        for tb, d in sel["tables"].items():
            out.append(f"| {sel['horizon']} | {tb.replace('_', ' ')} | {d['decision']} | {d['config'] or '-'} "
                       f"| {_fmt(d['one_side_only'])} | {_fmt(d['fit_gain_pts'])} | {status} |")
    out += [
        "",
        "## Configs with results",
        "",
        "| Config | Key | Fam. | Trig | Config | t | Coverage | Fit gain | 2019 | 2020 | Fit | Check | Cov. | Eligible |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in table["configs"]:
        cov = "-" if r["date_coverage"] is None else f"{100 * r['date_coverage']:.0f}%"
        ck = r["check_minus_trigger_pts"]
        out.append(
            f"| {r['config']} | {r['config_key']} | {r['family']} | {_fmt(r['trigger_edge_pts'])} | {_fmt(r['config_edge_pts'])} "
            f"| {_fmt(r['config_t'])} | {cov} | {_fmt(r['fit_gain_pts'])} | {_fmt(ck.get('2019'))} | {_fmt(ck.get('2020'))} "
            f"| {_fmt(r['eligible_fit'])} | {_fmt(r['eligible_check'])} | {_fmt(r['eligible_coverage'])} | **{_fmt(r['eligible'])}** |"
        )
    if not table["configs"]:
        out.append("| (none yet) |" + " |" * 13)
    out += ["", "## Pending (replay not landed yet)", "", "| Table | Config | Missing replays |", "|---|---|---|"]
    for p in table["pending"]:
        out.append(f"| {p['table'].replace('_', ' ')} | {p['config']} | {', '.join(f'`{m}`' for m in p['missing'])} |")
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
    for sel in table["selections"]:
        for tb, d in sel["tables"].items():
            print(f"{tb}: {d['decision']} {d['config'] or ''}".rstrip() + ("" if sel["final"] else " (provisional)"))
    print(f"{len(table['configs'])} configs with results, {len(table['pending'])} pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
