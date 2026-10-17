"""Scoring: hits, market line, edge, directional move after costs, random baseline.

Per SPEC.md section 3 ("Scoring") and section 2 (universe, liquidity floor, futures).
A pick is a `date, symbol, side` row, where `side` is +1 (bullish) or -1 (bearish) -
the sign convention a strategy's `score(history)` is read under (SPEC.md section 5:
"one score per symbol; NaN means abstain").
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.yml"

# Cost model, SPEC.md section 3. A bullish pick is realised as a cash-delivery
# round trip (buy then sell); a bearish pick only through stock futures (section 2:
# "a short is realistic only through stock futures" - short covering has no delivery
# STT or stamp duty).
_DELIVERY_STT_EACH_SIDE = 0.001        # 0.1% STT, buy and sell
_DELIVERY_STAMP_DUTY = 0.00015         # 0.015% stamp duty
_FUTURES_STT_SELL_LEG = 0.0005         # 0.05% STT, sell leg only
_SLIPPAGE_EACH_WAY = 0.001             # 10 bps, entry and exit

DELIVERY_COST = 2 * _DELIVERY_STT_EACH_SIDE + _DELIVERY_STAMP_DUTY + 2 * _SLIPPAGE_EACH_WAY
FUTURES_COST = _FUTURES_STT_SELL_LEG + 2 * _SLIPPAGE_EACH_WAY


def load_universe_config(path: Path = UNIVERSE_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def universe_membership(dataset: pd.DataFrame, min_median_turnover_20d_cr: float | None = None) -> pd.DataFrame:
    """One row per (date, symbol) with `in_universe` (SPEC.md section 2).

    A symbol is in the universe on a date iff it has an active stock future that
    date AND its 20-day trailing median turnover is at least the configured floor.
    The trailing window ends at and includes the row's own date: that day's
    turnover is known at its own close, the same timing already used for its
    open-to-close move, so including it is not a look-ahead the way seeing a
    future day's price would be.
    """
    if min_median_turnover_20d_cr is None:
        min_median_turnover_20d_cr = load_universe_config()["min_median_turnover_20d_cr"]
    floor_rupees = min_median_turnover_20d_cr * 1e7  # 1 crore = 1e7 rupees

    df = dataset.sort_values(["symbol", "date"])[["date", "symbol", "has_future", "turnover"]].copy()
    df["median_turnover_20d"] = df.groupby("symbol")["turnover"].transform(
        lambda s: s.rolling(20, min_periods=20).median()
    )
    df["in_universe"] = df["has_future"].fillna(False) & (df["median_turnover_20d"] >= floor_rupees)
    return df[["date", "symbol", "in_universe"]].reset_index(drop=True)


def day_moves(dataset: pd.DataFrame) -> pd.DataFrame:
    """Open-to-close fractional move for every (date, symbol) row (SPEC.md section 1)."""
    out = dataset[["date", "symbol", "open", "close"]].copy()
    out["move"] = out["close"] / out["open"] - 1.0
    return out[["date", "symbol", "move"]]


def week_moves(dataset: pd.DataFrame) -> pd.DataFrame:
    """Monday-open-to-Friday-close fractional move, indexed by the week's first trading date.

    A week pick is made at the first trading date of its ISO week (Monday's open,
    SPEC.md section 1); its outcome is that same week's last trading date's close.
    """
    df = dataset[["date", "symbol", "open", "close"]].copy()
    iso = pd.to_datetime(df["date"]).dt.isocalendar()
    df["iso_year"], df["iso_week"] = iso["year"], iso["week"]
    keys = ["symbol", "iso_year", "iso_week"]

    first = df.loc[df.groupby(keys)["date"].idxmin(), [*keys, "date", "open"]]
    first = first.rename(columns={"date": "week_start", "open": "week_open"})
    last = df.loc[df.groupby(keys)["date"].idxmax(), [*keys, "close"]]
    last = last.rename(columns={"close": "week_close"})

    merged = first.merge(last, on=keys)
    merged["move"] = merged["week_close"] / merged["week_open"] - 1.0
    return merged[["week_start", "symbol", "move"]].rename(columns={"week_start": "date"})


def moves_for_horizon(dataset: pd.DataFrame, horizon: str) -> pd.DataFrame:
    if horizon == "day":
        return day_moves(dataset)
    if horizon == "week":
        return week_moves(dataset)
    raise ValueError(f"unknown horizon {horizon!r}; must be 'day' or 'week'")


def hit(move: pd.Series, side) -> pd.Series:
    """True iff the move is strictly in the picked direction (SPEC.md section 3).

    A flat move (close equals open) is always a miss: `move * side` is exactly 0
    for `side` in {+1, -1} whenever `move` is 0, which fails the strict `> 0` test
    regardless of which direction was picked.
    """
    return (move * side) > 0


def market_line(moves: pd.DataFrame, universe: pd.DataFrame, side: int) -> pd.Series:
    """Per-date share of the universe that moved in `side`'s direction (SPEC.md section 3).

    `side` = +1 (bullish: share of the universe that rose) or -1 (bearish: share
    that fell). Returned as a Series indexed by date.
    """
    in_universe = universe.loc[universe["in_universe"], ["date", "symbol"]]
    merged = moves.merge(in_universe, on=["date", "symbol"], how="inner")
    merged["moved_with_side"] = hit(merged["move"], side)
    return merged.groupby("date")["moved_with_side"].mean()


def edge(picks: pd.DataFrame, moves: pd.DataFrame, universe: pd.DataFrame) -> float:
    """SPEC.md section 3: hit rate minus market line, averaged over the same dates.

    `picks` must be pre-filtered to a single side's `date, symbol` rows - gates
    are "checked separately for each horizon and side" (SPEC.md section 6), and
    mixing sides here would average a hit rate against the wrong market line.
    """
    sides = picks["side"].unique()
    if len(sides) != 1:
        raise ValueError(f"edge() expects picks pre-filtered to a single side, got {sorted(sides)}")
    side = int(sides[0])

    joined = picks.merge(moves, on=["date", "symbol"], how="inner")
    joined["hit"] = hit(joined["move"], side)
    per_date_hit_rate = joined.groupby("date")["hit"].mean()
    per_date_market_line = market_line(moves, universe, side)

    aligned = per_date_hit_rate.to_frame("hit_rate").join(per_date_market_line.rename("market_line"), how="inner")
    if aligned.empty:
        raise ValueError("no overlapping dates between picks and the universe's market line")
    return float((aligned["hit_rate"] - aligned["market_line"]).mean())


def directional_move_after_costs(picks: pd.DataFrame, moves: pd.DataFrame) -> float:
    """SPEC.md section 3: mean of (move x side), after costs.

    Internal-only metric so a strategy can't be "right" through tiny moves while
    its misses are large. `picks` carries `date, symbol, side` (side may mix +1
    and -1 rows; each pick's own side picks its own cost model).
    """
    joined = picks.merge(moves, on=["date", "symbol"], how="inner")
    if joined.empty:
        raise ValueError("no picks with a known outcome")
    cost = np.where(joined["side"] > 0, DELIVERY_COST, FUTURES_COST)
    net = joined["move"] * joined["side"] - cost
    return float(net.mean())


def random_baseline_percentile(
    picks: pd.DataFrame,
    moves: pd.DataFrame,
    universe: pd.DataFrame,
    n_random: int = 1000,
    rng: np.random.Generator | None = None,
) -> float:
    """SPEC.md section 3: where the strategy's hit rate ranks among `n_random`
    random pick lists of the same size, drawn from the same universe on the
    same dates.

    One random list draws, for every (date, side) the real picks contain, the
    same count of symbols without replacement from that date's universe
    (falling back to the whole universe if it is smaller than the pick count).
    Hit/miss for a random draw uses the real market move for the drawn symbol
    under the real picks' side on that date. Returns the fraction of the
    `n_random` random lists' pooled hit rate that the real pooled hit rate
    strictly beats (0.0 = beats none, 1.0 = beats all of them).
    """
    rng = np.random.default_rng() if rng is None else rng

    joined = picks.merge(moves, on=["date", "symbol"], how="inner")
    if joined.empty:
        raise ValueError("no picks with a known outcome")
    real_hit_rate = float(hit(joined["move"], joined["side"]).mean())

    moves_by_date = {date: g.set_index("symbol")["move"] for date, g in moves.groupby("date")}
    universe_by_date = {
        date: g["symbol"].to_numpy() for date, g in universe.loc[universe["in_universe"]].groupby("date")
    }
    groups = picks.groupby(["date", "side"]).size()

    random_hit_rates = np.empty(n_random)
    for i in range(n_random):
        hits = 0
        n = 0
        for (date, side), k in groups.items():
            pool = universe_by_date.get(date)
            date_moves = moves_by_date.get(date)
            if pool is None or date_moves is None or len(pool) == 0:
                continue
            k = min(int(k), len(pool))
            drawn = rng.choice(pool, size=k, replace=False)
            drawn_moves = date_moves.reindex(drawn).dropna()
            hits += int(hit(drawn_moves, side).sum())
            n += len(drawn_moves)
        random_hit_rates[i] = (hits / n) if n else np.nan

    valid = random_hit_rates[~np.isnan(random_hit_rates)]
    if len(valid) == 0:
        raise ValueError("no random draw had any valid outcome")
    return float(np.mean(real_hit_rate > valid))
