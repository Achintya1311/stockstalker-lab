"""COMPOSITE_V1_DAY_BULLISH: T04 bullish picks kept only where all of G3 AND G4 AND G7 AND G9 hold.

C2 composite (`cards/COMPOSITE_V1.yml`); rules in `strategies/composite_v1.py`, gates in `strategies/g_gates.py`.
Compare with T04 alone and with `strategies/composite_v1_day_bullish_not.py`.
"""

from strategies.composite_v1 import composite

score, rules_fired = composite("day_bullish", keep=True)
