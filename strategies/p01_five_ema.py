"""P01: Five-EMA alert candle (daily adaptation), both sides, one fixed literal parameter set.

Card `cards/P01.yml` (source credited there, assumptions listed); rules and attribution in
`strategies/guru_core.py`; causality check in `strategies/guru_audit.py`.
"""

from strategies.guru_core import config

score, rules_fired = config("p01_five_ema")
