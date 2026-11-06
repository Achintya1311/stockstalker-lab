"""F13: accelerating range top on a turnover surge, faded (`cards/F13.yml`, port lane).

Alpha#17 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 6 Nov 2026, SPEC.md section 5):

    (((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) * rank(ts_rank((volume / adv20), 5)))

Port: `ts_rank(close, 10)` on the adjusted close; `delta(delta(close, 1), 1)` as the
second difference of the log adjusted close (so prices on different scales rank
together); `volume / adv20` as today's turnover over the mean of the last 20 sessions'
turnover (traded value for both, as in F09), its time-series rank over 5 sessions. The
three are percentile-ranked among the stocks scored that date and multiplied (p). The
paper's product is one-signed, so the port centres it: score = median(p) - p. An
accelerating close at its 10-session top on surging turnover scores bearish; a
decelerating close at its 10-session low on light turnover bullish.

Cross-section: stocks with a future on the slice's last date (`strategies/alpha101_common.py`).
Cross-sectional through the ranks and the median (`strategies/f13_accel_range_top_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.alpha101_common import centred, live_cross_section, ts_rank_last

WINDOW = 10
VOL_MEAN = 20
VOL_RANK = 5
MIN_ROWS = VOL_MEAN + VOL_RANK - 1  # 5 ratios, each over its own 20-session mean


def parts(frame: pd.DataFrame) -> tuple[float, float, float]:
    """(ts-rank of the close in 10, second difference of the log close, ts-rank of turnover ratio in 5)."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    turnover = frame["turnover"].to_numpy(float)[-MIN_ROWS:]
    tsr = ts_rank_last(close[-WINDOW:])
    lc = np.log(close[-3:])
    acc = float((lc[2] - lc[1]) - (lc[1] - lc[0]))
    mean20 = np.convolve(turnover, np.ones(VOL_MEAN) / VOL_MEAN, mode="valid")
    ratio = turnover[VOL_MEAN - 1:] / mean20
    return tsr, acc, ts_rank_last(ratio)


def components(history: pd.DataFrame) -> pd.DataFrame:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    rows = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        t = group["turnover"].to_numpy(float)
        c = group["adj_close"].to_numpy(float)
        if not (np.isfinite(t).all() and (t > 0).all() and np.isfinite(c).all() and (c > 0).all()):
            continue
        rows[symbol] = parts(group.sort_values("date"))
    return pd.DataFrame.from_dict(rows, orient="index", columns=["ts_rank", "accel", "vol_rank"])


def score(history: pd.DataFrame) -> pd.Series:
    """median(p) - p, p = product of the three cross-sectional ranks."""
    if history.empty or "turnover" not in history.columns:
        return pd.Series(dtype=float)
    history = live_cross_section(history)
    if history.empty:
        return pd.Series(dtype=float)
    comp = components(history)
    if len(comp) < 2:
        return pd.Series(dtype=float)
    p = comp["ts_rank"].rank(pct=True) * comp["accel"].rank(pct=True) * comp["vol_rank"].rank(pct=True)
    return centred(-p)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F13 accelerating range top: insufficient history, no turnover, or at the median, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    tsr, acc, vr = parts(sub)
    side = "bullish" if sc[symbol] > 0 else "bearish"
    shape = "accelerating" if acc > 0 else "decelerating"
    return (f"F13 accelerating range top (Alpha#17): close ranks {tsr:.2f} in its 10-session range, "
            f"last move {shape}, turnover-surge rank {vr:.2f} of 5 sessions, {side}")
