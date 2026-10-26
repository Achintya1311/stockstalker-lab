import pandas as pd

from strategies import q06_wick_balance, t04_connors_rsi2, t04_q06_fallback
from strategies.t04_q06_fallback_audit import bars, check_cross_symbol_causality

FLOOR = 25 * 1e7  # config/universe.yml: 25 crore


def _history(**turnover):
    """20 rows per symbol with an active future and the given turnover (rupees)."""
    rows = []
    for symbol, value in turnover.items():
        for day in pd.bdate_range("2016-01-01", periods=20):
            rows.append({"date": day, "symbol": symbol, "has_future": True, "turnover": value})
    return pd.DataFrame(rows)


HISTORY = _history(AAA=2 * FLOOR, BBB=2 * FLOOR, CCC=2 * FLOOR, DDD=2 * FLOOR, THIN=FLOOR / 10)


def _stub(monkeypatch, t04: dict, q06: dict):
    monkeypatch.setattr(t04_connors_rsi2, "score", lambda h: pd.Series(t04, dtype=float))
    monkeypatch.setattr(q06_wick_balance, "score", lambda h: pd.Series(q06, dtype=float))


def test_reads_t04_when_it_has_a_bullish_pick(monkeypatch):
    _stub(monkeypatch, {"AAA": 0.5, "BBB": -0.3}, {"CCC": 0.9, "DDD": 0.4})
    out = t04_q06_fallback.score(HISTORY)
    pd.testing.assert_series_equal(out, pd.Series({"AAA": 0.5}, dtype=float))


def test_falls_back_to_q06_when_t04_has_no_bullish_pick(monkeypatch):
    _stub(monkeypatch, {"BBB": -0.3}, {"CCC": 0.9, "DDD": -0.4, "AAA": 0.2})
    out = t04_q06_fallback.score(HISTORY)
    pd.testing.assert_series_equal(out, pd.Series({"CCC": 0.9, "AAA": 0.2}, dtype=float))


def test_t04_pick_outside_the_universe_does_not_block_the_fallback(monkeypatch):
    """The E2A_D01C_FB defect: a member pick the universe filter drops left the date blank."""
    _stub(monkeypatch, {"THIN": 0.8}, {"CCC": 0.9})
    assert t04_q06_fallback.chosen_member(HISTORY)[0] == "q06"
    assert list(t04_q06_fallback.score(HISTORY).index) == ["CCC"]


def test_likely_in_universe_checks_future_and_turnover():
    hist = _history(AAA=2 * FLOOR, THIN=FLOOR / 10, SHORT=2 * FLOOR)
    hist = hist[~((hist.symbol == "SHORT") & (hist.date > hist.date.min()))]  # 1 row: no 20-session median
    no_future = _history(NOFUT=2 * FLOOR).assign(has_future=False)
    assert t04_q06_fallback.likely_in_universe(pd.concat([hist, no_future])) == {"AAA"}


def test_never_bearish(monkeypatch):
    _stub(monkeypatch, {}, {"CCC": -1.0, "DDD": -0.5})
    assert t04_q06_fallback.score(HISTORY).empty


def test_empty_history():
    assert t04_q06_fallback.score(pd.DataFrame()).empty


def test_real_members_on_synthetic_bars():
    """Unstubbed: a dip inside an uptrend fires T04, so the table reads from T04."""
    hist = pd.concat([bars("AAA", t04_connors_rsi2.MIN_ROWS + 20, 1), bars("CCC", t04_connors_rsi2.MIN_ROWS + 20, 2)])
    member, scores = t04_q06_fallback.chosen_member(hist)
    assert member == "t04" and (scores > 0).all() and not scores.empty


def test_rules_fired_names_the_member_and_wording_is_safe(monkeypatch):
    _stub(monkeypatch, {}, {"CCC": 0.9})
    picked = t04_q06_fallback.rules_fired(HISTORY, "CCC")
    skipped = t04_q06_fallback.rules_fired(HISTORY, "ZZZ")
    assert "Q06" in picked and "+0.9000 (bullish)" in picked
    assert "abstain" in skipped
    for text in (picked, skipped):
        for word in ("buy", "sell", "target", "stop"):
            assert word not in text.lower()


def test_causality_audit_passes():
    result = check_cross_symbol_causality()
    assert result["passed"], result
