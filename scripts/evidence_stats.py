"""Block-bootstrap evidence for per-date edge series, with data-snooping control (SPEC.md section 6 companion).

The lab's edge t-stat is already per date (picks on one date count once). What it does not handle is
serial correlation between dates and the fact that dozens of variants were tried. This module adds both
with `arch`: a stationary-bootstrap confidence interval per series, and Hansen's SPA, Romano-Wolf StepM
and the Model Confidence Set across the whole set of trials. Pure functions on a dates x strategies
frame, so they test on synthetic data with a planted edge.

Loss convention: lower is better, so a strategy's loss is minus its per-date edge and the benchmark
(the market line itself, edge 0) has loss 0. A date on which a strategy made no pick counts as edge 0
("no bet, no gain"), the same for every strategy, so selective strategies are not flattered.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from arch.bootstrap import MCS, SPA, StationaryBootstrap, StepM, optimal_block_length

MAX_BLOCK = 20


def block_size(x: np.ndarray) -> int:
    """Politis-White optimal stationary block length, clipped to [1, MAX_BLOCK]."""
    x = np.asarray(x, float)
    if len(x) < 30 or np.nanstd(x) == 0:
        return 1
    b = float(optimal_block_length(x)["stationary"].iloc[0])
    return int(min(max(round(b), 1), MAX_BLOCK))


def boot_ci(x, reps: int = 2000, seed: int = 0, level: float = 0.95) -> dict:
    """Mean of a per-date series with a stationary-bootstrap percentile interval and P(mean <= 0)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    mean = float(x.mean())
    if len(x) < 30 or x.std() == 0:
        return {"mean": mean, "lo": float("nan"), "hi": float("nan"), "p_le0": float("nan"), "block": 1, "n": int(len(x))}
    b = block_size(x)
    bs = StationaryBootstrap(b, x, seed=seed)
    means = np.array([float(d[0][0].mean()) for d in bs.bootstrap(reps)])
    a = (1 - level) / 2
    return {"mean": mean, "lo": float(np.quantile(means, a)), "hi": float(np.quantile(means, 1 - a)),
            "p_le0": float((means <= 0).mean()), "block": b, "n": int(len(x))}


def multiple_testing(edges: pd.DataFrame, size: float = 0.10, reps: int = 2000, seed: int = 0) -> dict:
    """SPA p-values, StepM superior set and MCS inclusion for a dates x strategies edge frame."""
    edges = edges.fillna(0.0)
    if edges.shape[1] < 2 or len(edges) < 50:
        return {"n_models": int(edges.shape[1]), "spa": {}, "stepm": [], "mcs": list(edges.columns), "block": 1}
    losses = -edges
    bench = pd.Series(0.0, index=edges.index) + 1e-12 * np.arange(len(edges)) / len(edges)  # non-degenerate
    b = int(np.median([block_size(edges[c].to_numpy()) for c in edges.columns]))
    spa = SPA(bench, losses, block_size=b, reps=reps, seed=seed)
    spa.compute()
    step = StepM(bench, losses, size=size, block_size=b, reps=reps, seed=seed)
    step.compute()
    mcs = MCS(losses, size=size, block_size=b, reps=reps, seed=seed)
    mcs.compute()
    return {"n_models": int(edges.shape[1]), "block": b,
            "spa": {k: float(v) for k, v in spa.pvalues.items()},
            "stepm": list(step.superior_models), "mcs": list(mcs.included)}
