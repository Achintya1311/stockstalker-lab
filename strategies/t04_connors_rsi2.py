"""T04: Connors RSI-2 (`cards/T04.yml`, `state/queue.md` port lane).

Connors and Alvarez (2009): price above its own 200-day SMA with a fast,
2-period RSI under 10 is a bullish mean-reversion setup (oversold inside an
uptrend); price below the 200-day SMA with RSI(2) over 90 is the bearish
mirror (overbought inside a downtrend). Unlike `strategies/t03_rsi_thresholds.py`'s
single-oscillator gate, this card is a conjunction of two conditions and is
asymmetric by construction: there is no bullish case below the 200-day SMA
and no bearish case above it, since the book's rule never states a view on
those crosswise combinations - both abstain (NaN, SPEC.md section 3), same
as the RSI sitting inside its own 10-90 band.

Within each active case the score is still continuous, same convention
every other card here uses: `score = (10 - rsi2) / 10` when bullish (0 at
rsi2=10, 1.0 at rsi2=0) and `score = -(rsi2 - 90) / 10` when bearish (0 at
rsi2=90, -1.0 at rsi2=100).

`_wilder_smooth`/`_rsi` are `strategies/t03_rsi_thresholds.py`'s own
vectorized Wilder-smoothing shape, copied (not imported) with `PERIOD = 2`
instead of 14 so this card stays standalone like every other
`strategies/t0*` card; `_sma` is `strategies/t02_golden_death_cross.py`'s
plain trailing-mean shape, same reason.

Catalog lists this card's horizon as day only (unlike T01/T03's "both"):
the book's own setup is a next-day mean-reversion trade inside a slow
trend filter, not a week-ahead one, so only a day-split experiment is
queued.

Per SPEC.md section 2, both the SMA and the RSI run on the adjusted close
series (`scripts.adjustments.compute_adjustment_factors`), so a split or
bonus inside either window doesn't masquerade as a real move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

RSI_PERIOD = 2
OVERSOLD, OVERBOUGHT = 10.0, 90.0
TREND_WINDOW = 200

# The 200-day SMA needs TREND_WINDOW rows; RSI(2)'s own minimum (period + 1
# = 3) is already satisfied once the slower trend filter is.
MIN_ROWS = TREND_WINDOW


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """See `strategies/t03_rsi_thresholds.py::_wilder_smooth` (itself
    mirroring `strategies/champion_v1.py`) for the derivation and the
    real-dataset performance note; same formula, copied rather than
    imported so this card stays standalone."""
    arr = values.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if arr.size > period:
        seed = arr[1 : period + 1].mean()
        tail = np.concatenate(([seed], arr[period + 1 :]))
        out[period:] = pd.Series(tail).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy()
    return pd.Series(out, index=values.index)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    avg_gain = _wilder_smooth(delta.clip(lower=0), period)
    avg_loss = _wilder_smooth(-delta.clip(upper=0), period)
    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    result[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return result


def _sma(close: pd.Series, window: int) -> float:
    return float(close.tail(window).mean())


def _connors_score(close_latest: float, sma_latest: float, rsi2_latest: float) -> float:
    """NaN means abstain (SPEC.md section 5): either the trend filter and
    the RSI(2) extreme disagree, or the RSI(2) extreme never fired."""
    if pd.isna(rsi2_latest) or pd.isna(sma_latest):
        return float("nan")
    if close_latest > sma_latest and rsi2_latest < OVERSOLD:
        return (OVERSOLD - rsi2_latest) / OVERSOLD
    if close_latest < sma_latest and rsi2_latest > OVERBOUGHT:
        return -(rsi2_latest - OVERBOUGHT) / OVERSOLD
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """One Connors-RSI-2 score per symbol with at least `MIN_ROWS` rows of
    history and both legs (trend filter, RSI(2) extreme) agreed; every
    other symbol abstains (left out of the returned Series, same
    convention every other card here uses)."""
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
        group = group.sort_values("date")
        close = group["adj_close"]
        close_latest = float(close.iloc[-1])
        sma_latest = _sma(close, TREND_WINDOW)
        rsi2_latest = _rsi(close, RSI_PERIOD).iloc[-1]
        value = _connors_score(close_latest, sma_latest, rsi2_latest)
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T04 Connors RSI-2: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    close = adjusted["adj_close"]
    close_latest = float(close.iloc[-1])
    sma_latest = _sma(close, TREND_WINDOW)
    rsi2_latest = _rsi(close, RSI_PERIOD).iloc[-1]
    value = _connors_score(close_latest, sma_latest, rsi2_latest)
    trend = "above" if close_latest > sma_latest else "below" if close_latest < sma_latest else "at"
    if pd.isna(value):
        return (
            f"T04 Connors RSI-2: close {trend} SMA{TREND_WINDOW}={sma_latest:.2f}, "
            f"RSI(2)={rsi2_latest:.2f} -> no agreed setup, abstain"
        )
    direction = "bullish (oversold in uptrend)" if value > 0 else "bearish (overbought in downtrend)"
    return (
        f"T04 Connors RSI-2: close {trend} SMA{TREND_WINDOW}={sma_latest:.2f}, "
        f"RSI(2)={rsi2_latest:.2f} -> score {value:+.4f} ({direction})"
    )
