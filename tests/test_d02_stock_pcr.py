import pandas as pd
import pytest

from strategies import d02_stock_pcr_confirmatory, d02_stock_pcr_contrarian, d02_stock_pcr_core as core
from strategies.d02_stock_pcr_audit import check_cross_symbol_causality


def _row(symbol, date, oi_ce, oi_pe, has_future=True):
    return {
        "date": date,
        "symbol": symbol,
        "has_future": has_future,
        "oi_ce_optstk": oi_ce,
        "oi_pe_optstk": oi_pe,
    }


def _stable_then_extreme(symbol, extreme_ce, extreme_pe, n_stable=19, has_future=True):
    """`n_stable` sessions of a mildly wobbling PCR around 1.0, then one more
    session at the given (ce, pe) - enough rows (`n_stable + 1`) for the
    20-session rolling window once `n_stable == 19`."""
    rows = [
        _row(symbol, f"2015-01-{i + 1:02d}", 1000.0, 1000.0 + (i % 3) * 5.0, has_future=has_future)
        for i in range(n_stable)
    ]
    rows.append(_row(symbol, "2015-01-20", extreme_ce, extreme_pe, has_future=has_future))
    return pd.DataFrame(rows)


def test_extreme_high_pcr_contrarian_scores_bullish():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0)  # pcr = 5.0, far above baseline
    scores = d02_stock_pcr_contrarian.score(history)
    assert scores["AAA"] > 0


def test_extreme_high_pcr_confirmatory_scores_bearish():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0)
    scores = d02_stock_pcr_confirmatory.score(history)
    assert scores["AAA"] < 0


def test_extreme_low_pcr_contrarian_scores_bearish():
    history = _stable_then_extreme("AAA", 5000.0, 50.0)  # pcr way below baseline
    scores = d02_stock_pcr_contrarian.score(history)
    assert scores["AAA"] < 0


def test_extreme_low_pcr_confirmatory_scores_bullish():
    history = _stable_then_extreme("AAA", 5000.0, 50.0)
    scores = d02_stock_pcr_confirmatory.score(history)
    assert scores["AAA"] > 0


def test_both_variants_agree_on_magnitude_only_sign_differs():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0)
    contrarian = d02_stock_pcr_contrarian.score(history)
    confirmatory = d02_stock_pcr_confirmatory.score(history)
    assert contrarian["AAA"] == pytest.approx(-confirmatory["AAA"])


def test_non_extreme_pcr_abstains():
    # Last session's pcr sits inside the stable wobble, no extreme.
    rows = [
        _row("AAA", f"2015-01-{i + 1:02d}", 1000.0, 1000.0 + (i % 3) * 5.0)
        for i in range(20)
    ]
    history = pd.DataFrame(rows)
    assert "AAA" not in d02_stock_pcr_contrarian.score(history)
    assert "AAA" not in d02_stock_pcr_confirmatory.score(history)


def test_fewer_than_window_sessions_abstains():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0, n_stable=10)
    assert "AAA" not in d02_stock_pcr_contrarian.score(history)


def test_zero_oi_ce_abstains():
    history = _stable_then_extreme("AAA", 0.0, 5000.0)
    assert "AAA" not in d02_stock_pcr_contrarian.score(history)


def test_missing_oi_columns_abstain_rather_than_erroring():
    history = pd.DataFrame([{"date": "2015-01-05", "symbol": "AAA", "has_future": True}])
    assert d02_stock_pcr_contrarian.score(history).empty
    assert d02_stock_pcr_confirmatory.score(history).empty


def test_symbol_never_having_a_future_abstains():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0, has_future=False)
    assert "AAA" not in d02_stock_pcr_contrarian.score(history)


def test_empty_history_returns_empty_series():
    columns = ["date", "symbol", "has_future", "oi_ce_optstk", "oi_pe_optstk"]
    assert d02_stock_pcr_contrarian.score(pd.DataFrame(columns=columns)).empty
    assert d02_stock_pcr_confirmatory.score(pd.DataFrame(columns=columns)).empty


def test_degenerate_zero_std_abstains():
    # Every pcr identical -> std is exactly 0, z is undefined.
    rows = [_row("AAA", f"2015-01-{i + 1:02d}", 1000.0, 1000.0) for i in range(20)]
    history = pd.DataFrame(rows)
    assert "AAA" not in d02_stock_pcr_contrarian.score(history)


def test_score_is_per_symbol_not_coupled_across_the_universe():
    bullish = _stable_then_extreme("AAA", 1000.0, 5000.0)
    bearish = _stable_then_extreme("BBB", 5000.0, 50.0)
    history = pd.concat([bullish, bearish], ignore_index=True)
    scores = d02_stock_pcr_contrarian.score(history)
    assert scores["AAA"] > 0
    assert scores["BBB"] < 0


def test_rules_fired_reports_contrarian_reversal():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0)
    reasoning = d02_stock_pcr_contrarian.rules_fired(history, "AAA")
    assert "reversal" in reasoning
    assert "bullish" in reasoning
    assert "contrarian" in reasoning


def test_rules_fired_reports_confirmatory_continuation():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0)
    reasoning = d02_stock_pcr_confirmatory.rules_fired(history, "AAA")
    assert "continuation" in reasoning
    assert "bearish" in reasoning
    assert "confirmatory" in reasoning


def test_rules_fired_reports_abstain_on_non_extreme():
    rows = [
        _row("AAA", f"2015-01-{i + 1:02d}", 1000.0, 1000.0 + (i % 3) * 5.0)
        for i in range(20)
    ]
    history = pd.DataFrame(rows)
    reasoning = d02_stock_pcr_contrarian.rules_fired(history, "AAA")
    assert "abstain" in reasoning


def test_rules_fired_reports_abstain_on_empty_history():
    reasoning = d02_stock_pcr_contrarian.rules_fired(pd.DataFrame(columns=["date", "symbol"]), "AAA")
    assert "abstain" in reasoning


def test_core_signal_requires_contrarian_keyword():
    history = _stable_then_extreme("AAA", 1000.0, 5000.0)
    with pytest.raises(TypeError):
        core.signal(history)  # must be called with contrarian=...


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
