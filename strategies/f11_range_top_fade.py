"""F11: close near its 10-session high on an up bar, faded (`cards/F11.yml`, port lane).

Alpha#38 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 5 Nov 2026, SPEC.md section 5):

    ((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))

`Ts_Rank(close, 10)` is the rank of the last adjusted close among the last 10 (ties
averaged), divided by 10; `close / open` is the last bar's own ratio (same session, so no
adjustment). Both are percentile-ranked among the stocks scored that date. The paper's
product is one-signed (always bearish), so the port centres it: score = median(p) - p with
p = rank(ts_rank) x rank(close / open). A close at the top of its 10-session range after
an up bar scores bearish; a close at the bottom after a down bar bullish.

Cross-sectional through the ranks and the median (`strategies/f11_range_top_fade_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 10
MIN_ROWS = WINDOW


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(time-series rank of the last adjusted close in 10 sessions, last close / open)."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    last = close[-1]
    ts_rank = ((close < last).sum() + 0.5 * ((close == last).sum() + 1)) / len(close)
    bar = float(frame["close"].iloc[-1]) / float(frame["open"].iloc[-1])
    return float(ts_rank), bar


def components(history: pd.DataFrame) -> pd.DataFrame:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    rows = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        ts_rank, bar = parts(group.sort_values("date"))
        if np.isfinite(ts_rank) and np.isfinite(bar) and bar > 0:
            rows[symbol] = (ts_rank, bar)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["ts_rank", "bar"])


def score(history: pd.DataFrame) -> pd.Series:
    """Median-centred minus the product of the two ranks."""
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
    p = comp["ts_rank"].rank(pct=True) * comp["bar"].rank(pct=True)
    sc = p.median() - p
    return sc[sc.abs() > 1e-12].astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F11 range-top fade: insufficient history or at the median, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    ts_rank, bar = parts(sub)
    side = "bullish" if sc[symbol] > 0 else "bearish"
    return (f"F11 range-top fade (Alpha#38): close ranks {ts_rank:.2f} in its 10-session range, "
            f"last bar {bar - 1:+.1%} open to close, {side}")
