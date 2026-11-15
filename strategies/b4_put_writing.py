"""B4A: put writing on an up day (put OI up faster than call OI), bullish side only, one fixed parameter set.

Card `cards/B4A.yml` (idea credited there, assumptions listed); rules and attribution in
`strategies/bull_core.py`; causality check in `strategies/bull_audit.py`.
"""

from strategies.bull_core import config

score, rules_fired = config("b4_put_writing")
