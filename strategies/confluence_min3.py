"""CONFLUENCE_MIN3: CONFLUENCE_V1, setups with at least 3 of 7 components True, both sides.

A setup needs a location (order block or support / resistance) AND an event (sweep or candle).
Card `cards/CONFLUENCE_V1.yml`; rules and attribution in `strategies/confluence_core.py`.
"""

from strategies.confluence_core import config

score, rules_fired = config("confluence_min3")
