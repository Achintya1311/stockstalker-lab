"""P02: Bollinger 1.5 sd alert candle, both sides, one fixed literal parameter set.

Card `cards/P02.yml` (source credited there, assumptions listed); rules and attribution in
`strategies/guru_core.py`; causality check in `strategies/guru_audit.py`.
"""

from strategies.guru_core import config

score, rules_fired = config("p02_bollinger_1p5")
