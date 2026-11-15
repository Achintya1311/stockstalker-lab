"""B4B: extreme down day with futures OI falling (mirror of E2A), bullish side only, one fixed parameter set.

Card `cards/B4B.yml` (idea credited there, assumptions listed); rules and attribution in
`strategies/bull_core.py`; causality check in `strategies/bull_audit.py`.
"""

from strategies.bull_core import config

score, rules_fired = config("b4_long_liquidation_end")
