"""B1: 20/50 EMA cross above the 200-day average, bullish side only, one fixed parameter set.

Card `cards/B1.yml` (idea credited there, assumptions listed); rules and attribution in
`strategies/bull_core.py`; causality check in `strategies/bull_audit.py`.
"""

from strategies.bull_core import config

score, rules_fired = config("b1_trend_cross")
