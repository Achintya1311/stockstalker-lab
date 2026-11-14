"""R02: Turtle Soup (failed 20-session breakout), both sides, one fixed literal parameter set.

Card `cards/R02.yml` (source credited there, assumptions listed); rules and attribution in
`strategies/guru_core.py`; causality check in `strategies/guru_audit.py`.
"""

from strategies.guru_core import config

score, rules_fired = config("r02_turtle_soup")
