"""F09: volume-backed seven-session fall (`cards/F09.yml`, `state/queue.md` port lane).

Alpha#43 of Kakushadze (2016), "101 Formulaic Alphas" (X03; re-implemented from the
paper's formula, checked against its appendix A.1 on 5 Nov 2026, SPEC.md section 5):

    ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8)

The paper's `adv20` is average daily *dollar* volume while `volume` is shares, so the
port uses traded value (`turnover`, rupees; `docs/nse_formats.md`) for both: today's
turnover over the mean of the last 20 sessions' turnover (today's included). The price
term uses the 7-session log change of the adjusted close, so prices on different scales
rank together. `ts_rank(x, d)` is the rank of today's value among the last `d` values
(today's included), divided by `d`, so each factor lies in (0, 1].

The paper's product is one-signed. The port centres it by the median over the stocks
scored that date (score = raw - median), so an unusually heavy session after a 7-session
fall scores bullish and a light session after a rise scores bearish. Cross-sectional only
through the median (`strategies/f09_volume_backed_fall_audit.py`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

VOL_WINDOW = 20
LAG = 7
PRICE_WINDOW = 8
MIN_ROWS = 2 * VOL_WINDOW - 1  # 20 ratios, each over its own 20-session mean


def ts_rank_last(values: np.ndarray) -> float:
    """Rank of the last value among `values` (ties averaged), divided by len(values)."""
    last = values[-1]
    return float(((values < last).sum() + 0.5 * ((values == last).sum() + 1)) / len(values))


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(volume factor, price factor) for one symbol's rows in date order."""
    turnover = frame["turnover"].to_numpy(float)[-MIN_ROWS:]
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    mean20 = np.convolve(turnover, np.ones(VOL_WINDOW) / VOL_WINDOW, mode="valid")  # 20 values
    ratio = turnover[VOL_WINDOW - 1:] / mean20
    fall = -(np.log(close[LAG:]) - np.log(close[:-LAG]))[-PRICE_WINDOW:]
    return ts_rank_last(ratio), ts_rank_last(fall)


def _raw(frame: pd.DataFrame) -> float:
    if len(frame) < MIN_ROWS:
        return float("nan")
    t = frame["turnover"].to_numpy(float)[-MIN_ROWS:]
    if not np.isfinite(t).all() or (t <= 0).any():
        return float("nan")
    v, p = parts(frame)
    return v * p if np.isfinite(v * p) else float("nan")


def raw_scores(history: pd.DataFrame) -> pd.Series:
    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        value = _raw(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def score(history: pd.DataFrame) -> pd.Series:
    """Alpha#43's product minus its median over the stocks scored this date."""
    if history.empty or "turnover" not in history.columns:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see `strategies/t01_sma_crossover.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    raw = raw_scores(history)
    if len(raw) < 2:
        return pd.Series(dtype=float)
    sc = raw - raw.median()
    return sc[sc.abs() > 1e-12].astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "F09 volume-backed fall: insufficient history, no turnover, or at the median, abstain"
    sub = compute_adjustment_factors(history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS))
    v, p = parts(sub)
    side = "bullish" if sc[symbol] > 0 else "bearish"
    return (f"F09 volume-backed fall (Alpha#43): turnover rank {v:.2f} of 20 sessions, "
            f"7-session fall rank {p:.2f} of 8, {side}")
