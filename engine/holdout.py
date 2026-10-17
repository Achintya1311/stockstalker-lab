"""Reusable holdout (Thresholdout, Dwork et al. 2015).

Per SPEC.md section 4 (validation split): "Only through the reusable
holdout (Thresholdout, Dwork et al. 2015): noisy pass/fail answers, at
most 60 queries a week." This module is the minimal, reusable mechanism
itself - one function answering one scalar query safely. The weekly
query-rate budget and the full gate machinery are B8's job
(`state/queue.md`: "Gates, ledger, Thresholdout, budgets..."); this piece
is built now, for B7's "then validation" step, because B8 bundles the
same mechanism and the design is small enough to build once and reuse.

The problem Thresholdout solves: a query asks about a statistic computed
two ways - on the train split (unlimited looks, SPEC.md section 4) and on
the validation split (the true holdout). Comparing them without noise
would let repeated querying tune against the holdout exactly as if it
were train, defeating the point of having a separate split. Thresholdout
instead:

1. Computes `|train_value - holdout_value|`.
2. Adds Laplace noise to the comparison threshold itself, so whether train
   and holdout actually disagree is never decided on exact numbers.
3. If they disagree by more than noise can explain, releases the holdout
   value plus its own, separate noise ("budget spent" - the released
   answer now tracks the true holdout, so repeating this costs
   information and should be rate-limited, per SPEC.md section 4).
4. Otherwise releases the train value unchanged (free - train has an
   unlimited query budget by design, so no holdout information leaks).

The true, un-noised holdout value is never returned - only
`released_value` is, together with `budget_spent` saying whether that
value is holdout-derived (noisily) or just the train value again.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdoutAnswer:
    train_value: float
    released_value: float
    budget_spent: bool  # True iff the (noisy) holdout value leaked through


def _laplace(rng: random.Random, scale: float) -> float:
    """One Laplace(0, scale) sample via inverse CDF (`random` has no laplace())."""
    u = rng.random() - 0.5
    return -scale * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))


def thresholdout_query(
    train_value: float,
    holdout_value: float,
    *,
    threshold: float,
    tolerance: float,
    rng: random.Random | None = None,
) -> ThresholdoutAnswer:
    """One Thresholdout query (Dwork et al. 2015, Algorithm 1).

    `threshold` is how much train/holdout disagreement is tolerated before
    the mechanism treats it as real overfitting signal rather than noise;
    `tolerance` sets the scale of both Laplace draws. Both are in the same
    units as `train_value`/`holdout_value` (e.g. edge as a fraction, not
    percentage points). `rng` defaults to a fresh `random.Random()` (real
    randomness) - tests pass a seeded one for determinism.
    """
    rng = rng if rng is not None else random.Random()
    xi = _laplace(rng, 2 * tolerance)
    if abs(train_value - holdout_value) > threshold + xi:
        eta = _laplace(rng, tolerance)
        return ThresholdoutAnswer(train_value, holdout_value + eta, True)
    return ThresholdoutAnswer(train_value, train_value, False)
