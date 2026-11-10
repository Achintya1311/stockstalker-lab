"""consensus_dbu_v1: day-bullish consensus of four near-independent strategies (P2, `state/queue.md`).

`cards/CONSENSUS_DBU_V1.yml`. The day-bullish counterpart of `strategies/consensus_wb_v1.py` and
`strategies/consensus_db_v1.py`, with the same combination rule (imported, not copied): per member,
strength ranked across the stocks it read that date, abstention counted as neutral (0.5), mean of the
members, stocks above 0.5 kept. Here the strength is bullish: `combine` ranks bearish strength (minus
the score), so it is called on the negated readings, and the kept stocks are scored
`+2 * (mean - 0.5)`. Bullish table only.

Members are the four day-bullish train readings with a top-5 edge interval above 0 and at least 4 of 6
positive years under AB's edge-only bullish rule (26 Oct 2026), which share 2-19% of their daily top
five with each other (`research/diagnostics/f14.md`). D01C (+2.54 train) is left out: its validation
answer was -1.05.

- `strategies.t04_connors_rsi2`: RSI(2) below 10 above the 200-day mean (oversold in an uptrend).
- `strategies.q06_wick_balance`: long lower wick against the upper wick (intraday rejection of lows).
- `strategies.f14_trend_switched_fade`: largest 3-session fall inside a rising 100-session trend.
- `strategies.t10_nr7_narrow_range`: narrowest range of 7 days, read with the 20/50 trend.

The score depends on which peers are present (ranking); `strategies/consensus_dbu_v1_audit.py` checks
that each member's own reading of a symbol is unchanged when another symbol's history changes.
"""

from __future__ import annotations

import pandas as pd

from strategies import f14_trend_switched_fade, q06_wick_balance, t04_connors_rsi2, t10_nr7_narrow_range
from strategies.consensus_wb_v1 import NEUTRAL, combine

MEMBERS = {
    "t04": t04_connors_rsi2,
    "q06": q06_wick_balance,
    "f14": f14_trend_switched_fade,
    "t10nr7": t10_nr7_narrow_range,
}


def member_scores(history: pd.DataFrame) -> pd.DataFrame:
    """Each member's raw score per symbol (columns = member names); NaN where a member abstains."""
    return pd.DataFrame({name: module.score(history) for name, module in MEMBERS.items()})


def bullish_mean_rank(readings: pd.DataFrame) -> pd.Series:
    """Mean bullish rank per symbol, abstentions as neutral: the imported rule on negated readings."""
    if readings.empty:
        return pd.Series(dtype=float)
    return combine(-readings)


def _scores_from_mean(mean_rank: pd.Series) -> pd.Series:
    bullish = mean_rank[mean_rank > NEUTRAL]
    return (2.0 * (bullish - NEUTRAL)).astype(float)


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return _scores_from_mean(bullish_mean_rank(member_scores(history)))


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    readings = member_scores(history)
    mean_rank = bullish_mean_rank(readings)
    if symbol not in mean_rank.index:
        return "consensus_dbu_v1: no member read this stock, abstain"
    row = readings.loc[symbol]
    voted = [name for name in MEMBERS if pd.notna(row.get(name))]
    if mean_rank[symbol] <= NEUTRAL:
        return (
            f"consensus_dbu_v1: mean bullish rank {mean_rank[symbol]:.2f} from {len(voted)}/4 members "
            f"({'+'.join(voted) or 'none'}) is not above neutral, abstain"
        )
    value = float(_scores_from_mean(mean_rank)[symbol])
    return (
        f"consensus_dbu_v1 (day-bullish consensus of T04 RSI-2, Q06 wick balance, F14 trend-switched fade, "
        f"T10 NR7): mean bullish rank {mean_rank[symbol]:.2f} from {len(voted)}/4 members ({'+'.join(voted)}) "
        f"across {len(mean_rank)} stocks -> score {value:+.3f} (bullish)"
    )
