"""A04: 52-week-high proximity (`cards/A04.yml`, `state/queue.md` port lane).

Ported from George and Hwang (2004, JF): rank stocks by how close their
current price sits to its own trailing `WINDOW_DAYS` high (approximating
52 weeks). The paper's own claim is that nearness to the 52-week high
predicts returns better than past return alone, and that this subsumes
most of standard 12-month price momentum - stocks near their high keep
outperforming, stocks far below it keep underperforming. Neither the
paper's own effect size nor its multi-month holding period is assumed to
transfer to a one-week NSE pick (SPEC.md section 5) - this module only
computes the signal; `cards/A04.yml`'s `status` moves to
`confirmed`/`refuted` once a real train replay's edge is in.

The catalog's own rule ("close / 52-week high: nearest to the high
bullish, farthest bearish") is a ratio in (0, 1], not directly signed. The
paper assigns sign via a cross-sectional decile sort (top decile by
nearness is bullish, bottom decile bearish) - but every other card on this
roster (and `engine.champion_report`/`engine.selftest`) reads a pick's
side from its own score's sign in absolute terms, not from where it ranks
against the rest of the universe that day. So this card centres the ratio
on each stock's own trailing high/low range instead: `score = 2 *
(close - low) / (high - low) - 1`. A close sitting exactly at the
52-week high scores +1 (most bullish); a close sitting exactly at the
52-week low scores -1 (most bearish); the midpoint of the stock's own
range scores 0. This is a deliberate adaptation (`cards/A04.yml`'s red
flags), not a literal replication of the paper's portfolio construction.

Per SPEC.md section 2, the rolling high/low/close are computed on the
adjusted close series (`scripts.adjustments.compute_adjustment_factors`),
so a split or bonus inside the window doesn't masquerade as a real price
move.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

WINDOW_DAYS = 252

MIN_ROWS = WINDOW_DAYS


def _range_score(close: pd.Series) -> float:
    window = close.iloc[-WINDOW_DAYS:]
    high = window.max()
    low = window.min()
    last = window.iloc[-1]
    if high == low:
        return 0.0
    nearness = (last - low) / (high - low)
    return float(2.0 * nearness - 1.0)


def score(history: pd.DataFrame) -> pd.Series:
    """One 52-week-high-proximity score per symbol with at least `MIN_ROWS` rows.

    A symbol with too little history, or a flat (high == low) trailing
    window, abstains or scores exactly 0.0 rather than falling back to a
    default that would masquerade as a real reading.
    """
    if history.empty:
        return pd.Series(dtype=float)

    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/champion_v1.py`'s identical prefilter): a symbol with
        # no F&O future anywhere in its visible history can never survive
        # the downstream universe restriction regardless of what it scores
        # here, so skipping it here avoids recomputing adjustment factors
        # over the full EQ series on every pick date.
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
        out[symbol] = _range_score(group["adj_close"])
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if len(sub) < MIN_ROWS:
        return "A04 52-week-high proximity: insufficient history, abstain"

    adjusted = compute_adjustment_factors(sub)
    window = adjusted["adj_close"].iloc[-WINDOW_DAYS:]
    high, low, last = window.max(), window.min(), window.iloc[-1]
    rscore = _range_score(adjusted["adj_close"])
    direction = "bullish" if rscore > 0 else "bearish" if rscore < 0 else "neutral"
    return (
        "A04 52-week-high proximity (George and Hwang 2004): "
        f"close {last:.2f} within trailing {WINDOW_DAYS}-day range [{low:.2f}, {high:.2f}] "
        f"-> range score {rscore:+.4f} ({direction})"
    )
