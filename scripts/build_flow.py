"""Publish one session's market flow for the desk: each F&O stock's cumulative percent move from its
first bar's open, at 15-minute steps, plus the equal-weight market average.

Reads the 5-minute archive that `fetch_intraday.py` keeps in the Actions cache and writes a small JSON
of percentages only (no prices, no volume; SPEC.md section 10). The bars themselves are never published.

    python3 scripts/build_flow.py --store intraday/5m.parquet --out reports/flow --keep 20

Output `reports/flow/<session>.json`:
    {"session": "2026-11-09", "step_min": 15, "source": "derived from Yahoo Finance 5-minute bars",
     "times": ["09:15", "09:30", ...], "market": {"ret": [...]}, "stocks": [{"s": "TECHM", "ret": [...]}]}
`ret[i]` is the percent move from the open to the close of the last 5-minute bar that ended at or before
`times[i]` (`times[0]` is the open, so `ret[0]` is 0); null where the stock has no bar yet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

STEP_MIN = 15
BAR_MIN = 5
SOURCE = "derived from Yahoo Finance 5-minute bars"
MIN_SYMBOLS = 50   # a session with fewer stocks than this is a partial fetch, not a market


def flow_for_session(bars: pd.DataFrame) -> dict:
    """`bars`: one session's rows (symbol, ts, open, close). Returns the flow payload without the session key."""
    bars = bars.sort_values(["symbol", "ts"])
    start = bars["ts"].min().normalize() + pd.Timedelta(hours=9, minutes=15)
    last_end = bars["ts"].max() + pd.Timedelta(minutes=BAR_MIN)
    marks = list(pd.date_range(start, last_end, freq=f"{STEP_MIN}min"))
    if marks[-1] < last_end:
        marks.append(last_end)
    stocks = []
    for sym, g in bars.groupby("symbol"):
        first_open = float(g["open"].iloc[0])
        if not first_open > 0:
            continue
        ends = (g["ts"] + pd.Timedelta(minutes=BAR_MIN)).to_numpy()
        pct = ((g["close"] / first_open - 1.0) * 100).to_numpy()
        ret = []
        for i, t in enumerate(marks):
            n = int((ends <= t.to_datetime64()).sum())
            ret.append(0.0 if i == 0 and g["ts"].iloc[0] <= t + pd.Timedelta(minutes=STEP_MIN) else (round(float(pct[n - 1]), 2) if n else None))
        stocks.append({"s": sym, "ret": ret})
    market = []
    for i in range(len(marks)):
        vals = [s["ret"][i] for s in stocks if s["ret"][i] is not None]
        market.append(round(sum(vals) / len(vals), 3) if vals else None)
    return {"step_min": STEP_MIN, "source": SOURCE, "times": [t.strftime("%H:%M") for t in marks],
            "market": {"ret": market}, "stocks": stocks}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", default="intraday/5m.parquet")
    ap.add_argument("--out", default="reports/flow")
    ap.add_argument("--keep", type=int, default=20, help="number of newest session files to keep")
    ap.add_argument("--sessions", type=int, default=1, help="how many of the newest sessions to (re)write")
    args = ap.parse_args(argv)
    df = pd.read_parquet(args.store, columns=["symbol", "ts", "open", "close"])
    df["day"] = df["ts"].dt.strftime("%Y-%m-%d")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    wrote = 0
    for day in sorted(df["day"].unique())[-args.sessions:]:
        part = df[df["day"] == day]
        if part["symbol"].nunique() < MIN_SYMBOLS:
            print(f"{day}: only {part['symbol'].nunique()} symbols, skipped", file=sys.stderr)
            continue
        payload = {"session": day, **flow_for_session(part)}
        (out / f"{day}.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n")
        wrote += 1
        print(f"{day}: {len(payload['stocks'])} stocks, {len(payload['times'])} points")
    files = sorted(out.glob("20*.json"))
    for old in files[:-args.keep]:
        old.unlink()
    (out / "index.json").write_text(json.dumps({"sessions": [f.stem for f in sorted(out.glob("20*.json"))]}) + "\n")
    return 0 if wrote else 1


if __name__ == "__main__":
    sys.exit(main())
