"""Selecting one table's picks for one pick date (B9's "Then pick" step,
`state/queue.md`).

A production pick (live or dry) sits outside every backtest split (SPEC.md
section 4's train/validation/test/exam/live rows are about *scoring*
history, not about today's real decision), so there is nothing to
`engine.replay.authorize()` against here - only its causal truncation is
reused, at the session date itself (exclusive), which is exactly the data
a decision made before that session's open could honestly have seen.
"""

from __future__ import annotations

import pandas as pd

from engine.replay import truncate
from picks.chart import chart_for
from engine.scoring import load_universe_config, universe_membership


def picks_per_table(config: dict | None = None) -> int:
    return (config or load_universe_config())["picks_per_table"]


def eligible_symbols(dataset: pd.DataFrame, asof: str) -> set[str]:
    """Symbols in the universe as of `asof` (the previous close).

    `engine.scoring.universe_membership` lets a date's own turnover count
    toward its own membership - honest for a backtest reading that date's
    own close (SPEC.md section 2), but a pick made before the *next*
    session's open cannot know that next session's own turnover yet. Using
    `asof`'s row is the most recent universe reading a live decision could
    honestly have.
    """
    universe = universe_membership(dataset)
    return set(universe.loc[(universe["date"] == asof) & universe["in_universe"], "symbol"])


def select_side(scores: pd.Series, side: int, eligible: set[str], n: int) -> pd.Series:
    """Up to `n` eligible symbols on `side`, ranked by score magnitude.

    `side` = +1 keeps positive (bullish) scores, -1 keeps negative
    (bearish) ones - the same sign convention every other strategy reader
    in this repo uses (`engine.champion_report._side_picks`,
    `engine.selftest`). Abstaining symbols (dropped from `scores` already,
    per the strategy contract) and symbols outside `eligible` never appear.
    """
    scores = scores[scores.index.isin(eligible)]
    scores = scores[scores > 0] if side > 0 else scores[scores < 0]
    return scores.reindex(scores.abs().sort_values(ascending=False).index).head(n)


def pick_table(
    dataset: pd.DataFrame, strategy, strategy_id: str, session: str, side: int, asof: str, n: int | None = None
) -> list[dict]:
    """One table's picks for `session`: `[{"symbol", "strategy", "reasoning", "chart"?}, ...]`.

    `strategy` must expose `score(history) -> pd.Series` and
    `rules_fired(history, symbol) -> str` (SPEC.md section 5). Both are
    called on the same truncated-as-of-`session` history, so the reasoning
    text describes exactly the data the pick was actually made from.
    `strategy_id` (e.g. "champion_v1@v1") is written into each pick as-is -
    bullish and bearish sides of the same table can come from different
    strategies (`config/live_source.json` picks them independently).
    """
    n = picks_per_table() if n is None else n
    history = truncate(dataset, session)
    eligible = eligible_symbols(dataset, asof)
    scores = strategy.score(history)
    chosen = select_side(scores, side, eligible, n)
    picks = []
    for symbol in chosen.index:
        pick = {"symbol": symbol, "strategy": strategy_id, "reasoning": strategy.rules_fired(history, symbol)}
        chart = chart_for(history, symbol)
        if chart:
            pick["chart"] = chart
        picks.append(pick)
    return picks
