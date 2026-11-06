"""F15: three-session streak reversal on recent volume (`cards/F15.yml`, port lane).

Alpha#30 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 6 Nov 2026, SPEC.md section 5):

    (((1.0 - rank(((sign((close - delay(close, 1))) + sign((delay(close, 1) - delay(close, 2))))
      + sign((delay(close, 2) - delay(close, 3)))))) * sum(volume, 5)) / sum(volume, 20))

Port: the signs of the last three daily changes of the adjusted close are summed (-3 to
+3) and percentile-ranked among the stocks scored that date; p = (1 - that rank) x the
last 5 sessions' turnover over the last 20 sessions' (traded value in place of share
volume, as F09, so a split does not move the ratio). The paper's product is one-signed,
so the port centres it: score = p - median(p). Three down closes on heavy recent trading
score bullish; three up closes on light trading bearish. Week horizon: the slice ends at
Friday's close and the pick holds Monday's open to Friday's close.

Cross-section: stocks with a future on the slice's last date (`strategies/alpha101_common.py`).
Cross-sectional through the rank and the median (`strategies/f15_streak_volume_reversal_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.alpha101_common import centred, live_cross_section

STREAK = 3
SHORT = 5
LONG = 20
MIN_ROWS = LONG


def parts(frame: pd.DataFrame) -> tuple[int, float]:
    """(sum of the signs of the last 3 daily adjusted-close changes, 5/20-session turnover ratio)."""
    close = frame["adj_close"].to_numpy(float)[-(STREAK + 1):]
    t = frame["turnover"].to_numpy(float)[-LONG:]
    return int(np.sign(np.diff(close)).sum()), float(t[-SHORT:].sum() / t.sum())


def components(history: pd.DataFrame) -> pd.DataFrame:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    rows = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        t = group["turnover"].to_numpy(float)
        c = group["adj_close"].to_numpy(float)
        if not (np.isfinite(t).all() and (t > 0).all() and np.isfinite(c).all()):
            continue
        rows[symbol] = parts(group.sort_values("date"))
    return pd.DataFrame.from_dict(rows, orient="index", columns=["streak", "vol_ratio"])


def score(history: pd.DataFrame) -> pd.Series:
    """(1 - rank(streak)) x turnover ratio, minus its median."""
    if history.empty or "turnover" not in history.columns:
        return pd.Series(dtype=float)
    history = live_cross_section(history)
    if history.empty:
        return pd.Series(dtype=float)
    comp = components(history)
    if len(comp) < 2:
        return pd.Series(dtype=float)
    p = (1.0 - comp["streak"].rank(pct=True)) * comp["vol_ratio"]
    return centred(p)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F15 streak reversal: insufficient history, no turnover, or at the median, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    streak, ratio = parts(sub)
    side = "bullish" if sc[symbol] > 0 else "bearish"
    return (f"F15 streak reversal (Alpha#30): signs of the last 3 daily changes sum to {streak:+d}, last 5 "
            f"sessions carry {ratio:.0%} of 20-session turnover, {side}")
