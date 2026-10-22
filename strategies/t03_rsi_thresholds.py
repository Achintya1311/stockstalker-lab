"""T03: RSI(14) 30/70 thresholds (`cards/T03.yml`, `state/queue.md` port lane).

Wilder's RSI (Wilder 1978), the most common retail oscillator rule
(`cards/catalog.csv`'s `prior_claim`): RSI(14) below 30 is "oversold"
(bullish), above 70 is "overbought" (bearish). Unlike `strategies/t01_sma_crossover.py`
and `strategies/t02_golden_death_cross.py`'s always-on trend spread, the
catalog's literal rule only takes a stance at the two extremes - a symbol
with RSI between 30 and 70 abstains (SPEC.md section 3: "selective
strategies may abstain on a date"), it is not scored as a weak signal in
either direction.

Within each active zone the score is still continuous, not a bare flag
(sign gives direction, magnitude gives conviction, same convention every
other card in this lab uses): `score = (30 - rsi) / 30` when oversold
(0 at the rsi=30 boundary, 1.0 at rsi=0) and `score = -(rsi - 70) / 30`
when overbought (0 at rsi=70, -1.0 at rsi=100) - symmetric by
construction since RSI is bounded to [0, 100].

`_wilder_smooth`/`_rsi` below are the same vectorized Wilder's-smoothing
shape `strategies/champion_v1.py` already uses (simple-mean seed, then
`ewm(alpha=1/period, adjust=False)` for the recursion) rather than a
per-row Python loop - `state/engine-issues.md`'s "real-data Replay run
took 1h45m+" entry documents why a per-row loop here would multiply into a
replay job several orders of magnitude slower against the real dataset.
Reimplemented locally (not imported from `champion_v1`) so this card
stays a standalone, independently testable module like every other
`strategies/t0*` card.

Catalog lists this card's horizon as "both": RSI needs no pick-date
knowledge, so one module serves both horizons the same way T01's does.

Per SPEC.md section 2, RSI runs on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`), so a split or bonus
inside the lookback window doesn't masquerade as a real momentum move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

PERIOD = 14
OVERSOLD, OVERBOUGHT = 30.0, 70.0

# Wilder's smoothing needs `period + 1` closes (one lost to `diff()`, then
# `period` more to seed the recursion) to produce its first non-NaN RSI.
MIN_ROWS = PERIOD + 1


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """See `strategies/champion_v1.py::_wilder_smooth` for the derivation
    and the real-dataset performance note; same formula, copied rather than
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


def _threshold_score(rsi_latest: float) -> float:
    """NaN means abstain (SPEC.md section 5): neither extreme fired."""
    if pd.isna(rsi_latest):
        return float("nan")
    if rsi_latest < OVERSOLD:
        return (OVERSOLD - rsi_latest) / OVERSOLD
    if rsi_latest > OVERBOUGHT:
        return -(rsi_latest - OVERBOUGHT) / OVERSOLD
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """One RSI-threshold score per symbol with at least `MIN_ROWS` rows of
    history and an RSI past one of the two thresholds; every other symbol
    abstains (left out of the returned Series, same convention every other
    card here uses)."""
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
        rsi_latest = _rsi(group["adj_close"], PERIOD).iloc[-1]
        value = _threshold_score(rsi_latest)
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T03 RSI(14) 30/70: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    rsi_latest = _rsi(adjusted["adj_close"], PERIOD).iloc[-1]
    value = _threshold_score(rsi_latest)
    if pd.isna(value):
        return f"T03 RSI(14) 30/70: RSI={rsi_latest:.2f} inside 30-70, abstain"
    direction = "bullish (oversold)" if value > 0 else "bearish (overbought)"
    return f"T03 RSI(14) 30/70: RSI={rsi_latest:.2f} -> score {value:+.4f} ({direction})"
