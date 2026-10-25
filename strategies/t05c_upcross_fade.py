"""T05C: T05's fresh MACD up-cross read as bearish (`cards/T05C.yml`).

T05's bullish side (a fresh cross of MACD above its signal line) was significantly wrong-way in train on
both horizons (week -3.90, interval -7.04 to -0.68; day -2.86, -4.47 to -1.25;
`research/diagnostics/t05.md`), while its bearish side (fresh down-cross) was positive on the week. So
this card flips the up-cross only: score = -T05 where T05 > 0, and every other symbol abstains,
including fresh down-crosses (flipping those would call T05's one positive reading the other way).
Imports T05 as a library so crosses and magnitudes are bit-for-bit T05's. Serves both horizons, as T05.
"""

from __future__ import annotations

import pandas as pd

from strategies import t05_macd_crossover


def score(history: pd.DataFrame) -> pd.Series:
    base = t05_macd_crossover.score(history)
    return -base[base > 0]


def rules_fired(history: pd.DataFrame, symbol: str) -> str:
    base = t05_macd_crossover.rules_fired(history, symbol)
    head = base.replace("T05 MACD crossover", "T05C MACD up-cross fade", 1)
    if "abstain" in base:
        return head
    _, _, tail = head.partition(" -> score ")
    value = float(tail.split(" ")[0])
    if value < 0:
        return head.partition(" -> score ")[0] + " -> fresh down-cross, not this card's event, abstain"
    return head.partition(" -> score ")[0] + f" -> fresh up-cross, score {-value:+.4f} (bearish)"
