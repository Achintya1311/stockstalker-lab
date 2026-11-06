"""F14: trend-switched fade (`cards/F14.yml`, port lane).

Alpha#24 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 6 Nov 2026, SPEC.md section 5):

    ((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) ||
      ((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05))
     ? (-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))

Port, on adjusted closes: g = (100-session mean now - the 100-session mean 100 sessions
ago) / the close 100 sessions ago. If g <= 5% (a flat or falling trend), score = minus
the distance of the close above its 100-session low, over the close (zero or bearish);
otherwise (a rising trend), score = minus the 3-session change, over the close (a short
reversal). The paper's price-unit terms are divided by the close so prices on different
scales compare; the raw two-branch value is kept (not centred), as the paper's form is
already two-signed. Needs 200 sessions, so most of 2015 is warm-up.

Per symbol except the cross-section filter (`strategies/alpha101_common.py`), so a stock's
score depends only on its own history (`strategies/f14_trend_switched_fade_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.alpha101_common import live_cross_section

MEAN = 100
LAG = 3
THRESHOLD = 0.05
MIN_ROWS = 2 * MEAN


def parts(close: np.ndarray) -> tuple[float, str, float]:
    """(trend g, branch "flat" or "rising", score) from the last 200 adjusted closes."""
    c = close[-MIN_ROWS:]
    g = (c[-MEAN:].mean() - c[:MEAN].mean()) / c[-MEAN - 1]
    last = c[-1]
    if g <= THRESHOLD:
        return float(g), "flat", float(-(last - c[-MEAN:].min()) / last)
    return float(g), "rising", float(-(last - c[-1 - LAG]) / last)


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    history = live_cross_section(history)
    if history.empty:
        return pd.Series(dtype=float)
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        close = group.sort_values("date")["adj_close"].to_numpy(float)
        if not (np.isfinite(close).all() and (close > 0).all()):
            continue
        s = parts(close)[2]
        if abs(s) > 1e-12:
            out[symbol] = s
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F14 trend-switched fade: insufficient history or no move, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    g, branch, s = parts(sub["adj_close"].to_numpy(float))
    side = "bullish" if s > 0 else "bearish"
    if branch == "flat":
        return (f"F14 trend-switched fade (Alpha#24): 100-session trend {g:+.1%} (at most +5%), close "
                f"{-s:.1%} above its 100-session low, {side}")
    return (f"F14 trend-switched fade (Alpha#24): 100-session trend {g:+.1%} (above +5%), "
            f"3-session change {-s:+.1%}, {side}")
