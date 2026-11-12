"""COMPOSITE_V1_WEEK_BEARISH_NOT: A01 bearish picks kept only where not all of G8 hold (among picks every gate judged).

C2 composite (`cards/COMPOSITE_V1.yml`); rules in `strategies/composite_v1.py`, gates in `strategies/g_gates.py`.
Compare with A01 alone and with `strategies/composite_v1_week_bearish.py`.
"""

from strategies.composite_v1 import composite

score, rules_fired = composite("week_bearish", keep=False)
