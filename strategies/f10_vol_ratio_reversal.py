"""F10: volatility-ratio plus one-day reversal (`cards/F10.yml`, port lane).

Alpha#34 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 5 Nov 2026, SPEC.md section 5):

    rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))

On adjusted closes (SPEC.md section 2), `returns` are daily close-to-close log returns and
`delta(close, 1)` is the last session's log return (the paper's raw price change would rank
stocks by price level, so the port uses the return). `stddev` is the sample standard
deviation (ddof 1) over the last 2 and 5 returns. Inner ranks are percentile ranks among
the stocks scored that date. The outer rank is monotone, so the port scores the inner sum
s = (1 - rank(ratio)) + (1 - rank(last return)) and centres it: score = s - median(s). Calm
last two sessions relative to the last five, and a fall yesterday, score bullish; the
reverse bearish. A zero 5-session deviation abstains.

Cross-sectional through the ranks and the median (`strategies/f10_vol_ratio_reversal_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

SHORT = 2
LONG = 5
MIN_ROWS = LONG + 1


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(stddev of the last 2 log returns / stddev of the last 5, last log return)."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    r = np.diff(np.log(close))
    long = r.std(ddof=1)
    ratio = r[-SHORT:].std(ddof=1) / long if long > 0 else float("nan")
    return float(ratio), float(r[-1])


def components(history: pd.DataFrame) -> pd.DataFrame:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    rows = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        ratio, last = parts(group.sort_values("date"))
        if np.isfinite(ratio) and np.isfinite(last):
            rows[symbol] = (ratio, last)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["ratio", "last"])


def score(history: pd.DataFrame) -> pd.Series:
    """Centred sum of (1 - rank of the volatility ratio) and (1 - rank of the last return)."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see `strategies/t01_sma_crossover.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    comp = components(history)
    if len(comp) < 2:
        return pd.Series(dtype=float)
    s = (1.0 - comp["ratio"].rank(pct=True)) + (1.0 - comp["last"].rank(pct=True))
    sc = s - s.median()
    return sc[sc.abs() > 1e-12].astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F10 volatility-ratio reversal: insufficient history, flat, or at the median, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    ratio, last = parts(sub)
    side = "bullish" if sc[symbol] > 0 else "bearish"
    return (f"F10 volatility-ratio reversal (Alpha#34): 2/5-session volatility ratio {ratio:.2f}, "
            f"last session {last:+.1%}, {side}")
