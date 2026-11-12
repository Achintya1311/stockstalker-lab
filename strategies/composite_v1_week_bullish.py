"""COMPOSITE_V1_WEEK_BULLISH: A05B bullish picks kept only where all of G5 hold.

C2 composite (`cards/COMPOSITE_V1.yml`); rules in `strategies/composite_v1.py`, gates in `strategies/g_gates.py`.
Compare with A05B alone and with `strategies/composite_v1_week_bullish_not.py`.
"""

from strategies.composite_v1 import composite

score, rules_fired = composite("week_bullish", keep=True)
