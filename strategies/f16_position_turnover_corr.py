"""F16: range position versus turnover correlation (`cards/F16.yml`, port lane).

Alpha#55 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 6 Nov 2026, SPEC.md section 5):

    (-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12)))), rank(volume), 6))

Port: on adjusted prices, the close's place in its 12-session high-low range (a
stochastic %K) is percentile-ranked among the stocks scored on each of the last 6
dates; so is turnover (traded value in place of share volume, as F09, so low-priced
stocks do not top the volume rank). Score = minus the per-stock Pearson correlation of
the two rank series over those 6 dates. Already two-signed: trading that rises with the
range position (buying into highs) bearish, trading that rises as the position falls
bullish. A stock without all 17 sessions in the slice, or with a constant rank series,
abstains.

Cross-section: stocks with a future on the slice's last date (`strategies/alpha101_common.py`).
Cross-sectional through the daily ranks (`strategies/f16_position_turnover_corr_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.alpha101_common import live_cross_section

RANGE = 12
CORR = 6
MIN_ROWS = RANGE + CORR - 1


def rank_panels(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(rank of %K, rank of turnover), date x symbol, over the last CORR dates of the slice."""
    dates = np.sort(history["date"].unique())[-MIN_ROWS:]
    h = history[history["date"].isin(dates)]
    counts = h.groupby("symbol")["date"].nunique()
    h = h[h["symbol"].isin(counts.index[counts == MIN_ROWS])].sort_values(["symbol", "date"])
    if h.empty:
        empty = pd.DataFrame()
        return empty, empty
    adj = compute_adjustment_factors(h)
    hi = adj.pivot(index="date", columns="symbol", values="adj_high")
    lo = adj.pivot(index="date", columns="symbol", values="adj_low")
    cl = adj.pivot(index="date", columns="symbol", values="adj_close")
    to = adj.pivot(index="date", columns="symbol", values="turnover").where(lambda x: x > 0)
    span = hi.rolling(RANGE).max() - lo.rolling(RANGE).min()
    k = (cl - lo.rolling(RANGE).min()) / span.where(span > 0)
    k, to = k.iloc[-CORR:], to.iloc[-CORR:]
    ok = k.notna().all() & to.notna().all()
    k, to = k.loc[:, ok], to.loc[:, ok]
    return k.rank(axis=1, pct=True), to.rank(axis=1, pct=True)


def correlations(history: pd.DataFrame) -> pd.Series:
    rk, rt = rank_panels(history)
    if rk.empty or rk.shape[1] < 2:
        return pd.Series(dtype=float)
    a = rk - rk.mean()
    b = rt - rt.mean()
    den = np.sqrt((a ** 2).sum() * (b ** 2).sum())
    corr = (a * b).sum() / den.where(den > 1e-12)
    return corr.dropna()


def score(history: pd.DataFrame) -> pd.Series:
    """Minus the 6-date correlation of the two daily rank series."""
    if history.empty or "turnover" not in history.columns:
        return pd.Series(dtype=float)
    history = live_cross_section(history)
    if history.empty:
        return pd.Series(dtype=float)
    sc = -correlations(history)
    return sc[sc.abs() > 1e-12].astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F16 range position vs turnover: insufficient history, no turnover, or flat ranks, abstain"
    side = "bullish" if sc[symbol] > 0 else "bearish"
    how = "rose with" if sc[symbol] < 0 else "moved against"
    return (f"F16 range position vs turnover (Alpha#55): over 6 sessions turnover rank {how} the close's "
            f"place in its 12-session range (correlation {-sc[symbol]:+.2f}), {side}")
