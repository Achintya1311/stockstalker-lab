"""Q01: price-volume divergence by correlation (`cards/Q01.yml`, `state/queue.md` port lane).

Alpha158's CORR feature (microsoft/qlib, MIT; feature list in
`third_party/qlib/loader.py`): the correlation of the close with log volume over a
window. The lab's reading, on the adjusted close and raw volume (SPEC.md section 2),
over the last 20 sessions:

- rho = correlation(close, log(volume + 1)); r20 = log(close / close 20 sessions back);
- r20 > 0 and rho < 0 (a rise while volume thins): bearish, score = rho;
- r20 < 0 and rho > 0 (a fall while volume thins): bullish, score = rho;
- otherwise abstain: volume grows with the move (rho has the move's sign), or
  there is no move.

So the score is rho itself whenever rho and the move disagree in sign, and its
size is how strongly volume dried up along the move. This is the correlation form of
the "volume does not confirm" idea T19 tests with OBV swing extremes.

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
    close = frame["adj_close"].to_numpy(float)
    logv = np.log(frame["volume"].to_numpy(float)[-WINDOW:] + 1.0)
    c = close[-WINDOW:]
    if np.std(c) == 0.0 or np.std(logv) == 0.0:
        rho = float("nan")
    else:
        rho = float(np.corrcoef(c, logv)[0, 1])
    return rho, float(np.log(close[-1] / close[-(WINDOW + 1)]))


def _score(frame: pd.DataFrame) -> float:
    rho, r20 = parts(frame)
    if np.isnan(rho) or not rho * r20 < 0:
        return float("nan")
    return rho


def score(history: pd.DataFrame) -> pd.Series:
    """Score for symbols whose 20-session move came on thinning volume; others abstain."""
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
        return "Q01 price-volume correlation: insufficient history, abstain"
    frame = compute_adjustment_factors(sub)
    rho, r20 = parts(frame)
    detail = f"20-session move {r20:+.1%}, close-volume correlation {rho:+.2f}"
    value = _score(frame)
    if np.isnan(value):
        return f"Q01 price-volume correlation: {detail}, abstain"
    side = "bearish (rise on thinning volume)" if value < 0 else "bullish (fall on thinning volume)"
    return f"Q01 price-volume correlation: {detail}, {side}"
