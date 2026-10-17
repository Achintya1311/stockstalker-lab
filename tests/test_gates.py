import pytest

from gates.gates import (
    GateResult,
    StrategyMetrics,
    evaluate_gates,
    high_conviction_tag,
    leak_alarm_cleared,
    leak_alarm_triggered,
    required_t,
)


def _passing_metrics(**overrides) -> StrategyMetrics:
    base = dict(
        edge=0.08,
        t_stat=3.5,
        n_trials=1,
        yearly_edges=[0.02, 0.03, -0.01, 0.04, 0.01, 0.02, 0.05, 0.01, 0.02, 0.03],  # 9/10 positive
        n_test_picks=600,
        directional_move=0.001,
        random_percentile=0.97,
        nudged_edges=[0.04, 0.05, 0.06],
        roster_overlaps={"champion_v1": 0.2},
    )
    base.update(overrides)
    return StrategyMetrics(**base)


def test_required_t_at_one_trial_is_the_spec_literal_bar():
    assert required_t(1) == pytest.approx(3.0, abs=1e-6)


def test_required_t_rises_with_more_trials():
    assert required_t(10) > required_t(1)
    assert required_t(100) > required_t(10)


def test_required_t_rejects_non_positive_trial_count():
    with pytest.raises(ValueError):
        required_t(0)


def test_all_gates_pass_for_a_clearly_strong_candidate():
    result = evaluate_gates(_passing_metrics())
    assert isinstance(result, GateResult)
    assert result.all_passed is True
    assert all(result.passed.values())


def test_gate_edge_fails_below_five_points():
    result = evaluate_gates(_passing_metrics(edge=0.04))
    assert result.passed["edge"] is False
    assert result.all_passed is False


def test_gate_significance_rises_with_trial_count():
    # t=3.5 clears the bar at 1 trial but not after many more trials are logged
    assert evaluate_gates(_passing_metrics(t_stat=3.5, n_trials=1)).passed["significance"] is True
    assert evaluate_gates(_passing_metrics(t_stat=3.5, n_trials=10_000)).passed["significance"] is False


def test_gate_positive_years_needs_seventy_percent():
    # 6/10 positive = 60%, below the 70% bar
    edges = [0.01] * 6 + [-0.01] * 4
    assert evaluate_gates(_passing_metrics(yearly_edges=edges)).passed["positive_years"] is False
    # 7/10 positive = 70%, clears it
    edges = [0.01] * 7 + [-0.01] * 3
    assert evaluate_gates(_passing_metrics(yearly_edges=edges)).passed["positive_years"] is True


def test_gate_positive_years_fails_closed_on_empty_history():
    assert evaluate_gates(_passing_metrics(yearly_edges=[])).passed["positive_years"] is False


def test_gate_min_test_picks():
    assert evaluate_gates(_passing_metrics(n_test_picks=499)).passed["min_test_picks"] is False
    assert evaluate_gates(_passing_metrics(n_test_picks=500)).passed["min_test_picks"] is True


def test_gate_directional_move_must_be_strictly_positive():
    assert evaluate_gates(_passing_metrics(directional_move=0.0)).passed["directional_move"] is False
    assert evaluate_gates(_passing_metrics(directional_move=-0.001)).passed["directional_move"] is False


def test_gate_random_baseline_needs_ninety_five_percent():
    assert evaluate_gates(_passing_metrics(random_percentile=0.94)).passed["random_baseline"] is False
    assert evaluate_gates(_passing_metrics(random_percentile=0.95)).passed["random_baseline"] is True


def test_gate_param_robustness_needs_every_nudge_above_bar():
    assert evaluate_gates(_passing_metrics(nudged_edges=[0.04, 0.02, 0.06])).passed["param_robustness"] is False
    assert evaluate_gates(_passing_metrics(nudged_edges=[])).passed["param_robustness"] is False
    assert evaluate_gates(_passing_metrics(nudged_edges=[0.03, 0.03])).passed["param_robustness"] is True


def test_gate_roster_overlap_needs_every_member_below_fifty_percent():
    assert evaluate_gates(_passing_metrics(roster_overlaps={"a": 0.49, "b": 0.50})).passed["roster_overlap"] is False
    assert evaluate_gates(_passing_metrics(roster_overlaps={"a": 0.49, "b": 0.10})).passed["roster_overlap"] is True
    # no roster yet (first strategy ever) - vacuously true, nothing to overlap with
    assert evaluate_gates(_passing_metrics(roster_overlaps={})).passed["roster_overlap"] is True


def test_high_conviction_tag_needs_both_conditions():
    assert high_conviction_tag(0.80, 199) is False
    assert high_conviction_tag(0.74, 300) is False
    assert high_conviction_tag(0.75, 200) is True


def test_leak_alarm_triggers_on_accuracy_or_edge():
    assert leak_alarm_triggered(accuracy=0.71, edge_value=0.02) is True
    assert leak_alarm_triggered(accuracy=0.50, edge_value=0.16) is True
    assert leak_alarm_triggered(accuracy=0.60, edge_value=0.05) is False


def test_leak_alarm_cleared_needs_both_rerun_edges_to_collapse():
    assert leak_alarm_cleared(shifted_edge=0.01, shuffled_edge=0.02) is True
    assert leak_alarm_cleared(shifted_edge=0.20, shuffled_edge=0.01) is False
    assert leak_alarm_cleared(shifted_edge=0.01, shuffled_edge=-0.16) is False
