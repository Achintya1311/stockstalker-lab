"""F19: intraday body volatility plus body, faded (`cards/F19.yml`, port lane).

Alpha#18 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 10 Nov 2026, SPEC.md section 5):

    (-1 * rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open, 10))))

Port: the body (close - open) is a same-session quantity, read from the raw bar and
expressed in percent of that bar's close, so a 1% body is 1.0 and sits on the same scale
as the correlation term (the paper's price units put a typical body of a large US stock at
about 1 too; in returns the correlation would swamp the sum). raw = 5-session std of
|body| + the last body + the 10-session correlation of the adjusted close with the
adjusted open. Score = median(rank) - rank(raw) across the stocks scored that date: a large
up body after volatile bars, with closes tracking opens, bearish; the reverse bullish. A
stock without 10 sessions in the slice, or with a constant close or open over them,
abstains.

Cross-section: stocks with a future on the slice's last date (`strategies/alpha101_common.py`).
Cross-sectional through the final rank (`strategies/f19_body_volatility_fade_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.alpha101_common import centred, live_cross_section

VOL = 5
CORR = 10
MIN_ROWS = CORR


def raw_values(history: pd.DataFrame) -> pd.Series:
    """Alpha#18's inner sum per symbol (before the rank), on each symbol's last CORR sessions."""
    h = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    counts = h.groupby("symbol")["date"].count()
    h = h[h["symbol"].isin(counts.index[counts == MIN_ROWS])]
    if h.empty:
        return pd.Series(dtype=float)
    adj = compute_adjustment_factors(h.sort_values(["symbol", "date"]))
    adj = adj.assign(body=100.0 * (adj["close"] - adj["open"]) / adj["close"])
    out = {}
    for sym, g in adj.groupby("symbol", sort=False):
        body = g["body"].to_numpy(float)
        c = g["adj_close"].to_numpy(float)
        o = g["adj_open"].to_numpy(float)
        if not (np.isfinite(body).all() and np.isfinite(c).all() and np.isfinite(o).all()):
            continue
        if c.std() < 1e-12 or o.std() < 1e-12:
            continue
        vol = float(np.abs(body[-VOL:]).std(ddof=1))
        corr = float(np.corrcoef(c, o)[0, 1])
        out[sym] = vol + float(body[-1]) + corr
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    history = live_cross_section(history)
    if history.empty:
        return pd.Series(dtype=float)
    raw = raw_values(history)
    if len(raw) < 2:
        return pd.Series(dtype=float)
    return centred(-raw.rank(pct=True))


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F19 body volatility fade: insufficient history, flat prices or median stock, abstain"
    side = "bullish" if sc[symbol] > 0 else "bearish"
    raw = raw_values(live_cross_section(history))
    return (f"F19 body volatility fade (Alpha#18): body volatility + last body (in % of close) + 10-session "
            f"close-open correlation = {raw[symbol]:+.2f}, ranked {'low' if side == 'bullish' else 'high'} "
            f"across stocks, {side}")
