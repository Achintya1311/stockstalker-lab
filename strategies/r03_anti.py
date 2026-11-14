"""R03: Anti (3-10 oscillator pullback), both sides, one fixed literal parameter set.

Card `cards/R03.yml` (source credited there, assumptions listed); rules and attribution in
`strategies/guru_core.py`; causality check in `strategies/guru_audit.py`.
"""

from strategies.guru_core import config

score, rules_fired = config("r03_anti")
