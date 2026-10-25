"""consensus_db_v1: day-bearish consensus of three near-independent strategies (P2, `state/queue.md`).

`cards/CONSENSUS_DB_V1.yml`. The day-bearish counterpart of `strategies/consensus_wb_v1.py`, with the
same combination rule (imported from there, not copied): per member, bearish strength ranked across the
stocks it read that date, abstention counted as neutral (0.5), mean of the three, stocks above 0.5
scored bearish. Bearish table only.

Members are the three day-bearish readings that clear the provisional rule's letter on train (positive
edge and positive directional move after costs) and overlap each other least (daily top-5 Jaccard
2.2-10.9%, `state/journal.md` 2026-10-25T1825Z):

- `strategies.e2a_a02_crowded`: A02's extreme-day fade kept only where futures OI rose (confluence).
- `strategies.d01c_oi_fade`: D01's price-and-OI classification, faded.
- `strategies.a09_gap_fade`: gap fade.
"""

from __future__ import annotations

import pandas as pd

from strategies import a09_gap_fade, d01c_oi_fade, e2a_a02_crowded
from strategies.consensus_wb_v1 import NEUTRAL, _scores_from_mean, combine

MEMBERS = {
    "e2a": e2a_a02_crowded,
    "d01c": d01c_oi_fade,
    "a09": a09_gap_fade,
}


def member_scores(history: pd.DataFrame) -> pd.DataFrame:
    """Each member's raw score per symbol (columns = member names); NaN where a member abstains."""
    return pd.DataFrame({name: module.score(history) for name, module in MEMBERS.items()})


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return _scores_from_mean(combine(member_scores(history)))


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    readings = member_scores(history)
    mean_rank = combine(readings)
    if symbol not in mean_rank.index:
        return "consensus_db_v1: no member read this stock, abstain"
    row = readings.loc[symbol]
    voted = [name for name in MEMBERS if pd.notna(row.get(name))]
    if mean_rank[symbol] <= NEUTRAL:
        return (
            f"consensus_db_v1: mean bearish rank {mean_rank[symbol]:.2f} from {len(voted)}/3 members "
            f"({'+'.join(voted) or 'none'}) is not above neutral, abstain"
        )
    value = float(_scores_from_mean(mean_rank)[symbol])
    return (
        f"consensus_db_v1 (day-bearish consensus of E2A crowded fade, D01C OI fade, A09 gap fade): mean "
        f"bearish rank {mean_rank[symbol]:.2f} from {len(voted)}/3 members ({'+'.join(voted)}) across "
        f"{len(mean_rank)} stocks -> score {value:+.3f} (bearish)"
    )
