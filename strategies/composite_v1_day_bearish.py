"""COMPOSITE_V1_DAY_BEARISH: E2A bearish picks kept only where all of G2 hold.

C2 composite (`cards/COMPOSITE_V1.yml`); rules in `strategies/composite_v1.py`, gates in `strategies/g_gates.py`.
Compare with E2A alone and with `strategies/composite_v1_day_bearish_not.py`.
"""

from strategies.composite_v1 import composite

score, rules_fired = composite("day_bearish", keep=True)
