"""T06: Bollinger %B mean reversion (`cards/T06.yml`, `state/queue.md` port
lane).

Bollinger (2001): a 20-day SMA middle band plus/minus 2 standard
deviations. The literal catalog rule only takes a stance at the band
extremes - "close below the lower band bullish, above the upper band
bearish" - the same "only the extremes fire, else abstain" shape
`strategies/t03_rsi_thresholds.py` already uses, not an always-on spread
the way `strategies/t01_sma_crossover.py` is.

Standard deviation uses the population convention (`ddof=0`), matching
`strategies/a02_extreme_day_reversal.py`, `a05_max_effect.py`,
`a06_low_volatility.py`, `a07_high_volume_premium.py` and
`a09_gap_fade.py`'s own rolling-window choice, kept consistent across
this codebase's cards rather than picking pandas' sample-std default used
elsewhere for unrelated windows.

Score is %B-based, continuous within each firing case: `-pctB` when
bullish (0 at the lower-band boundary, growing positive further below)
and `1 - pctB` when bearish (0 at the upper-band boundary, growing
negative further above) - both the same linear expression, so sign
always matches firing direction by construction.

Catalog horizon is "day" only (unlike T01/T03/T05's "both"), so only a
day-split experiment is queued for this card.

Per SPEC.md section 2, the SMA, std and %B all run on the adjusted close
series (`scripts.adjustments.compute_adjustment_factors`), so a split or
bonus inside the 20-day window doesn't masquerade as a real price move.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
SIGMA_MULT = 2

# The 20-day SMA and std both need at least WINDOW rows before they are
# stable values rather than pandas' own partial-window reading. Unlike
# T05's cross-event card, no extra prior-bar row is needed - this card
# reads the latest bar's %B directly, not a change in it.
MIN_ROWS = WINDOW


def _pctb(close: pd.Series) -> float:
    """%B of the latest bar, or NaN if the bands collapse to one price."""
    window = close.iloc[-WINDOW:]
    middle = float(window.mean())
    sigma = float(window.std(ddof=0))
    band_width = SIGMA_MULT * sigma
    if band_width == 0:
        return float("nan")
    upper = middle + band_width
    lower = middle - band_width
    close_latest = float(close.iloc[-1])
    return (close_latest - lower) / (upper - lower)


def _bollinger_score(pctb: float) -> float:
    """NaN means abstain (SPEC.md section 5): price inside the bands."""
    if pd.isna(pctb):
        return float("nan")
    if pctb < 0:
        return -pctb
    if pctb > 1:
        return 1 - pctb
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """One Bollinger-%B score per symbol with at least `MIN_ROWS` rows of
    history and a latest close outside the bands; every other symbol
    abstains (left out of the returned Series, same convention every
    other card here uses)."""
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
        value = _bollinger_score(_pctb(close))
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T06 Bollinger %B: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    close = adjusted["adj_close"]
    pctb = _pctb(close)
    value = _bollinger_score(pctb)
    if pd.isna(value):
        pctb_str = "undefined (flat bands)" if pd.isna(pctb) else f"{pctb:.4f}"
        return f"T06 Bollinger %B: %B={pctb_str} -> inside the bands, abstain"
    direction = "bullish (below lower band)" if value > 0 else "bearish (above upper band)"
    return f"T06 Bollinger %B: %B={pctb:.4f} -> score {value:+.4f} ({direction})"
