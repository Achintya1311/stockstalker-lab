"""F08: seven-session reversal weighted by the yearly move (`cards/F08.yml`, port lane).

Alpha#19 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 5 Nov 2026, SPEC.md section 5):

    (-1 * sign((close - delay(close, 7)) + delta(close, 7))) * (1 + rank((1 + sum(returns, 250))))

`(close - delay(close, 7)) + delta(close, 7)` is twice the 7-session change, so only its
sign matters. On adjusted closes (SPEC.md section 2): score = -sign(7-session change) x
(1 + the stock's percentile rank, among the stocks scored that date, of its summed daily
close-to-close return over the last 250 sessions). A 7-session fall is bullish and a rise
bearish; the weight runs from just above 1 (worst yearly return) to 2 (best), so last
year's winners are faded hardest when they rise and backed hardest when they fall. An
unchanged 7-session close abstains (the paper's 0).

Cross-sectional only through the rank (`strategies/f08_weighted_reversal_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

LAG = 7
LONG = 250
MIN_ROWS = LONG + 1


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(7-session log change, summed simple daily return over 250 sessions) for one symbol."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    change = float(np.log(close[-1] / close[-1 - LAG]))
    yearly = float((close[1:] / close[:-1] - 1.0).sum())
    return change, yearly


def components(history: pd.DataFrame) -> pd.DataFrame:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    rows = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        change, yearly = parts(group.sort_values("date"))
        if np.isfinite(change) and np.isfinite(yearly) and change != 0.0:
            rows[symbol] = (change, yearly)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["change", "yearly"])


def score(history: pd.DataFrame) -> pd.Series:
    """Minus the sign of the 7-session change, times (1 + yearly-return percentile)."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see `strategies/t01_sma_crossover.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    comp = components(history)
    if comp.empty:
        return pd.Series(dtype=float)
    weight = 1.0 + (1.0 + comp["yearly"]).rank(pct=True)
    return (-np.sign(comp["change"]) * weight).astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F08 weighted reversal: insufficient history or unchanged over 7 sessions, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    change, yearly = parts(sub)
    side = "bullish" if sc[symbol] > 0 else "bearish"
    return (f"F08 weighted reversal (Alpha#19): {change:+.1%} over 7 sessions, yearly summed return "
            f"{yearly:+.0%} (weight {abs(sc[symbol]):.2f}), {side}")
