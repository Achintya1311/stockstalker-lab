"""H04: same-calendar-month return seasonality (`cards/H04.yml`, `state/queue.md` port lane).

Heston and Sadka (2008), "Seasonality in the cross-section of stock returns", Journal
of Financial Economics 87(2) (replicated in Open Source Asset Pricing, X05): stocks
that earned high returns in a given calendar month in earlier years tend to earn
high returns in that month again. Here, on split/bonus-adjusted closes:

- target month = the month of the next Monday after the last visible date (the pick
  week; a Friday last row gives the following Monday);
- each earlier year's return for that calendar month = month-end close over the
  previous month-end close, using only months that ended on or before the last
  visible date;
- score = mean of those returns over all earlier years; at least `MIN_YEARS` years
  are required, otherwise the stock abstains (2015 and 2016 are warm-up on train).

Highest bullish, lowest bearish. Each stock uses only its own rows.
"""

from __future__ import annotations

import pandas as pd

from scripts.adjustments import compute_adjustment_factors

MIN_YEARS = 2


def monthly_returns(dates: pd.Series, adj_close: pd.Series) -> pd.Series:
    """Month-end-to-month-end returns, indexed by period; only calendar-complete months (month ended before last row)."""
    s = pd.Series(adj_close.to_numpy(dtype=float), index=pd.to_datetime(dates.to_numpy()))
    s = s.sort_index()
    last_day = s.index[-1]
    month_end = s.groupby(s.index.to_period("M")).last()
    month_end = month_end.iloc[:-1] if last_day.to_period("M") == month_end.index[-1] else month_end
    return month_end.pct_change().dropna()


def target_month(last_date: pd.Timestamp) -> int:
    nxt = last_date + pd.Timedelta(days=(7 - last_date.weekday()) % 7 or 7)  # next Monday
    return int(nxt.month)


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    if "has_future" in history.columns:
        # Performance prefilter, not a correctness check (see `strategies/a03_momentum_12_1.py`).
        eligible = history.loc[history["has_future"], "symbol"].unique()
        history = history[history["symbol"].isin(eligible)]
        if history.empty:
            return pd.Series(dtype=float)
    month = target_month(pd.Timestamp(history["date"].max()))
    adjusted = compute_adjustment_factors(history)
    out: dict[str, float] = {}
    for symbol, group in adjusted.groupby("symbol", sort=False):
        group = group.sort_values("date")
        if len(group) < 40:
            continue
        rets = monthly_returns(group["date"], group["adj_close"])
        same = rets[[p.month == month for p in rets.index]]
        if len(same) < MIN_YEARS:
            continue
        value = float(same.mean())
        if abs(value) > 1e-12:
            out[symbol] = value
    return pd.Series(out, dtype=float)


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    sc = score(history)
    if symbol not in sc.index:
        return "H04 return seasonality: fewer than 2 earlier years for the target month, abstain"
    value = float(sc[symbol])
    side = "bullish" if value > 0 else "bearish"
    return (
        f"H04 return seasonality (Heston and Sadka 2008): mean return in this calendar month over earlier years "
        f"{value:+.2%}, {side}"
    )
