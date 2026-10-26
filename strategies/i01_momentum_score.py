"""I01: Nifty200 Momentum 30 score (`cards/I01.yml`, `state/queue.md` port lane).

`cards/catalog.csv`'s reading of the NSE Indices momentum score: z-scores of
the 6- and 12-month returns, each divided by volatility, averaged. NSE's
whitepaper names the ingredients (6- and 12-month price return, adjusted for
daily price volatility) but not the windows or weights, so the lab's reading
is declared here and in the card:

- r6 and r12: adjusted-close return over the last 126 and 252 sessions, up to
  the last visible close (no month is skipped; A03 is the skip-a-month card);
- sigma: population standard deviation of the last 252 daily log returns,
  annualised by sqrt(252);
- m6 = r6 / sigma, m12 = r12 / sigma;
- per date, each of m6 and m12 is z-scored across every symbol scored that
  date, and score = (z6 + z12) / 2.

NSE then maps the average z to a positive weight multiplier (1 + z, or
1 / (1 - z) when negative). That map is monotone and keeps z = 0 at 1, so the
sign and the ranking are the same as the average z, which is what is used:
positive is bullish, negative bearish.

The z-scores depend on which symbols are present on a date, like
`strategies/o04_order_block_composite.py`. `raw_ratios` is the per-symbol part
that depends only on that symbol's rows; the audit checks it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.adjustments import compute_adjustment_factors

SHORT, LONG = 126, 252
VOL_WINDOW = 252
MIN_ROWS = max(LONG, VOL_WINDOW) + 1


def _ratios(close: pd.Series) -> tuple[float, float]:
    tail = close.iloc[-MIN_ROWS:].to_numpy(dtype=float)
    if (tail <= 0).any():
        return float("nan"), float("nan")
    sigma = float(np.std(np.diff(np.log(tail[-(VOL_WINDOW + 1):])))) * np.sqrt(252)
    if sigma <= 0:
        return float("nan"), float("nan")
    last = tail[-1]
    r6 = last / tail[-1 - SHORT] - 1
    r12 = last / tail[-1 - LONG] - 1
    return r6 / sigma, r12 / sigma


def raw_ratios(history: pd.DataFrame) -> pd.DataFrame:
    """Columns m6, m12 per symbol; symbols with too little history or a flat
    series are left out."""
    empty = pd.DataFrame(columns=["m6", "m12"], dtype=float)
    if history.empty:
        return empty
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see
        # `strategies/t01_sma_crossover.py`'s identical prefilter).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return empty

    adjusted = compute_adjustment_factors(history)
    out: dict[str, tuple[float, float]] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        if len(group) < MIN_ROWS:
            continue
        m6, m12 = _ratios(group.sort_values("date")["adj_close"])
        if not (np.isnan(m6) or np.isnan(m12)):
            out[symbol] = (m6, m12)
    if not out:
        return empty
    return pd.DataFrame.from_dict(out, orient="index", columns=["m6", "m12"]).astype(float)


def _z(col: pd.Series) -> pd.Series:
    sd = col.std(ddof=0)
    if not sd > 0:
        return pd.Series(np.nan, index=col.index)
    return (col - col.mean()) / sd


def score(history: pd.DataFrame) -> pd.Series:
    """Average of the cross-sectional z-scores of m6 and m12. Needs at least
    two symbols with different readings; otherwise every symbol abstains."""
    ratios = raw_ratios(history)
    if len(ratios) < 2:
        return pd.Series(dtype=float)
    combined = (_z(ratios["m6"]) + _z(ratios["m12"])) / 2
    return combined.dropna().astype(float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    ratios = raw_ratios(history)
    scores = score(history)
    if symbol not in scores.index:
        return "I01 momentum score: insufficient history or cross-section, abstain"
    value = float(scores[symbol])
    direction = "bullish" if value > 0 else "bearish" if value < 0 else "neutral"
    m6, m12 = ratios.loc[symbol, "m6"], ratios.loc[symbol, "m12"]
    return (
        f"I01 momentum score: 6m return/vol {m6:+.2f}, 12m return/vol {m12:+.2f}, "
        f"average z {value:+.3f} across {len(scores)} symbols ({direction})"
    )
