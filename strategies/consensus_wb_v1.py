"""consensus_wb_v1: week-bearish consensus of three near-independent strategies (P2, `state/queue.md`).

`cards/CONSENSUS_WB_V1.yml`. The go-live track's P2 item: a rank-average of the best train strategies for
one table, drawn from different families, on the idea that weak, unrelated signals can add up to more
than any one of them. For the week-bearish table the members are the three train readings that clear
the provisional rule's letter there and barely overlap each other (daily top-5 Jaccard 0.4-6.8%,
`research/diagnostics/t15.md`):

- `strategies.d02_stock_pcr_contrarian`: extreme-low put/call OI ratio (options positioning).
- `strategies.a01_weekly_reversal`: last week's winners fade (price reversal).
- `strategies.t15_adx_regime`: strong downtrend by ADX (trend strength).

Each member is imported, never copied, and scored on the same `history`. Per member, each symbol's
bearish strength (minus its score) is ranked across the symbols that member read that date
(`rank(pct=True)`), so the strongest bearish reading scores 1 and the strongest bullish reading the
lowest. A member that abstains on a symbol counts as neutral (0.5), not as missing: D02 fires on only a
few stocks a date, and skipping it would let a lone D02 reading of 1.0 outrank a stock all three members
agree on. The consensus is the mean of the three, and only symbols with a mean above 0.5 (net bearish)
are returned, as `score = -2 * (mean - 0.5)`, so this card fills the bearish table only.

The score depends on which peers are present (ranking), as in `strategies/o04_order_block_composite.py`;
`strategies/consensus_wb_v1_audit.py` checks that each member's own reading of a symbol is unchanged when
another symbol's history changes.
"""

from __future__ import annotations

import pandas as pd

from strategies import a01_weekly_reversal, d02_stock_pcr_contrarian, t15_adx_regime

MEMBERS = {
    "d02c": d02_stock_pcr_contrarian,
    "a01": a01_weekly_reversal,
    "t15": t15_adx_regime,
}
NEUTRAL = 0.5


def member_scores(history: pd.DataFrame) -> pd.DataFrame:
    """Each member's raw score per symbol (columns = member names); NaN where a member abstains."""
    return pd.DataFrame({name: module.score(history) for name, module in MEMBERS.items()})


def combine(readings: pd.DataFrame) -> pd.Series:
    """Mean bearish rank per symbol, abstentions as neutral. Pure function of `readings`."""
    if readings.empty:
        return pd.Series(dtype=float)
    ranks = pd.DataFrame(
        {name: (-readings[name]).rank(pct=True) for name in readings.columns}, index=readings.index
    )
    return ranks.fillna(NEUTRAL).mean(axis=1)


def _scores_from_mean(mean_rank: pd.Series) -> pd.Series:
    bearish = mean_rank[mean_rank > NEUTRAL]
    return (-2.0 * (bearish - NEUTRAL)).astype(float)


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return _scores_from_mean(combine(member_scores(history)))


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    readings = member_scores(history)
    mean_rank = combine(readings)
    if symbol not in mean_rank.index:
        return "consensus_wb_v1: no member read this stock, abstain"
    row = readings.loc[symbol]
    voted = [name for name in MEMBERS if pd.notna(row.get(name))]
    if mean_rank[symbol] <= NEUTRAL:
        return (
            f"consensus_wb_v1: mean bearish rank {mean_rank[symbol]:.2f} from {len(voted)}/3 members "
            f"({'+'.join(voted) or 'none'}) is not above neutral, abstain"
        )
    value = float(_scores_from_mean(mean_rank)[symbol])
    return (
        f"consensus_wb_v1 (week-bearish consensus of D02 contrarian, A01 reversal, T15 ADX): mean bearish "
        f"rank {mean_rank[symbol]:.2f} from {len(voted)}/3 members ({'+'.join(voted)}) across "
        f"{len(mean_rank)} stocks -> score {value:+.3f} (bearish)"
    )
