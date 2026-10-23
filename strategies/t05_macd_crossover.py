"""T05: MACD crossover (`cards/T05.yml`, `state/queue.md` port lane).

Appel's MACD(12, 26, 9): the MACD line (12-day EMA minus 26-day EMA of the
adjusted close) crossing above its own 9-day signal line (the EMA of the
MACD line itself) is bullish; crossing below is bearish. Unlike
`strategies/t01_sma_crossover.py`'s always-on spread, the catalog's own
wording ("crossing above ... crossing below") is explicitly an event, not
a persisted state - this card only fires on the bar the two lines actually
cross and abstains on every other bar, including one where MACD already
sits well above (or below) its signal line without a fresh cross.

MACD's EMAs are the plain (non-Wilder) kind: `close.ewm(span=N,
adjust=False).mean()`, pandas' own recursive EMA seeded by the first
observation, published as MACD's own definition - a different smoothing
convention from `strategies/t03_rsi_thresholds.py`/
`strategies/t04_connors_rsi2.py`'s hand-seeded Wilder smoothing
(`alpha=1/period`, simple-mean seed). No custom seeding is needed here, so
this module calls pandas' `ewm` directly rather than copying a Wilder
helper.

Score is continuous within each firing case, same sign-gives-direction/
magnitude-gives-conviction convention every other card here uses:
`score = (macd_latest - signal_latest) / abs(close_latest)`, normalised by
the latest adjusted close since MACD is price-denominated (an absolute EMA
difference), not already a ratio the way T01/T03/T04's scores are. The
sign always matches the cross direction by construction once a fresh
cross is confirmed.

Needs no pick-date knowledge, so one module serves both horizons, the same
way `strategies/t01_sma_crossover.py` and `strategies/t03_rsi_thresholds.py`
already do.

Per SPEC.md section 2, both EMAs run on the adjusted close series
(`scripts.adjustments.compute_adjustment_factors`), so a split or bonus
inside either window doesn't masquerade as a real trend move.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

FAST, SLOW, SIGNAL = 12, 26, 9

# The slow EMA and the signal EMA on top of it need at least SLOW + SIGNAL
# rows before the signal line is a stable value rather than pandas' own
# unseeded-recursion value from only a handful of rows, plus one more row
# so a prior-bar MACD/signal pair exists to compare against for the cross
# itself.
MIN_ROWS = SLOW + SIGNAL + 1


def _macd_and_signal(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema_fast = close.ewm(span=FAST, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=SIGNAL, adjust=False).mean()
    return macd_line, signal_line


def _macd_score(
    close_latest: float,
    macd_latest: float,
    macd_prev: float,
    signal_latest: float,
    signal_prev: float,
) -> float:
    """NaN means abstain (SPEC.md section 5): no fresh cross on this bar."""
    if close_latest == 0 or pd.isna(macd_latest) or pd.isna(macd_prev) or pd.isna(signal_latest) or pd.isna(signal_prev):
        return float("nan")
    crossed_up = macd_prev <= signal_prev and macd_latest > signal_latest
    crossed_down = macd_prev >= signal_prev and macd_latest < signal_latest
    if not (crossed_up or crossed_down):
        return float("nan")
    return (macd_latest - signal_latest) / abs(close_latest)


def score(history: pd.DataFrame) -> pd.Series:
    """One MACD-crossover score per symbol with at least `MIN_ROWS` rows of
    history and a fresh cross on the latest bar; every other symbol
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
        close = group["adj_close"]
        macd_line, signal_line = _macd_and_signal(close)
        value = _macd_score(
            float(close.iloc[-1]),
            float(macd_line.iloc[-1]),
            float(macd_line.iloc[-2]),
            float(signal_line.iloc[-1]),
            float(signal_line.iloc[-2]),
        )
        if not pd.isna(value):
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "T05 MACD crossover: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    close = adjusted["adj_close"]
    macd_line, signal_line = _macd_and_signal(close)
    close_latest = float(close.iloc[-1])
    macd_latest, macd_prev = float(macd_line.iloc[-1]), float(macd_line.iloc[-2])
    signal_latest, signal_prev = float(signal_line.iloc[-1]), float(signal_line.iloc[-2])
    value = _macd_score(close_latest, macd_latest, macd_prev, signal_latest, signal_prev)
    if pd.isna(value):
        return (
            f"T05 MACD crossover: MACD={macd_latest:.4f}, signal={signal_latest:.4f} "
            f"(prior bar MACD={macd_prev:.4f}, signal={signal_prev:.4f}) -> no fresh cross, abstain"
        )
    direction = "bullish (crossed up)" if value > 0 else "bearish (crossed down)"
    return (
        f"T05 MACD crossover: MACD={macd_latest:.4f}, signal={signal_latest:.4f} "
        f"(prior bar MACD={macd_prev:.4f}, signal={signal_prev:.4f}) -> score {value:+.4f} ({direction})"
    )
