"""consensus_wb_v2: week-bearish consensus of four independent readings, side-anchored ranks (P2).

`cards/CONSENSUS_WB_V2.yml`. A second week-bearish consensus (v1: `strategies/consensus_wb_v1.py`, D02
contrarian + A01 + T15, +2.48 train, below its best member). Members are the four week-bearish readings
that meet the full SPEC 10 helps rule on train with intervals above 0 and share 1.6-5.6% of their weekly
top five (`research/diagnostics/f15.md`):

- `strategies.h02_idiosyncratic_volatility`: highest stock-specific volatility (two-sided).
- `strategies.t05c_upcross_fade`: a fresh MACD up-cross faded (bearish only, about 9 stocks a week).
- `strategies.f15_streak_volume_reversal`: three up closes on light recent turnover (two-sided).
- `strategies.q01c_thin_volume_fall`: a fall on thinning volume (bearish only, about 46 stocks a week).

**Combination rule (changed from v1, on purpose).** v1 ranks each member's bearish strength across every
stock the member read, so for a one-sided member such as T05C or Q01C its weakest bearish reading ranks
near 0 and counts as a vote *against* bearish. Here ranks are anchored to the side: a member's bearish
readings are ranked among its bearish readings and mapped to (0.5, 1]; its bullish readings among its
bullish readings, mapped to [0, 0.5); a zero or an abstention is 0.5 (no view). The consensus is the mean
over the four members; stocks above 0.5 are scored `-2 * (mean - 0.5)`. Bearish table only.

The score depends on which peers are present (ranking, and H02/F15 are cross-sectional themselves);
`strategies/consensus_wb_v2_audit.py` checks that a peer's older history does not move a stock's readings.
"""

from __future__ import annotations

import pandas as pd

from strategies import f15_streak_volume_reversal, h02_idiosyncratic_volatility, q01c_thin_volume_fall, t05c_upcross_fade

MEMBERS = {
    "h02": h02_idiosyncratic_volatility,
    "t05c": t05c_upcross_fade,
    "f15": f15_streak_volume_reversal,
    "q01c": q01c_thin_volume_fall,
}
NEUTRAL = 0.5


def member_scores(history: pd.DataFrame) -> pd.DataFrame:
    """Each member's raw score per symbol (columns = member names); NaN where a member abstains."""
    return pd.DataFrame({name: module.score(history) for name, module in MEMBERS.items()})


def side_anchored(column: pd.Series) -> pd.Series:
    """Bearish readings -> (0.5, 1] by bearish rank among bearish; bullish -> [0, 0.5); zero / NaN -> 0.5."""
    out = pd.Series(NEUTRAL, index=column.index, dtype=float)
    bear = column[column < 0]
    bull = column[column > 0]
    if not bear.empty:
        out.loc[bear.index] = NEUTRAL + 0.5 * (-bear).rank(pct=True)
    if not bull.empty:
        out.loc[bull.index] = NEUTRAL - 0.5 * bull.rank(pct=True)
    return out


def combine(readings: pd.DataFrame) -> pd.Series:
    """Mean side-anchored bearish value per symbol over all members. Pure function of `readings`."""
    if readings.empty:
        return pd.Series(dtype=float)
    return pd.DataFrame({name: side_anchored(readings[name]) for name in readings.columns}).mean(axis=1)


def _scores_from_mean(mean_value: pd.Series) -> pd.Series:
    bearish = mean_value[mean_value > NEUTRAL]
    return (-2.0 * (bearish - NEUTRAL)).astype(float)


def score(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    return _scores_from_mean(combine(member_scores(history)))


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    readings = member_scores(history)
    mean_value = combine(readings)
    if symbol not in mean_value.index:
        return "consensus_wb_v2: no member read this stock, abstain"
    row = readings.loc[symbol]
    bearish_votes = [name for name in MEMBERS if pd.notna(row.get(name)) and row.get(name) < 0]
    if mean_value[symbol] <= NEUTRAL:
        return (
            f"consensus_wb_v2: mean bearish value {mean_value[symbol]:.2f} "
            f"({len(bearish_votes)}/4 members bearish) is not above neutral, abstain"
        )
    value = float(_scores_from_mean(mean_value)[symbol])
    return (
        f"consensus_wb_v2 (week-bearish consensus of H02 stock-specific volatility, T05C MACD up-cross fade, "
        f"F15 quiet up-streak, Q01C thin-volume fall): mean bearish value {mean_value[symbol]:.2f}, "
        f"{len(bearish_votes)}/4 members bearish ({'+'.join(bearish_votes) or 'none'}) across "
        f"{len(mean_value)} stocks -> score {value:+.3f} (bearish)"
    )
