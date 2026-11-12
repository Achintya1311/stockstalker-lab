"""COMPOSITE_V1_DAY_BEARISH_NOT: E2A bearish picks kept only where not all of G2 hold (among picks every gate judged).

C2 composite (`cards/COMPOSITE_V1.yml`); rules in `strategies/composite_v1.py`, gates in `strategies/g_gates.py`.
Compare with E2A alone and with `strategies/composite_v1_day_bearish.py`.
"""

from strategies.composite_v1 import composite

score, rules_fired = composite("day_bearish", keep=False)
