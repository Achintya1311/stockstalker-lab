import pandas as pd
import pytest

from strategies import d01c_oi_fade, e2a_a02_crowded, e2a_d01c_fallback
from strategies.e2a_d01c_fallback_audit import check_cross_symbol_causality

HISTORY = pd.DataFrame({"date": ["2016-01-04"], "symbol": ["AAA"]})  # members are stubbed; only non-empty matters


def _stub(monkeypatch, e2a: dict, d01c: dict):
    monkeypatch.setattr(e2a_a02_crowded, "score", lambda h: pd.Series(e2a, dtype=float))
    monkeypatch.setattr(d01c_oi_fade, "score", lambda h: pd.Series(d01c, dtype=float))


def test_reads_e2a_when_it_has_a_bearish_pick(monkeypatch):
    _stub(monkeypatch, {"AAA": -0.04, "BBB": 0.02}, {"CCC": -1.0, "DDD": -0.5})
    out = e2a_d01c_fallback.score(HISTORY)
    pd.testing.assert_series_equal(out, pd.Series({"AAA": -0.04}, dtype=float))


def test_falls_back_to_d01c_when_e2a_has_no_bearish_pick(monkeypatch):
    _stub(monkeypatch, {"BBB": 0.02}, {"CCC": -1.0, "DDD": 0.5, "EEE": -0.5})
    out = e2a_d01c_fallback.score(HISTORY)
    pd.testing.assert_series_equal(out, pd.Series({"CCC": -1.0, "EEE": -0.5}, dtype=float))


def test_falls_back_when_e2a_abstains_everywhere(monkeypatch):
    _stub(monkeypatch, {}, {"CCC": -1.0})
    assert list(e2a_d01c_fallback.score(HISTORY).index) == ["CCC"]
    assert e2a_d01c_fallback.chosen_member(HISTORY)[0] == "d01c"


def test_never_bullish(monkeypatch):
    _stub(monkeypatch, {}, {"CCC": 1.0, "DDD": 0.5})
    assert e2a_d01c_fallback.score(HISTORY).empty


def test_empty_history():
    assert e2a_d01c_fallback.score(pd.DataFrame()).empty


def test_rules_fired_names_the_member_and_wording_is_safe(monkeypatch):
    _stub(monkeypatch, {}, {"CCC": -1.0})
    picked = e2a_d01c_fallback.rules_fired(HISTORY, "CCC")
    skipped = e2a_d01c_fallback.rules_fired(HISTORY, "ZZZ")
    assert "D01C" in picked and "-1.0000 (bearish)" in picked
    assert "abstain" in skipped
    for text in (picked, skipped):
        for word in ("buy", "sell", "target", "stop"):
            assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
