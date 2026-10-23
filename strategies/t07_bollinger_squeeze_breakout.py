"""T07: Bollinger squeeze breakout (`cards/T07.yml`, `state/queue.md` port
lane).

Bollinger (2001): the same 20-day SMA +/- 2 standard deviation bands
`strategies/t06_bollinger_pctb.py` already ports, but read as a
breakout/continuation signal, not a mean-reversion one. The catalog's
literal rule has two conditions, both required: "band width at a 6-month
low" (a volatility squeeze), "then close outside a band" (the break),
"direction of the break" (bullish on an upper-band break, bearish on a
lower-band break - the opposite sign mapping from T06's mean-reversion
read of the identical bands).

"Then" is read as "on the bar where both conditions are simultaneously
true," not "a break some unspecified number of bars after a squeeze" -
every other card in this codebase reads its signal off a single bar
handed by `history`, with no cross-bar state, and `engine.replay` gives
no mechanism to remember a squeeze seen on an earlier call. See
`cards/T07.yml`'s rules_plain for the full reasoning and the red flag
this choice carries if the card shows no edge.

Standard deviation uses the population convention (`ddof=0`), matching
T06 and the `a0*` cards' own rolling-window choice.

Score is continuous within each firing case: `pctB - 1` when bullish (0
at the upper-band boundary, growing positive the further above) and
`pctB` when bearish (already negative since %B < 0 there, growing more
negative the further below) - both monotonic in distance from the
triggering band, sign always matches firing direction by construction.

Catalog horizon is "week" only (unlike T01/T03/T05's "both"), so only a
week-split experiment is queued for this card.

Per SPEC.md section 2, the SMA, std, %B and the width-percentile window
all run on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`), so a split or bonus
inside either rolling window doesn't masquerade as a real volatility or
price move.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW = 20
SIGMA_MULT = 2
WIDTH_LOOKBACK = 126

# The width series needs WINDOW rows per point and WIDTH_LOOKBACK points
# to compare the latest one against, so the squeeze condition needs
# WINDOW + WIDTH_LOOKBACK - 1 rows of close before it reads a stable
# value rather than a partial window. Only the trailing MIN_ROWS rows of
# close are ever used, so this stays a fixed-size computation regardless
# of how much history the replay has accumulated by a given date
# (`state/engine-issues.md`'s "Replay took 1h45m+" WATCH entry).
MIN_ROWS = WINDOW + WIDTH_LOOKBACK - 1


def _pctb_and_squeeze(close: pd.Series) -> tuple[float, bool]:
    """%B of the latest bar and whether today's band width is at (or
    below, for floating-point safety) its own trailing WIDTH_LOOKBACK
    low. Returns (NaN, False) if the width series itself isn't fully
    defined over the lookback window (e.g. a flat sub-window collapses
    the band to zero width)."""
    tail = close.iloc[-MIN_ROWS:]
    middle = tail.rolling(WINDOW, min_periods=WINDOW).mean()
    sigma = tail.rolling(WINDOW, min_periods=WINDOW).std(ddof=0)
    band_width = SIGMA_MULT * sigma

    width_pct = (2 * band_width) / middle
    width_pct = width_pct.where(middle != 0)

    latest_width = width_pct.iloc[-1]
    lookback = width_pct.iloc[-WIDTH_LOOKBACK:]
    if pd.isna(latest_width) or lookback.isna().any():
        return float("nan"), False

    squeeze = bool(latest_width <= lookback.min())

    band_width_latest = float(band_width.iloc[-1])
    if band_width_latest == 0:
        return float("nan"), squeeze

    middle_latest = float(middle.iloc[-1])
    close_latest = float(close.iloc[-1])
    upper = middle_latest + band_width_latest
    lower = middle_latest - band_width_latest
    pctb = (close_latest - lower) / (upper - lower)
    return pctb, squeeze


def _squeeze_breakout_score(pctb: float, squeeze: bool) -> float:
    """NaN means abstain (SPEC.md section 5): no squeeze, or squeezed but
    no break on this bar."""
    if not squeeze or pd.isna(pctb):
        return float("nan")
    if pctb > 1:
        return pctb - 1
    if pctb < 0:
        return pctb
    return float("nan")


def score(history: pd.DataFrame) -> pd.Series:
    """One squeeze-breakout score per symbol with at least `MIN_ROWS` rows
    of history, today's band width at its own trailing 126-session low,
    and a latest close outside the bands on that same bar; every other
    symbol abstains (left out of the returned Series, same convention
    every other card here uses)."""
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
        pctb, squeeze = _pctb_and_squeeze(close)
        value = _squeeze_breakout_score(pctb, squeeze)
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T07 Bollinger squeeze breakout: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    close = adjusted["adj_close"]
    pctb, squeeze = _pctb_and_squeeze(close)
    value = _squeeze_breakout_score(pctb, squeeze)
    if pd.isna(value):
        if not squeeze:
            return "T07 Bollinger squeeze breakout: band width not at its 126-session low, abstain"
        pctb_str = "undefined (flat bands)" if pd.isna(pctb) else f"{pctb:.4f}"
        return f"T07 Bollinger squeeze breakout: squeeze held, %B={pctb_str} -> inside the bands, abstain"
    direction = "bullish (break above upper band)" if value > 0 else "bearish (break below lower band)"
    return f"T07 Bollinger squeeze breakout: squeeze held, %B={pctb:.4f} -> score {value:+.4f} ({direction})"
