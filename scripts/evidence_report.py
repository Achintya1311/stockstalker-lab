"""Re-test every finished train experiment with block-bootstrap intervals and data-snooping control.

Reads `experiments/done/*/picks.json` and the parsed dataset (Actions cache only), rebuilds each
experiment's per-date edge series for the published `top` selection with the engine's own functions,
then reports, per horizon and side: a stationary-bootstrap 95% interval and P(edge <= 0) per
experiment, and SPA / StepM / MCS across all of them (scripts/evidence_stats.py).

Does not change any gate. It is extra evidence next to `reports/train_leaderboard.md`.
    python3 -m scripts.evidence_report --data data/dataset.parquet --done experiments/done --out reports/evidence_train
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from engine.experiment_report import SIDES, Context, NOT_STRATEGIES, _load_picks, select
from engine.scoring import hit
from scripts.evidence_stats import boot_ci, multiple_testing

TRAIN_START, TRAIN_END = "2015-01-01", "2020-12-31"


def edge_series(picks: pd.DataFrame, side: int, horizon: str, ctx: Context) -> pd.Series:
    """Per pick-date edge (hit rate minus market line) for the `top` selection, as engine.experiment_report scores it."""
    picks = picks.merge(ctx.in_universe, on=["date", "symbol"], how="inner")
    sel = select(picks, side, ctx.k)
    joined = sel.merge(ctx.moves(horizon), on=["date", "symbol"], how="inner")
    if joined.empty:
        return pd.Series(dtype=float)
    joined["hit"] = hit(joined["move"], side)
    per_date = joined.groupby("date")["hit"].mean().to_frame("hit_rate").join(ctx.line(horizon, side).rename("line"), how="inner")
    return per_date["hit_rate"] - per_date["line"]


def build(data: Path, done: Path) -> dict:
    ctx = Context(pd.read_parquet(data))
    series: dict[tuple[str, int], dict[str, pd.Series]] = {}
    for d in sorted(done.iterdir()):
        mf, pk = d / "manifest.json", d / "picks.json"
        if not (mf.exists() and pk.exists()):
            continue
        m = json.loads(mf.read_text())
        if m["strategy"] in NOT_STRATEGIES or m["split"] != "train":
            continue
        picks = _load_picks(pk)
        for side in SIDES:
            s = edge_series(picks, side, m["horizon"], ctx)
            if len(s) >= 100:
                series.setdefault((m["horizon"], side), {})[m["id"]] = s
    out = {}
    for (horizon, side), by_id in series.items():
        dates = sorted(ctx.line(horizon, side).index)
        dates = [x for x in dates if TRAIN_START <= str(x) <= TRAIN_END]
        frame = pd.DataFrame({k: v.reindex(dates) for k, v in by_id.items()})   # NaN = no pick that date
        rows = {k: {**boot_ci(v.dropna().to_numpy()), "coverage": float(v.notna().mean())} for k, v in frame.items()}
        out[f"{horizon}/{SIDES[side]}"] = {"experiments": rows, "joint": multiple_testing(frame, size=0.10)}
    return out


def render(res: dict) -> str:
    lines = ["# Evidence, train split: block-bootstrap intervals and data-snooping control", "",
             "Edge is in points of hit rate over the market line, per pick date, `top` selection, as in `train_leaderboard.md`. "
             "The 95% interval and P(edge <= 0) come from a stationary bootstrap over dates (block length chosen per series), "
             "so serial correlation is respected. SPA is Hansen's test that NO strategy beats the market line across all trials "
             "of that horizon and side (small p = something real survives snooping). StepM names the strategies individually "
             "superior at the 10% level. MCS is the set statistically indistinguishable from the best at 10%. "
             "Dates with no pick count as edge 0 in the joint tests.", ""]
    for key, r in sorted(res.items()):
        j = r["joint"]
        spa = j.get("spa", {})
        lines += [f"## {key}  ({j['n_models']} experiments, block {j['block']})", "",
                  f"SPA p-value (consistent): **{spa.get('consistent', float('nan')):.3f}**  (lower {spa.get('lower', float('nan')):.3f}, upper {spa.get('upper', float('nan')):.3f}). "
                  f"StepM superior: {', '.join(j['stepm']) or 'none'}. MCS size: {len(j['mcs'])} of {j['n_models']}."
                  + ("".join(f" {c} repeats {o} exactly (same picks every date), so the joint tests ran on one copy." for c, o in j.get("twins", {}).items())), "",
                  "| Experiment | Dates | Coverage | Edge (pts) | 95% interval | P(edge<=0) | Block |", "|---|---|---|---|---|---|---|"]
        for k, v in sorted(r["experiments"].items(), key=lambda kv: -kv[1]["mean"]):
            lines.append(f"| {k} | {v['n']} | {v['coverage'] * 100:.0f}% | {v['mean'] * 100:+.2f} | {v['lo'] * 100:+.2f} to {v['hi'] * 100:+.2f} | {v['p_le0']:.3f} | {v['block']} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--done", default="experiments/done")
    ap.add_argument("--out", default="reports/evidence_train")
    a = ap.parse_args(argv)
    res = build(Path(a.data), Path(a.done))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    out.with_suffix(".md").write_text(render(res))
    print(f"wrote {out}.md for {len(res)} horizon/side groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
