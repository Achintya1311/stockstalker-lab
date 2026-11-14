"""CONFLUENCE_V1 train results: every minimum count against the live rule, the declared selection, and the
ablation table (`cards/CONFLUENCE_V1.yml`).

Pure reader, a sibling of `scripts/composite_v2_report.py` (it reuses the loaders of
`scripts/composite_ingredients.py`): it reads `experiments/done/<id>/results.json` for the 20 CONFLUENCE_V1
replays (10 modules x day and week) and the four live-rule replays, and writes
`research/diagnostics/confluence_v1.md` and `reports/confluence_v1.json`. No network, no dataset, train split
only. Every module scores both sides, so each replay is read twice (bullish and bearish table of its
horizon). A replay that has not landed is listed as pending; the script runs cleanly with all of them pending.

Pre-declared success rule per table (card, written before any replay), `top` selection:
  at least 500 train picks; train edge above zero AND above the table's live rule (points: day bullish
  +3.37, day bearish +7.46, week bullish +2.23, week bearish +2.48); positive edge in at least 4 of 6 train
  years.

Selection of ONE minimum count per table for a later unseen-data check, among the counts that meet the rule
on that table AND beat the live rule's own per-year edge in both 2019 and 2020: the highest mean edge over
2015-2018 (years with picks, at least 3). Per horizon, a count that qualifies on both the bullish and the
bearish table is preferred (highest sum of the two fit means; ties: the lower count); otherwise each table
takes its own best qualifying count, marked one side only; a table with none selects nothing. Ablations are
descriptive and never selected.

    python3 -m scripts.confluence_report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.composite_ingredients import DONE, TRIGGER_RUNS, by_year, load_results, pts, side_block
from strategies import confluence_core as C
from strategies.g_gates import TRIGGERS

ROOT = Path(__file__).resolve().parent.parent
MD_OUT = ROOT / "research" / "diagnostics" / "confluence_v1.md"
JSON_OUT = ROOT / "reports" / "confluence_v1.json"
HELD = ROOT / "experiments" / "held" / "conf"

HORIZONS = ("day", "week")
TABLES: dict[str, tuple[str, int]] = {
    "day_bullish": ("day", 1),
    "day_bearish": ("day", -1),
    "week_bullish": ("week", 1),
    "week_bearish": ("week", -1),
}
# The live rule per table (config/live_source.json) and its train edge in points, as declared in the card.
LIVE: dict[str, tuple[str, float]] = {
    "day_bullish": ("t04", 3.37),
    "day_bearish": ("e2a", 7.46),
    "week_bullish": ("a05b", 2.23),
    "week_bearish": ("a01", 2.48),
}
FOLDERS: dict[str, tuple[tuple[str, ...], str]] = {
    "main_day": (C.MAIN, "day"),
    "main_week": (C.MAIN, "week"),
    "ablation_day": (C.ABLATIONS, "day"),
    "ablation_week": (C.ABLATIONS, "week"),
}

TRAIN_YEARS = tuple(range(2015, 2021))
MIN_PICKS = 500
MIN_YEARS_POSITIVE = 4
FIT_YEARS = (2015, 2016, 2017, 2018)
CHECK_YEARS = (2019, 2020)
MIN_FIT_YEARS = 3
TRIALS = {"modules": len(C.CONFIGS), "horizons": len(HORIZONS), "replays": len(C.CONFIGS) * len(HORIZONS),
          "side_readings": 2 * len(C.CONFIGS) * len(HORIZONS)}


def experiment_id(name: str, horizon: str) -> str:
    return name.replace("confluence_", "conf-").replace("_", "-") + f"-{horizon}"


def _row(table: str, name: str, block: dict, live_block: dict | None) -> dict:
    horizon, side = TABLES[table]
    _, live_edge = LIVE[table]
    ey = by_year(block)
    ly = by_year(live_block) if live_block is not None else {}
    edge = block.get("edge")
    n_picks = int(block.get("n_picks") or 0)
    years_pos = sum(ey.get(y, 0.0) > 0 for y in TRAIN_YEARS)
    edge_pts = pts(edge)
    fit = [ey[y] for y in FIT_YEARS if y in ey]
    fit_mean = sum(fit) / len(fit) if len(fit) >= MIN_FIT_YEARS else None
    check = {y: (ey[y] - ly[y]) if y in ey and y in ly else None for y in CHECK_YEARS}
    rule = {
        "picks": n_picks >= MIN_PICKS,
        "edge_positive": edge_pts is not None and edge_pts > 0,
        "beats_live": edge_pts is not None and edge_pts > live_edge,
        "years_positive": years_pos >= MIN_YEARS_POSITIVE,
    }
    passes = all(rule.values())
    check_ok = all(d is not None and d > 0 for d in check.values())
    return {
        "table": table,
        "config": C.CONFIGS[name].config_id,
        "name": name,
        "min_count": C.CONFIGS[name].min_count,
        "dropped": C.CONFIGS[name].drop,
        "experiment": experiment_id(name, horizon),
        "n_picks": n_picks,
        "n_dates": int(block.get("n_dates") or 0),
        "edge_pts": edge_pts,
        "edge_t": None if block.get("edge_t") is None else round(float(block["edge_t"]), 2),
        "directional_move": block.get("directional_move"),
        "years_positive": years_pos,
        "edge_by_year_pts": {str(y): pts(ey[y]) for y in sorted(ey)},
        "live_rule": TRIGGERS[LIVE[table][0]].label,
        "live_edge_pts": live_edge,
        "edge_minus_live_pts": None if edge_pts is None else round(edge_pts - live_edge, 2),
        "rule": rule,
        "passes_rule": passes,
        "fit_mean_pts": pts(fit_mean),
        "fit_years_used": [y for y in FIT_YEARS if y in ey],
        "check_minus_live_pts": {str(y): pts(d) for y, d in check.items()},
        "beats_live_2019_2020": check_ok,
        "qualifies": bool(passes and check_ok and fit_mean is not None),
        "_fit": fit_mean,
    }


def select(horizon: str, rows: list[dict], complete: bool) -> dict:
    tables = [t for t, (h, _) in TABLES.items() if h == horizon]
    q = {(r["table"], r["name"]): r for r in rows if r["qualifies"]}
    both = [n for n in C.MAIN if all((t, n) in q for t in tables)]
    out = {"horizon": horizon, "final": complete, "counts_qualifying_on_both": [C.CONFIGS[n].min_count for n in both],
           "tables": {}}
    if both:
        best = max(both, key=lambda n: (sum(q[(t, n)]["_fit"] for t in tables), -C.CONFIGS[n].min_count))
        for t in tables:
            out["tables"][t] = {"selected": C.CONFIGS[best].config_id, "min_count": C.CONFIGS[best].min_count,
                                "one_side_only": False, "fit_mean_pts": q[(t, best)]["fit_mean_pts"]}
        return out
    for t in tables:
        mine = [q[(t, n)] for n in C.MAIN if (t, n) in q]
        if not mine:
            out["tables"][t] = {"selected": None, "min_count": None, "one_side_only": False, "fit_mean_pts": None}
            continue
        best = max(mine, key=lambda r: (r["_fit"], -r["min_count"]))
        out["tables"][t] = {"selected": best["config"], "min_count": best["min_count"], "one_side_only": True,
                            "fit_mean_pts": best["fit_mean_pts"]}
    return out


def build(done: Path = DONE) -> dict:
    rows, ablations, pending, selections = [], [], [], []
    live = {t: load_results(done, TRIGGER_RUNS[LIVE[t][0]]) for t in TABLES}
    for horizon in HORIZONS:
        complete = True
        h_rows = []
        results = {n: load_results(done, experiment_id(n, horizon)) for n in C.CONFIGS}
        for name, res in results.items():
            if res is None:
                pending.append({"horizon": horizon, "config": C.CONFIGS[name].config_id,
                                "experiment": experiment_id(name, horizon)})
                if name in C.MAIN:
                    complete = False
        for t, (h, side) in TABLES.items():
            if h != horizon:
                continue
            lb = side_block(live[t], side) if live[t] is not None else None
            if lb is None:
                complete = False
            for name in C.MAIN:
                if results[name] is not None:
                    h_rows.append(_row(t, name, side_block(results[name], side), lb))
            base = results[f"confluence_min{C.ABLATION_MIN}"]
            base_edge = pts(side_block(base, side).get("edge")) if base is not None else None
            for name in C.ABLATIONS:
                res = results[name]
                if res is None:
                    continue
                b = side_block(res, side)
                e = pts(b.get("edge"))
                ablations.append({
                    "table": t, "config": C.CONFIGS[name].config_id, "dropped": C.CONFIGS[name].drop,
                    "experiment": experiment_id(name, horizon), "n_picks": int(b.get("n_picks") or 0),
                    "edge_pts": e, "min4_edge_pts": base_edge,
                    "minus_min4_pts": None if e is None or base_edge is None else round(e - base_edge, 2),
                })
        selections.append(select(horizon, h_rows, complete))
        rows += h_rows
    for r in rows:
        r.pop("_fit")
    return {
        "split": "train",
        "selection": "top",
        "rule": {"min_picks": MIN_PICKS, "edge_above": "zero and the live rule",
                 "live_edge_pts": {t: v for t, (_, v) in LIVE.items()},
                 "min_years_positive": MIN_YEARS_POSITIVE, "of_years": len(TRAIN_YEARS),
                 "selection_fit_years": list(FIT_YEARS), "selection_check_years": list(CHECK_YEARS),
                 "selection_check": "edge above the live rule's own edge in each check year"},
        "trials": TRIALS,
        "configs": rows,
        "selections": selections,
        "ablations": ablations,
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
        "# CONFLUENCE_V1: train results",
        "",
        "The confluence method as the trigger itself: a setup needs a location (order block or support / resistance) AND an event (liquidity sweep or candle); its count is how many of 7 components agree (`cards/CONFLUENCE_V1.yml`, `strategies/confluence_core.py`).",
        "Edges are in points: hit rate above the market line, `top` selection (5 picks per date and side). Bullish picks are read on the bullish table, bearish picks on the bearish table of the same replay.",
        f"Trials: {t['modules']} modules x {t['horizons']} horizons = {t['replays']} train replays ({t['side_readings']} side readings). Train split (2015-2020) only.",
        "The market component is a stand-in built from the lab's own universe: the dataset has no volatility index and no overseas index series.",
        "These are aggregate statements about rules, not about any single stock; nothing here is advice. Generated by `scripts/confluence_report.py`.",
        "",
        "## Pre-declared rule (per table)",
        "",
        f"- At least {MIN_PICKS} train picks; train edge above zero and above the live rule "
        + ", ".join(f"({k.replace('_', ' ')} {v:+.2f})" for k, v in table["rule"]["live_edge_pts"].items())
        + f"; positive in at least {MIN_YEARS_POSITIVE} of {len(TRAIN_YEARS)} train years.",
        f"- Selection of one minimum count per table: among counts meeting the rule and beating the live rule's own edge in both {CHECK_YEARS[0]} and {CHECK_YEARS[1]}, the highest mean edge over {FIT_YEARS[0]}-{FIT_YEARS[-1]}; a count qualifying on both tables of a horizon is preferred.",
        "- Ablations are descriptive and never get a validation query.",
        "",
        "## Selection",
        "",
        "| Horizon | Table | Selected | Min count | One side only | Fit mean | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for sel in table["selections"]:
        status = "final" if sel["final"] else "provisional (replays pending)"
        for tb, d in sel["tables"].items():
            out.append(f"| {sel['horizon']} | {tb.replace('_', ' ')} | {d['selected'] or 'none'} | {_fmt(d['min_count'])} "
                       f"| {_fmt(d['one_side_only'])} | {_fmt(d['fit_mean_pts'])} | {status} |")
    if not any(sel["tables"] for sel in table["selections"]):
        out.append("| (none yet) |" + " |" * 6)
    out += [
        "",
        "## Minimum counts with results",
        "",
        "| Table | Config | Picks | Dates | Edge | t | Years + | Live rule | vs live | 2019 vs live | 2020 vs live | Fit mean | Rule | Qualifies |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in table["configs"]:
        ck = r["check_minus_live_pts"]
        out.append(
            f"| {r['table'].replace('_', ' ')} | {r['config']} | {r['n_picks']} | {r['n_dates']} | {_fmt(r['edge_pts'])} "
            f"| {_fmt(r['edge_t'])} | {r['years_positive']} of 6 | {r['live_rule']} {_fmt(r['live_edge_pts'])} "
            f"| {_fmt(r['edge_minus_live_pts'])} | {_fmt(ck.get('2019'))} | {_fmt(ck.get('2020'))} | {_fmt(r['fit_mean_pts'])} "
            f"| {_fmt(r['passes_rule'])} | **{_fmt(r['qualifies'])}** |"
        )
    if not table["configs"]:
        out.append("| (none yet) |" + " |" * 13)
    out += [
        "",
        "## Ablations (minimum 4, one component ignored; descriptive)",
        "",
        "| Table | Ignored | Picks | Edge | Min 4 edge | Edge minus min 4 |",
        "|---|---|---|---|---|---|",
    ]
    for a in table["ablations"]:
        out.append(f"| {a['table'].replace('_', ' ')} | {a['dropped']} | {a['n_picks']} | {_fmt(a['edge_pts'])} "
                   f"| {_fmt(a['min4_edge_pts'])} | {_fmt(a['minus_min4_pts'])} |")
    if not table["ablations"]:
        out.append("| (none yet) |" + " |" * 5)
    out += ["", "## Pending (replay not landed yet)", "", "| Horizon | Config | Replay |", "|---|---|---|"]
    for p in table["pending"]:
        out.append(f"| {p['horizon']} | {p['config']} | `{p['experiment']}` |")
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
            print(f"{tb}: {d['selected'] or 'none'}" + ("" if sel["final"] else " (provisional)"))
    print(f"{len(table['configs'])} table rows with results, {len(table['ablations'])} ablation rows, {len(table['pending'])} replays pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
