"""T09: Supertrend, ATR(10) x 3 (`cards/T09.yml`, `state/queue.md` port lane).

Olivier Seban's Supertrend, the most common ATR-based trend line in
Indian retail technical analysis (`cards/catalog.csv`'s `prior_claim`):
close above the recursive Supertrend line is bullish, below is bearish -
always-on, like `strategies/t01_sma_crossover.py`, not selective like
T03/T04/T07.

Unlike every earlier `t0*` card, the line itself cannot be computed with
a single vectorised `ewm()` call: each day's final upper/lower band only
ever ratchets toward price, and the line sticks to whichever band it was
already tracking until price closes through it - a path-dependent
recursion against the PREVIOUS day's own resolved state, not a
fixed-weight decay. `_supertrend_line` below runs a plain Python loop,
but only over the fixed-size trailing `MIN_ROWS` window `score()` hands
it per symbol per call, the same bounded-tail convention T06/T07/T08
already use (`state/engine-issues.md`'s "Replay took 1h45m+" entry) -
see `cards/T09.yml`'s rules_plain for the full derivation and why this
loop's cost does not multiply the way a full-history loop would.

Score is continuous: `(close - line) / abs(line)`, already carrying the
correct sign for both direction and conviction by construction (the line
only ever sits at or below a bullish close, at or above a bearish one),
the same sign-gives-direction convention every other card here uses.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

ATR_PERIOD = 10
MULTIPLIER = 3.0
WARMUP = 50
# First valid ATR index (0-indexed) is ATR_PERIOD, per `_wilder_smooth`'s
# "out[period:] filled" convention (copied from `t03_rsi_thresholds.py`,
# itself copied from `champion_v1.py`). WARMUP more rows let the
# band-ratchet recursion run far enough past that seed that its
# arbitrary starting side has washed out (cards/T09.yml's red_flags).
MIN_ROWS = ATR_PERIOD + WARMUP


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """See `strategies/champion_v1.py::_wilder_smooth` for the derivation
    and the real-dataset performance note; same formula, copied rather
    than imported so this card stays standalone."""
    arr = values.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if arr.size > period:
        seed = arr[1 : period + 1].mean()
        tail = np.concatenate(([seed], arr[period + 1 :]))
        out[period:] = pd.Series(tail).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy()
    return pd.Series(out, index=values.index)


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """`close` is each row's OWN close shifted by one for the prior-close
    terms; row 0's prior close falls back to its own close (so its true
    range is just `high[0]-low[0]`), which is harmless - `_wilder_smooth`'s
    seed (`arr[1:period+1].mean()`) never reads index 0 at all, so this
    approximation at row 0 is discarded identically to how T03's RSI
    discards the row `diff()` loses."""
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    return np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))


def _supertrend_line(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int, multiplier: float) -> np.ndarray:
    """One Supertrend-line value per row; NaN before the first valid ATR
    (row index < `period`). See `cards/T09.yml`'s rules_plain for the
    four-branch recursion this implements."""
    n = len(close)
    tr = _true_range(high, low, close)
    atr = _wilder_smooth(pd.Series(tr), period).to_numpy()

    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    start = period
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    line = np.full(n, np.nan)

    if start >= n:
        return line

    final_upper[start] = basic_upper[start]
    final_lower[start] = basic_lower[start]
    # Arbitrary seed (cards/T09.yml's red_flags): side is picked by which
    # band sits on the same side as the day's own midpoint. WARMUP more
    # rows of recursion wash this choice out before `score()` ever reads
    # the final bar.
    line[start] = final_lower[start] if close[start] >= hl2[start] else final_upper[start]

    for i in range(start + 1, n):
        final_upper[i] = (
            basic_upper[i]
            if (basic_upper[i] < final_upper[i - 1]) or (close[i - 1] > final_upper[i - 1])
            else final_upper[i - 1]
        )
        final_lower[i] = (
            basic_lower[i]
            if (basic_lower[i] > final_lower[i - 1]) or (close[i - 1] < final_lower[i - 1])
            else final_lower[i - 1]
        )
        if line[i - 1] == final_upper[i - 1]:
            line[i] = final_upper[i] if close[i] <= final_upper[i] else final_lower[i]
        else:
            line[i] = final_lower[i] if close[i] >= final_lower[i] else final_upper[i]

    return line


def _latest_score(high: pd.Series, low: pd.Series, close: pd.Series) -> float:
    """`high`/`low`/`close` must already be the trailing `MIN_ROWS` rows,
    sorted by date. NaN means abstain: insufficient history (callers
    filter this before calling), or the line sits exactly at the close
    (undefined direction; vanishingly rare with real prices)."""
    line = _supertrend_line(high.to_numpy(), low.to_numpy(), close.to_numpy(), ATR_PERIOD, MULTIPLIER)
    latest_line = line[-1]
    latest_close = float(close.iloc[-1])
    if pd.isna(latest_line) or latest_line == 0:
        return float("nan")
    value = (latest_close - latest_line) / abs(latest_line)
    return float("nan") if value == 0 else value


def score(history: pd.DataFrame) -> pd.Series:
    """One Supertrend score per symbol with at least `MIN_ROWS` rows of
    history; everything else abstains (left out of the returned Series,
    same convention every other card here uses)."""
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)

    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        group = group.sort_values("date").tail(MIN_ROWS)
        value = _latest_score(group["adj_high"], group["adj_low"], group["adj_close"])
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T09 Supertrend: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub).tail(MIN_ROWS)
    value = _latest_score(adjusted["adj_high"], adjusted["adj_low"], adjusted["adj_close"])
    if pd.isna(value):
        return "T09 Supertrend: line undefined or at the close, abstain"
    direction = "bullish (close above the Supertrend line)" if value > 0 else "bearish (close below the Supertrend line)"
    return f"T09 Supertrend: score {value:+.4f} ({direction})"
