"""R04: 80-20 (reversal of an extreme bar), both sides, one fixed literal parameter set.

Card `cards/R04.yml` (source credited there, assumptions listed); rules and attribution in
`strategies/guru_core.py`; causality check in `strategies/guru_audit.py`.
"""

from strategies.guru_core import config

score, rules_fired = config("r04_eighty_twenty")
