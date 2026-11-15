"""B5: failed E2A bearish setup (no fall in 3 sessions), bullish side only, one fixed parameter set.

Card `cards/B5.yml` (idea credited there, assumptions listed); rules and attribution in
`strategies/bull_core.py`; causality check in `strategies/bull_audit.py`.
"""

from strategies.bull_core import config

score, rules_fired = config("b5_failed_bearish")
