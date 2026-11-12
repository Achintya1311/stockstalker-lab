"""COMPOSITE_V1_WEEK_BULLISH_NOT: A05B bullish picks kept only where not all of G5 hold (among picks every gate judged).

C2 composite (`cards/COMPOSITE_V1.yml`); rules in `strategies/composite_v1.py`, gates in `strategies/g_gates.py`.
Compare with A05B alone and with `strategies/composite_v1_week_bullish.py`.
"""

from strategies.composite_v1 import composite

score, rules_fired = composite("week_bullish", keep=False)
