"""Shared core for D02's two variants (`cards/D02.yml`): stock-level
put/call open-interest ratio, extreme vs its own trailing 20-session
distribution.

The catalog disputes which direction an extreme should read ("contrarian or
confirmatory, test both") - so the two public modules
(`d02_stock_pcr_contrarian.py`, `d02_stock_pcr_confirmatory.py`) are kept
thin wrappers around this one, sharing every line of logic except the final
sign given to an extreme. Neither variant is assumed right (SPEC.md section
5); both are scored and logged as independent trials.

PCR for a session = `oi_pe_optstk / oi_ce_optstk` (D1's options-OI
continuation: near-month stock-option open interest, puts over calls,
already summed by option type across strikes in
`scripts/build_dataset.py`). "Extreme" = `|z| >= THRESHOLD`, where `z` is
that session's own PCR against the trailing `WINDOW`-session mean/std of
the *same symbol's own* PCR history, computed once per symbol from
`history`'s own last visible row - the same "last visible row only"
convention `d01_oi_buildup.py` uses to lag a rule into the next pick,
lagging one week here (this card's horizon, per the catalog).
"""

from __future__ import annotations

import pandas as pd

THRESHOLD = 2.0
WINDOW = 20


def _pcr_series(group: pd.DataFrame) -> pd.Series:
    """One symbol's own PCR by date (sorted order already assumed), NaN
    wherever `oi_ce_optstk`/`oi_pe_optstk` make the ratio undefined."""
    ce = group["oi_ce_optstk"]
    pe = group["oi_pe_optstk"]
    pcr = pe / ce
    return pcr.where((ce > 0) & ce.notna() & pe.notna())


def last_zscore(group: pd.DataFrame) -> float | None:
    """The last visible row's PCR z-score against its own trailing
    `WINDOW`-session distribution (that row included), or `None` if there is
    no active future on it, fewer than `WINDOW` valid trailing PCR sessions,
    or the distribution is degenerate (zero standard deviation)."""
    if group.empty:
        return None
    last = group.iloc[-1]
    if not bool(last.get("has_future", False)):
        return None

    pcr = _pcr_series(group)
    if pd.isna(pcr.iloc[-1]):
        return None

    mean = pcr.rolling(WINDOW, min_periods=WINDOW).mean()
    std = pcr.rolling(WINDOW, min_periods=WINDOW).std()
    m, s = mean.iloc[-1], std.iloc[-1]
    if pd.isna(m) or pd.isna(s) or s == 0:
        return None

    return (pcr.iloc[-1] - m) / s


def signal(history: pd.DataFrame, *, contrarian: bool) -> pd.Series:
    """One score per symbol: `direction * abs(z)` wherever `abs(z) >=
    THRESHOLD`; every other symbol abstains (left out of the result).

    `direction` is `sign(z)` for the contrarian reading (extreme-high PCR ->
    bullish reversal, extreme-low -> bearish reversal) and `-sign(z)` for
    the confirmatory reading (extreme-high PCR -> bearish continuation,
    extreme-low -> bullish continuation) - the only difference between the
    two variants; everything about which sessions count as extreme is
    identical.
    """
    if history.empty:
        return pd.Series(dtype=float)

    needed = {"oi_ce_optstk", "oi_pe_optstk", "has_future", "symbol", "date"}
    if not needed.issubset(history.columns):
        return pd.Series(dtype=float)

    eligible = history.loc[history["has_future"], "symbol"].unique()
    history = history[history["symbol"].isin(eligible)]
    if history.empty:
        return pd.Series(dtype=float)

    out: dict[str, float] = {}
    for symbol, group in history.groupby("symbol", sort=False):
        group = group.sort_values("date")
        z = last_zscore(group)
        if z is None or abs(z) < THRESHOLD:
            continue
        raw_direction = 1.0 if z > 0 else -1.0
        direction = raw_direction if contrarian else -raw_direction
        out[symbol] = direction * abs(z)
    return pd.Series(out, dtype=float)


def reasoning(history: pd.DataFrame, symbol: str, *, contrarian: bool, label: str) -> str:
    sub = history[history["symbol"] == symbol].sort_values("date")
    if sub.empty:
        return f"D02 stock PCR ({label}): no history, abstain"

    z = last_zscore(sub)
    if z is None or abs(z) < THRESHOLD:
        return (
            f"D02 stock PCR ({label}): no active future, fewer than "
            f"{WINDOW} valid trailing sessions, a degenerate distribution, "
            f"or |z| < {THRESHOLD:.1f}, abstain"
        )

    raw_direction = 1.0 if z > 0 else -1.0
    direction = raw_direction if contrarian else -raw_direction
    extreme = "high" if z > 0 else "low"
    read = "reversal" if contrarian else "continuation"
    side = "bullish" if direction > 0 else "bearish"
    return (
        f"D02 stock PCR ({label}): extreme-{extreme} put/call OI (z={z:+.2f}) "
        f"read as {read} -> {side}"
    )
