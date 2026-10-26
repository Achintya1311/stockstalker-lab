"""Q02: return-volume change correlation (`cards/Q02.yml`, `state/queue.md` port lane).

Alpha158's CORD feature (microsoft/qlib, MIT; feature list in
`third_party/qlib/loader.py`): the correlation of the daily price change ratio with
the log volume change ratio over a window. The lab's reading, on the adjusted close
and raw volume (SPEC.md section 2), over the last 20 sessions:

- x = close / previous close, y = log(volume / previous volume + 1), 20 pairs;
- rho = correlation(x, y): above 0 means up days came on rising volume and down
  days on falling volume (moves "confirmed" by volume);
- r20 = log(close / close 20 sessions back);
- score = rho x sign(r20). A confirmed rise is bullish, a confirmed fall bearish;
  an unconfirmed move scores the other way. No move, or a flat series, abstains.

This is the return form of Q01's level correlation (`research/diagnostics/q01.md`).
Only the last `MIN_ROWS` rows per symbol are read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
MIN_ROWS = WINDOW + 1


def parts(frame: pd.DataFrame) -> tuple[float, float]:
    """(rho, r20) on the last row of `frame`; rho is NaN when either series is flat."""
    close = frame["adj_close"].to_numpy(float)[-MIN_ROWS:]
    volume = frame["volume"].to_numpy(float)[-MIN_ROWS:]
    x = close[1:] / close[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.log(volume[1:] / volume[:-1] + 1.0)
    if not np.isfinite(y).all() or np.std(x) == 0.0 or np.std(y) == 0.0:
        rho = float("nan")
    else:
        rho = float(np.corrcoef(x, y)[0, 1])
    return rho, float(np.log(close[-1] / close[0]))


def _score(frame: pd.DataFrame) -> float:
    rho, r20 = parts(frame)
    if np.isnan(rho) or r20 == 0.0 or rho == 0.0:
        return float("nan")
    return rho * float(np.sign(r20))


def score(history: pd.DataFrame) -> pd.Series:
    """rho signed by the 20-session move, per symbol; flat or zero-move symbols abstain."""
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    history = history.sort_values("date").groupby("symbol", sort=False).tail(MIN_ROWS)
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        value = _score(group.sort_values("date"))
        if not np.isnan(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date").tail(MIN_ROWS)
    if len(sub) < MIN_ROWS:
        return "Q02 return-volume correlation: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    rho, r20 = parts(frame)
    detail = f"20-session move {r20:+.1%}, return-volume change correlation {rho:+.2f}"
    value = _score(frame)
    if np.isnan(value):
        return f"Q02 return-volume correlation: {detail}, abstain"
    kind = "confirmed" if rho > 0 else "unconfirmed"
    side = "bullish" if value > 0 else "bearish"
    return f"Q02 return-volume correlation: {detail}, {kind} move, {side}"
