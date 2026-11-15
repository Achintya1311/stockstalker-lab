"""Bullish trials table (BULLISH_PLAN B1 to B5): `research/diagnostics/bull_v1.md`.

    python3 -m scripts.bull_report
    python3 -m scripts.bull_report --done experiments/done --out research/diagnostics/bull_v1.md

Reads every train `experiments/done/<id>/results.json` whose id starts with b1- to b5- and writes one table,
bullish side, `top` selection: horizon, yardstick, basket size (top_n), picks, dates, hit rate, market line,
edge, t, 95% interval, positive years, directional move after costs, and for exit runs the payoff columns
(`engine/exits.py`). A PASS column applies the plan's bar, fixed before any result was seen (14 Nov 2026):

- at least 500 picks;
- edge of at least 3 points; for an exit run instead: average R above the universe baseline > 0 with t >= 2;
- positive in at least 4 of the 6 train years (exit runs: years with average R above baseline > 0);
- directional move after costs above zero (exit runs: the exit plan's average outcome after costs).

Ids held in `experiments/held/bull/` or queued in `experiments/pending/` without a result are listed as
"not run yet"; a refused one shows its reason. Train only, observation only: nothing here is a gate or a
roster input. Intervals: month runs carry the engine's moving-block bootstrap; day and week runs the
engine's per-date t, so their interval is edge +/- 1.96 x edge / t (the same standard error).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

DONE = Path("experiments/done")
HELD = Path("experiments/held/bull")
PENDING = Path("experiments/pending")
OUT = Path("research/diagnostics/bull_v1.md")
ID_RE = re.compile(r"^b[1-5]-")
MIN_PICKS, MIN_EDGE, MIN_EXIT_T, MIN_POS_YEARS = 500, 0.03, 2.0, 4
COLUMNS = ["Id", "Horizon", "Yardstick", "Top n", "Picks", "Dates", "Hit rate", "Market line", "Edge (pts)", "t",
           "95% interval", "Years positive", "Dir. move after costs", "Avg R above baseline (t)", "Profit factor",
           "PASS"]
LIVE = [("day bullish", "T04 (t04_connors_rsi2)", "+3.37", "+4.36"),
        ("week bullish", "A05B (a05b_max_effect_ranked)", "+2.23", "+2.23")]


def _pts(x) -> str:
    return "n/a" if x is None else f"{x * 100:+.2f}"


def _pct(x, digits=1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def _num(x, digits=2) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def _interval(m: dict) -> list | None:
    if m.get("edge_interval"):
        return m["edge_interval"]
    t, e = m.get("edge_t"), m.get("edge")
    if t and e is not None and t != 0:
        se = abs(e / t)
        return [e - 1.96 * se, e + 1.96 * se]
    return None


def evaluate(r: dict) -> tuple[list[str], bool]:
    """One table row (bullish, top) and whether it clears the plan's bar."""
    m = r["selections"]["top"].get("bullish", {})
    top_n = r.get("top_n") or r.get("picks_per_table")
    head = [r["id"], r["horizon"], r.get("yardstick", "absolute"), str(top_n)]
    if not m.get("n_picks"):
        return head + ["0"] + ["n/a"] * (len(COLUMNS) - 6) + ["no"], False
    years = m.get("by_year") or []
    pos_years = sum(1 for y in years if y["edge"] > 0)
    iv = _interval(m)
    x = (r.get("exit") or {}).get("sides", {}).get("bullish")
    if x and x.get("n_picks"):
        xyears = [y for y in x.get("by_year", []) if y.get("avg_r_above_baseline") is not None]
        pos_x = sum(1 for y in xyears if y["avg_r_above_baseline"] > 0)
        above = x.get("avg_r_above_baseline")
        passed = (x["n_picks"] >= MIN_PICKS and above is not None and above > 0
                  and (x.get("t") or 0) >= MIN_EXIT_T and pos_x >= MIN_POS_YEARS and x["avg_pct"] > 0)
        exit_cols = [f"{_num(above, 3)} (t {_num(x.get('t'))})", _num(x.get("profit_factor"))]
        years_text = f"{pos_x} / {len(xyears)} (payoff); {pos_years} / {len(years)} (edge)"
        move_text = f"{_pct(x['avg_pct'], 2)} (exit plan); {_pct(m['directional_move'], 2)} (horizon)"
    else:
        passed = (m["n_picks"] >= MIN_PICKS and m["edge"] >= MIN_EDGE and pos_years >= MIN_POS_YEARS
                  and m["directional_move"] > 0)
        exit_cols = ["", ""]
        years_text = f"{pos_years} / {len(years)}"
        move_text = _pct(m["directional_move"], 2)
    row = head + [str(m["n_picks"]), str(m["n_dates"]), _pct(m["accuracy"]), _pct(m["market_line"]),
                  _pts(m["edge"]), _num(m.get("edge_t")),
                  "n/a" if iv is None else f"{_pts(iv[0])} to {_pts(iv[1])}", years_text, move_text,
                  *exit_cols, "**yes**" if passed else "no"]
    return row, passed


def _waiting_ids(held_dir: Path, pending_dir: Path) -> list[str]:
    ids = set()
    for p in list(held_dir.rglob("*.yml")) + list(pending_dir.glob("b*.yml")):
        try:
            exp_id = (yaml.safe_load(p.read_text()) or {}).get("id") or p.stem
        except (OSError, yaml.YAMLError):
            exp_id = p.stem
        if ID_RE.match(str(exp_id)):
            ids.add(str(exp_id))
    return sorted(ids)


def render(done_dir: Path = DONE, held_dir: Path = HELD, pending_dir: Path = PENDING) -> str:
    rows: dict[str, list[str]] = {}
    passed = []
    for f in sorted(done_dir.glob("b*/results.json")):
        r = json.loads(f.read_text())
        if not ID_RE.match(r["id"]) or r.get("split") != "train":
            continue
        rows[r["id"]], ok = evaluate(r)
        if ok:
            passed.append(r["id"])
    for d in sorted(done_dir.glob("b*/refused.json")):
        exp_id = d.parent.name
        if ID_RE.match(exp_id) and exp_id not in rows:
            reason = json.loads(d.read_text()).get("reason", "")
            rows[exp_id] = [exp_id] + [""] * (len(COLUMNS) - 2) + [f"refused: {reason}"]
    for exp_id in _waiting_ids(held_dir, pending_dir):
        if exp_id not in rows:
            rows[exp_id] = [exp_id] + ["not run yet"] + [""] * (len(COLUMNS) - 2)
    lines = ["# Bullish trials (BULLISH_PLAN B1 to B5): train results", "",
             "Train split only (2015 to 2020), bullish side, `top` selection (the picks per date the run's basket "
             "keeps; `Top n`). Observation only: no number here is a gate, a roster input or shown on the desk. "
             "Rebuilt by `python3 -m scripts.bull_report`.", "",
             "Yardstick `absolute`: a bullish pick is right when the stock rose over the horizon; market line = "
             "share of universe stocks that rose (SPEC.md section 3). Yardstick `relative`: right when the stock "
             "did better than the median universe stock on that pick date; market line = exact share of universe "
             "stocks above that median (at or just under 50%). Costs cancel in the relative comparison; the "
             "directional move after costs is the usual absolute one either way.", "",
             f"PASS (plan's bar, fixed 14 Nov 2026): picks >= {MIN_PICKS}; edge >= {MIN_EDGE * 100:.0f} points (exit "
             f"runs: average R above the universe baseline > 0 with t >= {MIN_EXIT_T:g}); positive in >= "
             f"{MIN_POS_YEARS} of 6 train years; directional move after costs > 0. A pass earns exactly one check "
             "on the unseen 2021 to 2023 years; it goes forward only if it holds there and beats the current rule "
             "for its table by at least 1 point.", "",
             "Intervals: month rows use the engine's moving-block bootstrap (block t); day and week rows use the "
             "engine's per-date t, interval = edge +/- 1.96 x standard error.", "",
             "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    if not rows:
        lines.append("| (no b1- to b5- experiments found) |" + " |" * (len(COLUMNS) - 1))
    lines += ["| " + " | ".join(rows[k]) + " |" for k in sorted(rows)]
    lines += ["", f"Passing: {', '.join(passed) if passed else 'none yet'}.", "",
              "## Live comparison (current bullish rules, edge in points, absolute yardstick, top 5)", "",
              "| Table | Rule | Train edge | Released validation edge |", "|---|---|---|---|"]
    lines += [f"| {t} | {rule} | {tr} | {rel} |" for t, rule, tr, rel in LIVE]
    lines += ["", "A relative-yardstick edge and an absolute one answer different questions, so they are not "
              "directly comparable; a wider basket is not what a five-row table publishes. SPEC.md needs a wording "
              "amendment before either is used for a roster decision (`state/engine-issues.md`).", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--done", default=str(DONE))
    ap.add_argument("--held", default=str(HELD))
    ap.add_argument("--pending", default=str(PENDING))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    text = render(Path(args.done), Path(args.held), Path(args.pending))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
