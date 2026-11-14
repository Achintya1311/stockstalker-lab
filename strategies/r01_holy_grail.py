"""R01: Holy Grail (ADX trend pullback to EMA20), both sides, one fixed literal parameter set.

Card `cards/R01.yml` (source credited there, assumptions listed); rules and attribution in
`strategies/guru_core.py`; causality check in `strategies/guru_audit.py`.
"""

from strategies.guru_core import config

score, rules_fired = config("r01_holy_grail")
