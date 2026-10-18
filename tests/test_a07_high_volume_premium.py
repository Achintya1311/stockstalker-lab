import numpy as np
import pandas as pd
import pytest

from strategies import a07_high_volume_premium
from strategies.a07_high_volume_premium_audit import check_cross_symbol_causality


def _series_with_baseline_and_recent_volume(
    symbol: str,
    baseline_step: float,
    recent_shift: float,
    leading_rows: int = 0,
    base_price: float = 100.0,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """A series whose trailing `MIN_ROWS` window has a known expected z-score.

    The baseline window (`BASELINE_WINDOW` days, immediately before the
    recent window) alternates `base_volume + baseline_step,
    base_volume - baseline_step, ...`: an even-length sequence whose mean
    is exactly `base_volume` and whose population standard deviation
    (`ddof=0`) is exactly `baseline_step`. The recent window
    (`RECENT_WINDOW` days, right after it) is a flat `base_volume +
    recent_shift`, so its mean is exactly `base_volume + recent_shift`.
    Expected `z = (avg_recent_volume - baseline_mean) / baseline_std
    = recent_shift / baseline_step`.

    `leading_rows` extra rows at a flat baseline volume are optionally
    prepended before the baseline window, to prove they can't change the
    score (the module only reads the trailing `MIN_ROWS` rows). Price is
    an arbitrary flat walk - this card's score never reads it.
    """
    assert a07_high_volume_premium.BASELINE_WINDOW % 2 == 0

    baseline_volumes = [
        base_volume + (baseline_step if i % 2 == 0 else -baseline_step)
        for i in range(a07_high_volume_premium.BASELINE_WINDOW)
    ]
    recent_volumes = [base_volume + recent_shift] * a07_high_volume_premium.RECENT_WINDOW
    leading_volumes = [base_volume] * leading_rows

    volumes = leading_volumes + baseline_volumes + recent_volumes
    n_rows = len(volumes)
    dates = pd.bdate_range("2015-01-01", periods=n_rows).strftime("%Y-%m-%d")

    rows = []
    prev_close = base_price
    for date, volume in zip(dates, volumes):
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open": prev_close,
                "high": prev_close,
                "low": prev_close,
                "close": prev_close,
                "prevclose": prev_close,
                "volume": float(volume),
            }
        )
    return pd.DataFrame(rows)


def test_unusually_high_volume_scores_bullish():
    # z = 50_000 / 100_000 = 0.5 (bullish): unusually high recent volume.
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=50_000
    )
    scores = a07_high_volume_premium.score(history)
    assert scores["AAA"] == pytest.approx(0.5, rel=1e-6)


def test_unusually_low_volume_scores_bearish():
    # z = -200_000 / 100_000 = -2.0 (bearish): unusually low recent volume.
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=-200_000
    )
    scores = a07_high_volume_premium.score(history)
    assert scores["AAA"] == pytest.approx(-2.0, rel=1e-6)


def test_score_magnitude_matches_the_known_formula():
    # z = 75_000 / 50_000 = 1.5.
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=50_000, recent_shift=75_000
    )
    scores = a07_high_volume_premium.score(history)
    assert scores["AAA"] == pytest.approx(1.5, rel=1e-6)


def test_same_volume_as_baseline_scores_neutral():
    # recent_shift = 0 -> z = 0.0.
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=0
    )
    scores = a07_high_volume_premium.score(history)
    assert scores["AAA"] == pytest.approx(0.0, abs=1e-9)


def test_zero_baseline_volume_std_abstains():
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=0, recent_shift=50_000
    )
    scores = a07_high_volume_premium.score(history)
    assert "AAA" not in scores


def test_leading_history_does_not_change_the_score():
    short = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=50_000
    )
    long = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=50_000, leading_rows=30
    )
    assert a07_high_volume_premium.score(short)["AAA"] == pytest.approx(
        a07_high_volume_premium.score(long)["AAA"], rel=1e-9
    )


def test_too_little_history_abstains():
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=50_000
    )
    history = history.iloc[1:]  # drop one row: now below MIN_ROWS
    scores = a07_high_volume_premium.score(history)
    assert "AAA" not in scores


def test_empty_history_returns_empty_series():
    scores = a07_high_volume_premium.score(
        pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "prevclose", "volume"])
    )
    assert scores.empty


def test_score_is_per_symbol_not_coupled_across_the_universe():
    high = _series_with_baseline_and_recent_volume("AAA", baseline_step=100_000, recent_shift=50_000)
    low = _series_with_baseline_and_recent_volume("BBB", baseline_step=100_000, recent_shift=-200_000)
    scores = a07_high_volume_premium.score(pd.concat([high, low], ignore_index=True))
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_the_same_direction_as_score():
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=-200_000
    )
    reasoning = a07_high_volume_premium.rules_fired(history, "AAA")
    assert "bearish" in reasoning
    assert "score" in reasoning


def test_rules_fired_reports_abstain_on_insufficient_history():
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=50_000
    )
    history = history.iloc[1:]
    reasoning = a07_high_volume_premium.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_on_zero_baseline_volume_std():
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=0, recent_shift=50_000
    )
    reasoning = a07_high_volume_premium.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result


def test_score_drops_a_symbol_that_never_had_a_future():
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=50_000
    )
    history["has_future"] = False
    scores = a07_high_volume_premium.score(history)
    assert "AAA" not in scores


def test_score_keeps_an_eligible_symbol_with_has_future_column_present():
    history = _series_with_baseline_and_recent_volume(
        "AAA", baseline_step=100_000, recent_shift=50_000
    )
    history["has_future"] = True
    scores = a07_high_volume_premium.score(history)
    assert scores["AAA"] == pytest.approx(0.5, rel=1e-6)


def test_score_prefilter_does_not_change_an_eligible_symbols_score():
    eligible = _series_with_baseline_and_recent_volume("AAA", baseline_step=100_000, recent_shift=50_000)
    ineligible = _series_with_baseline_and_recent_volume("ZZZ", baseline_step=100_000, recent_shift=-200_000)

    with_future_column = pd.concat([eligible, ineligible], ignore_index=True)
    with_future_column["has_future"] = with_future_column["symbol"] == "AAA"

    without_future_column = eligible  # no ineligible symbol, no has_future column at all

    assert a07_high_volume_premium.score(with_future_column)["AAA"] == a07_high_volume_premium.score(
        without_future_column
    )["AAA"]
