import pandas as pd
import pytest

from strategies import a07_high_volume_premium, a07c_volume_fade
from strategies.a07c_volume_fade_audit import check_cross_symbol_causality
from tests.test_a07_high_volume_premium import _series_with_baseline_and_recent_volume


def test_volume_spike_scores_bearish():
    # A07: z = 50_000 / 100_000 = +0.5 (bullish) -> A07C: -0.5 (bearish).
    history = _series_with_baseline_and_recent_volume("AAA", baseline_step=100_000, recent_shift=50_000)
    assert a07c_volume_fade.score(history)["AAA"] == pytest.approx(-0.5, rel=1e-6)


def test_volume_drought_scores_bullish():
    # A07: z = -2.0 (bearish) -> A07C: +2.0 (bullish).
    history = _series_with_baseline_and_recent_volume("AAA", baseline_step=100_000, recent_shift=-200_000)
    assert a07c_volume_fade.score(history)["AAA"] == pytest.approx(2.0, rel=1e-6)


def test_is_exactly_minus_a07_including_abstentions():
    frames = [
        _series_with_baseline_and_recent_volume("AAA", 100_000, 50_000),
        _series_with_baseline_and_recent_volume("BBB", 100_000, -150_000),
        _series_with_baseline_and_recent_volume("CCC", 0, 50_000),  # zero baseline std: abstain
        _series_with_baseline_and_recent_volume("DDD", 100_000, 50_000).iloc[-5:],  # too short: abstain
    ]
    history = pd.concat(frames, ignore_index=True)
    base, flipped = a07_high_volume_premium.score(history), a07c_volume_fade.score(history)
    assert list(flipped.index) == list(base.index)
    assert "CCC" not in flipped.index and "DDD" not in flipped.index
    pd.testing.assert_series_equal(flipped, -base)


def test_empty_history():
    assert a07c_volume_fade.score(pd.DataFrame()).empty


def test_rules_fired_direction_matches_score_and_wording_is_safe():
    history = _series_with_baseline_and_recent_volume("AAA", baseline_step=100_000, recent_shift=50_000)
    text = a07c_volume_fade.rules_fired(history, "AAA")
    assert text.startswith("A07C volume fade")
    assert "-0.5000 (bearish)" in text
    for word in ("buy", "sell", "target", "stop"):
        assert word not in text.lower()


def test_rules_fired_abstain():
    history = _series_with_baseline_and_recent_volume("AAA", 0, 50_000)
    text = a07c_volume_fade.rules_fired(history, "AAA")
    assert text.startswith("A07C volume fade") and "abstain" in text


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
