"""F17: volume-weighted close location versus 10-session high recency (`cards/F17.yml`, port lane).

Alpha#60 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 6 Nov 2026, SPEC.md section 5):

    (0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) - scale(rank(ts_argmax(close, 10))))))

Port: the last bar's close location value ((close - low) - (high - close)) / (high - low)
(same session, so no adjustment) times turnover (traded value in place of share volume,
as F09); `ts_argmax(close, 10)` as the position of the highest adjusted close in the
last 10 sessions, 1 for the oldest to 10 for the last (first occurrence on ties). Both
are percentile-ranked among the stocks scored that date; `scale` divides by the sum of
absolute values. raw = scale(rank(argmax)) - 2 x scale(rank(clv x turnover)). The
paper's form is mostly one-signed after scaling, so the port centres it by the date's
median. A close near the bar's high on heavy turnover, with an old 10-session high,
scores bearish; a close near the low with a fresh high bullish. A bar with high = low
abstains.

Cross-section: stocks with a future on the slice's last date (`strategies/alpha101_common.py`).
Cross-sectional through the ranks, the scaling and the median (`strategies/f17_close_location_recency_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors
from strategies.alpha101_common import centred, live_cross_section

WINDOW = 10
MIN_ROWS = WINDOW


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(close location value x turnover of the last bar, position 1..10 of the 10-session closing high)."""
    last = frame.iloc[-1]
    h, l, c = float(last["high"]), float(last["low"]), float(last["close"])
    clv = ((c - l) - (h - c)) / (h - l) if h > l else float("nan")
    close = frame["adj_close"].to_numpy(float)[-WINDOW:]
    return clv * float(last["turnover"]), float(np.argmax(close) + 1)


def components(history: pd.DataFrame) -> pd.DataFrame:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    rows = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        flow, pos = parts(group.sort_values("date"))
        if np.isfinite(flow) and np.isfinite(pos):
            rows[symbol] = (flow, pos)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["flow", "high_pos"])


def _scale(x: pd.Series) -> pd.Series:
    return x / x.abs().sum()


def score(history: pd.DataFrame) -> pd.Series:
    """scale(rank(high_pos)) - 2 scale(rank(flow)), median-centred."""
    if history.empty or "turnover" not in history.columns:
        return pd.Series(dtype=float)
    history = live_cross_section(history)
    if history.empty:
        return pd.Series(dtype=float)
    comp = components(history)
    if len(comp) < 2:
        return pd.Series(dtype=float)
    raw = _scale(comp["high_pos"].rank(pct=True)) - 2 * _scale(comp["flow"].rank(pct=True))
    return centred(raw)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F17 close location vs high recency: insufficient history, a flat bar, or at the median, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    last = sub.iloc[-1]
    h, l, c = float(last["high"]), float(last["low"]), float(last["close"])
    clv = ((c - l) - (h - c)) / (h - l)
    pos = int(np.argmax(sub["adj_close"].to_numpy(float)) + 1)
    ago = WINDOW - pos
    side = "bullish" if sc[symbol] > 0 else "bearish"
    when = "set in the last session" if ago == 0 else f"set {ago} sessions before the last"
    return (f"F17 close location vs high recency (Alpha#60): last close at {clv:+.2f} of its bar's range "
            f"(-1 low, +1 high), 10-session closing high {when}, {side}")
