"""GURU_V1 train results: the published setups (`strategies/guru_core.py`) next to the live rule of each table.

Pure reader, a sibling of `scripts/confluence_report.py`: it reads `experiments/done/<id>/results.json` (and
`picks.json` for the first and last pick date) for the 14 GURU_V1 replays (7 modules x day and week, train
split, `top` selection) and the four live-rule replays, and writes `research/diagnostics/guru_v1.md`. No
network, no dataset. Every module scores both sides, so each replay fills the bullish and the bearish table of
its horizon. A replay that has not landed is listed as pending; with none landed the report says "not run yet".

Per strategy and table: dates covered (first and last pick date, dates with picks, coverage), picks per date,
hit rate, market line, edge above the market line in points with a 95% interval (the engine's interval when the
results carry one, otherwise edge +/- 1.96 x edge / t, the t being the engine's per-date t), the per-year sign
count over the train years, and the live rule's own train numbers on the same table. Descriptive only: nothing
is selected and no rule is pre-declared here (cards R01-R04, R02B, P01, P02). These are aggregate statements
about rules, not about any stock, and not advice.

    python3 -m scripts.guru_report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.composite_ingredients import DONE, TRIGGER_RUNS, by_year, load_results, pts, side_block
from strategies import guru_core as C

ROOT = Path(__file__).resolve().parent.parent
MD_OUT = ROOT / "research" / "diagnostics" / "guru_v1.md"
HELD = ROOT / "experiments" / "held" / "guru"

HORIZONS = ("day", "week")
TABLES: dict[str, tuple[str, int]] = {
    "day_bullish": ("day", 1),
    "day_bearish": ("day", -1),
    "week_bullish": ("week", 1),
    "week_bearish": ("week", -1),
}
# The live rule per table (config/live_source.json) and the replay holding its train numbers.
LIVE: dict[str, tuple[str, str]] = {
    "day_bullish": ("T04 Connors RSI(2)", TRIGGER_RUNS["t04"]),
    "day_bearish": ("E2A crowded extreme-day reversal", TRIGGER_RUNS["e2a"]),
    "week_bullish": ("A05B MAX effect, ranked", TRIGGER_RUNS["a05b"]),
    "week_bearish": ("A01 weekly reversal", TRIGGER_RUNS["a01"]),
}
TRAIN_YEARS = tuple(range(2015, 2021))
Z95 = 1.96
NOT_RUN = "not run yet"


def experiment_id(name: str, horizon: str) -> str:
    return name.replace("_", "-") + f"-{horizon}"


EXPERIMENTS: dict[str, tuple[str, str]] = {
    experiment_id(n, h): (n, h) for h in HORIZONS for n in C.CONFIGS
}


def _pick_dates(done: Path, eid: str) -> tuple[str | None, str | None]:
    path = done / eid / "picks.json"
    if not path.exists():
        return None, None
    picks = json.loads(path.read_text())
    dates = [p["date"] for p in picks if isinstance(p, dict) and "date" in p]
    return (min(dates), max(dates)) if dates else (None, None)


def _ci(block: dict) -> list[float] | None:
    for key in ("edge_ci95", "edge_ci"):
        v = block.get(key)
        if isinstance(v, (list, tuple)) and len(v) == 2 and None not in v:
            return [pts(float(v[0])), pts(float(v[1]))]
    edge, t = block.get("edge"), block.get("edge_t")
    if edge is None or not t:
        return None
    se = abs(float(edge) / float(t))
    return [round(100.0 * (edge - Z95 * se), 2), round(100.0 * (edge + Z95 * se), 2)]


def _summary(block: dict) -> dict:
    n_picks, n_dates = int(block.get("n_picks") or 0), int(block.get("n_dates") or 0)
    ey = by_year(block)
    years = [y for y in TRAIN_YEARS if y in ey]
    return {
        "n_picks": n_picks,
        "n_dates": n_dates,
        "coverage": block.get("coverage"),
        "picks_per_date": round(n_picks / n_dates, 2) if n_dates else None,
        "hit_rate": block.get("accuracy"),
        "market_line": block.get("market_line"),
        "edge_pts": pts(block.get("edge")),
        "edge_t": None if block.get("edge_t") is None else round(float(block["edge_t"]), 2),
        "edge_ci95_pts": _ci(block) if n_picks else None,
        "years_positive": f"{sum(ey[y] > 0 for y in years)}/{len(years)}",
        "edge_by_year_pts": {str(y): pts(ey[y]) for y in years},
        "directional_move": block.get("directional_move"),
    }


def build(done: Path = DONE) -> dict:
    live = {}
    for table, (label, run) in LIVE.items():
        r = load_results(done, run)
        live[table] = {"label": label, "run": run,
                       **(_summary(side_block(r, TABLES[table][1])) if r is not None else {"edge_pts": None})}
    rows, pending = [], []
    for eid, (name, horizon) in EXPERIMENTS.items():
        r = load_results(done, eid)
        if r is None:
            pending.append(eid)
            continue
        first, last = _pick_dates(done, eid)
        for table, (h, side) in TABLES.items():
            if h != horizon:
                continue
            s = _summary(side_block(r, side))
            lv = live[table]
            rows.append({
                "module": name, "id": C.CONFIGS[name].config_id, "label": C.CONFIGS[name].label,
                "experiment": eid, "table": table, "first_date": first, "last_date": last, **s,
                "live_rule": lv["label"], "live_edge_pts": lv.get("edge_pts"),
                "live_years_positive": lv.get("years_positive"),
                "edge_minus_live_pts": None if s["edge_pts"] is None or lv.get("edge_pts") is None
                else round(s["edge_pts"] - lv["edge_pts"], 2),
            })
    return {"rows": rows, "pending": pending, "live": live}


def _f(x, fmt: str = "{:+.2f}") -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return fmt.format(x)
    return str(x)


def render_md(t: dict) -> str:
    out = [
        "# GURU_V1: published setups on NSE F&O stocks (train)",
        "",
        "Holy Grail, Turtle Soup, Turtle Soup Plus One, Anti and 80-20 (Raschke and Connors), the Five-EMA alert "
        "candle (Subasish Pani; a daily adaptation of an intraday method) and a Bollinger 1.5 sd variant, each "
        "coded literally with one fixed parameter set (`strategies/guru_core.py`; assumptions in each card).",
        "Train split (2015-2020), `top` selection (the strongest readings per date on each side). Edge = hit rate "
        "minus the market line, in points; the 95% interval is edge +/- 1.96 x edge / t unless the engine "
        "reported its own. Years = train years with positive edge / years with picks.",
        "These are aggregate statements about rules, not about any single stock; nothing here is advice. "
        "Generated by `scripts/guru_report.py`.",
        "",
    ]
    if not t["rows"]:
        out += [f"**{NOT_RUN}**: none of the {len(t['pending'])} replays has results in `experiments/done/` "
                f"(they are held in `experiments/held/guru/`).", ""]
    for table in TABLES:
        rows = [r for r in t["rows"] if r["table"] == table]
        lv = t["live"][table]
        out += [f"## {table.replace('_', ' ')}", "",
                f"Live rule: {lv['label']} (`{lv['run']}`): edge {_f(lv.get('edge_pts'))} pts, "
                f"years {lv.get('years_positive') or '-'}, picks per date {_f(lv.get('picks_per_date'), '{:.2f}')}.",
                ""]
        if not rows:
            out += [NOT_RUN, ""]
            continue
        out += ["| Setup | Dates covered | Dates with picks | Coverage | Picks/date | Hit rate | Market line | "
                "Edge (pts) | 95% interval | t | Years + | Edge - live (pts) |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            ci = r["edge_ci95_pts"]
            out.append(
                f"| {r['id']} {r['label']} | {r['first_date'] or '-'} to {r['last_date'] or '-'} | {r['n_dates']} | "
                f"{_f(r['coverage'], '{:.2f}')} | {_f(r['picks_per_date'], '{:.2f}')} | "
                f"{_f(r['hit_rate'], '{:.3f}')} | {_f(r['market_line'], '{:.3f}')} | {_f(r['edge_pts'])} | "
                f"{'-' if ci is None else f'{ci[0]:+.2f} to {ci[1]:+.2f}'} | {_f(r['edge_t'])} | "
                f"{r['years_positive']} | {_f(r['edge_minus_live_pts'])} |")
        out.append("")
    if t["pending"]:
        out += ["## Pending", "", ", ".join(f"`{e}`" for e in t["pending"]), ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--done", type=Path, default=DONE)
    ap.add_argument("--md", type=Path, default=MD_OUT)
    args = ap.parse_args(argv)
    t = build(args.done)
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render_md(t))
    if not t["rows"]:
        print(f"{NOT_RUN}: 0 of {len(EXPERIMENTS)} GURU_V1 replays have results; wrote {args.md}")
    else:
        print(f"{len(EXPERIMENTS) - len(t['pending'])} of {len(EXPERIMENTS)} GURU_V1 replays have results, "
              f"{len(t['rows'])} table rows; wrote {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
