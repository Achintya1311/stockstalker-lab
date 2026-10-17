import numpy as np
import pandas as pd
import pytest

from engine.scoring import day_moves, universe_membership
from engine.selftest import (
    LEAK_ACCURACY_THRESHOLD,
    LEAK_EDGE_THRESHOLD,
    RANDOM_EDGE_TOLERANCE,
    LeakyStrategy,
    RandomStrategy,
    _is_leak_flagged,
    _restrict_to_universe,
    _side_picks,
    check_leak,
    check_random,
    maybe_write_selftest_report,
    selftest_passed,
)

SPLITS = {
    "train": {"start": "2015-01-01", "end": "2020-12-31"},
    "validation": {"start": "2021-01-01", "end": "2023-12-31"},
    "test": {"start": "2024-01-01", "end": "2026-07-31"},
    "exam": {"start": "2026-08-01", "end": "go-live"},
}

N_SYMBOLS = 1000
WARM_UP_DAYS = 20  # universe_membership needs 20 prior trading days per symbol
WINDOW_DAYS = 60  # enough independent trading days to average the random check's per-day noise down
TOTAL_DAYS = WARM_UP_DAYS + WINDOW_DAYS


def _trading_dates(n):
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2015-01-01", periods=n)]


def _make_dataset():
    """Half the symbols always close up, half always close down - every day,
    forever. A real market line of exactly 0.5 for either side, so the leaky
    strategy's edge is exact and a random strategy's expected edge is exactly
    zero (1,000 symbols over 60 window days gives the random check enough
    independent draws that its realised edge reliably lands near that
    expectation too - see the comment on `N_SYMBOLS`/`WINDOW_DAYS` above).
    """
    dates = _trading_dates(TOTAL_DAYS)
    symbols = [f"SYM{i:03d}" for i in range(N_SYMBOLS)]
    up = np.arange(N_SYMBOLS) % 2 == 0
    close = np.where(up, 101.0, 99.0)
    n_dates = len(dates)
    return pd.DataFrame({
        "date": np.repeat(dates, N_SYMBOLS),
        "symbol": np.tile(symbols, n_dates),
        "open": 100.0,
        "close": np.tile(close, n_dates),
        "has_future": True,
        "turnover": 30_00_00_000.0,  # Rs 30cr: above the Rs 25cr floor
    })


@pytest.fixture(scope="module")
def dataset():
    return _make_dataset()


@pytest.fixture(scope="module")
def moves(dataset):
    return day_moves(dataset)


@pytest.fixture(scope="module")
def universe(dataset):
    return universe_membership(dataset, min_median_turnover_20d_cr=25.0)


@pytest.fixture(scope="module")
def window():
    dates = _trading_dates(TOTAL_DAYS)
    return dates[WARM_UP_DAYS], dates[-1]  # the post-warm-up tail only


# ---- LeakyStrategy ----------------------------------------------------------


def test_leaky_strategy_picks_exactly_the_symbols_that_rise_the_next_day(moves):
    strategy = LeakyStrategy(moves)
    # History ending on day 1: the next date is day 2, where even-indexed
    # symbols (SYM000, SYM002, ...) are the ones that close up.
    history = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["SYM000"]})
    picked = strategy.score(history)
    assert set(picked.index) == {"SYM000"}
    assert (picked == 1.0).all()


def test_leaky_strategy_abstains_on_a_symbol_that_falls_the_next_day(moves):
    strategy = LeakyStrategy(moves)
    history = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["SYM001"]})
    assert strategy.score(history).empty


def test_leaky_strategy_abstains_entirely_past_the_dataset_s_last_date(moves):
    strategy = LeakyStrategy(moves)
    last_date = sorted(moves["date"].unique())[-1]
    history = pd.DataFrame({"date": [last_date], "symbol": ["SYM000"]})
    assert strategy.score(history).empty


def test_leaky_strategy_ignores_history_s_own_values_entirely(moves):
    # Two histories differing only in non-date/symbol content must score
    # identically: the leak comes from the next-date lookup alone.
    strategy = LeakyStrategy(moves)
    h1 = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["SYM000"], "close": [1.0]})
    h2 = pd.DataFrame({"date": ["2015-01-01"], "symbol": ["SYM000"], "close": [999.0]})
    pd.testing.assert_series_equal(strategy.score(h1), strategy.score(h2))


# ---- RandomStrategy ----------------------------------------------------------


def test_random_strategy_is_deterministic_for_a_fixed_seed():
    history = pd.DataFrame({"date": ["2015-01-01"] * 5, "symbol": [f"S{i}" for i in range(5)]})
    a = RandomStrategy(seed=0).score(history)
    b = RandomStrategy(seed=0).score(history)
    pd.testing.assert_series_equal(a.sort_index(), b.sort_index())


def test_random_strategy_only_ever_emits_plus_or_minus_one():
    history = pd.DataFrame({"date": ["2015-01-01"] * 50, "symbol": [f"S{i}" for i in range(50)]})
    out = RandomStrategy(seed=1).score(history)
    assert set(out.unique()) <= {1.0, -1.0}


def test_random_strategy_abstains_on_empty_history():
    assert RandomStrategy(seed=0).score(pd.DataFrame(columns=["date", "symbol"])).empty


# ---- helpers: universe restriction / side split -----------------------------


def test_restrict_to_universe_drops_a_pick_outside_the_universe():
    picks = pd.DataFrame({"date": ["d1", "d1"], "symbol": ["IN", "OUT"], "score": [1.0, 1.0]})
    universe_frame = pd.DataFrame({
        "date": ["d1", "d1"],
        "symbol": ["IN", "OUT"],
        "in_universe": [True, False],
    })
    out = _restrict_to_universe(picks, universe_frame)
    assert list(out["symbol"]) == ["IN"]


def test_side_picks_splits_on_score_sign_and_drops_zero():
    picks = pd.DataFrame({
        "date": ["d1"] * 3,
        "symbol": ["BULL", "BEAR", "FLAT"],
        "score": [1.0, -1.0, 0.0],
    })
    bull = _side_picks(picks, 1)
    bear = _side_picks(picks, -1)
    assert list(bull["symbol"]) == ["BULL"]
    assert list(bear["symbol"]) == ["BEAR"]
    assert (bull["side"] == 1).all() and (bear["side"] == -1).all()


# ---- leak-flag threshold (pure logic) ---------------------------------------


def test_is_leak_flagged_true_above_either_threshold():
    assert _is_leak_flagged(accuracy=LEAK_ACCURACY_THRESHOLD, strategy_edge=0.0) is True
    assert _is_leak_flagged(accuracy=0.0, strategy_edge=LEAK_EDGE_THRESHOLD) is True


def test_is_leak_flagged_false_below_both_thresholds():
    assert _is_leak_flagged(accuracy=0.5, strategy_edge=0.02) is False


# ---- check_leak / check_random end to end -----------------------------------


def test_check_leak_is_always_100pct_accurate_by_construction(dataset, moves, universe, window):
    start, end = window
    result = check_leak(dataset, moves, universe, SPLITS, start, end)
    assert result["accuracy"] == pytest.approx(1.0)
    assert result["edge"] == pytest.approx(0.5)  # 100% hit rate - 50% market line
    assert result["flagged"] is True


def test_check_random_shows_edge_within_noise_of_zero_on_every_official_seed(dataset, moves, universe, window):
    start, end = window
    results = check_random(dataset, moves, universe, SPLITS, start, end)
    assert len(results) == 5
    for r in results:
        # Random side assignment is independent of which symbols are
        # permanently up/down, so the expected edge is exactly zero; any
        # seed's realised edge must still land inside the tolerance band.
        assert abs(r["bull_edge"]) <= RANDOM_EDGE_TOLERANCE
        assert abs(r["bear_edge"]) <= RANDOM_EDGE_TOLERANCE
        assert r["within_tolerance"] is True


def test_check_leak_raises_if_no_in_universe_picks_survive(dataset, moves, window):
    start, end = window
    empty_universe = pd.DataFrame({"date": [], "symbol": [], "in_universe": []})
    with pytest.raises(ValueError):
        check_leak(dataset, moves, empty_universe, SPLITS, start, end)


# ---- selftest_passed ---------------------------------------------------------


def test_selftest_passed_requires_both_leak_flagged_and_all_random_within_tolerance():
    leak_ok = {"flagged": True}
    leak_bad = {"flagged": False}
    random_ok = [{"within_tolerance": True}, {"within_tolerance": True}]
    random_bad = [{"within_tolerance": True}, {"within_tolerance": False}]
    assert selftest_passed(leak_ok, random_ok) is True
    assert selftest_passed(leak_bad, random_ok) is False
    assert selftest_passed(leak_ok, random_bad) is False


# ---- maybe_write_selftest_report --------------------------------------------


def test_maybe_write_selftest_report_noops_without_required_columns(tmp_path):
    dataset = pd.DataFrame({"date": ["2018-01-02"], "symbol": ["AAA"], "close": [1.0]})
    out_path = tmp_path / "selftest.md"
    assert maybe_write_selftest_report(dataset, out_path) is False
    assert not out_path.exists()


def test_maybe_write_selftest_report_noops_when_dataset_misses_the_window(dataset, tmp_path):
    # The shared fixture dataset only covers 2015; the default self-test
    # window is 2018 - a report that can't be computed must not crash the
    # whole run_queue pipeline, so this is a no-op, not a raise.
    out_path = tmp_path / "selftest.md"
    assert maybe_write_selftest_report(dataset, out_path) is False
    assert not out_path.exists()


def test_maybe_write_selftest_report_writes_when_window_and_columns_both_present(dataset, window, tmp_path):
    start, end = window
    out_path = tmp_path / "selftest.md"
    assert maybe_write_selftest_report(dataset, out_path, start, end) is True
    text = out_path.read_text()
    assert "Engine self-test" in text
    assert "PASS" in text
