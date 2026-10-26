"""Q01C: Q01's "fall on thinning volume" read as bearish (`cards/Q01C.yml`).

Q01 called a 20-session fall on thinning volume (close-volume correlation above 0
against a negative move) bullish. On train that side was significantly wrong-way on
the week horizon (-3.39, interval -5.69 to -1.25, negative in all 6 years;
`research/diagnostics/q01.md`): those stocks kept falling. So this card flips that
side only: score = -Q01 where Q01 > 0, and every other symbol abstains, including
Q01's "rise on thinning volume" readings (week -0.58, nothing to flip). Imports Q01
as a library so the correlation and move are bit-for-bit Q01's. Week horizon only:
Q01's day cells give no usable flip after costs.
"""

from __future__ import annotations

import pandas as pd

from strategies import q01_price_volume_corr as q01


def score(history: pd.DataFrame) -> pd.Series:
    base = q01.score(history)
    return -base[base > 0]


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    base = q01.rules_fired(history, symbol)
    head = base.replace("Q01 price-volume correlation", "Q01C thin-volume fall", 1)
    if head.endswith("abstain"):
        return head
    detail = head.rsplit(", ", 1)[0]
    if "rise on thinning volume" in base:
        return f"{detail}, rise on thinning volume, not this card's event, abstain"
    return f"{detail}, bearish (fall on thinning volume continues)"
