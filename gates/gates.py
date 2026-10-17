"""Roster gates (B8, `state/queue.md`): SPEC.md section 6, checked on test.

This module is policy only - pure predicates over already-computed metrics.
It does not run the replay engine or touch a dataset: the `evaluate` lane
(SPEC.md section 9), once built, is what will compute a candidate's edge,
t-stat, yearly breakdown, random-baseline percentile, parameter-nudge
results and roster overlaps (via `engine.scoring` and `engine.replay`) and
hand them here as a `StrategyMetrics`. Keeping the gates themselves free of
engine calls makes every threshold in SPEC.md section 6 independently
testable against hand-picked numbers, the way `engine.holdout`'s mechanism
is tested against hand-picked train/holdout values rather than real data.

Every gate is checked "separately for each horizon and side" (SPEC.md
section 6): one `StrategyMetrics` is one (strategy, horizon, side) trial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import NormalDist

# Gate 1: edge of at least 5 points over the market line.
EDGE_BAR = 0.05

# Gate 2: trial-corrected significance. A single, first-ever trial must
# clear plain t >= 3 (SPEC.md section 6, "a trial-corrected significance of
# t >= 3 ... the trial count is the cumulative count in `ledger/trials.csv`.
# The bar rises as more is tried."). Modelled as a Bonferroni correction
# that holds the overall false-positive rate at the single-trial rate for
# t=3: with n_trials tried, the per-trial two-sided significance level is
# divided by n_trials, and the bar is the t (here, z - the engine does not
# track degrees of freedom) that level requires. n_trials=1 reproduces the
# literal t>=3 bar from the spec; it only rises from there.
_BASE_T = 3.0
_BASE_TWO_SIDED_P = 2 * (1 - NormalDist().cdf(_BASE_T))

# Gate 3: positive edge in at least 70% of calendar years across train,
# validation and test (one combined list of yearly edges is passed in).
POSITIVE_YEAR_FRACTION = 0.70

# Gate 4: at least 500 test picks.
MIN_TEST_PICKS = 500

# Gate 6: beats at least 95% of random lists (engine.scoring.random_baseline_percentile).
RANDOM_PERCENTILE_BAR = 0.95

# Gate 7: +-10% trigger-value nudges must each keep edge >= 3 points.
PARAM_NUDGE_EDGE_BAR = 0.03

# Gate 8: pick overlap with every current roster member below 50%.
ROSTER_OVERLAP_BAR = 0.50

# High-conviction tag: selective-pick test hit rate >= 75% with >= 200 picks.
HIGH_CONVICTION_HIT_RATE = 0.75
HIGH_CONVICTION_MIN_PICKS = 200

# Leak alarm: long-sample accuracy >= 70% or edge >= 15 points is quarantined
# until two re-runs (outcomes shifted by +1 day; outcomes shuffled within
# each date) both collapse its edge. Same thresholds `engine.selftest`
# encodes independently for its own narrower self-test fixtures (B6,
# already shipped and tested; not touched here to avoid regressing it) -
# this is the general mechanism SPEC.md section 6 describes for any
# roster candidate.
LEAK_ACCURACY_THRESHOLD = 0.70
LEAK_EDGE_THRESHOLD = 0.15


def required_t(n_trials: int) -> float:
    """The t (z, strictly) gate 2 requires after `n_trials` cumulative trials.

    `n_trials` is the row count in `ledger/trials.csv` including the trial
    being judged (SPEC.md section 6: "the trial count is the cumulative
    count"). Must be >= 1 - a trial being evaluated is itself trial number
    at least 1.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    alpha = _BASE_TWO_SIDED_P / n_trials
    return NormalDist().inv_cdf(1 - alpha / 2)


@dataclass(frozen=True)
class StrategyMetrics:
    """One (strategy, horizon, side) trial's test-split metrics, plus the
    cross-split yearly breakdown and robustness checks gates 3/7/8 need."""

    edge: float
    t_stat: float
    n_trials: int
    yearly_edges: list[float]  # per calendar year, train + validation + test combined
    n_test_picks: int
    directional_move: float
    random_percentile: float
    nudged_edges: list[float]  # one edge per +-10% trigger-value nudge tried
    roster_overlaps: dict[str, float] = field(default_factory=dict)  # roster_id -> overlap fraction


@dataclass(frozen=True)
class GateResult:
    passed: dict[str, bool]
    all_passed: bool
    required_t: float


_GATE_NAMES = (
    "edge",
    "significance",
    "positive_years",
    "min_test_picks",
    "directional_move",
    "random_baseline",
    "param_robustness",
    "roster_overlap",
)


def evaluate_gates(m: StrategyMetrics) -> GateResult:
    """SPEC.md section 6's eight gates, each a named bool. `all_passed` is
    the "needs all of these" verdict; individual results stay so a failing
    candidate's report can say which gate(s) it missed."""
    req_t = required_t(m.n_trials)
    positive_year_fraction = (
        sum(1 for e in m.yearly_edges if e > 0) / len(m.yearly_edges) if m.yearly_edges else 0.0
    )
    passed = {
        "edge": m.edge >= EDGE_BAR,
        "significance": m.t_stat >= req_t,
        "positive_years": positive_year_fraction >= POSITIVE_YEAR_FRACTION,
        "min_test_picks": m.n_test_picks >= MIN_TEST_PICKS,
        "directional_move": m.directional_move > 0,
        "random_baseline": m.random_percentile >= RANDOM_PERCENTILE_BAR,
        "param_robustness": len(m.nudged_edges) > 0 and all(e >= PARAM_NUDGE_EDGE_BAR for e in m.nudged_edges),
        "roster_overlap": all(o < ROSTER_OVERLAP_BAR for o in m.roster_overlaps.values()),
    }
    assert set(passed) == set(_GATE_NAMES)
    return GateResult(passed=passed, all_passed=all(passed.values()), required_t=req_t)


def high_conviction_tag(selective_hit_rate: float, selective_n_picks: int) -> bool:
    """SPEC.md section 6: tagged if, on selective picks only, test hit rate
    is >= 75% with >= 200 picks. Coverage is reported alongside, not gated."""
    return selective_hit_rate >= HIGH_CONVICTION_HIT_RATE and selective_n_picks >= HIGH_CONVICTION_MIN_PICKS


def leak_alarm_triggered(accuracy: float, edge_value: float) -> bool:
    """SPEC.md section 6: long-sample accuracy >= 70% or edge >= 15 points."""
    return accuracy >= LEAK_ACCURACY_THRESHOLD or edge_value >= LEAK_EDGE_THRESHOLD


def leak_alarm_cleared(shifted_edge: float, shuffled_edge: float) -> bool:
    """A quarantined strategy clears the alarm only once both re-runs'
    (+1 day outcome shift; outcomes shuffled within each date) edges
    collapse back under the same bar that would itself trigger the alarm -
    a strategy still showing 15+ points of edge against shifted or shuffled
    outcomes was never reading a real, date-aligned signal."""
    return abs(shifted_edge) < LEAK_EDGE_THRESHOLD and abs(shuffled_edge) < LEAK_EDGE_THRESHOLD
