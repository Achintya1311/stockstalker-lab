"""CONFLUENCE_MIN4_NO_MARKET: CONFLUENCE_V1 ablation, minimum 4 of 6 with the market component ignored.

The market component (market backdrop stand-in (universe trend and universe volatility; no volatility index in the data)) is neither counted nor usable to satisfy the
location / event requirement. Descriptive only: an ablation never gets a validation query.
Card `cards/CONFLUENCE_V1.yml`; rules and attribution in `strategies/confluence_core.py`.
"""

from strategies.confluence_core import config

score, rules_fired = config("confluence_min4_no_market")
