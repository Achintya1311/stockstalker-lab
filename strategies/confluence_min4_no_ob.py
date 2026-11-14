"""CONFLUENCE_MIN4_NO_OB: CONFLUENCE_V1 ablation, minimum 4 of 6 with the ob component ignored.

The ob component (order block (close at or near an agreeing zone)) is neither counted nor usable to satisfy the
location / event requirement. Descriptive only: an ablation never gets a validation query.
Card `cards/CONFLUENCE_V1.yml`; rules and attribution in `strategies/confluence_core.py`.
"""

from strategies.confluence_core import config

score, rules_fired = config("confluence_min4_no_ob")
